from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store, reset_job_store
from parse_pipeline.orchestrator.runner import JobRunner
from parse_pipeline.schemas.job import JobStatus

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_office_standard_markitdown_local(tmp_path: Path) -> None:
    reset_job_store()
    source_file = FIXTURES / "file_explorer_bug_mr.docx"
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    storage_spec = {
        "read": {"url": source_file.as_uri(), "filename": "file_explorer_bug_mr.docx"},
        "write": {
            "content_md": {"url": (out_dir / "content.md").as_uri(), "method": "PUT"},
            "meta_json": {"url": (out_dir / "meta.json").as_uri(), "method": "PUT"},
            "pageindex_json": {"url": (out_dir / "pageindex.json").as_uri(), "method": "PUT"},
        },
    }
    store = get_job_store()
    await store.create_job(
        JobRecord(
            job_id="job_test_office",
            caller_id="test",
            pipeline_id="office_standard",
            storage_spec=storage_spec,
            source={"filename": "file_explorer_bug_mr.docx"},
            options={"office": {"markitdown_enabled": True}},
            callbacks={},
        )
    )
    result = await JobRunner().run_job("job_test_office")
    assert result is not None
    assert result.status == JobStatus.SUCCEEDED
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["parse_engine"] == "markitdown"
    assert (out_dir / "pageindex.json").exists()


@pytest.mark.asyncio
async def test_office_gate_fallback_to_document_mind(tmp_path: Path) -> None:
    reset_job_store()
    source_file = FIXTURES / "file_explorer_bug_mr.docx"
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    storage_spec = {
        "read": {"url": source_file.as_uri(), "filename": "file_explorer_bug_mr.docx"},
        "write": {
            "content_md": {"url": (out_dir / "content.md").as_uri(), "method": "PUT"},
            "meta_json": {"url": (out_dir / "meta.json").as_uri(), "method": "PUT"},
        },
    }
    store = get_job_store()
    await store.create_job(
        JobRecord(
            job_id="job_test_office_fb",
            caller_id="test",
            pipeline_id="office_standard",
            storage_spec=storage_spec,
            source={"filename": "file_explorer_bug_mr.docx"},
            options={"office": {"markitdown_enabled": True}},
            callbacks={},
        )
    )

    with patch(
        "parse_pipeline.orchestrator.runner.evaluate_office_markdown",
    ) as mock_gate:
        from parse_pipeline.quality.office_gate import GateDecision, GateGrade, GateResult

        mock_gate.return_value = GateResult(
            decision=GateDecision.FALLBACK,
            grade=GateGrade.POOR,
            parse_score=0.0,
            checks=[],
            signals={},
        )
        with patch.object(JobRunner, "_parse_document_mind") as mock_dm:
            from parse_pipeline.normalize.artifacts import normalize_text_artifacts

            mock_dm.return_value = normalize_text_artifacts(
                content="# fallback\n",
                job_id="job_test_office_fb",
                pipeline_id="office_standard",
                parse_engine="document_mind",
                provider_id="document_mind",
            )
            result = await JobRunner().run_job("job_test_office_fb")

    assert result is not None
    assert result.status == JobStatus.SUCCEEDED
    mock_dm.assert_called_once()
    call_kwargs = mock_dm.call_args.kwargs
    assert call_kwargs["job_options"]["document_mind"]["llm_enhancement"] is False
