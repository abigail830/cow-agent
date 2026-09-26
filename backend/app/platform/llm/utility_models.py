from __future__ import annotations

import asyncio
import logging
from enum import Enum

from agent_framework import Agent
from agent_framework.exceptions import ChatClientException
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
from httpx import ConnectError as HttpxConnectError
from openai import APIConnectionError

from app.config import Settings, get_settings
from app.platform.llm.model_registry import _azure_responses_base_url, _openai_compatible_base_url

logger = logging.getLogger(__name__)

_UTILITY_COMPLETE_RETRIES = 3
_UTILITY_RETRY_BASE_SEC = 0.6


class UtilityPurpose(str, Enum):
    CHAT_TITLE = "chat_title"
    HISTORY_COMPACTION = "history_compaction"
    ATTACHMENT_GIST = "attachment_gist"


def _uses_azure_responses_api(base_url: str) -> bool:
    normalized = base_url.rstrip("/").lower()
    return "cognitiveservices.azure.com" in normalized or ".openai.azure.com" in normalized


def _is_transient_utility_error(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, HttpxConnectError)):
        return True
    if isinstance(exc, ChatClientException):
        cause = exc.__cause__
        if isinstance(cause, (APIConnectionError, HttpxConnectError)):
            return True
        message = str(exc).lower()
        return "connection error" in message
    return False


class UtilityModelRegistry:
    """Platform utility LLM — isolated from user agent sessions."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_client(
        self,
        purpose: UtilityPurpose | None = None,
    ) -> OpenAIChatClient | OpenAIChatCompletionClient:
        if purpose == UtilityPurpose.ATTACHMENT_GIST:
            api_key = self._settings.attachment_gist_api_key()
            if not api_key:
                raise RuntimeError("ATTACHMENT_GIST requires DASHSCOPE_API_KEY or ATTACHMENT_GIST_MODEL_API_KEY")
            base_url = self._settings.attachment_gist_base_url()
            model = self._settings.attachment_gist_model_name()
            return OpenAIChatCompletionClient(
                model=model,
                api_key=api_key,
                base_url=_openai_compatible_base_url(base_url),
            )

        s = self._settings
        base_url = s.utility_base_url()
        if _uses_azure_responses_api(base_url):
            return OpenAIChatClient(
                model=s.utility_deployment(),
                api_key=s.utility_api_key(),
                base_url=_azure_responses_base_url(base_url),
                api_version=s.utility_api_version(),
            )
        return OpenAIChatCompletionClient(
            model=s.utility_deployment(),
            api_key=s.utility_api_key(),
            base_url=_openai_compatible_base_url(base_url),
        )

    def _instructions_for(self, purpose: UtilityPurpose) -> str:
        if purpose == UtilityPurpose.CHAT_TITLE:
            from app.platform.chat.title_prompt import CHAT_TITLE_SYSTEM_INSTRUCTIONS

            return CHAT_TITLE_SYSTEM_INSTRUCTIONS
        if purpose == UtilityPurpose.ATTACHMENT_GIST:
            from app.platform.attachments.gist.prompt import GIST_SYSTEM_INSTRUCTIONS

            return GIST_SYSTEM_INSTRUCTIONS
        return (
            "Summarize the conversation history concisely. Preserve key facts, decisions, and tool outcomes. "
            "Omit reasoning traces. Reply with summary text only."
        )

    async def _complete_openai_chat_direct(
        self,
        *,
        purpose: str,
        api_key: str,
        base_url: str,
        model: str,
        prompt: str,
        max_tokens: int,
        instructions: str,
        temperature: float | None,
    ) -> str:
        """Direct Chat Completions (no Agent.run); DashScope gets enable_thinking=false."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        kwargs: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if "dashscope" in base_url.lower():
            kwargs["extra_body"] = {"enable_thinking": False}

        last_exc: BaseException | None = None
        for attempt in range(_UTILITY_COMPLETE_RETRIES):
            try:
                response = await client.chat.completions.create(**kwargs)
                if not response.choices:
                    return ""
                message = response.choices[0].message
                content = (message.content or "").strip()
                if content:
                    return content
                extra = getattr(message, "model_extra", None) or {}
                reasoning = extra.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning.strip():
                    logger.warning(
                        "utility LLM returned reasoning only purpose=%s finish=%s",
                        purpose,
                        response.choices[0].finish_reason,
                    )
                return ""
            except Exception as exc:
                if not _is_transient_utility_error(exc) or attempt >= _UTILITY_COMPLETE_RETRIES - 1:
                    raise
                last_exc = exc
                delay = _UTILITY_RETRY_BASE_SEC * (2**attempt)
                logger.warning(
                    "utility LLM transient error purpose=%s attempt=%s/%s retry_in=%.1fs: %s",
                    purpose,
                    attempt + 1,
                    _UTILITY_COMPLETE_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        if last_exc is not None:
            raise last_exc
        return ""

    async def _complete_attachment_gist(
        self,
        *,
        prompt: str,
        max_tokens: int,
        instructions: str,
        temperature: float | None,
    ) -> str:
        api_key = self._settings.attachment_gist_api_key()
        if not api_key:
            raise RuntimeError("ATTACHMENT_GIST requires DASHSCOPE_API_KEY or ATTACHMENT_GIST_MODEL_API_KEY")
        return await self._complete_openai_chat_direct(
            purpose=UtilityPurpose.ATTACHMENT_GIST.value,
            api_key=api_key,
            base_url=self._settings.attachment_gist_base_url(),
            model=self._settings.attachment_gist_model_name(),
            prompt=prompt,
            max_tokens=max_tokens,
            instructions=instructions,
            temperature=temperature,
        )

    async def complete(
        self,
        purpose: UtilityPurpose,
        *,
        prompt: str,
        max_tokens: int = 256,
        instructions: str | None = None,
        temperature: float | None = None,
    ) -> str:
        system = instructions if instructions is not None else self._instructions_for(purpose)
        if purpose == UtilityPurpose.ATTACHMENT_GIST:
            return await self._complete_attachment_gist(
                prompt=prompt,
                max_tokens=max_tokens,
                instructions=system,
                temperature=temperature,
            )

        if purpose == UtilityPurpose.CHAT_TITLE:
            base_url = self._settings.utility_base_url()
            if not _uses_azure_responses_api(base_url):
                return await self._complete_openai_chat_direct(
                    purpose=UtilityPurpose.CHAT_TITLE.value,
                    api_key=self._settings.utility_api_key(),
                    base_url=base_url,
                    model=self._settings.utility_deployment(),
                    prompt=prompt,
                    max_tokens=max_tokens,
                    instructions=system,
                    temperature=temperature,
                )

        client = self.get_client(purpose)
        options: dict = {"max_tokens": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        agent = Agent(
            client=client,
            name=f"utility-{purpose.value}",
            instructions=system,
            default_options=options,
        )

        last_exc: BaseException | None = None
        for attempt in range(_UTILITY_COMPLETE_RETRIES):
            try:
                result = await agent.run(prompt)
                return (result.text or "").strip()
            except Exception as exc:
                if not _is_transient_utility_error(exc) or attempt >= _UTILITY_COMPLETE_RETRIES - 1:
                    raise
                last_exc = exc
                delay = _UTILITY_RETRY_BASE_SEC * (2**attempt)
                logger.warning(
                    "utility LLM transient error purpose=%s attempt=%s/%s retry_in=%.1fs: %s",
                    purpose.value,
                    attempt + 1,
                    _UTILITY_COMPLETE_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        if last_exc is not None:
            raise last_exc
        return ""

    async def smoke_test(self) -> str:
        return await self.complete(
            UtilityPurpose.CHAT_TITLE,
            prompt="User: What is 2+2?\nAssistant: 4",
            max_tokens=64,
        )
