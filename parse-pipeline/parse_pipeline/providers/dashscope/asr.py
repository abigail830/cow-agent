"""DashScope async ASR (qwen3-asr-flash-filetrans / fun-asr)."""

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


class DashScopeAsrClient:
    def __init__(
        self,
        *,
        api_key: str,
        provider: str,
        fallback_provider: str | None = None,
        poll_interval_sec: float = 5.0,
        poll_timeout_sec: float = 7200.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.provider = provider.strip()
        self.fallback_provider = (fallback_provider or "").strip() or None
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec

    async def transcribe_file_url(
        self,
        *,
        file_url: str,
        context_text: str | None = None,
        on_poll: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> tuple[str, str]:
        task_id, provider_used = await self._submit(file_url=file_url, context_text=context_text)
        result = await self._poll_until_done(task_id, on_poll=on_poll)
        text = _extract_transcript_text(result)
        if not text.strip():
            raise RuntimeError("ASR returned empty transcript")
        return text.strip(), provider_used

    async def _submit(self, *, file_url: str, context_text: str | None) -> tuple[str, str]:
        last_error: Exception | None = None
        for model in [self.provider, self.fallback_provider]:
            if not model:
                continue
            try:
                task_id = await self._submit_model(model=model, file_url=file_url, context_text=context_text)
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
    ) -> str:
        parameters: dict[str, Any] = {}
        if context_text:
            parameters["vocabulary_id"] = None
            parameters["corpus_text"] = context_text
        body = {
            "model": model,
            "input": {"file_urls": [file_url]},
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
        on_poll: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout_sec
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = _DASHSCOPE_TASK_URL.format(task_id=task_id)
        async with httpx.AsyncClient(timeout=60.0) as client:
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


def _extract_transcript_text(payload: dict[str, Any]) -> str:
    output = payload.get("output") or {}
    results = output.get("results") or output.get("transcription") or output.get("text")
    if isinstance(results, str):
        return results
    if isinstance(results, list):
        chunks: list[str] = []
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
