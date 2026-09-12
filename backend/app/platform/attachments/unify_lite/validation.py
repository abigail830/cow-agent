"""Unify-lite file type whitelist (text + images)."""

from __future__ import annotations

from pathlib import PurePath

from app.config import Settings
from app.platform.attachments.attachment_storage import is_image_mime
from app.platform.attachments.validation import validate_attachment_file

UNIFY_LITE_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".docx"})

UNIFY_LITE_TEXT_MIME_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

UNIFY_LITE_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})

UNIFY_LITE_IMAGE_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }
)


def unify_lite_extension(filename: str) -> str:
    return PurePath(filename or "").suffix.lower()


def is_unify_lite_image(*, filename: str, mime_type: str) -> bool:
    ext = unify_lite_extension(filename)
    if ext in UNIFY_LITE_IMAGE_EXTENSIONS:
        return True
    return is_image_mime(mime_type)


def is_unify_lite_text(*, filename: str, mime_type: str) -> bool:
    ext = unify_lite_extension(filename)
    if ext in UNIFY_LITE_TEXT_EXTENSIONS:
        return True
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    return normalized in UNIFY_LITE_TEXT_MIME_TYPES


def is_unify_lite_file(*, filename: str, mime_type: str) -> bool:
    return is_unify_lite_text(filename=filename, mime_type=mime_type) or is_unify_lite_image(
        filename=filename, mime_type=mime_type
    )


def validate_unify_lite_attachment_file(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    settings: Settings | None = None,
) -> None:
    validate_attachment_file(
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        settings=settings,
    )
    if not is_unify_lite_file(filename=filename, mime_type=mime_type):
        raise ValueError(
            "Unify-lite supports .txt, .md, .docx, and images (PNG/JPEG/GIF/WebP). "
            "Switch to Native mode for PDF and other formats."
        )
