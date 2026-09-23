"""Unit tests for Phase 0 probe fixtures and payload builders (no live API)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts.probe_file_api_phase0.fixtures import (  # noqa: E402
    PROBE_MD_SENTINEL,
    PROBE_PDF_SENTINEL,
    fileid_system_message,
    make_minimal_pdf,
    make_probe_markdown,
    openai_pdf_file_data_part,
    pdf_file_data_url,
)
from scripts.probe_file_api_phase0.http_client import normalize_v1_base  # noqa: E402


def test_probe_markdown_contains_sentinel_and_exceeds_32k_when_long():
    short = make_probe_markdown(long=False).decode("utf-8")
    assert PROBE_MD_SENTINEL in short
    assert len(short) < 32_000

    long_doc = make_probe_markdown(long=True).decode("utf-8")
    assert PROBE_MD_SENTINEL in long_doc
    assert len(long_doc) > 32_000


def test_minimal_pdf_starts_with_header_and_contains_sentinel_bytes():
    pdf = make_minimal_pdf()
    assert pdf.startswith(b"%PDF-")
    assert PROBE_PDF_SENTINEL.encode("ascii") in pdf


def test_openai_pdf_file_data_part_shape():
    pdf = make_minimal_pdf()
    part = openai_pdf_file_data_part(pdf_bytes=pdf, filename="report.pdf")
    assert part["type"] == "file"
    file_obj = part["file"]
    assert file_obj["filename"] == "report.pdf"
    assert file_obj["file_data"].startswith("data:application/pdf;base64,")
    raw = base64.b64decode(file_obj["file_data"].split(",", 1)[1])
    assert raw == pdf


def test_pdf_file_data_url_roundtrip():
    pdf = make_minimal_pdf()
    url = pdf_file_data_url(pdf)
    decoded = base64.b64decode(url.split(",", 1)[1])
    assert decoded == pdf


def test_fileid_system_message_format():
    msg = fileid_system_message("file-fe-abc123")
    assert msg == {"role": "system", "content": "fileid://file-fe-abc123"}


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://dashscope.aliyuncs.com/compatible-mode/v1", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        ("https://api.deepseek.com", "https://api.deepseek.com/v1"),
        ("https://api.deepseek.com/v1/", "https://api.deepseek.com/v1"),
    ],
)
def test_normalize_v1_base(base: str, expected: str):
    assert normalize_v1_base(base) == expected
