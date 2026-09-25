from __future__ import annotations

from pathlib import Path

from parse_pipeline.quality.docx_probe import probe_docx_bytes, probe_docx_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_probe_docx_bytes_reads_page_signals() -> None:
    data = (FIXTURES / "file_explorer_bug_mr.docx").read_bytes()
    probe = probe_docx_bytes(data)
    assert probe.has_legacy_doc is False
    assert probe.paragraph_count > 0
    assert probe.page_count == 2
    assert len(probe.page_break_after_para) >= 1


def test_probe_docx_path_legacy_doc() -> None:
    probe = probe_docx_path(Path("sample.doc"))
    assert probe.has_legacy_doc is True
