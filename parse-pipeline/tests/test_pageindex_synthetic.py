from __future__ import annotations

from pathlib import Path

from parse_pipeline.normalize.finalize import finalize_office_markitdown_artifacts
from parse_pipeline.normalize.artifacts import normalize_text_artifacts
from parse_pipeline.normalize.pageindex_synthetic import build_pageindex_from_markdown
from parse_pipeline.quality.docx_probe import probe_docx_bytes, probe_docx_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_pageindex_from_fixture_docx() -> None:
    path = FIXTURES / "file_explorer_bug_mr.docx"
    file_bytes = path.read_bytes()
    probe = probe_docx_path(path)
    from parse_pipeline.providers.local.markitdown_office import extract_docx_markdown

    content, _ = extract_docx_markdown(file_bytes)
    result = build_pageindex_from_markdown(content, probe, file_bytes=file_bytes)
    assert result is not None
    layouts = result.pageindex["layouts"]
    assert len(layouts) >= 1
    assert result.pageindex["source"] == "markitdown_ooxml_pages"
    assert all("pageNum" in layout for layout in layouts)


def test_finalize_office_applies_synthetic_pages() -> None:
    path = FIXTURES / "file_explorer_bug_mr.docx"
    file_bytes = path.read_bytes()
    probe = probe_docx_bytes(file_bytes)
    from parse_pipeline.providers.local.markitdown_office import extract_docx_markdown

    content, _ = extract_docx_markdown(file_bytes)
    artifacts = normalize_text_artifacts(
        content=content,
        job_id="job1",
        pipeline_id="office_standard",
        parse_engine="markitdown",
        provider_id="markitdown",
    )
    artifacts.docx_probe = probe
    artifacts.office_source_bytes = file_bytes
    finalized = finalize_office_markitdown_artifacts(artifacts)
    assert finalized.pageindex_json is not None
    assert finalized.meta_json.get("pageindex_path") == "pageindex.json"
    pages = finalized.meta_json.get("pages") or []
    assert len(pages) >= 1


def test_degraded_when_anchors_missing() -> None:
    probe = probe_docx_bytes((FIXTURES / "file_explorer_bug_mr.docx").read_bytes())
    content = "totally unrelated content\n" * 5
    result = build_pageindex_from_markdown(content, probe, file_bytes=b"")
    assert result is not None
    assert "pageindex_alignment_degraded" in result.warnings
