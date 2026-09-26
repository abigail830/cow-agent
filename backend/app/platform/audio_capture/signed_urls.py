"""HMAC-signed public URLs for ASR providers (DashScope requires internet-reachable file URLs)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

from app.config import get_settings
from app.platform.attachments.storage import inline_attachment_blob_path
from app.platform.blob.client import blob_presigned_get_url, blob_storage_enabled

logger = logging.getLogger(__name__)


def _secret() -> bytes:
    settings = get_settings()
    material = (settings.dashscope_api_key or settings.parse_pipeline_service_api_key or "dev-asr-signing")
    return material.encode()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def mint_asr_file_token(*, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    ttl = max(300, int(settings.asr_signed_url_ttl_sec))
    expires_at = int(time.time()) + ttl
    payload = {
        "chat_id": str(chat_id),
        "attachment_id": str(attachment_id),
        "exp": expires_at,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}", expires_at


def verify_asr_file_token(token: str) -> dict[str, Any]:
    if "." not in token:
        raise ValueError("invalid token")
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("invalid signature")
    payload = json.loads(_b64url_decode(body))
    exp = int(payload.get("exp") or 0)
    if exp < int(time.time()):
        raise ValueError("token expired")
    return payload


def public_asr_file_url(*, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    settings = get_settings()
    public_base = (settings.parse_pipeline_public_base_url or "http://127.0.0.1:8000").strip()
    token, _ = mint_asr_file_token(chat_id=chat_id, attachment_id=attachment_id)
    return f"{public_base.rstrip('/')}/api/v1/public/asr-files/{token}"


def mint_asr_download_url(*, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[str, int]:
    """Mint an internet-reachable audio URL for external ASR providers."""
    settings = get_settings()
    ttl_sec = max(300, int(settings.asr_signed_url_ttl_sec))
    expires_at = int(time.time()) + ttl_sec
    if blob_storage_enabled():
        pathname = inline_attachment_blob_path(chat_id, attachment_id)
        try:
            url = blob_presigned_get_url(pathname, valid_until_ms=expires_at * 1000)
            return url, expires_at
        except Exception as exc:
            logger.warning(
                "Blob presigned ASR URL failed for %s, falling back to proxy URL: %s",
                pathname,
                exc,
            )
    return public_asr_file_url(chat_id=chat_id, attachment_id=attachment_id), expires_at
