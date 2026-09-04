"""Anthropic client with Files API support for user message attachments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import Content, Message
from agent_framework.anthropic import AnthropicClient

FILES_API_BETA = "files-api-2025-04-14"

# MAF session layer passes conversation_id for Azure/OpenAI-style threads; Anthropic Messages API rejects it.
_ANTHROPIC_STRIPPED_OPTIONS = frozenset({"conversation_id"})


def _hosted_file_to_anthropic_block(content: Content) -> dict[str, Any]:
    media = (content.media_type or "").lower()
    if media.startswith("image/"):
        return {
            "type": "image",
            "source": {"type": "file", "file_id": content.file_id},
        }
    return {
        "type": "document",
        "source": {"type": "file", "file_id": content.file_id},
    }


class PlatformAnthropicClient(AnthropicClient):
    """Extends MAF AnthropicClient to map hosted_file inputs for the Files API."""

    def _prepare_options(
        self,
        messages: Sequence[Message],
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        cleaned_options = {
            key: value
            for key, value in options.items()
            if key not in _ANTHROPIC_STRIPPED_OPTIONS
        }
        cleaned_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in _ANTHROPIC_STRIPPED_OPTIONS
        }
        return super()._prepare_options(messages, cleaned_options, **cleaned_kwargs)

    def _prepare_message_for_anthropic(self, message: Message) -> dict[str, Any]:
        contents = message.contents or []
        if not any(content.type == "hosted_file" for content in contents):
            return super()._prepare_message_for_anthropic(message)

        a_content: list[dict[str, Any]] = []
        for content in contents:
            if content.type == "hosted_file":
                a_content.append(_hosted_file_to_anthropic_block(content))
                continue
            sub = Message(role=message.role, contents=[content])
            sub_result = super()._prepare_message_for_anthropic(sub)
            sub_blocks = sub_result.get("content")
            if isinstance(sub_blocks, list):
                a_content.extend(sub_blocks)
            elif sub_blocks:
                a_content.append(sub_blocks)

        from agent_framework_anthropic._chat_client import ROLE_MAP

        return {
            "role": ROLE_MAP.get(message.role, "user"),
            "content": a_content,
        }
