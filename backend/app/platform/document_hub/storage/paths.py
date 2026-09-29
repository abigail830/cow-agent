"""Canonical Document Hub storage paths (local disk + Vercel Blob)."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.platform.attachments.storage import INLINE_PROVIDER_PREFIX
from app.platform.docstore.paths import HUB_STORAGE_ROOT

HUB_BLOB_PREFIX = "document-hub"


def format_hub_inline_provider_file_id(item_id: uuid.UUID) -> str:
    return f"{INLINE_PROVIDER_PREFIX}{item_id}"


def hub_original_blob_path(user_id: uuid.UUID, item_id: uuid.UUID) -> str:
    return f"{HUB_BLOB_PREFIX}/{user_id}/{item_id}"


def hub_original_local_path(user_id: uuid.UUID, item_id: uuid.UUID) -> Path:
    user_dir = (HUB_STORAGE_ROOT / str(user_id)).resolve()
    root = HUB_STORAGE_ROOT.resolve()
    if root not in user_dir.parents and user_dir != root:
        raise ValueError("Invalid hub storage path")
    return user_dir / str(item_id)
