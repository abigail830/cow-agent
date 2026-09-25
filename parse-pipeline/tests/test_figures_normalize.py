from __future__ import annotations

from unittest.mock import MagicMock, patch

from parse_pipeline.normalize.artifacts import normalize_text_artifacts
from parse_pipeline.normalize.finalize import finalize_normalized_artifacts
from parse_pipeline.normalize.figures import _FIGURE_MAX_BYTES, mirror_markdown_figures
from parse_pipeline.normalize.pageindex_pages import build_pages_from_pageindex


_TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def test_mirror_markdown_figures_rewrites_data_uri_png() -> None:
    content = f"Intro\n\n![dot](data:image/png;base64,{_TINY_PNG_BASE64})\n\nDone"
    result = mirror_markdown_figures(content)

    assert "figure:f1" in result.content_md
    assert "base64" not in result.content_md
    assert len(result.figures) == 1
    assert result.figures[0].figure_id == "f1"
    assert result.figures[0].extension == "png"
    assert result.figures[0].mime_type == "image/png"
    assert not result.warnings


def test_mirror_markdown_figures_preserves_relative_paths() -> None:
    content = "See ![local](./img.png) and ![asset](assets/chart.png)"
    result = mirror_markdown_figures(content)

    assert result.content_md == content
    assert result.figures == ()
    assert not result.warnings


def test_mirror_markdown_figures_warns_on_oversized_data_uri() -> None:
    oversized = "A" * ((_FIGURE_MAX_BYTES // 3) * 4 + 4)
    content = f"![big](data:image/png;base64,{oversized})"
    result = mirror_markdown_figures(content)

    assert "figure:f1" not in result.content_md
    assert "base64" in result.content_md
    assert result.figures == ()
    assert any("figure_data_uri_failed" in warning for warning in result.warnings)


def test_mirror_markdown_figures_rewrites_remote_urls() -> None:
    content = "Intro\n\n![chart](https://example.com/a.jpeg)\n\nDone"
    fake_response = MagicMock()
    fake_response.headers = {"content-type": "image/jpeg"}
    fake_response.content = b"fake-image-bytes"
    fake_response.raise_for_status = MagicMock()

    with patch("parse_pipeline.normalize.figures.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = fake_response
        result = mirror_markdown_figures(content)

    assert "figure:f1" in result.content_md
    assert "example.com" not in result.content_md
    assert len(result.figures) == 1
    assert result.figures[0].figure_id == "f1"
    assert result.figures[0].extension == "jpeg"


def test_finalize_applies_pageindex_pages() -> None:
    content = "line1\nline2\nline3\nline4"
    pageindex = {
        "layouts": [
            {"pageNum": 1, "markdownContent": "line1\nline2\n"},
            {"pageNum": 2, "markdownContent": "line3\nline4\n"},
        ]
    }
    artifacts = normalize_text_artifacts(
        content=content,
        job_id="job1",
        pipeline_id="pdf_standard",
        parse_engine="document_mind",
        pageindex=pageindex,
    )
    finalized = finalize_normalized_artifacts(artifacts, mirror_figures=False)
    pages = finalized.meta_json["pages"]
    assert len(pages) == 2
    assert pages[0]["page"] == 1
    assert pages[1]["page"] == 2
    assert pages[0]["line_start"] <= pages[0]["line_end"]
    assert pages[1]["line_start"] <= pages[1]["line_end"]


def test_build_pages_from_pageindex_returns_none_without_page_nums() -> None:
    pageindex = {"layouts": [{"markdownContent": "hello"}]}
    assert build_pages_from_pageindex("hello", pageindex) is None
