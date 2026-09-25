"""Vercel Blob client-upload token minting for audio capture parts."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.platform.blob.client import blob_storage_enabled, generate_client_upload_token
from app.config import get_settings
from app.platform.attachments.storage import inline_attachment_blob_path


def capture_upload_mode() -> str:
    return "blob" if blob_storage_enabled() else "multipart"


def _parse_client_payload(raw: str | None) -> tuple[uuid.UUID, uuid.UUID]:
    if not raw:
        raise ValueError("clientPayload is required")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("clientPayload must be JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("clientPayload must be a JSON object")
    try:
        chat_id = uuid.UUID(str(data["chat_id"]))
        attachment_id = uuid.UUID(str(data["attachment_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("clientPayload must include chat_id and attachment_id") from exc
    return chat_id, attachment_id


def _validate_capture_pathname(
    *,
    chat_id: uuid.UUID,
    pathname: str,
    client_payload: str | None,
) -> uuid.UUID:
    payload_chat_id, attachment_id = _parse_client_payload(client_payload)
    if payload_chat_id != chat_id:
        raise ValueError("clientPayload chat_id does not match route")
    expected = inline_attachment_blob_path(chat_id, attachment_id)
    normalized = pathname.lstrip("/")
    if normalized != expected:
        raise ValueError("pathname does not match prepared attachment location")
    return attachment_id


def handle_blob_upload_request(
    *,
    chat_id: uuid.UUID,
    body: dict[str, Any],
) -> dict[str, Any]:
    if not blob_storage_enabled():
        raise RuntimeError("Vercel Blob storage is not configured")

    event_type = body.get("type")
    if event_type != "blob.generate-client-token":
        raise ValueError(f"Unsupported blob upload event: {event_type}")

    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Invalid blob upload payload")

    pathname = payload.get("pathname")
    if not isinstance(pathname, str) or not pathname.strip():
        raise ValueError("pathname is required")

    client_payload = payload.get("clientPayload")
    if client_payload is not None and not isinstance(client_payload, str):
        raise ValueError("clientPayload must be a string")

    _validate_capture_pathname(
        chat_id=chat_id,
        pathname=pathname,
        client_payload=client_payload,
    )

    settings = get_settings()
    max_total = int(settings.audio_capture_max_total_bytes)
    client_token = generate_client_upload_token(
        pathname,
        maximum_size_in_bytes=max_total,
        allowed_content_types=["audio/*", "application/octet-stream", "video/webm"],
        allow_overwrite=True,
        add_random_suffix=False,
    )
    return {"type": event_type, "clientToken": client_token}
