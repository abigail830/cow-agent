"""Vercel Blob client-upload token minting for Document Hub files."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from app.config import get_settings
from app.platform.attachments.limits import attachment_limits
from app.platform.blob.client import blob_storage_enabled, generate_client_upload_token
from app.platform.document_hub.storage.paths import hub_original_blob_path


def hub_upload_mode() -> str:
    """Browser → Blob client upload only on Vercel (or when explicitly forced). Local dev uses multipart."""
    if not blob_storage_enabled():
        return "multipart"
    if os.getenv("VERCEL") == "1":
        return "blob"
    forced = (os.getenv("HUB_CLIENT_BLOB_UPLOAD") or "").strip().lower()
    if forced in {"1", "true", "yes"}:
        return "blob"
    return "multipart"


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
        user_id = uuid.UUID(str(data["user_id"]))
        item_id = uuid.UUID(str(data["item_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("clientPayload must include user_id and item_id") from exc
    return user_id, item_id


def _validate_hub_pathname(
    *,
    user_id: uuid.UUID,
    pathname: str,
    client_payload: str | None,
) -> uuid.UUID:
    payload_user_id, item_id = _parse_client_payload(client_payload)
    if payload_user_id != user_id:
        raise ValueError("clientPayload user_id does not match authenticated user")
    expected = hub_original_blob_path(user_id, item_id)
    normalized = pathname.lstrip("/")
    if normalized != expected:
        raise ValueError("pathname does not match prepared hub item location")
    return item_id


def handle_hub_blob_upload_request(
    *,
    user_id: uuid.UUID,
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

    _validate_hub_pathname(
        user_id=user_id,
        pathname=pathname,
        client_payload=client_payload,
    )

    _, max_file_bytes, _, _, _ = attachment_limits(get_settings())
    client_token = generate_client_upload_token(
        pathname,
        maximum_size_in_bytes=max_file_bytes,
        allowed_content_types=None,
        allow_overwrite=True,
        add_random_suffix=False,
    )
    return {"type": event_type, "clientToken": client_token}
