from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.schemas.job import JobCallbacks, JobStatus
from parse_pipeline.webhooks import sender


def _record_with_webhook() -> JobRecord:
    record = JobRecord(
        job_id="job_test",
        caller_id="gha",
        pipeline_id="text_standard",
        storage_spec={},
        source={},
        options={},
        callbacks=JobCallbacks(
            webhook_url="https://example.test/internal/parse/v1/webhook",
            webhook_secret="whsec_test",
            events=["job.failed"],
        ).model_dump(),
    )
    record.status = JobStatus.RUNNING
    return record


@pytest.mark.asyncio
async def test_webhook_retries_once_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_MAX_RETRIES", "1")
    sender.get_settings.cache_clear()

    calls = {"count": 0}

    async def fake_post(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("network")
        response = MagicMock()
        response.status_code = 204
        response.raise_for_status = MagicMock()
        return response

    client = AsyncMock()
    client.post = fake_post
    client_cm = AsyncMock()
    client_cm.__aenter__.return_value = client

    with patch("parse_pipeline.webhooks.sender.httpx.AsyncClient", return_value=client_cm):
        await sender.emit_job_failed(_record_with_webhook())

    assert calls["count"] == 2
