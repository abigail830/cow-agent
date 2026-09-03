"""Tests for cross-provider tool history sanitization."""

from __future__ import annotations

from app.memory.maf_mapping import to_maf_messages
from app.memory.provider_history import sanitize_rows_for_provider
from app.platform.model_registry import ModelProvider


def _tool_call_row(call_id: str, *, seq: int = 2) -> dict:
    return {
        "id": f"tc-{seq}",
        "chat_id": "chat-1",
        "role": "assistant",
        "message_type": "tool_call",
        "content": None,
        "metadata": {
            "call_id": call_id,
            "tool_name": "render_html_ppt",
            "arguments": {"source": "<html></html>", "title": "Demo"},
        },
        "parent_id": None,
        "sequence": seq,
    }


def _tool_result_row(call_id: str, *, seq: int = 3) -> dict:
    return {
        "id": f"tr-{seq}",
        "chat_id": "chat-1",
        "role": "tool",
        "message_type": "tool_result",
        "content": '{"status":"ok"}',
        "metadata": {"call_id": call_id, "tool_name": "render_html_ppt", "result": {"status": "ok"}},
        "parent_id": None,
        "sequence": seq,
    }


def test_openai_drops_anthropic_toolu_history() -> None:
    rows = [
        {
            "id": "u1",
            "chat_id": "chat-1",
            "role": "user",
            "message_type": "text",
            "content": "继续",
            "metadata": {},
            "parent_id": None,
            "sequence": 1,
        },
        _tool_call_row("toolu_01K99JDrKRK4tHTlWTMeWFSS"),
        _tool_result_row("toolu_01K99JDrKRK4tHTlWTMeWFSS"),
    ]

    sanitized = sanitize_rows_for_provider(rows, provider=ModelProvider.AZURE_OPENAI.value)
    assert len(sanitized) == 1
    assert sanitized[0]["message_type"] == "text"

    messages = to_maf_messages(sanitized)
    assert len(messages) == 1
    assert messages[0].role == "user"


def test_anthropic_drops_openai_call_history() -> None:
    rows = [
        {
            "id": "u1",
            "chat_id": "chat-1",
            "role": "user",
            "message_type": "text",
            "content": "hi",
            "metadata": {},
            "parent_id": None,
            "sequence": 1,
        },
        _tool_call_row("call_abc123"),
        _tool_result_row("call_abc123"),
    ]

    sanitized = sanitize_rows_for_provider(rows, provider=ModelProvider.AZURE_ANTHROPIC.value)
    assert len(sanitized) == 1

    kept = sanitize_rows_for_provider(rows, provider=ModelProvider.AZURE_OPENAI.value)
    assert len(kept) == 3


def test_neutral_call_ids_kept_for_both_providers() -> None:
    rows = [_tool_call_row("call-1", seq=1), _tool_result_row("call-1", seq=2)]

    for provider in (
        ModelProvider.AZURE_OPENAI.value,
        ModelProvider.AZURE_ANTHROPIC.value,
        ModelProvider.SILICONFLOW.value,
    ):
        assert len(sanitize_rows_for_provider(rows, provider=provider)) == 2
