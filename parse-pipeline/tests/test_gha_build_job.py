from __future__ import annotations

import json
from pathlib import Path

from parse_pipeline.gha.build_job import build_job_payload


def test_build_job_from_repo_path(tmp_path: Path) -> None:
    src = tmp_path / "in.md"
    src.write_text("# hi", encoding="utf-8")
    out = tmp_path / "out"
    payload = build_job_payload(
        pipeline_id="text_standard",
        source_path=src,
        out_dir=out,
    )
    assert payload["pipeline_id"] == "text_standard"
    assert payload["storage"]["read"]["filename"] == "in.md"
    assert "content.md" in payload["storage"]["write"]["content_md"]["url"]


def test_build_job_from_url() -> None:
    payload = build_job_payload(
        pipeline_id="pdf_standard",
        source_url="https://example.com/a.pdf",
        out_dir=Path("/tmp/out"),
        filename="a.pdf",
    )
    assert payload["storage"]["read"]["url"] == "https://example.com/a.pdf"
