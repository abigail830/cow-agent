"""Serialize attachment DB rows for message metadata and API responses."""

from __future__ import annotations

from typing import Any

from app.platform.parse_pipeline.serialization import attachment_out_extras


def attachment_metadata(att: Any) -> dict[str, Any]:
    payload = {
        "id": str(att.id),
        "chat_id": str(att.chat_id),
        "filename": att.filename,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "provider": att.provider,
        "provider_file_id": att.provider_file_id,
    }
    content_hash = getattr(att, "content_hash", None)
    if content_hash:
        payload["content_hash"] = content_hash
    created_at = getattr(att, "created_at", None)
    if created_at is not None:
        payload["created_at"] = created_at.isoformat()
    payload.update(attachment_out_extras(att))
    return payload
