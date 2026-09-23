from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from parse_pipeline.providers.document_mind.client import (
    DEFAULT_OUTPUT_FORMATS,
    DM_OUTPUT_MARKDOWN,
    DM_OUTPUT_VISUAL_LAYOUT,
    DocumentMindClient,
    DocumentMindConfig,
)


def _client() -> DocumentMindClient:
    config = DocumentMindConfig(
        access_key_id="id",
        access_key_secret="secret",
        endpoint="docmind-api.cn-hangzhou.aliyuncs.com",
        output_formats=list(DEFAULT_OUTPUT_FORMATS),
    )
    client = DocumentMindClient(config)
    client._client = MagicMock()
    return client


def test_submit_passes_output_format_to_sdk() -> None:
    client = _client()
    mock_response = MagicMock()
    mock_response.body.data.id = "docmind-test-123"
    client._client.submit_doc_parser_job_advance.return_value = mock_response

    captured: dict = {}

    def _capture(request, runtime):
        captured["request"] = request
        captured["runtime"] = runtime
        return mock_response

    client._client.submit_doc_parser_job_advance.side_effect = _capture

    task_id = client.submit(
        b"%PDF-1.4",
        "sample.pdf",
        output_formats=[DM_OUTPUT_MARKDOWN, DM_OUTPUT_VISUAL_LAYOUT],
    )
    assert task_id == "docmind-test-123"
    assert captured["request"].to_map()["OutputFormat"] == [
        DM_OUTPUT_MARKDOWN,
        DM_OUTPUT_VISUAL_LAYOUT,
    ]


@pytest.mark.asyncio
async def test_poll_until_done_emits_on_each_query() -> None:
    client = _client()
    calls: list[dict] = []

    async def on_poll(status_data: dict) -> None:
        calls.append(dict(status_data))

    statuses = [
        {"Status": "processing", "NumberOfSuccessfulParsing": 1},
        {"Status": "processing", "NumberOfSuccessfulParsing": 3},
        {"Status": "success"},
    ]

    def fake_query(_task_id: str) -> dict:
        return statuses.pop(0)

    client.query_status = fake_query  # type: ignore[method-assign]
    client._config.poll_interval_sec = 0

    await client.poll_until_done("docmind-test", on_poll=on_poll)
    assert len(calls) == 3
    assert calls[0]["NumberOfSuccessfulParsing"] == 1
    assert calls[-1]["Status"] == "success"
