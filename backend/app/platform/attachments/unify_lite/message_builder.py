from __future__ import annotations

import uuid
from typing import Any

from agent_framework import Message

from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.replay import build_materialized_user_message
from app.platform.attachments.native.maf_content import attachment_metadata
from app.platform.attachments.unify_lite.pipeline import wrap_unify_lite_attachment_section
from app.platform.attachments.unify_lite.types import ExtractedAttachment

__all__ = [
    "build_unify_lite_message_metadata",
    "build_user_run_input_lite",
    "wrap_unify_lite_attachment_section",
]


def build_unify_lite_message_metadata(
    extracted: list[ExtractedAttachment],
    image_attachments: list | None = None,
    *,
    size_bytes_by_id: dict | None = None,
    content_hash_by_id: dict | None = None,
) -> dict[str, Any]:
    """Build message metadata for unify-lite send/replay (prefer snapshot fields when present)."""
    sizes = size_bytes_by_id or {}
    hashes = content_hash_by_id or {}
    attachments: list[dict[str, Any]] = []

    for item in extracted:
        att_id = str(item.attachment_id)
        snapshot: dict[str, Any] = {
            "text": item.content,
            "truncated": item.truncated,
            "char_count": item.char_count,
        }
        content_hash = hashes.get(item.attachment_id) or hashes.get(att_id)
        if content_hash:
            snapshot["content_hash"] = content_hash
        attachments.append(
            {
                "id": att_id,
                "filename": item.filename,
                "mime_type": item.mime_type,
                "size_bytes": int(sizes.get(item.attachment_id, 0)),
                "provider": "unify_lite",
                "provider_file_id": f"inline:{att_id}",
                "extracted_snapshot": snapshot,
            }
        )

    for row in image_attachments or []:
        meta = attachment_metadata(row, processing_mode="unify_lite")
        att_id = str(meta.get("id") or "")
        content_hash = hashes.get(getattr(row, "id", None)) or hashes.get(att_id)
        if content_hash:
            meta["content_hash"] = content_hash
        attachments.append(meta)

    return {"attachment_mode": "unify_lite", "attachments": attachments}


def _resolve_chat_id(
    extracted: list[ExtractedAttachment],
    image_attachments: list | None,
) -> uuid.UUID:
    for row in image_attachments or []:
        chat_id = getattr(row, "chat_id", None)
        if chat_id is not None:
            return uuid.UUID(str(chat_id))
    if extracted:
        return uuid.uuid4()
    return uuid.uuid4()


def build_user_run_input_lite(
    content: str,
    extracted: list[ExtractedAttachment],
    *,
    image_attachments: list | None = None,
    size_bytes_by_id: dict | None = None,
    content_hash_by_id: dict | None = None,
    chat_id: uuid.UUID | None = None,
    turn_sequence: int = 0,
    registry: AttachmentMaterializationRegistry | None = None,
) -> str | Message:
    """Build user input via the shared materialization path (full inject when registry is empty)."""
    if not extracted and not image_attachments and not content.strip():
        return content.strip()

    resolved_chat_id = chat_id or _resolve_chat_id(extracted, image_attachments)
    metadata = build_unify_lite_message_metadata(
        extracted,
        image_attachments,
        size_bytes_by_id=size_bytes_by_id,
        content_hash_by_id=content_hash_by_id,
    )
    if not metadata.get("attachments") and not content.strip():
        return content.strip()

    return build_materialized_user_message(
        content,
        metadata,
        chat_id=resolved_chat_id,
        turn_sequence=turn_sequence,
        registry=registry or AttachmentMaterializationRegistry(),
    )
