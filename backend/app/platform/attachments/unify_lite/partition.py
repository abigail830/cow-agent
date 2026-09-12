"""Partition unify-lite attachment rows by processing strategy."""

from __future__ import annotations

from app.platform.attachments.unify_lite.validation import is_unify_lite_image, is_unify_lite_text


def partition_unify_lite_attachments(rows: list) -> tuple[list, list]:
    """Return (text_rows_for_extract, image_rows_for_native_vision)."""
    text_rows: list = []
    image_rows: list = []
    for row in rows:
        filename = str(getattr(row, "filename", "") or "")
        mime_type = str(getattr(row, "mime_type", "") or "")
        if is_unify_lite_image(filename=filename, mime_type=mime_type):
            image_rows.append(row)
        elif is_unify_lite_text(filename=filename, mime_type=mime_type):
            text_rows.append(row)
        else:
            raise ValueError(
                f"Unsupported unify-lite attachment: {filename}. "
                "Supported: .txt, .md, .docx, and images (PNG/JPEG/GIF/WebP)."
            )
    return text_rows, image_rows
