"""Unify-lite file type whitelist (phase 1: txt / md / docx only)."""

from __future__ import annotations

from pathlib import PurePath

from app.config import Settings
from app.platform.attachments.validation import validate_attachment_file

UNIFY_LITE_EXTENSIONS = frozenset({".txt", ".md", ".docx"})

UNIFY_LITE_MIME_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


def unify_lite_extension(filename: str) -> str:
    return PurePath(filename or "").suffix.lower()


def is_unify_lite_file(*, filename: str, mime_type: str) -> bool:
    ext = unify_lite_extension(filename)
    if ext in UNIFY_LITE_EXTENSIONS:
        return True
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    return normalized in UNIFY_LITE_MIME_TYPES


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
            "Unify-lite currently supports .txt, .md, and .docx files only. "
            "Switch to Native mode for PDF, images, and other formats."
        )
