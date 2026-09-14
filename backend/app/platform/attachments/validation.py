"""Platform-wide attachment validation — type whitelist, size, and page budgets."""

from __future__ import annotations

from app.config import Settings
from app.platform.attachments.limits import attachment_limits
from app.platform.attachments.kinds import (
    AttachmentKind,
    classify_attachment,
    office_reject_message,
)

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
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
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
    ".xls",
    ".xlsx",
)


def _format_mb(size_bytes: int) -> int:
    return max(1, size_bytes // (1024 * 1024))


def validate_attachment_file(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    settings: Settings | None = None,
    page_count: int | None = None,
) -> AttachmentKind:
    _, max_file_bytes, _, max_pages_per_file, _ = attachment_limits(settings)
    if size_bytes <= 0:
        raise ValueError("File is empty")
    if size_bytes > max_file_bytes:
        raise ValueError(
            f"文件超过 {_format_mb(max_file_bytes)} MB 上限（当前 {size_bytes / (1024 * 1024):.1f} MB）"
        )
    try:
        kind = classify_attachment(filename=filename, mime_type=mime_type)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if kind == AttachmentKind.OFFICE:
        raise ValueError(office_reject_message(filename=filename, mime_type=mime_type))
    if kind == AttachmentKind.PDF and page_count is not None and page_count > max_pages_per_file:
        raise ValueError(
            f"PDF 超过单文件 {max_pages_per_file} 页上限（当前 {page_count} 页）"
        )
    return kind


def validate_message_attachments(
    *,
    size_bytes_list: list[int],
    page_counts: list[int] | None = None,
    settings: Settings | None = None,
) -> None:
    max_files, _, max_total_bytes, _, max_pages_per_message = attachment_limits(settings)
    count = len(size_bytes_list)
    if count > max_files:
        raise ValueError(f"At most {max_files} attachments per message")
    total = sum(size_bytes_list)
    if total > max_total_bytes:
        raise ValueError(f"本轮附件合计超过 {_format_mb(max_total_bytes)} MB 上限")
    if page_counts is not None:
        total_pages = sum(page_counts)
        if total_pages > max_pages_per_message:
            raise ValueError(
                f"本轮附件合计超过 {max_pages_per_message} 页上限（当前 {total_pages} 页）"
            )
