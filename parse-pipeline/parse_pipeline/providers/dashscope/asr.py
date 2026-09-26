"""DashScope async ASR (qwen-audio-3.x-asr-flash-filetrans / fun-asr)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

_DASHSCOPE_SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
_DASHSCOPE_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"


@dataclass(frozen=True)
class AsrTranscriptPart:
    attachment_id: str
    filename: str
    sort_order: int
    text: str
    provider_id: str
    external_job_id: str


def _uses_file_urls(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith("fun-asr") or normalized.startswith("qwen-audio-3")


class DashScopeAsrClient:
    def __init__(
        self,
        *,
        api_key: str,
        provider: str,
        fallback_providers: list[str] | None = None,
        poll_interval_sec: float = 5.0,
        poll_timeout_sec: float = 7200.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.provider = provider.strip()
        self.fallback_providers = [item.strip() for item in (fallback_providers or []) if item.strip()]
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec

    def _model_chain(self) -> list[str]:
        chain: list[str] = []
        seen: set[str] = set()
        for model in [self.provider, *self.fallback_providers]:
            if model and model not in seen:
                seen.add(model)
                chain.append(model)
        return chain

    async def transcribe_file_url(
        self,
        *,
        file_url: str,
        context_text: str | None = None,
        diarization_enabled: bool = False,
        speaker_count: int | None = None,
        on_poll: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> tuple[str, str]:
        task_id, provider_used = await self._submit(
            file_url=file_url,
            context_text=context_text,
            diarization_enabled=diarization_enabled,
            speaker_count=speaker_count,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            poll_data = await self._poll_until_done(task_id, client=client, on_poll=on_poll)
            payload = await _resolve_transcription_payload(client, poll_data)
        text = _extract_transcript_text(payload)
        if not text.strip():
            raise RuntimeError("ASR returned empty transcript")
        return text.strip(), provider_used

    async def _submit(
        self,
        *,
        file_url: str,
        context_text: str | None,
        diarization_enabled: bool,
        speaker_count: int | None,
    ) -> tuple[str, str]:
        last_error: Exception | None = None
        for model in self._model_chain():
            try:
                task_id = await self._submit_model(
                    model=model,
                    file_url=file_url,
                    context_text=context_text,
                    diarization_enabled=diarization_enabled,
                    speaker_count=speaker_count,
                )
                return task_id, model
            except Exception as exc:
                last_error = exc
                logger.warning("ASR submit failed model=%s: %s", model, exc)
        raise RuntimeError(f"ASR submit failed: {last_error}")

    async def _submit_model(
        self,
        *,
        model: str,
        file_url: str,
        context_text: str | None,
        diarization_enabled: bool,
        speaker_count: int | None,
    ) -> str:
        parameters: dict[str, Any] = {"channel_id": [0]}
        if diarization_enabled:
            parameters["diarization_enabled"] = True
            if speaker_count is not None:
                parameters["speaker_count"] = int(speaker_count)

        input_body: dict[str, Any]
        if _uses_file_urls(model):
            input_body = {"file_urls": [file_url]}
            if context_text:
                input_body["context"] = [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": context_text[:400]}],
                    }
                ]
        else:
            input_body = {"file_url": file_url}
            if context_text:
                parameters["corpus"] = {"text": context_text}

        body = {
            "model": model,
            "input": input_body,
            "parameters": parameters,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(_DASHSCOPE_SUBMIT_URL, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
        output = data.get("output") or {}
        task_id = output.get("task_id") or data.get("task_id")
        if not task_id:
            raise RuntimeError(f"ASR submit missing task_id: {data}")
        return str(task_id)

    async def _poll_until_done(
        self,
        task_id: str,
        *,
        client: httpx.AsyncClient,
        on_poll: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout_sec
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = _DASHSCOPE_TASK_URL.format(task_id=task_id)
        while time.monotonic() < deadline:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if on_poll is not None:
                await on_poll(data)
            status = str((data.get("output") or {}).get("task_status") or data.get("task_status") or "").upper()
            if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
                return data
            if status in {"FAILED", "CANCELED", "CANCELLED"}:
                message = (data.get("output") or {}).get("message") or data.get("message") or status
                raise RuntimeError(f"ASR task failed: {message}")
            await asyncio.sleep(self.poll_interval_sec)
        raise TimeoutError(f"ASR task timed out: {task_id}")


async def _resolve_transcription_payload(client: httpx.AsyncClient, poll_data: dict[str, Any]) -> dict[str, Any]:
    output = poll_data.get("output") or {}
    if output.get("transcripts"):
        return output

    results = output.get("results") or []
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("transcripts"):
            return item
        transcription_url = item.get("transcription_url")
        if transcription_url:
            response = await client.get(str(transcription_url))
            response.raise_for_status()
            return response.json()

    return output


def _format_sentences(sentences: list[Any]) -> str:
    lines: list[str] = []
    for sentence in sentences:
        if not isinstance(sentence, dict):
            continue
        text = str(sentence.get("text") or "").strip()
        if not text:
            continue
        speaker_id = sentence.get("speaker_id")
        if speaker_id is not None:
            lines.append(f"**Speaker {speaker_id}:** {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _extract_transcript_text(payload: dict[str, Any]) -> str:
    transcripts = payload.get("transcripts")
    if isinstance(transcripts, list) and transcripts:
        chunks: list[str] = []
        for transcript in transcripts:
            if not isinstance(transcript, dict):
                continue
            sentences = transcript.get("sentences")
            if isinstance(sentences, list) and sentences:
                formatted = _format_sentences(sentences)
                if formatted:
                    chunks.append(formatted)
                    continue
            text = str(transcript.get("text") or "").strip()
            if text:
                chunks.append(text)
        if chunks:
            return "\n\n".join(chunks)

    output = payload.get("output") or payload
    results = output.get("results") or output.get("transcription") or output.get("text")
    if isinstance(results, str):
        return results
    if isinstance(results, list):
        chunks = []
        for item in results:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("transcription") or item.get("sentence")
                if text:
                    chunks.append(str(text))
        if chunks:
            return "\n".join(chunks)

    choices = output.get("choices") or []
    for choice in choices:
        if isinstance(choice, dict):
            message = choice.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
    return str(output.get("text") or "")


def merge_transcript_markdown(
    *,
    title: str,
    parts: list[AsrTranscriptPart],
) -> str:
    lines = [f"# {title}", ""]
    for index, part in enumerate(parts, start=1):
        if len(parts) > 1:
            lines.extend([f"## Part {index}: {part.filename}", ""])
        lines.append(part.text.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"
