"""Read/write hub item original bytes (local or Vercel Blob)."""

from __future__ import annotations

import os
import uuid

from app.platform.blob.client import blob_get, blob_put, blob_storage_enabled
from app.platform.document_hub.storage.paths import hub_original_blob_path, hub_original_local_path


def require_hub_writable_storage() -> None:
    if os.getenv("VERCEL") == "1" and not blob_storage_enabled():
        raise RuntimeError(
            "Document Hub on Vercel requires BLOB_READ_WRITE_TOKEN "
            "(set ARTIFACT_STORAGE=auto or vercel_blob)."
        )


def save_hub_original(user_id: uuid.UUID, item_id: uuid.UUID, data: bytes) -> None:
    require_hub_writable_storage()
    if blob_storage_enabled():
        blob_put(
            hub_original_blob_path(user_id, item_id),
            data,
            content_type="application/octet-stream",
        )
        return
    path = hub_original_local_path(user_id, item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load_hub_original(user_id: uuid.UUID, item_id: uuid.UUID) -> bytes:
    if blob_storage_enabled():
        raw = blob_get(hub_original_blob_path(user_id, item_id))
        if raw is None:
            raise FileNotFoundError(str(item_id))
        return raw
    path = hub_original_local_path(user_id, item_id)
    if not path.is_file():
        raise FileNotFoundError(str(item_id))
    return path.read_bytes()


def delete_hub_original_local(user_id: uuid.UUID, item_id: uuid.UUID) -> None:
    path = hub_original_local_path(user_id, item_id)
    if path.is_file():
        path.unlink(missing_ok=True)
