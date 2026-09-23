from __future__ import annotations

import json
from pathlib import Path

import pytest

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store, reset_job_store
from parse_pipeline.orchestrator.runner import JobRunner
from parse_pipeline.schemas.job import JobStatus

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_sheet_standard_csv(tmp_path: Path) -> None:
    reset_job_store()
    source_file = FIXTURES / "sample.csv"
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()

    storage_spec = {
        "read": {"url": source_file.as_uri(), "filename": "sample.csv"},
        "write": {
            "content_md": {"url": (out_dir / "content.md").as_uri(), "method": "PUT"},
            "meta_json": {"url": (out_dir / "meta.json").as_uri(), "method": "PUT"},
        },
    }
    store = get_job_store()
    await store.create_job(
        JobRecord(
            job_id="job_test_sheet",
            caller_id="test",
            pipeline_id="sheet_standard",
            storage_spec=storage_spec,
            source={"filename": "sample.csv"},
            options={"table_max_rows_per_sheet": 100},
            callbacks={},
        )
    )
    result = await JobRunner().run_job("job_test_sheet")
    assert result is not None
    assert result.status == JobStatus.SUCCEEDED
    content = (out_dir / "content.md").read_text(encoding="utf-8")
    assert "alpha" in content
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["parse_engine"] == "local_sheet"
