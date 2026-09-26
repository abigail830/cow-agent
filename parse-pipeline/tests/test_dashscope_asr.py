from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from parse_pipeline.providers.dashscope.asr import (
    DashScopeAsrClient,
    _extract_transcript_text,
    _resolve_transcription_payload,
)


@pytest.mark.asyncio
async def test_submit_qwen_audio_uses_file_urls_and_diarization() -> None:
    client = DashScopeAsrClient(
        api_key="sk-test",
        provider="qwen-audio-3.0-asr-flash-filetrans",
    )
    captured: dict = {}

    async def _fake_post(_url: str, *, json: dict, headers: dict) -> MagicMock:
        captured["json"] = json
        captured["headers"] = headers
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"output": {"task_id": "task-123"}}
        return response

    transcription_payload = {
        "transcripts": [
            {
                "sentences": [
                    {"text": "Hello there.", "speaker_id": 0},
                    {"text": "Hi back.", "speaker_id": 1},
                ]
            }
        ]
    }

    poll_response = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(
            return_value={
                "output": {
                    "task_status": "SUCCEEDED",
                    "results": [{"transcription_url": "https://example.com/result.json"}],
                }
            }
        ),
    )
    transcript_response = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value=transcription_payload),
    )

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(side_effect=_fake_post)
    mock_http.get = AsyncMock(side_effect=[poll_response, transcript_response])

    with patch("parse_pipeline.providers.dashscope.asr.httpx.AsyncClient", return_value=mock_http):
        text, provider = await client.transcribe_file_url(
            file_url="https://example.com/audio.m4a",
            context_text="meeting notes",
            diarization_enabled=True,
            speaker_count=2,
        )

    assert provider == "qwen-audio-3.0-asr-flash-filetrans"
    assert "**Speaker 0:** Hello there." in text
    assert "**Speaker 1:** Hi back." in text
    body = captured["json"]
    assert body["input"]["file_urls"] == ["https://example.com/audio.m4a"]
    assert body["input"]["context"][0]["content"][0]["text"] == "meeting notes"
    assert body["parameters"]["diarization_enabled"] is True
    assert body["parameters"]["speaker_count"] == 2
    assert captured["headers"]["X-DashScope-Async"] == "enable"


@pytest.mark.asyncio
async def test_resolve_transcription_payload_fetches_result_url() -> None:
    mock_http = AsyncMock()
    mock_http.get.return_value = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={"transcripts": [{"text": "done"}]}),
    )
    payload = await _resolve_transcription_payload(
        mock_http,
        {"output": {"results": [{"transcription_url": "https://example.com/result.json"}]}},
    )
    assert payload["transcripts"][0]["text"] == "done"


@pytest.mark.asyncio
async def test_submit_falls_back_to_next_model() -> None:
    client = DashScopeAsrClient(
        api_key="sk-test",
        provider="qwen-audio-3.1-asr-flash-filetrans",
        fallback_providers=["qwen-audio-3.0-asr-flash-filetrans", "fun-asr"],
    )
    attempts: list[str] = []

    async def _fake_post(_url: str, *, json: dict, headers: dict) -> MagicMock:
        attempts.append(str(json["model"]))
        response = MagicMock()
        response.raise_for_status = MagicMock()
        if json["model"] == "qwen-audio-3.1-asr-flash-filetrans":
            raise RuntimeError("model unavailable")
        response.json.return_value = {"output": {"task_id": "task-456"}}
        return response

    poll_response = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(
            return_value={
                "output": {
                    "task_status": "SUCCEEDED",
                    "transcripts": [{"sentences": [{"text": "fallback ok"}]}],
                }
            }
        ),
    )

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(side_effect=_fake_post)
    mock_http.get = AsyncMock(return_value=poll_response)

    with patch("parse_pipeline.providers.dashscope.asr.httpx.AsyncClient", return_value=mock_http):
        text, provider = await client.transcribe_file_url(file_url="https://example.com/audio.m4a")

    assert attempts == [
        "qwen-audio-3.1-asr-flash-filetrans",
        "qwen-audio-3.0-asr-flash-filetrans",
    ]
    assert provider == "qwen-audio-3.0-asr-flash-filetrans"
    assert text == "fallback ok"


def test_extract_transcript_text_formats_speaker_labels() -> None:
    text = _extract_transcript_text(
        {
            "transcripts": [
                {
                    "sentences": [
                        {"text": "First line.", "speaker_id": 0},
                        {"text": "Second line.", "speaker_id": 1},
                    ]
                }
            ]
        }
    )
    assert text == "**Speaker 0:** First line.\n\n**Speaker 1:** Second line."
