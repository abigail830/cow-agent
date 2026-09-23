"""Thin httpx helpers for OpenAI-compatible file + chat APIs."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


def normalize_v1_base(base_url: str) -> str:
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._base = normalize_v1_base(base_url)
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def upload_file(
        self,
        *,
        filename: str,
        data: bytes,
        mime_type: str,
        purpose: str,
    ) -> dict[str, Any]:
        url = f"{self._base}/files"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                headers=self._headers(),
                files={"file": (filename, data, mime_type)},
                data={"purpose": purpose},
            )
        if response.status_code >= 400:
            raise RuntimeError(f"upload {response.status_code}: {response.text[:800]}")
        payload = response.json()
        if not payload.get("id"):
            raise RuntimeError(f"upload missing id: {payload!r}")
        return payload

    async def retrieve_file(self, file_id: str) -> dict[str, Any]:
        url = f"{self._base}/files/{file_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=self._headers())
        if response.status_code >= 400:
            raise RuntimeError(f"retrieve {response.status_code}: {response.text[:800]}")
        return response.json()

    async def wait_file_processed(
        self,
        file_id: str,
        *,
        max_wait_s: float = 120.0,
        poll_interval_s: float = 2.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max_wait_s
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = await self.retrieve_file(file_id)
            status = str(last.get("status") or "").lower()
            if status in {"processed", "active", "ready"}:
                return last
            if status == "error":
                raise RuntimeError(f"file processing error: {last!r}")
            await asyncio.sleep(poll_interval_s)
        raise TimeoutError(f"file not processed within {max_wait_s}s: {last!r}")

    async def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        url = f"{self._base}/chat/completions"
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=self._headers(), json=body)
        if response.status_code >= 400:
            raise RuntimeError(f"chat {response.status_code}: {response.text[:1200]}")
        return response.json()

    @staticmethod
    def assistant_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")
