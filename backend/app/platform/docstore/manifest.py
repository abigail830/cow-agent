"""DB-backed manifest for parsed attachment artifacts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.platform.blob.client import blob_storage_enabled
from app.platform.docstore.content_types import parsed_artifact_media_type

_MANIFEST_VERSION = 1
_ARTIFACT_KEYS = ("content_md", "meta_json", "pageindex_json")
_ARTIFACT_FILENAMES = {
    "content_md": "content.md",
    "meta_json": "meta.json",
    "pageindex_json": "pageindex.json",
}


def parsed_storage_backend() -> str:
    return "vercel_blob" if blob_storage_enabled() else "local"


def parsed_artifact_prefix(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    return f"chat-attachments/{chat_id}/parsed/{attachment_id}"


def parsed_artifact_storage_path(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    artifact_key: str,
) -> str:
    filename = _ARTIFACT_FILENAMES.get(artifact_key, artifact_key)
    return f"{parsed_artifact_prefix(chat_id, attachment_id)}/{filename}"


def empty_parsed_artifact_manifest(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> dict[str, Any]:
    return {
        "version": _MANIFEST_VERSION,
        "storage": parsed_storage_backend(),
        "prefix": parsed_artifact_prefix(chat_id, attachment_id),
        "artifacts": {},
    }


def merge_parsed_artifact_record(
    manifest: dict[str, Any] | None,
    *,
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    artifact_key: str,
    size_bytes: int,
    content_type: str | None = None,
) -> dict[str, Any]:
    base = dict(manifest or empty_parsed_artifact_manifest(chat_id, attachment_id))
    artifacts = dict(base.get("artifacts") or {})
    filename = _ARTIFACT_FILENAMES.get(artifact_key, artifact_key)
    artifacts[artifact_key] = {
        "artifact_key": artifact_key,
        "relative_path": filename,
        "storage_path": parsed_artifact_storage_path(chat_id, attachment_id, artifact_key),
        "size_bytes": int(size_bytes),
        "content_type": content_type or parsed_artifact_media_type(artifact_key),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    base["version"] = _MANIFEST_VERSION
    base["storage"] = parsed_storage_backend()
    base["prefix"] = parsed_artifact_prefix(chat_id, attachment_id)
    base["artifacts"] = artifacts
    return base


def parsed_artifacts_flags_from_manifest(manifest: dict[str, Any] | None) -> dict[str, bool]:
    artifacts = (manifest or {}).get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    return {key: key in artifacts for key in _ARTIFACT_KEYS}


def parsed_artifact_in_manifest(manifest: dict[str, Any] | None, artifact_key: str) -> bool:
    return parsed_artifacts_flags_from_manifest(manifest).get(artifact_key, False)


def parsed_artifact_record(
    manifest: dict[str, Any] | None,
    artifact_key: str,
) -> dict[str, Any] | None:
    if not manifest:
        return None
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    record = artifacts.get(artifact_key)
    return record if isinstance(record, dict) else None


def iter_manifest_storage_paths(manifest: dict[str, Any] | None) -> list[str]:
    """Return deduplicated blob/local logical paths recorded in a manifest."""
    if not manifest:
        return []
    paths: list[str] = []
    seen: set[str] = set()

    def add(path: str | None) -> None:
        if not path or not isinstance(path, str):
            return
        normalized = path.lstrip("/")
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        paths.append(normalized)

    prefix = manifest.get("prefix")
    if isinstance(prefix, str):
        add(prefix)

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, dict):
        for record in artifacts.values():
            if isinstance(record, dict):
                add(record.get("storage_path"))

    return paths


def manifest_parsed_prefix(
    manifest: dict[str, Any] | None,
    *,
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> str:
    prefix = (manifest or {}).get("prefix")
    if isinstance(prefix, str) and prefix.strip():
        return prefix.lstrip("/")
    return parsed_artifact_prefix(chat_id, attachment_id)
