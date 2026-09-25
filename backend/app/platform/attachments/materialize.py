"""Attachment injection for send and history replay.

First appearance of an attachment_id in a session is materialized in full; later
mentions emit a compact reference stub until history tail drops the full copy.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from agent_framework import Content, Message

from app.config import Settings, get_settings
from app.platform.attachments.capabilities import AttachmentCapabilities, attachment_capabilities
from app.platform.attachments.convert.pdf_pages import rasterize_pdf_pages
from app.platform.attachments.extract.tables import extract_sheet_bytes
from app.platform.attachments.extract.text import extract_text_bytes
from app.platform.attachments.extract.truncate import truncate_chars
from app.platform.attachments.image_io import (
    normalize_image_for_llm,
    resolve_image_mime,
    validate_image_bytes,
)
from app.platform.attachments.kinds import AttachmentKind, classify_attachment, normalize_mime

_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
from app.platform.attachments.pages import load_attachment_bytes
from app.platform.attachments.storage import is_inline_provider_file_id
from app.platform.doc_retrieval.context import get_doc_retrieval_context
from app.platform.doc_retrieval.manifest import build_hydrate_text
from app.platform.docstore.blob import parsed_artifact_exists
from app.platform.docstore.models import PARSE_READY_STATUSES


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


ATTACHMENT_BLOCK_MARKER = "\n\n### "


def split_user_prompt_text(text: str) -> str:
    """User-visible prompt only (strip legacy merged attachment materialization tails)."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    marker = stripped.find(ATTACHMENT_BLOCK_MARKER)
    if marker >= 0:
        return stripped[:marker].strip()
    if stripped.startswith("### ") and "```" in stripped:
        return ""
    return stripped


def is_attachment_materialization_text(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.startswith("### ") and "```" in stripped


def format_attachment_reference_text(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    attachment_id: str,
) -> str:
    return (
        f"### {filename} ({mime_type}, {_format_size(size_bytes)})\n"
        f"_Previously shared in this conversation (attachment_id={attachment_id}). "
        f"Refer to the earlier inline copy in this chat history._"
    )


def is_attachment_reference_text(text: str) -> bool:
    stripped = (text or "").strip()
    return (
        stripped.startswith("### ")
        and "Previously shared in this conversation" in stripped
        and "attachment_id=" in stripped
    )


def is_attachment_body_text(text: str) -> bool:
    return is_attachment_materialization_text(text) or is_attachment_reference_text(text)


def _attachment_key(item: Any) -> str:
    att_id = str(_item_attr(item, "id") or "").strip()
    if att_id:
        return att_id
    return str(_item_attr(item, "filename") or "").strip()


_ATTACHMENT_ID_IN_REFERENCE_RE = re.compile(r"attachment_id=([^)\s]+)")


def _attachment_ids_in_reference_text(text: str) -> set[str]:
    return {match.strip() for match in _ATTACHMENT_ID_IN_REFERENCE_RE.findall(text or "")}


def _binary_attachment_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    binary: list[dict[str, Any]] = []
    for item in items:
        filename = str(_item_attr(item, "filename") or "attachment")
        mime_type = str(_item_attr(item, "mime_type") or "application/octet-stream")
        kind = classify_attachment(filename=filename, mime_type=mime_type)
        if kind in (AttachmentKind.IMAGE, AttachmentKind.PDF):
            binary.append(item)
    return binary


def full_inline_attachment_ids_in_message(message: Message) -> set[str]:
    """Attachment ids materialized in full inside this message's contents."""
    if message.role != "user":
        return set()
    platform = (message.additional_properties or {}).get("platform") or {}
    items = _attachment_items(platform)
    if not items:
        return set()

    inline_modes = _inline_modes_for_message(message)
    found: set[str] = set()
    binary_items = _binary_attachment_items(items)
    binary_idx = 0

    for content in message.contents or []:
        content_type = getattr(content, "type", None)
        if content_type in ("hosted_file", "data", "uri"):
            if binary_idx < len(binary_items):
                key = _attachment_key(binary_items[binary_idx])
                if key and inline_modes.get(key) != "reference":
                    found.add(key)
                binary_idx += 1
            continue
        if content_type != "text":
            continue
        text = getattr(content, "text", "") or ""
        if is_attachment_reference_text(text):
            continue
        if not is_attachment_materialization_text(text):
            continue
        for item in items:
            filename = str(_item_attr(item, "filename") or "")
            if filename and text.startswith(f"### {filename}"):
                key = _attachment_key(item)
                if key and inline_modes.get(key) != "reference":
                    found.add(key)
                break

    return found


def prior_full_attachment_ids_in_context(
    messages: list[Message],
    *,
    chat_id: uuid.UUID,
    model_id: str | None = None,
    provider: str | None = None,
) -> set[str]:
    """Ids that still have a full inline copy after reference policy (matches LLM history)."""
    if not messages:
        return set()
    replayed = apply_attachment_reference_policy(
        messages,
        chat_id=chat_id,
        model_id=model_id,
        provider=provider,
    )
    return fully_inlined_attachment_ids_in_context(replayed)


def reference_only_attachment_ids_in_message(message: Message) -> set[str]:
    """Attachment ids represented only as reference stubs in this message."""
    if message.role != "user":
        return set()
    platform = (message.additional_properties or {}).get("platform") or {}
    items = _attachment_items(platform)
    if not items:
        return set()

    referenced: set[str] = set()
    for content in message.contents or []:
        if getattr(content, "type", None) != "text":
            continue
        text = getattr(content, "text", "") or ""
        if not is_attachment_reference_text(text):
            continue
        referenced.update(_attachment_ids_in_reference_text(text))

    item_keys = {_attachment_key(item) for item in items if _attachment_key(item)}
    return referenced & item_keys


def _forced_inline_modes(metadata: dict[str, Any]) -> dict[str, str]:
    raw = metadata.get("attachment_inline_modes")
    if not isinstance(raw, dict):
        return {}
    modes: dict[str, str] = {}
    for key, value in raw.items():
        att_id = str(key or "").strip()
        mode = str(value or "").strip().lower()
        if att_id and mode in {"full", "reference"}:
            modes[att_id] = mode
    return modes


def fully_inlined_attachment_ids_in_context(messages: list[Message]) -> set[str]:
    """Attachment ids that still have at least one full inline copy in context."""
    full: set[str] = set()
    for message in messages:
        full.update(full_inline_attachment_ids_in_message(message))
    return full


def already_full_attachment_ids(messages: list[Message]) -> set[str]:
    """Alias for callers that gate new @ sends on visible full inline copies."""
    return fully_inlined_attachment_ids_in_context(messages)


def _extract_user_prompt_from_message(message: Message) -> str:
    for content in message.contents or []:
        if getattr(content, "type", None) != "text":
            continue
        text = getattr(content, "text", "") or ""
        if is_attachment_body_text(text):
            continue
        return split_user_prompt_text(text)
    return ""


def materialize_attachment_reference(item: Any) -> list[Content]:
    attachment_id = str(_item_attr(item, "id") or _attachment_key(item))
    return [
        Content.from_text(
            format_attachment_reference_text(
                filename=str(_item_attr(item, "filename") or "attachment"),
                mime_type=str(_item_attr(item, "mime_type") or "application/octet-stream"),
                size_bytes=int(_item_attr(item, "size_bytes") or 0),
                attachment_id=attachment_id,
            )
        )
    ]


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


def _should_rematerialize_from_disk(item: Any, caps: AttachmentCapabilities) -> bool:
    """Re-read bytes from storage instead of preserving stale message body parts."""
    filename = str(_item_attr(item, "filename") or "attachment")
    mime_type = str(_item_attr(item, "mime_type") or "application/octet-stream")
    kind = classify_attachment(filename=filename, mime_type=mime_type)
    # DeepSeek / Qwen / GPT vision use inline image_url; never replay old hosted_file stubs.
    if kind == AttachmentKind.IMAGE and not caps.image_file_id:
        return True
    return False


def _explicit_parse_ready(item: Any) -> bool:
    status = _item_attr(item, "parse_status")
    if not status:
        return False
    return str(status) in PARSE_READY_STATUSES


def should_hydrate_parsed_document(
    item: Any,
    caps: AttachmentCapabilities,
    *,
    chat_id: uuid.UUID | None = None,
    settings: Settings | None = None,
) -> bool:
    """Use parse artifacts + doc_retrieval tools instead of inline extract/raster."""
    settings = settings or get_settings()
    if not _explicit_parse_ready(item):
        return False
    filename = str(_item_attr(item, "filename") or "attachment")
    mime_type = str(_item_attr(item, "mime_type") or "application/octet-stream")
    kind = classify_attachment(filename=filename, mime_type=mime_type)
    if kind == AttachmentKind.IMAGE:
        return False
    if chat_id is not None:
        att_id = str(_item_attr(item, "id") or "").strip()
        if not att_id:
            return False
        try:
            if not parsed_artifact_exists(chat_id, uuid.UUID(att_id), "content_md"):
                return False
        except (ValueError, FileNotFoundError):
            return False
    hydrate_kinds = (
        AttachmentKind.TEXT,
        AttachmentKind.SHEET,
        AttachmentKind.PDF,
        AttachmentKind.OFFICE,
    )
    if settings.document_hydrate_unified:
        return kind in hydrate_kinds
    if kind == AttachmentKind.PDF and caps.pdf_file_id:
        return False
    return kind in hydrate_kinds


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
        validate_image_bytes(data, filename=filename)
        data, effective_mime = normalize_image_for_llm(data)
        return [_data_content(data=data, mime_type=effective_mime, filename=filename)]

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
    already_full_inlined: set[str] | None = None,
    forced_inline_modes: dict[str, str] | None = None,
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
    seen = already_full_inlined if already_full_inlined is not None else set()
    inline_modes = forced_inline_modes or {}
    text_blocks: list[str] = []
    binary: list[Content] = []
    hydrate_items: list[Any] = []
    remaining_chars = settings.attachment_extract_max_chars_per_message
    for item in items:
        key = _attachment_key(item)
        forced_mode = inline_modes.get(key or "")
        if forced_mode == "reference" or (key and key in seen):
            parts = materialize_attachment_reference(item)
        elif should_hydrate_parsed_document(item, caps, chat_id=chat_id, settings=settings):
            hydrate_items.append(item)
            parts = []
            if key:
                seen.add(key)
        else:
            parts = materialize_attachment(
                item,
                chat_id=chat_id,
                caps=caps,
                current_provider=provider,
                settings=settings,
            )
            if key:
                seen.add(key)
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
    if hydrate_items:
        hydrate_text = build_hydrate_text(hydrate_items, ctx=get_doc_retrieval_context())
        if hydrate_text:
            text_blocks.insert(0, hydrate_text)
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
    already_full_inlined: set[str] | None = None,
) -> str | Message:
    text = content.strip()
    parts = materialize_attachments(
        attachments,
        chat_id=chat_id,
        model_id=model_id,
        provider=provider,
        already_full_inlined=already_full_inlined,
    )
    if not text and not parts:
        return text
    contents: list[Content] = []
    if text:
        contents.append(Content.from_text(text))
    for part in parts:
        contents.append(part)
    if not contents:
        return text
    if not parts:
        return text
    return Message(role="user", contents=contents)


def build_replay_attachment_contents(
    row: dict[str, Any],
    *,
    model_id: str | None = None,
    provider: str | None = None,
    already_full_inlined: set[str] | None = None,
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
        already_full_inlined=already_full_inlined,
        forced_inline_modes=_forced_inline_modes(metadata),
    )


def _inline_modes_for_message(message: Message) -> dict[str, str]:
    platform = (message.additional_properties or {}).get("platform") or {}
    return _forced_inline_modes(platform)


def _set_inline_modes_on_message(message: Message, modes: dict[str, str]) -> None:
    if not modes:
        return
    props = dict(message.additional_properties or {})
    platform = dict(props.get("platform") or {})
    platform["attachment_inline_modes"] = modes
    props["platform"] = platform
    message.additional_properties = props


def _existing_full_parts_for_item(message: Message, item: dict[str, Any]) -> list[Content]:
    key = _attachment_key(item)
    filename = str(_item_attr(item, "filename") or "attachment")
    mime_type = str(_item_attr(item, "mime_type") or "application/octet-stream")
    kind = classify_attachment(filename=filename, mime_type=mime_type)
    parts: list[Content] = []

    for content in message.contents or []:
        content_type = getattr(content, "type", None)
        if kind in (AttachmentKind.IMAGE, AttachmentKind.PDF) and content_type in (
            "hosted_file",
            "data",
            "uri",
        ):
            if content_type == "hosted_file":
                file_id = str(getattr(content, "file_id", "") or "")
                stored_file_id = str(_item_attr(item, "provider_file_id") or "")
                if not stored_file_id or file_id == stored_file_id:
                    parts.append(content)
                    break
            else:
                parts.append(content)
                break
        if content_type != "text":
            continue
        text = getattr(content, "text", "") or ""
        if is_attachment_materialization_text(text) and text.startswith(f"### {filename}"):
            parts.append(content)
            break

    return parts


def _merge_attachment_parts(parts: list[Content]) -> list[Content]:
    text_blocks: list[str] = []
    binary: list[Content] = []
    for part in parts:
        if getattr(part, "type", None) == "text":
            chunk = getattr(part, "text", None) or ""
            if chunk:
                text_blocks.append(chunk)
        else:
            binary.append(part)
    merged: list[Content] = []
    if text_blocks:
        merged.append(Content.from_text("\n\n".join(text_blocks)))
    merged.extend(binary)
    return merged


def _materialize_attachment_parts_for_message(
    message: Message,
    items: list[dict[str, Any]],
    *,
    chat_id: uuid.UUID,
    model_id: str | None = None,
    provider: str | None = None,
    already_full_inlined: set[str],
) -> list[Content]:
    ref_only = reference_only_attachment_ids_in_message(message)
    inline_modes = dict(_inline_modes_for_message(message))
    for att_id in ref_only:
        inline_modes.setdefault(att_id, "reference")

    caps = attachment_capabilities(model_id=model_id, provider=provider)
    parts: list[Content] = []
    existing_full = full_inline_attachment_ids_in_message(message)
    for item in items:
        key = _attachment_key(item)
        if not key:
            continue
        forced_mode = inline_modes.get(key)
        if forced_mode == "reference" or key in already_full_inlined or key in ref_only:
            parts.extend(materialize_attachment_reference(item))
            continue
        settings = get_settings()
        if should_hydrate_parsed_document(item, caps, chat_id=chat_id, settings=settings):
            hydrate_text = build_hydrate_text([item], ctx=get_doc_retrieval_context())
            if hydrate_text:
                parts.append(Content.from_text(hydrate_text))
            already_full_inlined.add(key)
            continue
        if key in existing_full and not _should_rematerialize_from_disk(item, caps):
            preserved = _existing_full_parts_for_item(message, item)
            if preserved:
                parts.extend(preserved)
                already_full_inlined.add(key)
                continue
        parts.extend(
            materialize_attachment(
                item,
                chat_id=chat_id,
                caps=caps,
                current_provider=provider,
            )
        )
        already_full_inlined.add(key)

    return _merge_attachment_parts(parts)


def stub_superseded_attachment_full_inlines(messages: list[Message]) -> bool:
    """Convert older duplicate full inlines to reference stubs (no disk re-read)."""
    last_full_index: dict[str, int] = {}
    for idx, message in enumerate(messages):
        for att_id in full_inline_attachment_ids_in_message(message):
            last_full_index[att_id] = idx

    changed = False
    for idx, message in enumerate(messages):
        if message.role != "user":
            continue
        full_ids = full_inline_attachment_ids_in_message(message)
        superseded = {att_id for att_id in full_ids if last_full_index.get(att_id) != idx}
        if not superseded:
            continue

        platform = (message.additional_properties or {}).get("platform") or {}
        items = _attachment_items(platform)
        if not items:
            continue

        inline_modes = dict(_inline_modes_for_message(message))
        for att_id in superseded:
            inline_modes[att_id] = "reference"

        prompt = _extract_user_prompt_from_message(message)
        attachment_parts: list[Content] = []
        for item in items:
            key = _attachment_key(item)
            if key and key in superseded:
                attachment_parts.extend(materialize_attachment_reference(item))
            elif key and key in full_ids:
                for content in message.contents or []:
                    content_type = getattr(content, "type", None)
                    if content_type in ("hosted_file", "data", "uri"):
                        attachment_parts.append(content)
                    elif content_type == "text":
                        text = getattr(content, "text", "") or ""
                        if is_attachment_materialization_text(text):
                            filename = str(_item_attr(item, "filename") or "")
                            if filename and text.startswith(f"### {filename}"):
                                attachment_parts.append(content)
            else:
                attachment_parts.extend(materialize_attachment_reference(item))

        contents: list[Content] = []
        if prompt:
            contents.append(Content.from_text(prompt))
        contents.extend(_merge_attachment_parts(attachment_parts))
        message.contents = contents
        _set_inline_modes_on_message(message, inline_modes)
        changed = True

    return changed


def apply_attachment_reference_policy(
    messages: list[Message],
    *,
    chat_id: uuid.UUID,
    model_id: str | None = None,
    provider: str | None = None,
) -> list[Message]:
    """Rewrite user attachment contents: first inline, later references only.

    Stubbed / reference-only turns stay stubbed on passive replay. Re-inline
    happens only when the caller sends a new @ mention and context has no full
    copy left (see fully_inlined_attachment_ids_in_context).
    """
    already_full: set[str] = set()
    result: list[Message] = []
    for message in messages:
        if message.role != "user":
            result.append(message)
            continue
        platform = (message.additional_properties or {}).get("platform") or {}
        items = _attachment_items(platform)
        if not items:
            result.append(message)
            continue
        prompt = _extract_user_prompt_from_message(message)
        parts = _materialize_attachment_parts_for_message(
            message,
            items,
            chat_id=chat_id,
            model_id=model_id,
            provider=provider,
            already_full_inlined=already_full,
        )
        contents: list[Content] = []
        if prompt:
            contents.append(Content.from_text(prompt))
        contents.extend(parts)
        result.append(
            Message(
                role="user",
                contents=contents,
                additional_properties=message.additional_properties,
            )
        )
    return result
