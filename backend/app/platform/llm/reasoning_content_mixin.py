"""OpenAI-compatible Chat Completions reasoning_content round-trip.

MAF's OpenAIChatCompletionClient natively maps OpenRouter-style ``reasoning_details``.
DeepSeek, Qwen (DashScope), Kimi, and other domestic models use the Chat Completions
``reasoning_content`` field instead — see:

- https://api-docs.deepseek.com/guides/thinking_mode
- https://docs.qwencloud.com/developer-guides/tool-calling/function-calling
- https://github.com/microsoft/agent-framework/issues/5538

Pattern aligned with agent-framework-ep ReasoningContentMixin (MIT).
"""

from __future__ import annotations

from typing import Any

from agent_framework import ChatResponse, ChatResponseUpdate, Content, Message


def reasoning_content_from(obj: Any) -> str | None:
    text = getattr(obj, "reasoning_content", None)
    if isinstance(text, str) and text:
        return text
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict):
        nested = extra.get("reasoning_content")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _content_is_empty(content: Any) -> bool:
    return content is None or content == "" or content == []


def _message_has_tool_calls(message: Message) -> bool:
    return any(getattr(content, "type", None) == "function_call" for content in message.contents or [])


def _leading_text_as_reasoning(message: Message) -> tuple[list[Content], str | None]:
    """Promote leading plain text on tool-call rows to reasoning (slim demotion path)."""
    if message.role != "assistant" or not _message_has_tool_calls(message):
        return list(message.contents or []), None

    remaining: list[Content] = []
    promoted: str | None = None
    for content in message.contents or []:
        if promoted is None and getattr(content, "type", None) == "text":
            text = (getattr(content, "text", None) or "").strip()
            if text:
                promoted = text
                continue
        remaining.append(content)
    return remaining, promoted


def coalesce_reasoning_tool_messages(messages: list[Message]) -> list[Message]:
    """Merge split reasoning/tool assistant rows before OpenAI request serialization."""
    if not messages:
        return messages
    wrapper = ChatResponse(messages=list(messages))
    return ReasoningContentMixin()._normalize_assistant_reasoning(wrapper).messages


def _set_additional_property(obj: ChatResponse | ChatResponseUpdate, key: str, value: str) -> None:
    if obj.additional_properties is None:
        obj.additional_properties = {}
    obj.additional_properties[key] = value


class ReasoningContentMixin:
    """Parse/replay ``reasoning_content`` for OpenAI-compatible thinking models."""

    def _normalize_assistant_reasoning(self, chat_response: ChatResponse) -> ChatResponse:
        """Coalesce split reasoning/tool assistant rows and attach reasoning for replay.

        MAF ``from_updates`` merges ``reasoning_content`` onto the response, not the
        assistant ``Message``. Per-service-call history reload then replays tool calls
        without reasoning, which DeepSeek/Qwen reject on the next model call.
        """
        if not chat_response.messages:
            return chat_response

        pending: str | None = None
        response_props = chat_response.additional_properties or {}
        orphan = response_props.get("reasoning_content")
        if isinstance(orphan, str) and orphan.strip():
            pending = orphan

        normalized: list[Message] = []

        for msg in chat_response.messages:
            if msg.role != "assistant":
                if pending:
                    normalized.append(
                        Message(
                            role="assistant",
                            contents=[Content.from_text_reasoning(text=pending)],
                            additional_properties={"reasoning_content": pending},
                        )
                    )
                    pending = None
                normalized.append(msg)
                continue

            props = msg.additional_properties or {}
            props_reasoning = props.get("reasoning_content")
            content_reasoning_parts: list[str] = []
            other_contents: list[Content] = []
            for content in msg.contents or []:
                if getattr(content, "type", None) == "text_reasoning":
                    text = getattr(content, "text", None)
                    if text and not getattr(content, "protected_data", None):
                        content_reasoning_parts.append(text)
                        continue
                other_contents.append(content)

            if content_reasoning_parts:
                reasoning = "".join(content_reasoning_parts)
            elif isinstance(props_reasoning, str) and props_reasoning:
                reasoning = props_reasoning
            else:
                reasoning = None
            has_tools = any(getattr(c, "type", None) == "function_call" for c in other_contents)

            if reasoning and not has_tools and not other_contents:
                pending = reasoning if pending is None else pending + reasoning
                continue

            if has_tools and pending:
                if not reasoning:
                    reasoning = pending
                elif pending != reasoning and pending not in reasoning:
                    reasoning = pending + reasoning
                pending = None

            if has_tools and reasoning:
                merged_props = dict(props)
                merged_props["reasoning_content"] = reasoning
                normalized.append(
                    Message(
                        role=msg.role,
                        contents=[Content.from_text_reasoning(text=reasoning), *other_contents],
                        author_name=msg.author_name,
                        additional_properties=merged_props,
                        message_id=msg.message_id,
                    )
                )
                continue

            normalized.append(msg)

        if pending:
            normalized.append(
                Message(
                    role="assistant",
                    contents=[Content.from_text_reasoning(text=pending)],
                    additional_properties={"reasoning_content": pending},
                )
            )

        chat_response.messages = normalized
        return chat_response

    def _extract_reasoning_from_message(self, message: Message) -> tuple[Message, str | None]:
        pending: str | None = None
        filtered_contents: list[Content] = []

        for content in message.contents or []:
            if getattr(content, "type", None) == "text_reasoning":
                text = getattr(content, "text", None)
                protected = getattr(content, "protected_data", None)
                if text and protected is None:
                    pending = text if pending is None else pending + text
                else:
                    filtered_contents.append(content)
            else:
                filtered_contents.append(content)

        if pending is None:
            props = message.additional_properties or {}
            if isinstance(props.get("reasoning_content"), str):
                pending = props["reasoning_content"]

        promoted_contents, promoted_text = _leading_text_as_reasoning(
            Message(
                role=message.role,
                contents=filtered_contents,
                author_name=message.author_name,
                additional_properties=message.additional_properties,
            )
        )
        if promoted_text and (pending is None or (promoted_text not in pending and pending not in promoted_text)):
            pending = promoted_text if pending is None else pending + promoted_text
            filtered_contents = promoted_contents
        elif promoted_text and pending:
            filtered_contents = promoted_contents

        if len(filtered_contents) != len(message.contents or []):
            message = Message(
                role=message.role,
                contents=filtered_contents,
                author_name=message.author_name,
                additional_properties=message.additional_properties,
            )

        return message, pending

    def _inject_reasoning_to_openai_message(self, result: list[dict[str, Any]], reasoning: str | None) -> None:
        if not reasoning:
            return
        for msg in reversed(result):
            if msg.get("role") == "assistant" and ("content" in msg or "tool_calls" in msg):
                msg["reasoning_content"] = reasoning
                msg.pop("reasoning_details", None)
                return
        result.append({"role": "assistant", "content": "", "reasoning_content": reasoning})

    def _propagate_reasoning_in_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach standalone reasoning rows to the following tool_call assistant row."""
        out: list[dict[str, Any]] = []
        pending: str | None = None

        for msg in messages:
            role = msg.get("role")
            if role != "assistant":
                if pending:
                    out.append({"role": "assistant", "content": "", "reasoning_content": pending})
                    pending = None
                out.append(msg)
                continue

            reasoning = msg.get("reasoning_content")
            details = msg.get("reasoning_details")
            tool_calls = msg.get("tool_calls")
            has_reasoning = bool(reasoning or details)

            content = msg.get("content")
            content_text = content.strip() if isinstance(content, str) else ""
            if tool_calls and not reasoning and content_text and not details:
                merged = dict(msg)
                merged["reasoning_content"] = content_text
                merged["content"] = ""
                merged.pop("reasoning_details", None)
                if pending:
                    merged["reasoning_content"] = pending + merged["reasoning_content"]
                    pending = None
                out.append(merged)
                continue

            if has_reasoning and not tool_calls and _content_is_empty(msg.get("content")):
                pending = str(reasoning or details)
                continue

            if tool_calls and pending and not reasoning:
                merged = dict(msg)
                merged["reasoning_content"] = pending
                merged.pop("reasoning_details", None)
                pending = None
                out.append(merged)
                continue

            if pending:
                out.append({"role": "assistant", "content": "", "reasoning_content": pending})
                pending = None
            out.append(msg)

        if pending:
            out.append({"role": "assistant", "content": "", "reasoning_content": pending})
        return out

    def _extract_reasoning_from_response(self, response: Any, chat_response: ChatResponse) -> ChatResponse:
        parts: list[str] = []
        for choice in response.choices:
            rc = reasoning_content_from(getattr(choice, "message", None))
            if not rc:
                continue
            parts.append(rc)
            msg_index = response.choices.index(choice)
            if msg_index >= len(chat_response.messages):
                continue
            msg = chat_response.messages[msg_index]
            if any(
                getattr(c, "type", None) == "text_reasoning" and getattr(c, "text", None) == rc
                for c in msg.contents or []
            ):
                continue
            msg.contents.insert(0, Content.from_text_reasoning(text=rc))

        if parts:
            _set_additional_property(chat_response, "reasoning_content", "".join(parts))
        return self._normalize_assistant_reasoning(chat_response)

    def _extract_reasoning_from_update(self, chunk: Any, update: ChatResponseUpdate) -> ChatResponseUpdate:
        accumulated: str | None = None
        for choice in chunk.choices:
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            rc = reasoning_content_from(delta)
            if not rc:
                continue
            update.contents.append(Content.from_text_reasoning(text=rc))
            accumulated = rc if accumulated is None else accumulated + rc

        if accumulated is not None:
            _set_additional_property(update, "reasoning_content", accumulated)
        return update
