from __future__ import annotations

import json
from pathlib import Path

import pytest

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store, reset_job_store
from parse_pipeline.orchestrator.runner import JobRunner
from parse_pipeline.schemas.job import JobStatus
from parse_pipeline.schemas.stages import StageId, StageStatus

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_text_standard_pipeline_file_storage(tmp_path: Path) -> None:
    reset_job_store()
    source_file = FIXTURES / "sample.md"
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()

    storage_spec = {
        "read": {
            "url": source_file.as_uri(),
            "method": "GET",
            "filename": "sample.md",
            "content_type": "text/markdown",
        },
        "write": {
            "content_md": {
                "url": (out_dir / "content.md").as_uri(),
                "method": "PUT",
                "content_type": "text/markdown; charset=utf-8",
            },
            "meta_json": {
                "url": (out_dir / "meta.json").as_uri(),
                "method": "PUT",
                "content_type": "application/json",
            },
            "pageindex_json": None,
        },
    }

    store = get_job_store()
    record = JobRecord(
        job_id="job_test_text",
        caller_id="test",
        pipeline_id="text_standard",
        storage_spec=storage_spec,
        source={"filename": "sample.md", "mime_type": "text/markdown"},
        options={},
        callbacks={},
    )
    await store.create_job(record)

    runner = JobRunner()
    result = await runner.run_job("job_test_text")
    assert result is not None
    assert result.status == JobStatus.SUCCEEDED
    assert result.artifacts.ready is True

    fetch_stage = next(s for s in result.stages if s.stage_id == StageId.FETCH)
    assert fetch_stage.status == StageStatus.SUCCEEDED
    analyze_stage = next(s for s in result.stages if s.stage_id == StageId.ANALYZE)
    assert analyze_stage.status == StageStatus.SKIPPED
    parse_submit = next(s for s in result.stages if s.stage_id == StageId.PARSE_SUBMIT)
    assert parse_submit.status == StageStatus.SKIPPED

    content = (out_dir / "content.md").read_text(encoding="utf-8")
    assert "Sample Document" in content
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["parse_engine"] == "local_text"
    assert meta["line_count"] >= 5
