"""DeepSeek Chat Completions client — preserve thinking-mode reasoning_content."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_framework import Content, Message
from agent_framework.openai import OpenAIChatCompletionClient
from openai.types.chat import ChatCompletion, ChatCompletionChunk


def _reasoning_content_from(obj: Any) -> str | None:
    text = getattr(obj, "reasoning_content", None)
    if isinstance(text, str) and text:
        return text
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict):
        nested = extra.get("reasoning_content")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _reasoning_text_from_message(message: Message) -> str:
    parts: list[str] = []
    for content in message.contents or []:
        if getattr(content, "type", None) == "text_reasoning":
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    return "".join(parts)


class PlatformDeepSeekClient(OpenAIChatCompletionClient):
    """MAF Chat Completions client that round-trips DeepSeek `reasoning_content`.

    DeepSeek thinking mode requires the previous assistant `reasoning_content`
    on the next request (including after tool calls). Upstream MAF only maps
    OpenRouter-style `reasoning_details`.
    """

    def _parse_response_from_openai(self, response: ChatCompletion, options: Mapping[str, Any]):
        parsed = super()._parse_response_from_openai(response, options)
        for message, choice in zip(parsed.messages, response.choices):
            reasoning = _reasoning_content_from(choice.message)
            if reasoning:
                message.contents.insert(0, Content.from_text_reasoning(text=reasoning))
        return parsed

    def _parse_response_update_from_openai(self, chunk: ChatCompletionChunk):
        update = super()._parse_response_update_from_openai(chunk)
        for choice in chunk.choices:
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            reasoning = _reasoning_content_from(delta)
            if reasoning:
                update.contents.append(Content.from_text_reasoning(text=reasoning))
        return update

    def _prepare_message_for_openai(self, message: Message) -> list[dict[str, Any]]:
        reasoning_text = _reasoning_text_from_message(message)
        hosted_files = [
            content
            for content in (message.contents or [])
            if getattr(content, "type", None) == "hosted_file" and getattr(content, "file_id", None)
        ]
        if reasoning_text or hosted_files:
            stripped = Message(
                message.role,
                [
                    content
                    for content in (message.contents or [])
                    if getattr(content, "type", None) not in {"text_reasoning", "hosted_file"}
                ],
                author_name=message.author_name,
                additional_properties=message.additional_properties,
            )
            prepared = super()._prepare_message_for_openai(stripped)
        else:
            prepared = super()._prepare_message_for_openai(message)

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

        if not reasoning_text:
            return prepared

        for item in prepared:
            if item.get("role") == "assistant":
                item["reasoning_content"] = reasoning_text
                item.pop("reasoning_details", None)
                return prepared
        prepared.insert(
            0,
            {"role": "assistant", "content": "", "reasoning_content": reasoning_text},
        )
        return prepared
