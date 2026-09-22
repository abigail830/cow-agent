"""OpenAI Chat Completions client for domestic / thinking-mode LLMs (DeepSeek, Qwen, …)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import ChatResponse, ChatResponseUpdate, Content, Message
from agent_framework.openai import OpenAIChatCompletionClient
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.platform.llm.openai_image_payload import sanitize_openai_image_payloads
from app.platform.llm.reasoning_content_mixin import (
    ReasoningContentMixin,
    coalesce_reasoning_tool_messages,
    reasoning_content_from,
)


def _merge_multimodal_user_openai_messages(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge MAF's per-content user dicts into one OpenAI multimodal message."""
    if len(items) == 1:
        return items[0]
    role = str(items[0].get("role") or "user")
    parts: list[Any] = []
    reasoning_details: Any | None = None
    for item in items:
        if reasoning_details is None and item.get("reasoning_details") is not None:
            reasoning_details = item["reasoning_details"]
        body = item.get("content")
        if isinstance(body, str):
            if body:
                parts.append({"type": "text", "text": body})
        elif isinstance(body, list):
            parts.extend(body)
        elif body is not None:
            parts.append(body)
    merged: dict[str, Any] = {"role": role, "content": parts if parts else ""}
    if reasoning_details is not None:
        merged["reasoning_details"] = reasoning_details
    return merged


class OpenAICompatibleReasoningClient(ReasoningContentMixin, OpenAIChatCompletionClient):
    """Chat Completions client with ``reasoning_content`` round-trip.

    Extends MAF's OpenAIChatCompletionClient (which handles ``reasoning_details``)
    for providers that use the OpenAI-compatible ``reasoning_content`` field:
    DeepSeek thinking mode, Qwen 3.7+/3.8 Max (DashScope), Kimi, etc.
    """

    def _parse_response_from_openai(self, response: ChatCompletion, options: Mapping[str, Any]) -> ChatResponse:
        chat_response = super()._parse_response_from_openai(response, options)
        return self._extract_reasoning_from_response(response, chat_response)

    def _parse_response_update_from_openai(self, chunk: ChatCompletionChunk) -> ChatResponseUpdate:
        update = super()._parse_response_update_from_openai(chunk)
        return self._extract_reasoning_from_update(chunk, update)

    def _finalize_response_updates(
        self,
        updates: Sequence[ChatResponseUpdate],
        *,
        response_format: Any | None = None,
    ) -> ChatResponse[Any]:
        response = super()._finalize_response_updates(updates, response_format=response_format)
        return self._normalize_assistant_reasoning(response)

    def _parse_text_from_openai(self, choice: Any) -> Content | None:
        """Drop thinking duplicated into ``content`` when ``reasoning_content`` is present."""
        message = choice.message if hasattr(choice, "message") and choice.message is not None else choice.delta
        text_content = super()._parse_text_from_openai(choice)
        if text_content is None:
            return None

        reasoning = reasoning_content_from(message)
        text = (text_content.text or "").strip()
        if not text:
            return text_content

        if reasoning:
            reasoning = reasoning.strip()
            if text == reasoning or text in reasoning or reasoning in text:
                return None

        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            return None

        return text_content

    def _prepare_message_for_openai(self, message: Message) -> list[dict[str, Any]]:
        filtered, reasoning = self._extract_reasoning_from_message(message)
        hosted_files = [
            content
            for content in (filtered.contents or [])
            if getattr(content, "type", None) == "hosted_file" and getattr(content, "file_id", None)
        ]
        if hosted_files:
            stripped = Message(
                filtered.role,
                [
                    content
                    for content in (filtered.contents or [])
                    if getattr(content, "type", None) != "hosted_file"
                ],
                author_name=filtered.author_name,
                additional_properties=filtered.additional_properties,
            )
            prepared = super()._prepare_message_for_openai(stripped)
        else:
            prepared = super()._prepare_message_for_openai(filtered)

        if message.role == "user" and len(prepared) > 1:
            prepared = [_merge_multimodal_user_openai_messages(prepared)]

        self._inject_reasoning_to_openai_message(prepared, reasoning)

        if hosted_files:
            file_parts = [{"type": "file", "file_id": content.file_id} for content in hosted_files]
            for item in prepared:
                if item.get("role") != "user":
                    continue
                body = item.get("content")
                if isinstance(body, list):
                    item["content"] = [*body, *file_parts]
                elif isinstance(body, str) and body:
                    item["content"] = [{"type": "text", "text": body}, *file_parts]
                else:
                    item["content"] = file_parts
                break
            else:
                prepared.append({"role": "user", "content": file_parts})

        return prepared

    def _prepare_messages_for_openai(
        self,
        chat_messages: Sequence[Message],
        role_key: str = "role",
        content_key: str = "content",
    ) -> list[dict[str, Any]]:
        del role_key, content_key
        coalesced = coalesce_reasoning_tool_messages(list(chat_messages))
        prepared: list[dict[str, Any]] = []
        for message in coalesced:
            prepared.extend(self._prepare_message_for_openai(message))
        prepared = sanitize_openai_image_payloads(prepared)
        return self._propagate_reasoning_in_messages(prepared)


# Backward-compatible alias (was PlatformDeepSeekClient).
PlatformDeepSeekClient = OpenAICompatibleReasoningClient
