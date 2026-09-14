"""Serialize attachment DB rows for message metadata and API responses."""

from __future__ import annotations

from typing import Any


def attachment_metadata(att: Any) -> dict[str, Any]:
    payload = {
        "id": str(att.id),
        "filename": att.filename,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "provider": att.provider,
        "provider_file_id": att.provider_file_id,
    }
    content_hash = getattr(att, "content_hash", None)
    if content_hash:
        payload["content_hash"] = content_hash
    return payload
