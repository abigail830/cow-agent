"""Synthetic fixtures and payload builders for file API probes."""

from __future__ import annotations

import base64
from dataclasses import dataclass

PROBE_MD_SENTINEL = "PROBE_MD_SENTINEL_7f3a9c2b"
PROBE_PDF_SENTINEL = "PROBE_PDF_SENTINEL_9e4d1f80"
PROBE_LONG_TAIL = "LONG_CONTEXT_MARKER_" + ("x" * 40000)


def make_probe_markdown(*, long: bool = False) -> bytes:
    """Markdown with a unique sentinel; optional tail to exceed 32k inline cap."""
    body = f"# Probe Document\n\nUnique token: {PROBE_MD_SENTINEL}\n\nAnswer must quote the token exactly.\n"
    if long:
        body += f"\n## Tail section\n\n{PROBE_LONG_TAIL}\n"
    return body.encode("utf-8")


def make_minimal_pdf(*, text: str = PROBE_PDF_SENTINEL) -> bytes:
    """Minimal valid PDF with embedded text (no external deps)."""
    # Escape parens for PDF string literal
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET"
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        ),
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream\nendobj\n".encode(),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    header = b"%PDF-1.4\n"
    body = b"".join(objects)
    xref_offset = len(header) + len(body)
    xref = (
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000370 00000 n \n"
    )
    trailer = f"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    return header + body + xref + trailer


def make_tiny_png() -> bytes:
    """1x1 red PNG."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def pdf_file_data_url(pdf_bytes: bytes) -> str:
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{encoded}"


@dataclass(frozen=True)
class OpenAIFilePart:
    """OpenAI-compatible file part for PDF (official qwen3.8 format)."""

    file_data: str
    filename: str

    def to_message_part(self) -> dict:
        return {
            "type": "file",
            "file": {
                "file_data": self.file_data,
                "filename": self.filename,
            },
        }


def openai_pdf_file_data_part(*, pdf_bytes: bytes, filename: str = "probe.pdf") -> dict:
    return OpenAIFilePart(
        file_data=pdf_file_data_url(pdf_bytes),
        filename=filename,
    ).to_message_part()


def maf_style_data_content_fields(*, pdf_bytes: bytes) -> dict:
    """What materialize.py currently emits via Content.from_data (for contrast)."""
    return {
        "type": "data",
        "media_type": "application/pdf",
        "data": pdf_bytes,
    }


def fileid_system_message(file_id: str) -> dict:
    return {"role": "system", "content": f"fileid://{file_id}"}
