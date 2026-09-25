from __future__ import annotations

import io
from typing import Any


def extract_docx_markdown(file_bytes: bytes) -> tuple[str, list[str]]:
    """Convert DOCX bytes to markdown via markitdown (keep_data_uris=True for figure materialize)."""

    from markitdown import MarkItDown

    converter = MarkItDown()
    stream: Any = io.BytesIO(file_bytes)
    result = converter.convert(stream, keep_data_uris=True)
    content = (result.text_content or "").strip()
    if content:
        content += "\n"
    return content, []
