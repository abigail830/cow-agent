"""Load parsed artifacts and enforce chat_library access."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment
from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.doc_retrieval.context import ChatAttachmentIndexEntry, DocRetrievalContext
from app.platform.docstore.blob import load_parsed_artifact, load_parsed_figure
from app.platform.docstore.models import PARSE_READY_STATUSES


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


def _entry_from_row(row: ChatAttachment, meta: dict[str, Any] | None = None) -> ChatAttachmentIndexEntry:
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
        line_count=line_count,
        page_count=page_count,
        figure_count=figure_count,
        gist=getattr(row, "gist", None),
        created_at=created_at,
        section_titles=section_titles,
    )


async def build_chat_library(
    db: AsyncSession,
    chat_id: uuid.UUID,
    *,
    load_meta: bool = True,
) -> dict[str, ChatAttachmentIndexEntry]:
    repo = AttachmentRepository(db)
    rows = await repo.list_for_chat(chat_id)
    library: dict[str, ChatAttachmentIndexEntry] = {}
    for row in rows:
        status = str(row.parse_status or "ready")
        if status not in PARSE_READY_STATUSES:
            continue
        meta: dict[str, Any] | None = None
        if load_meta:
            try:
                raw = load_parsed_artifact(chat_id, row.id, "meta_json")
                meta = json.loads(raw.decode("utf-8"))
            except FileNotFoundError:
                meta = None
        library[str(row.id)] = _entry_from_row(row, meta)
    return library


def assert_chat_library_access(ctx: DocRetrievalContext, attachment_id: str) -> ChatAttachmentIndexEntry:
    att_id = str(attachment_id or "").strip()
    entry = ctx.library.get(att_id)
    if entry is None:
        raise DocRetrievalError("not_found", f"attachment not found or not ready: {att_id}")
    if entry.parse_status not in PARSE_READY_STATUSES:
        raise DocRetrievalError("not_ready", f"attachment parse not ready: {entry.filename}")
    return entry


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
    meta = load_meta_json(ctx.chat_id, attachment_id)
    ctx.meta_cache[key] = meta
    return meta


def load_figure_bytes(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
    *,
    extension: str,
) -> bytes:
    return load_parsed_figure(chat_id, attachment_id, figure_id, extension)


def is_document_kind(kind: str) -> bool:
    return kind in {
        AttachmentKind.TEXT.value,
        AttachmentKind.SHEET.value,
        AttachmentKind.PDF.value,
        AttachmentKind.OFFICE.value,
    }
