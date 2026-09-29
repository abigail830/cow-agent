"""Build StorageSpec dicts for parse-pipeline jobs (internal HTTP URLs)."""

from __future__ import annotations

import uuid
from urllib.parse import urljoin


def _join(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _platform_auth_headers(run_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {run_token}"}


def build_internal_storage_spec(
    *,
    public_base_url: str,
    attachment_id: uuid.UUID,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content_hash: str | None,
    run_token: str,
) -> dict:
    file_base = _join(public_base_url, f"/internal/parse/v1/files/{attachment_id}")
    auth_headers = _platform_auth_headers(run_token)
    return {
        "read": {
            "url": f"{file_base}/original",
            "method": "GET",
            "filename": filename,
            "content_type": mime_type,
            "size_bytes": size_bytes,
            "headers": auth_headers,
            **({"sha256": content_hash} if content_hash else {}),
        },
        "write": {
            "artifacts_batch": {
                "url": f"{file_base}/artifacts/batch",
                "method": "PUT",
                "headers": auth_headers,
            },
            "content_md": {
                "url": f"{file_base}/artifacts/content_md",
                "method": "PUT",
                "content_type": "text/markdown; charset=utf-8",
                "headers": auth_headers,
            },
            "meta_json": {
                "url": f"{file_base}/artifacts/meta_json",
                "method": "PUT",
                "content_type": "application/json",
                "headers": auth_headers,
            },
            "pageindex_json": {
                "url": f"{file_base}/artifacts/pageindex_json",
                "method": "PUT",
                "content_type": "application/json",
                "headers": auth_headers,
            },
        },
    }
