"""Storage for inline image attachments (Azure OpenAI / SiliconFlow vision input)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.proposal.blob_client import blob_get, blob_put, blob_storage_enabled

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
INLINE_ATTACHMENTS_ROOT = _BACKEND_ROOT / "data" / "chat-attachments"

INLINE_PROVIDER_PREFIX = "inline:"
_BLOB_PREFIX = "chat-attachments"


def is_image_mime(mime_type: str) -> bool:
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    return normalized.startswith("image/")


def is_inline_provider_file_id(provider_file_id: str) -> bool:
    return str(provider_file_id or "").startswith(INLINE_PROVIDER_PREFIX)


def format_inline_provider_file_id(attachment_id: uuid.UUID) -> str:
    return f"{INLINE_PROVIDER_PREFIX}{attachment_id}"


def parse_inline_attachment_id(provider_file_id: str) -> uuid.UUID:
    suffix = str(provider_file_id).removeprefix(INLINE_PROVIDER_PREFIX).strip()
    return uuid.UUID(suffix)


def inline_attachment_path(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> Path:
    chat_dir = (INLINE_ATTACHMENTS_ROOT / str(chat_id)).resolve()
    chat_root = (INLINE_ATTACHMENTS_ROOT).resolve()
    if chat_dir != chat_root and chat_root not in chat_dir.parents:
        raise ValueError("Invalid chat attachment path")
    return chat_dir / str(attachment_id)


def _blob_object_name(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
    return f"{_BLOB_PREFIX}/{chat_id}/{attachment_id}"


def _require_writable_storage() -> None:
    if os.getenv("VERCEL") == "1" and not blob_storage_enabled():
        raise RuntimeError(
            "Chat attachments on Vercel require BLOB_READ_WRITE_TOKEN "
            "(set ARTIFACT_STORAGE=auto or vercel_blob)."
        )


def save_inline_attachment(chat_id: uuid.UUID, attachment_id: uuid.UUID, data: bytes) -> Path:
    _require_writable_storage()
    if blob_storage_enabled():
        blob_put(
            _blob_object_name(chat_id, attachment_id),
            data,
            content_type="application/octet-stream",
        )
        return inline_attachment_path(chat_id, attachment_id)

    path = inline_attachment_path(chat_id, attachment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def load_inline_attachment(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> bytes:
    if blob_storage_enabled():
        raw = blob_get(_blob_object_name(chat_id, attachment_id))
        if raw is None:
            raise FileNotFoundError(f"Inline attachment not found: {attachment_id}")
        return raw

    path = inline_attachment_path(chat_id, attachment_id)
    if not path.is_file():
        raise FileNotFoundError(f"Inline attachment not found: {attachment_id}")
    return path.read_bytes()
