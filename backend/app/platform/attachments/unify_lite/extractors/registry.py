from __future__ import annotations

import time

from app.platform.attachments.unify_lite.extractors.docx import extract_docx_bytes
from app.platform.attachments.unify_lite.extractors.text import extract_text_bytes
from app.platform.attachments.unify_lite.validation import is_unify_lite_file, unify_lite_extension


def extract_bytes(*, filename: str, mime_type: str, data: bytes) -> tuple[str, list[str], int]:
    if not is_unify_lite_file(filename=filename, mime_type=mime_type):
        raise ValueError(
            f"Unsupported file for unify-lite extraction: {filename}. "
            "Supported: .txt, .md, .docx"
        )

    started = time.perf_counter()
    ext = unify_lite_extension(filename)
    if ext == ".docx":
        content, warnings = extract_docx_bytes(data)
    else:
        content, warnings = extract_text_bytes(data)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return content, warnings, elapsed_ms
