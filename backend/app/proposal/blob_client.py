"""Minimal Vercel Blob REST client (Python backend has no official SDK)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_BLOB_CONTROL_API = "https://vercel.com/api/blob"
_API_VERSION = "12"


def blob_storage_enabled() -> bool:
    settings = get_settings()
    mode = settings.artifact_storage.strip().lower()
    if mode == "local":
        return False
    if mode == "vercel_blob":
        return True
    return bool(_resolve_blob_token())


def _resolve_blob_token() -> str | None:
    settings = get_settings()
    token = (settings.blob_read_write_token or "").strip().strip('"').strip("'")
    return token or None


def _normalize_store_id(store_id: str) -> str:
    value = store_id.strip().strip('"').strip("'")
    if value.startswith("store_"):
        return value[len("store_") :]
    return value


def _resolve_store_id() -> str:
    settings = get_settings()
    configured = (settings.blob_store_id or "").strip().strip('"').strip("'")
    if configured:
        return _normalize_store_id(configured)

    token = _resolve_blob_token()
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is required for Vercel Blob storage.")
    parts = token.split("_")
    if len(parts) >= 4 and parts[3]:
        return parts[3]
    raise RuntimeError(
        "Cannot resolve Blob store id. Set BLOB_STORE_ID or use a valid BLOB_READ_WRITE_TOKEN."
    )


def _resolve_access() -> str:
    access = (get_settings().blob_access or "private").strip().lower()
    if access not in {"private", "public"}:
        raise RuntimeError('BLOB_ACCESS must be "private" or "public".')
    return access


def _auth_headers(*, content_type: str | None = None) -> dict[str, str]:
    token = _resolve_blob_token()
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is required for Vercel Blob storage.")
    headers = {
        "authorization": f"Bearer {token}",
        "x-api-version": _API_VERSION,
        "x-vercel-blob-store-id": _resolve_store_id(),
    }
    if content_type:
        headers["content-type"] = content_type
    return headers


def blob_put(pathname: str, body: bytes | str, *, content_type: str) -> dict[str, Any]:
    access = _resolve_access()
    payload = body.encode("utf-8") if isinstance(body, str) else body
    url = f"{_BLOB_CONTROL_API}/?{urlencode({'pathname': pathname.lstrip('/')})}"
    headers = {
        **_auth_headers(content_type=content_type),
        "x-vercel-blob-access": access,
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
        "x-content-type": content_type,
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.put(url, content=payload, headers=headers)
    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason_phrase
        raise RuntimeError(f"Vercel Blob upload failed ({response.status_code}): {detail}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Vercel Blob upload returned unexpected payload.")
    return data


def blob_get(pathname: str) -> bytes | None:
    access = _resolve_access()
    store_id = _resolve_store_id()
    object_path = pathname.lstrip("/")
    url = f"https://{store_id}.{access}.blob.vercel-storage.com/{object_path}"
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=_auth_headers())
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason_phrase
        logger.warning("Vercel Blob read failed (%s): %s", response.status_code, detail)
        return None
    return response.content
