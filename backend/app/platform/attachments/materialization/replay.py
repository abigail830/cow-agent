"""Build MAF user contents for attachment replay and send paths."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import Content, Message

from app.platform.attachments.materialization.registry import (
    AttachmentMaterializationRegistry,
    resolve_materialized_kind,
)
from app.platform.attachments.materialization.stub import (
    format_attachment_stub,
    format_compaction_placeholder,
)
from app.platform.attachments.materialization.stub import user_requests_force_reread
from app.platform.attachments.native.maf_content import metadata_attachment_to_maf_content
from app.platform.attachments.unify_lite.pipeline import format_extracted_attachment_block, wrap_unify_lite_attachment_section
from app.platform.attachments.unify_lite.types import ExtractedAttachment
from app.platform.attachments.unify_lite.validation import is_unify_lite_image, is_unify_lite_text


def build_user_attachment_contents(
    *,
    user_text: str,
    metadata: dict[str, Any],
    chat_id: uuid.UUID,
    turn_sequence: int,
    registry: AttachmentMaterializationRegistry,
) -> list[Content]:
    """Build attachment-related Content blocks for one user message."""
    attachment_mode = str(metadata.get("attachment_mode") or "")
    items = _attachment_items(metadata)
    if not items:
        return []

    force_reread = user_requests_force_reread(user_text)
    text_blocks: list[str] = []
    binary_contents: list[Content] = []

    for item in items:
        att_id = str(item.get("id") or "")
        filename = str(item.get("filename") or "attachment")
        content_hash = _attachment_content_hash(item)

        if item.get("compaction_placeholder"):
            kind_label = "图片" if resolve_materialized_kind(item, attachment_mode=attachment_mode) == "vision" else "文档"
            text_blocks.append(
                format_compaction_placeholder(
                    filename=filename,
                    attachment_id=att_id,
                    kind=kind_label,
                )
            )
            continue

        full, hash_changed = registry.should_full_materialize(
            att_id,
            content_hash,
            force_reread=force_reread,
        )
        kind = resolve_materialized_kind(item, attachment_mode=attachment_mode)

        if full:
            registry.record_full_materialize(
                attachment_id=att_id,
                content_hash=content_hash,
                materialized_kind=kind,
                filename=filename,
                turn_sequence=turn_sequence,
            )
            if kind == "extract_text":
                block = _lite_document_block(item)
                if block:
                    if hash_changed:
                        text_blocks.append(f"_Note: newer version of {filename}_")
                    text_blocks.append(block)
            else:
                content = metadata_attachment_to_maf_content(item, chat_id=chat_id)
                if content is not None:
                    binary_contents.append(content)
        else:
            first_turn = registry.first_inject_turn(att_id) or turn_sequence
            text_blocks.append(
                format_attachment_stub(
                    filename=filename,
                    attachment_id=att_id,
                    first_turn_sequence=first_turn,
                    content_hash=content_hash,
                )
            )

    contents: list[Content] = []
    if text_blocks:
        section = wrap_unify_lite_attachment_section(text_blocks)
        if attachment_mode != "unify_lite":
            section = "\n\n".join(text_blocks)
        contents.append(Content.from_text(section))

    contents.extend(binary_contents)
    return contents


def build_replay_user_message_contents(
    row: dict[str, Any],
    *,
    registry: AttachmentMaterializationRegistry,
) -> list[Content]:
    """Attachment contents for history replay (excludes user text — caller adds that)."""
    metadata = row.get("metadata") or {}
    chat_id_raw = row.get("chat_id")
    if not chat_id_raw or not _attachment_items(metadata):
        return []
    return build_user_attachment_contents(
        user_text=str(row.get("content") or ""),
        metadata=metadata,
        chat_id=uuid.UUID(str(chat_id_raw)),
        turn_sequence=int(row.get("sequence") or 0),
        registry=registry,
    )


def _lite_document_block(item: dict[str, Any]) -> str | None:
    filename = str(item.get("filename") or "attachment")
    mime_type = str(item.get("mime_type") or "")
    if not is_unify_lite_text(filename=filename, mime_type=mime_type):
        return None
    snapshot = item.get("extracted_snapshot")
    if not isinstance(snapshot, dict):
        return None
    text = str(snapshot.get("text") or "")
    truncated = bool(snapshot.get("truncated"))
    char_count = int(snapshot.get("char_count") or len(text))
    size_bytes = int(item.get("size_bytes") or 0)
    extracted = ExtractedAttachment(
        attachment_id=uuid.UUID(str(item.get("id"))) if item.get("id") else uuid.uuid4(),
        filename=filename,
        mime_type=mime_type,
        content=text,
        truncated=truncated,
        char_count=char_count,
    )
    return format_extracted_attachment_block(extracted, size_bytes=size_bytes)


def _attachment_items(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    raw = metadata.get("attachments")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _attachment_content_hash(item: dict[str, Any]) -> str:
    snapshot = item.get("extracted_snapshot")
    if isinstance(snapshot, dict):
        value = str(snapshot.get("content_hash") or "")
        if value:
            return value
    return str(item.get("content_hash") or "")


def count_image_data_blocks(contents: list[Content]) -> int:
    return sum(1 for content in contents if getattr(content, "type", None) == "data")


def build_materialized_user_message(
    content: str,
    metadata: dict[str, Any],
    *,
    chat_id: uuid.UUID,
    turn_sequence: int,
    registry: AttachmentMaterializationRegistry,
) -> str | Message:
    """Build a full user Message for the current send turn (text + materialized attachments)."""
    text = content.strip()
    attachment_parts = build_user_attachment_contents(
        user_text=content,
        metadata=metadata,
        chat_id=chat_id,
        turn_sequence=turn_sequence,
        registry=registry,
    )

    if not text and not attachment_parts:
        return text

    contents: list[Content] = []
    attachment_text_chunks: list[str] = []
    binary_parts: list[Content] = []
    for part in attachment_parts:
        if getattr(part, "type", None) == "text":
            chunk = getattr(part, "text", None) or ""
            if chunk:
                attachment_text_chunks.append(chunk)
        else:
            binary_parts.append(part)

    sections: list[str] = []
    if text:
        sections.append(text)
    if attachment_text_chunks:
        sections.extend(attachment_text_chunks)
    if sections:
        contents.append(Content.from_text("\n\n".join(sections).strip()))
    contents.extend(binary_parts)

    if not contents:
        return text
    if len(contents) == 1 and getattr(contents[0], "type", None) == "text" and not binary_parts:
        merged = (getattr(contents[0], "text", None) or "").strip()
        if merged == text:
            return text
    return Message(role="user", contents=contents)

