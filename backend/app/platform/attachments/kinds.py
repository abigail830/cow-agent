"""Classify chat attachments into image / pdf / sheet / text / rejected office."""

from __future__ import annotations

from enum import Enum

OFFICE_REJECT_PPT = "当前环境不支持 PowerPoint，请先另存为 PDF 再上传。"
OFFICE_REJECT_WORD = "当前环境不支持 Word，请先另存为 PDF 再上传。"


class AttachmentKind(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    SHEET = "sheet"
    TEXT = "text"
    OFFICE = "office"
    AUDIO = "audio"


_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
_PDF_EXTS = frozenset({".pdf"})
_SHEET_EXTS = frozenset({".xls", ".xlsx", ".csv"})
_TEXT_EXTS = frozenset({".txt", ".md", ".json"})
_PPT_EXTS = frozenset({".ppt", ".pptx"})
_WORD_EXTS = frozenset({".doc", ".docx"})
_AUDIO_EXTS = frozenset({".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".opus", ".webm"})

_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_PDF_MIMES = frozenset({"application/pdf"})
_SHEET_MIMES = frozenset(
    {
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)
_TEXT_MIMES = frozenset({"text/plain", "text/markdown", "application/json"})
_PPT_MIMES = frozenset(
    {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)
_WORD_MIMES = frozenset(
    {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
_AUDIO_MIMES = frozenset(
    {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/flac",
        "audio/aac",
        "audio/ogg",
        "audio/opus",
        "audio/webm",
    }
)


def normalize_mime(mime_type: str | None) -> str:
    return (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()


def file_extension(filename: str) -> str:
    name = (filename or "").strip().lower()
    idx = name.rfind(".")
    return name[idx:] if idx >= 0 else ""


def classify_attachment(*, filename: str, mime_type: str | None) -> AttachmentKind:
    ext = file_extension(filename)
    mime = normalize_mime(mime_type)
    if ext in _PPT_EXTS or mime in _PPT_MIMES:
        return AttachmentKind.OFFICE
    if ext in _WORD_EXTS or mime in _WORD_MIMES:
        return AttachmentKind.OFFICE
    if ext in _IMAGE_EXTS or mime in _IMAGE_MIMES:
        return AttachmentKind.IMAGE
    if ext in _PDF_EXTS or mime in _PDF_MIMES:
        return AttachmentKind.PDF
    if ext in _SHEET_EXTS or mime in _SHEET_MIMES:
        return AttachmentKind.SHEET
    if ext in _TEXT_EXTS or mime in _TEXT_MIMES:
        return AttachmentKind.TEXT
    if ext in _AUDIO_EXTS or mime in _AUDIO_MIMES:
        return AttachmentKind.AUDIO
    if mime.startswith("image/"):
        return AttachmentKind.IMAGE
    if mime.startswith("audio/"):
        return AttachmentKind.AUDIO
    raise ValueError(f"Unsupported file type: {mime or filename}")


def office_reject_message(*, filename: str, mime_type: str | None) -> str:
    ext = file_extension(filename)
    mime = normalize_mime(mime_type)
    if ext in _PPT_EXTS or mime in _PPT_MIMES:
        return OFFICE_REJECT_PPT
    return OFFICE_REJECT_WORD


def page_cost_for_kind(kind: AttachmentKind, *, pdf_pages: int | None = None) -> int:
    """Images / sheets / text count as 1 page; PDFs use their real page count."""
    if kind == AttachmentKind.PDF:
        return max(1, int(pdf_pages or 1))
    return 1
