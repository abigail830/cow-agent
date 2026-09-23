"""Storage path conventions for originals and parse artifacts."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.platform.attachments.storage import INLINE_ATTACHMENTS_ROOT

_ARTIFACT_NAMES = {
    "content_md": "content.md",
    "meta_json": "meta.json",
    "pageindex_json": "pageindex.json",
}


def parsed_artifact_dir(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> Path:
    base = (INLINE_ATTACHMENTS_ROOT / str(chat_id) / "parsed" / str(attachment_id)).resolve()
    root = INLINE_ATTACHMENTS_ROOT.resolve()
    if root not in base.parents and base != root:
        raise ValueError("Invalid parsed artifact path")
    return base


def parsed_artifact_path(chat_id: uuid.UUID, attachment_id: uuid.UUID, artifact_key: str) -> Path:
    filename = _ARTIFACT_NAMES.get(artifact_key, artifact_key)
    return parsed_artifact_dir(chat_id, attachment_id) / filename


def blob_parsed_prefix(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    return f"chat-attachments/{chat_id}/parsed/{attachment_id}"


def blob_parsed_object_name(chat_id: uuid.UUID, attachment_id: uuid.UUID, artifact_key: str) -> str:
    filename = _ARTIFACT_NAMES.get(artifact_key, artifact_key)
    return f"{blob_parsed_prefix(chat_id, attachment_id)}/{filename}"
