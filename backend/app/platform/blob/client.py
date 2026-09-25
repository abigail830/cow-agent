"""Minimal Vercel Blob REST client for platform storage (attachments, artifacts, captures)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_BLOB_CONTROL_API = "https://vercel.com/api/blob"
_API_VERSION = "12"
_RETRIABLE_BLOB_STATUS = frozenset({429, 502, 503, 504})
_BLOB_PUT_MAX_ATTEMPTS = 4


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
    last_error: RuntimeError | None = None
    with httpx.Client(timeout=60.0) as client:
        for attempt in range(1, _BLOB_PUT_MAX_ATTEMPTS + 1):
            response = client.put(url, content=payload, headers=headers)
            if response.status_code < 400:
                data = response.json()
                if not isinstance(data, dict):
                    raise RuntimeError("Vercel Blob upload returned unexpected payload.")
                return data

            detail = (response.text or "").strip() or response.reason_phrase
            last_error = RuntimeError(
                f"Vercel Blob upload failed ({response.status_code}): {detail}"
            )
            if response.status_code not in _RETRIABLE_BLOB_STATUS or attempt >= _BLOB_PUT_MAX_ATTEMPTS:
                raise last_error

            delay = 0.5 * (2 ** (attempt - 1))
            logger.warning(
                "Vercel Blob upload retry %s/%s for %s (HTTP %s); sleeping %.1fs",
                attempt,
                _BLOB_PUT_MAX_ATTEMPTS,
                pathname,
                response.status_code,
                delay,
            )
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Vercel Blob upload failed.")


def _blob_object_url(pathname: str) -> str:
    access = _resolve_access()
    store_id = _resolve_store_id()
    object_path = pathname.lstrip("/")
    return f"https://{store_id}.{access}.blob.vercel-storage.com/{object_path}"


def blob_exists(pathname: str) -> bool:
    url = _blob_object_url(pathname)
    with httpx.Client(timeout=10.0) as client:
        response = client.head(url, headers=_auth_headers())
    if response.status_code == 404:
        return False
    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason_phrase
        logger.warning("Vercel Blob head failed (%s): %s", response.status_code, detail)
        return False
    return True


def blob_get(pathname: str) -> bytes | None:
    url = _blob_object_url(pathname)
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=_auth_headers())
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason_phrase
        logger.warning("Vercel Blob read failed (%s): %s", response.status_code, detail)
        return None
    return response.content


def blob_delete(pathname: str) -> bool:
    object_path = pathname.lstrip("/")
    url = f"{_BLOB_CONTROL_API}/?{urlencode({'pathname': object_path})}"
    with httpx.Client(timeout=30.0) as client:
        response = client.delete(url, headers=_auth_headers())
    if response.status_code in {200, 204, 404}:
        return True
    detail = (response.text or "").strip() or response.reason_phrase
    logger.warning("Vercel Blob delete failed (%s): %s", response.status_code, detail)
    return False


def blob_list(pathname_prefix: str, *, limit: int = 1000) -> list[str]:
    prefix = pathname_prefix.lstrip("/")
    pathnames: list[str] = []
    cursor: str | None = None
    with httpx.Client(timeout=30.0) as client:
        while True:
            params: dict[str, str] = {"prefix": prefix, "limit": str(limit)}
            if cursor:
                params["cursor"] = cursor
            url = f"{_BLOB_CONTROL_API}/?{urlencode(params)}"
            response = client.get(url, headers=_auth_headers())
            if response.status_code >= 400:
                detail = (response.text or "").strip() or response.reason_phrase
                logger.warning("Vercel Blob list failed (%s): %s", response.status_code, detail)
                break
            data = response.json()
            if not isinstance(data, dict):
                break
            blobs = data.get("blobs") or []
            if isinstance(blobs, list):
                for item in blobs:
                    if not isinstance(item, dict):
                        continue
                    pathname = item.get("pathname") or item.get("url")
                    if isinstance(pathname, str) and pathname.strip():
                        pathnames.append(pathname.lstrip("/"))
            if not data.get("hasMore"):
                break
            next_cursor = data.get("cursor")
            if not isinstance(next_cursor, str) or not next_cursor.strip():
                break
            cursor = next_cursor
    return pathnames


def blob_delete_prefix(pathname_prefix: str) -> int:
    deleted = 0
    for pathname in blob_list(pathname_prefix):
        if blob_delete(pathname):
            deleted += 1
    return deleted


def generate_client_upload_token(
    pathname: str,
    *,
    maximum_size_in_bytes: int | None = None,
    allowed_content_types: list[str] | None = None,
    valid_until_ms: int | None = None,
    add_random_suffix: bool = False,
    allow_overwrite: bool = True,
) -> str:
    """Mint a browser client token compatible with @vercel/blob/client upload()."""
    read_write_token = _resolve_blob_token()
    if not read_write_token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is required for client uploads.")

    parts = read_write_token.split("_")
    store_id = parts[3] if len(parts) >= 4 and parts[3] else None
    if not store_id:
        raise RuntimeError("Invalid BLOB_READ_WRITE_TOKEN")

    object_path = pathname.lstrip("/")
    now_ms = int(time.time() * 1000)
    payload_obj: dict[str, Any] = {
        "pathname": object_path,
        "validUntil": valid_until_ms or (now_ms + 60 * 60 * 1000),
        "addRandomSuffix": add_random_suffix,
        "allowOverwrite": allow_overwrite,
    }
    if maximum_size_in_bytes is not None:
        payload_obj["maximumSizeInBytes"] = maximum_size_in_bytes
    if allowed_content_types:
        payload_obj["allowedContentTypes"] = allowed_content_types

    payload_b64 = base64.b64encode(
        json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    signature = hmac.new(
        read_write_token.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    token_body = base64.b64encode(f"{signature}.{payload_b64}".encode("ascii")).decode("ascii")
    return f"vercel_blob_client_{store_id}_{token_body}"
