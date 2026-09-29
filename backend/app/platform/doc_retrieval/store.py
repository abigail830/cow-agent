"""Load parsed artifacts and enforce session import library access."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, ChatAttachment, HubItem
from app.db.repositories.attachments import AttachmentRepository
from app.db.repositories.chat_document_imports import ChatDocumentImportRepository
from app.db.repositories.hub_items import HubItemRepository
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.doc_retrieval.context import ChatAttachmentIndexEntry, DocRetrievalContext
from app.platform.docstore.blob import (
    load_parsed_artifact,
    load_parsed_artifact_scoped,
    load_parsed_figure_scoped,
)
from app.platform.docstore.manifest import parsed_artifact_in_manifest
from app.platform.docstore.models import PARSE_READY_STATUSES
from app.platform.docstore.scope import DocumentScope
from app.platform.session_documents.imports import lazy_backfill_chat_imports


class DocRetrievalError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _meta_summary(meta: dict[str, Any]) -> tuple[int | None, int | None, int, tuple[str, ...]]:
    line_count = meta.get("line_count")
    page_count = meta.get("page_count")
    figures = meta.get("figures") or []
    figure_count = len(figures) if isinstance(figures, list) else 0
    sections = meta.get("sections") or []
    titles: list[str] = []
    if isinstance(sections, list):
        for section in sections[:12]:
            if isinstance(section, dict):
                title = str(section.get("title") or "").strip()
                if title:
                    titles.append(title)
    return (
        int(line_count) if line_count is not None else None,
        int(page_count) if page_count is not None else None,
        figure_count,
        tuple(titles),
    )


def _entry_from_attachment(row: ChatAttachment, meta: dict[str, Any] | None = None) -> ChatAttachmentIndexEntry:
    kind = classify_attachment(filename=row.filename, mime_type=row.mime_type)
    line_count = page_count = None
    figure_count = 0
    section_titles: tuple[str, ...] = ()
    if meta:
        line_count, page_count, figure_count, section_titles = _meta_summary(meta)
    created_at = row.created_at.isoformat() if row.created_at is not None else None
    return ChatAttachmentIndexEntry(
        attachment_id=str(row.id),
        filename=row.filename,
        mime_type=row.mime_type,
        kind=kind.value,
        parse_status=str(row.parse_status or "ready"),
        source="chat_attachment",
        storage_scope_id=str(row.chat_id),
        line_count=line_count,
        page_count=page_count,
        figure_count=figure_count,
        gist=getattr(row, "gist", None),
        created_at=created_at,
        section_titles=section_titles,
    )


def _entry_from_hub_item(row: HubItem, meta: dict[str, Any] | None = None) -> ChatAttachmentIndexEntry:
    kind = classify_attachment(filename=row.filename, mime_type=row.mime_type)
    line_count = page_count = None
    figure_count = 0
    section_titles: tuple[str, ...] = ()
    if meta:
        line_count, page_count, figure_count, section_titles = _meta_summary(meta)
    created_at = row.created_at.isoformat() if row.created_at is not None else None
    return ChatAttachmentIndexEntry(
        attachment_id=str(row.id),
        filename=row.filename,
        mime_type=row.mime_type,
        kind=kind.value,
        parse_status=str(row.parse_status or "ready"),
        source="hub_item",
        storage_scope_id=str(row.user_id),
        line_count=line_count,
        page_count=page_count,
        figure_count=figure_count,
        gist=getattr(row, "gist", None),
        created_at=created_at,
        section_titles=section_titles,
    )


def _document_scope_for_entry(entry: ChatAttachmentIndexEntry) -> DocumentScope:
    doc_id = uuid.UUID(entry.attachment_id)
    scope_id = uuid.UUID(entry.storage_scope_id)
    if entry.source == "hub_item":
        return DocumentScope.hub(scope_id, doc_id)
    return DocumentScope.chat(scope_id, doc_id)


def _row_ready_attachment(row: ChatAttachment) -> bool:
    role = getattr(row, "attachment_role", None)
    if role == "audio_part":
        return False
    status = str(row.parse_status or "ready")
    if role == "transcript_host":
        return parsed_artifact_in_manifest(row.parsed_artifact_manifest, "content_md")
    return status in PARSE_READY_STATUSES


def _row_ready_hub(row: HubItem) -> bool:
    role = getattr(row, "attachment_role", None)
    if role == "audio_part":
        return False
    status = str(row.parse_status or "ready")
    if role == "transcript_host":
        return parsed_artifact_in_manifest(row.parsed_artifact_manifest, "content_md")
    return status in PARSE_READY_STATUSES


async def build_session_document_library(
    db: AsyncSession,
    chat_id: uuid.UUID,
    *,
    load_meta: bool = True,
) -> dict[str, ChatAttachmentIndexEntry]:
    chat = await db.get(Chat, chat_id)
    if chat is None:
        return {}
    await lazy_backfill_chat_imports(db, chat)

    import_repo = ChatDocumentImportRepository(db)
    att_repo = AttachmentRepository(db)
    hub_repo = HubItemRepository(db)
    imports = await import_repo.list_for_chat(chat_id)
    library: dict[str, ChatAttachmentIndexEntry] = {}

    for imp in imports:
        ref_key = str(imp.ref_id)
        if imp.source == "chat_attachment":
            row = await att_repo.get(imp.ref_id)
            if row is None or row.chat_id != chat_id or not _row_ready_attachment(row):
                continue
            meta: dict[str, Any] | None = None
            if load_meta:
                try:
                    raw = load_parsed_artifact(chat_id, row.id, "meta_json")
                    meta = json.loads(raw.decode("utf-8"))
                except FileNotFoundError:
                    meta = None
            library[ref_key] = _entry_from_attachment(row, meta)
        elif imp.source == "hub_item":
            row = await hub_repo.get(imp.ref_id)
            if row is None or row.user_id != chat.user_id or not _row_ready_hub(row):
                continue
            meta = None
            if load_meta:
                try:
                    scope = DocumentScope.hub(row.user_id, row.id)
                    raw = load_parsed_artifact_scoped(scope, "meta_json")
                    meta = json.loads(raw.decode("utf-8"))
                except FileNotFoundError:
                    meta = None
            library[ref_key] = _entry_from_hub_item(row, meta)
    return library


async def build_chat_library(
    db: AsyncSession,
    chat_id: uuid.UUID,
    *,
    load_meta: bool = True,
) -> dict[str, ChatAttachmentIndexEntry]:
    """Deprecated alias — session import library only."""
    return await build_session_document_library(db, chat_id, load_meta=load_meta)


def library_for_scope(
    ctx: DocRetrievalContext,
    scope: Literal["session", "turn"],
) -> dict[str, ChatAttachmentIndexEntry]:
    if scope == "turn":
        turn_ids = ctx.turn_attachment_ids
        return {k: v for k, v in ctx.library.items() if k in turn_ids}
    return dict(ctx.library)


def assert_chat_library_access(ctx: DocRetrievalContext, attachment_id: str) -> ChatAttachmentIndexEntry:
    att_id = str(attachment_id or "").strip()
    entry = ctx.library.get(att_id)
    if entry is None:
        raise DocRetrievalError("not_found", f"attachment not found or not ready: {att_id}")
    if entry.parse_status not in PARSE_READY_STATUSES:
        raise DocRetrievalError("not_ready", f"attachment parse not ready: {entry.filename}")
    return entry


def load_content_md_for_entry(entry: ChatAttachmentIndexEntry) -> str:
    scope = _document_scope_for_entry(entry)
    raw = load_parsed_artifact_scoped(scope, "content_md")
    return raw.decode("utf-8", errors="replace")


def load_meta_json_for_entry(entry: ChatAttachmentIndexEntry) -> dict[str, Any]:
    scope = _document_scope_for_entry(entry)
    raw = load_parsed_artifact_scoped(scope, "meta_json")
    return json.loads(raw.decode("utf-8"))


def load_pageindex_json_for_entry(entry: ChatAttachmentIndexEntry) -> dict[str, Any] | None:
    scope = _document_scope_for_entry(entry)
    try:
        raw = load_parsed_artifact_scoped(scope, "pageindex_json")
    except FileNotFoundError:
        return None
    return json.loads(raw.decode("utf-8"))


def load_content_md(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    raw = load_parsed_artifact(chat_id, attachment_id, "content_md")
    return raw.decode("utf-8", errors="replace")


def load_meta_json(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> dict[str, Any]:
    raw = load_parsed_artifact(chat_id, attachment_id, "meta_json")
    return json.loads(raw.decode("utf-8"))


def load_pageindex_json(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> dict[str, Any] | None:
    try:
        raw = load_parsed_artifact(chat_id, attachment_id, "pageindex_json")
    except FileNotFoundError:
        return None
    return json.loads(raw.decode("utf-8"))


def cached_meta(ctx: DocRetrievalContext, attachment_id: uuid.UUID) -> dict[str, Any]:
    key = str(attachment_id)
    cached = ctx.meta_cache.get(key)
    if cached is not None:
        return cached
    entry = ctx.library.get(key)
    if entry is None:
        meta = load_meta_json(ctx.chat_id, attachment_id)
    else:
        meta = load_meta_json_for_entry(entry)
    ctx.meta_cache[key] = meta
    return meta


def load_figure_bytes_for_entry(
    entry: ChatAttachmentIndexEntry,
    figure_id: str,
    *,
    extension: str,
) -> bytes:
    scope = _document_scope_for_entry(entry)
    return load_parsed_figure_scoped(scope, figure_id, extension)


def load_figure_bytes(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
    *,
    extension: str,
) -> bytes:
    return load_parsed_figure_scoped(
        DocumentScope.chat(chat_id, attachment_id),
        figure_id,
        extension,
    )


def is_document_kind(kind: str) -> bool:
    return kind in {
        AttachmentKind.TEXT.value,
        AttachmentKind.SHEET.value,
        AttachmentKind.PDF.value,
        AttachmentKind.OFFICE.value,
        AttachmentKind.AUDIO.value,
    }
