"""Always-FULL attachment injection for send and history replay."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import Content, Message

from app.config import Settings, get_settings
from app.platform.attachments.capabilities import AttachmentCapabilities, attachment_capabilities
from app.platform.attachments.convert.pdf_pages import rasterize_pdf_pages
from app.platform.attachments.extract.tables import extract_sheet_bytes
from app.platform.attachments.extract.text import extract_text_bytes
from app.platform.attachments.extract.truncate import truncate_chars
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.attachments.pages import load_attachment_bytes
from app.platform.attachments.storage import is_inline_provider_file_id


def _item_attr(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _attachment_items(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (metadata or {}).get("attachments")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _text_block(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content: str,
    warnings: list[str],
    truncated: bool,
) -> str:
    header = f"### {filename} ({mime_type}, {_format_size(size_bytes)})"
    if warnings:
        header += f"\n_Note: {'; '.join(warnings)}_"
    if truncated:
        header += "\n_Content truncated._"
    return f"{header}\n```\n{content}\n```"


def _apply_text_caps(text: str, *, settings: Settings) -> tuple[str, bool]:
    limit = settings.attachment_extract_max_chars_per_file
    if len(text) <= limit:
        return text, False
    return truncate_chars(text, limit)


def _has_usable_file_id(item: Any, *, provider: str | None) -> bool:
    file_id = str(_item_attr(item, "provider_file_id") or "")
    if not file_id or is_inline_provider_file_id(file_id):
        return False
    stored_provider = str(_item_attr(item, "provider") or "")
    if provider and stored_provider and stored_provider != provider:
        return False
    return True


def _hosted_file(item: Any) -> Content:
    return Content.from_hosted_file(
        file_id=str(_item_attr(item, "provider_file_id")),
        media_type=str(_item_attr(item, "mime_type") or "application/octet-stream"),
        name=str(_item_attr(item, "filename") or "attachment"),
    )


def _data_content(*, data: bytes, mime_type: str, filename: str) -> Content:
    return Content.from_data(
        data=data,
        media_type=mime_type,
        additional_properties={"filename": filename},
    )


def materialize_attachment(
    item: Any,
    *,
    chat_id: uuid.UUID,
    caps: AttachmentCapabilities,
    current_provider: str | None = None,
    settings: Settings | None = None,
) -> list[Content]:
    settings = settings or get_settings()
    filename = str(_item_attr(item, "filename") or "attachment")
    mime_type = str(_item_attr(item, "mime_type") or "application/octet-stream")
    size_bytes = int(_item_attr(item, "size_bytes") or 0)
    kind = classify_attachment(filename=filename, mime_type=mime_type)

    if kind == AttachmentKind.IMAGE:
        if caps.image_file_id and _has_usable_file_id(item, provider=current_provider):
            return [_hosted_file(item)]
        data = load_attachment_bytes(item, chat_id=chat_id)
        return [_data_content(data=data, mime_type=mime_type, filename=filename)]

    if kind == AttachmentKind.PDF:
        if caps.pdf_file_id and _has_usable_file_id(item, provider=current_provider):
            return [_hosted_file(item)]
        data = load_attachment_bytes(item, chat_id=chat_id)
        if caps.pdf_via == "file_data":
            return [_data_content(data=data, mime_type="application/pdf", filename=filename)]
        pages = rasterize_pdf_pages(data, filename=filename)
        return [
            _data_content(data=page.data, mime_type=page.mime_type, filename=page.filename)
            for page in pages
        ]

    if kind == AttachmentKind.SHEET:
        data = load_attachment_bytes(item, chat_id=chat_id)
        content, warnings = extract_sheet_bytes(
            data,
            filename=filename,
            max_rows_per_sheet=settings.attachment_table_max_rows_per_sheet,
        )
        content, truncated = _apply_text_caps(content, settings=settings)
        return [
            Content.from_text(
                _text_block(
                    filename=filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    content=content,
                    warnings=warnings,
                    truncated=truncated,
                )
            )
        ]

    if kind == AttachmentKind.TEXT:
        data = load_attachment_bytes(item, chat_id=chat_id)
        content, warnings = extract_text_bytes(data)
        content, truncated = _apply_text_caps(content, settings=settings)
        return [
            Content.from_text(
                _text_block(
                    filename=filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    content=content,
                    warnings=warnings,
                    truncated=truncated,
                )
            )
        ]

    raise ValueError(f"Unsupported attachment: {filename}")


def materialize_attachments(
    items: list[Any],
    *,
    chat_id: uuid.UUID,
    model_id: str | None = None,
    provider: str | None = None,
    settings: Settings | None = None,
) -> list[Content]:
    if not items:
        return []
    settings = settings or get_settings()
    if not provider:
        for item in items:
            stored = str(_item_attr(item, "provider") or "")
            if stored:
                provider = stored
                break
    caps = attachment_capabilities(model_id=model_id, provider=provider)
    text_blocks: list[str] = []
    binary: list[Content] = []
    remaining_chars = settings.attachment_extract_max_chars_per_message
    for item in items:
        parts = materialize_attachment(
            item,
            chat_id=chat_id,
            caps=caps,
            current_provider=provider,
            settings=settings,
        )
        for part in parts:
            if getattr(part, "type", None) == "text":
                chunk = getattr(part, "text", None) or ""
                if remaining_chars <= 0:
                    continue
                if len(chunk) > remaining_chars:
                    chunk, _ = truncate_chars(chunk, remaining_chars)
                    remaining_chars = 0
                    text_blocks.append(chunk)
                else:
                    remaining_chars -= len(chunk)
                    text_blocks.append(chunk)
            else:
                binary.append(part)
    contents: list[Content] = []
    if text_blocks:
        contents.append(Content.from_text("\n\n".join(text_blocks)))
    contents.extend(binary)
    return contents


def build_user_message_with_attachments(
    content: str,
    attachments: list[Any],
    *,
    chat_id: uuid.UUID,
    model_id: str | None = None,
    provider: str | None = None,
) -> str | Message:
    text = content.strip()
    parts = materialize_attachments(
        attachments,
        chat_id=chat_id,
        model_id=model_id,
        provider=provider,
    )
    if not text and not parts:
        return text
    contents: list[Content] = []
    text_chunks: list[str] = []
    binary: list[Content] = []
    if text:
        text_chunks.append(text)
    for part in parts:
        if getattr(part, "type", None) == "text":
            chunk = getattr(part, "text", None) or ""
            if chunk:
                text_chunks.append(chunk)
        else:
            binary.append(part)
    if text_chunks:
        contents.append(Content.from_text("\n\n".join(text_chunks).strip()))
    contents.extend(binary)
    if not contents:
        return text
    if len(contents) == 1 and getattr(contents[0], "type", None) == "text" and not binary:
        merged = (getattr(contents[0], "text", None) or "").strip()
        if merged == text:
            return text
    return Message(role="user", contents=contents)


def build_replay_attachment_contents(
    row: dict[str, Any],
    *,
    model_id: str | None = None,
    provider: str | None = None,
) -> list[Content]:
    metadata = row.get("metadata") or {}
    items = _attachment_items(metadata)
    chat_id_raw = row.get("chat_id")
    if not items or not chat_id_raw:
        return []
    return materialize_attachments(
        items,
        chat_id=uuid.UUID(str(chat_id_raw)),
        model_id=model_id,
        provider=provider,
    )
