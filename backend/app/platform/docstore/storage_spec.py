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


def build_file_storage_spec(
    *,
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content_hash: str | None,
) -> dict:
    """file:// StorageSpec for inline subprocess dispatch (local dev)."""
    from pathlib import Path

    from app.platform.attachments.storage import inline_attachment_path
    from app.platform.docstore.paths import parsed_artifact_path

    original = inline_attachment_path(chat_id, attachment_id).resolve()
    parsed_dir = parsed_artifact_path(chat_id, attachment_id, "content_md").parent.resolve()

    def uri(path: Path) -> str:
        return path.as_uri()

    return {
        "read": {
            "url": uri(original),
            "method": "GET",
            "filename": filename,
            "content_type": mime_type,
            "size_bytes": size_bytes,
            **({"sha256": content_hash} if content_hash else {}),
        },
        "write": {
            "content_md": {
                "url": uri(parsed_dir / "content.md"),
                "method": "PUT",
                "content_type": "text/markdown; charset=utf-8",
            },
            "meta_json": {
                "url": uri(parsed_dir / "meta.json"),
                "method": "PUT",
                "content_type": "application/json",
            },
            "pageindex_json": {
                "url": uri(parsed_dir / "pageindex.json"),
                "method": "PUT",
                "content_type": "application/json",
            },
        },
    }
