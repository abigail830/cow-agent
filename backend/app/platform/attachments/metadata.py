"""Serialize attachment DB rows for message metadata and API responses."""

from __future__ import annotations

import uuid
from typing import Any

from app.platform.attachments.source import is_hub_materialize_item
from app.platform.parse_pipeline.serialization import attachment_out_extras


def _is_hub_attachment_row(att: Any) -> bool:
    return is_hub_materialize_item(att) and getattr(att, "chat_id", None) is None


def attachment_metadata(att: Any, *, chat_id: uuid.UUID | None = None) -> dict[str, Any]:
    att_chat_id = getattr(att, "chat_id", None)
    resolved_chat_id = att_chat_id if att_chat_id is not None else chat_id
    provider = getattr(att, "provider", None) or "inline"
    if _is_hub_attachment_row(att):
        provider = "hub"
    payload = {
        "id": str(att.id),
        "filename": att.filename,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "provider": provider,
        "provider_file_id": att.provider_file_id,
    }
    if resolved_chat_id is not None:
        payload["chat_id"] = str(resolved_chat_id)
    if _is_hub_attachment_row(att):
        payload["source"] = "hub_item"
        payload["user_id"] = str(att.user_id)
        folder_id = getattr(att, "folder_id", None)
        if folder_id is not None:
            payload["folder_id"] = str(folder_id)
    content_hash = getattr(att, "content_hash", None)
    if content_hash:
        payload["content_hash"] = content_hash
    attachment_role = getattr(att, "attachment_role", None)
    if attachment_role:
        payload["attachment_role"] = attachment_role
    capture_id = getattr(att, "capture_id", None)
    if capture_id is not None:
        payload["capture_id"] = str(capture_id)
    created_at = getattr(att, "created_at", None)
    if created_at is not None:
        payload["created_at"] = created_at.isoformat()
    payload.update(attachment_out_extras(att))
    return payload
