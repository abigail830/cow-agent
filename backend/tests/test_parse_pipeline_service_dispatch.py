from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.platform.parse_pipeline.dispatcher_service import dispatch_service


@pytest.mark.asyncio
async def test_dispatch_service_posts_platform_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARSE_PIPELINE_SERVICE_URL", "http://127.0.0.1:8091")
    monkeypatch.setenv("PARSE_PIPELINE_SERVICE_API_KEY", "test_key")
    monkeypatch.setenv("PARSE_PIPELINE_SERVICE_CALLER_ID", "agent-platform")

    captured: dict = {}

    class FakeResponse:
        status_code = 202

        @staticmethod
        def json() -> dict:
            return {"job_id": "job_platform123", "status": "queued"}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, json: dict, headers: dict):  # noqa: A002
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(
        "app.platform.parse_pipeline.dispatcher_service.httpx.AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    payload = {
        "schema_version": "1.0",
        "job_id": "job_platform123",
        "pipeline_id": "office_standard",
        "storage": {"read": {"url": "http://example/original"}},
        "source": {"source_id": "abc"},
        "options": {},
        "callbacks": {"webhook_url": "http://127.0.0.1:8000/internal/parse/v1/webhook"},
    }
    job_id = await dispatch_service(payload=payload)
    assert job_id == "job_platform123"
    assert captured["url"] == "http://127.0.0.1:8091/v1/jobs"
    assert captured["json"]["job_id"] == "job_platform123"
    assert captured["headers"]["Authorization"] == "Bearer test_key"
