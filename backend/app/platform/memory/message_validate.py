"""Validate MAF Message payloads before persisting to chat_messages."""

from __future__ import annotations

from typing import Any

from agent_framework import Message


def message_body_from_dict(raw: dict[str, Any]) -> dict[str, Any]:
    message = Message.from_dict(raw)
    return message.to_dict()


def validate_message_body(raw: dict[str, Any]) -> dict[str, Any]:
    body = message_body_from_dict(raw)
    role = str(body.get("role") or "").strip()
    if role not in {"user", "assistant", "tool", "system"}:
        raise ValueError(f"Invalid MAF message role: {role!r}")
    if not isinstance(body.get("contents"), list):
        raise ValueError("MAF message body must include contents list")
    return body


def message_from_body(body: dict[str, Any]) -> Message:
    return Message.from_dict(body)


def _function_call_ids(message: Message) -> list[str]:
    return [
        str(getattr(content, "call_id", "") or "")
        for content in message.contents or []
        if getattr(content, "type", None) == "function_call" and getattr(content, "call_id", None)
    ]


def _function_result_ids(message: Message) -> set[str]:
    found: set[str] = set()
    for content in message.contents or []:
        if getattr(content, "type", None) != "function_result":
            continue
        call_id = str(getattr(content, "call_id", "") or "")
        if call_id:
            found.add(call_id)
    return found


def sanitize_messages_for_llm_history(messages: list[Message]) -> list[Message]:
    """Remove assistant tool_calls that lack matching tool responses.

    Does not synthesize placeholder tool results. Incomplete tool turns (legacy
    partial persist or failed mid-loop writes) are stripped so the next LLM
    request receives a valid OpenAI-style transcript.
    """
    if not messages:
        return messages

    sanitized: list[Message] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.role != "assistant":
            sanitized.append(message)
            index += 1
            continue

        call_ids = _function_call_ids(message)
        if not call_ids:
            sanitized.append(message)
            index += 1
            continue

        tool_block_end = index + 1
        result_ids: set[str] = set()
        while tool_block_end < len(messages) and messages[tool_block_end].role == "tool":
            result_ids |= _function_result_ids(messages[tool_block_end])
            tool_block_end += 1

        if all(call_id in result_ids for call_id in call_ids):
            sanitized.extend(messages[index:tool_block_end])
            index = tool_block_end
            continue

        non_tool_contents = [
            content
            for content in message.contents or []
            if getattr(content, "type", None) != "function_call"
        ]
        if non_tool_contents:
            sanitized.append(
                Message(
                    role="assistant",
                    contents=non_tool_contents,
                    additional_properties=message.additional_properties,
                )
            )
        index = tool_block_end

    return sanitized


def assert_no_tool_calls_in_partial_assistant(body: dict[str, Any]) -> None:
    """Partial assistant rows (cancel/failure) must not include tool_call contents."""
    platform = (body.get("additional_properties") or {}).get("platform") or {}
    if not platform.get("partial"):
        return
    for content in body.get("contents") or []:
        if isinstance(content, dict) and content.get("type") == "function_call":
            raise ValueError("Partial assistant message must not include function_call contents")


def maf_message_id_from_body(body: dict[str, Any]) -> str | None:
    mid = body.get("message_id")
    if mid is None:
        return None
    text = str(mid).strip()
    return text or None
