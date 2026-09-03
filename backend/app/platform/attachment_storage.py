"""Local storage for Azure OpenAI image attachments (inline vision input)."""

from __future__ import annotations

import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
INLINE_ATTACHMENTS_ROOT = _BACKEND_ROOT / "data" / "chat-attachments"

INLINE_PROVIDER_PREFIX = "inline:"


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


def save_inline_attachment(chat_id: uuid.UUID, attachment_id: uuid.UUID, data: bytes) -> Path:
    path = inline_attachment_path(chat_id, attachment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def load_inline_attachment(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> bytes:
    path = inline_attachment_path(chat_id, attachment_id)
    if not path.is_file():
        raise FileNotFoundError(f"Inline attachment not found: {attachment_id}")
    return path.read_bytes()
