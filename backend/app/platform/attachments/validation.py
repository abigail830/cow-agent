"""Platform-wide attachment validation — shared by native and unify-lite paths."""

from __future__ import annotations

from app.config import Settings
from app.platform.attachments.attachment_limits import attachment_limits

ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "text/plain",
        "text/csv",
        "text/markdown",
        "application/json",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
    }
)

SUPPORTED_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
)


def validate_attachment_file(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    settings: Settings | None = None,
) -> None:
    _, max_file_bytes, _ = attachment_limits(settings)
    if size_bytes <= 0:
        raise ValueError("File is empty")
    if size_bytes > max_file_bytes:
        raise ValueError(f"File exceeds {max_file_bytes // (1024 * 1024)} MB limit")
    normalized = (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if normalized not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {normalized or filename}")


def validate_message_attachments(*, size_bytes_list: list[int], settings: Settings | None = None) -> None:
    max_files, _, max_total_bytes = attachment_limits(settings)
    count = len(size_bytes_list)
    if count > max_files:
        raise ValueError(f"At most {max_files} attachments per message")
    total = sum(size_bytes_list)
    if total > max_total_bytes:
        limit_mb = max_total_bytes // (1024 * 1024)
        raise ValueError(f"Combined attachment size exceeds {limit_mb} MB per message")
