"""Tests for MAF history rebuild with OpenAI-compatible tool arguments."""

from __future__ import annotations

from agent_framework import Content

from app.memory.maf_mapping import to_maf_messages


def test_to_maf_messages_stringifies_tool_call_arguments() -> None:
    rows = [
        {
            "id": "u1",
            "chat_id": "chat-1",
            "role": "user",
            "message_type": "text",
            "content": "make slides",
            "metadata": {},
            "parent_id": None,
            "sequence": 1,
        },
        {
            "id": "tc1",
            "chat_id": "chat-1",
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "metadata": {
                "call_id": "call-1",
                "tool_name": "render_slidev",
                "arguments": {"source": "# Deck", "title": "Demo"},
            },
            "parent_id": None,
            "sequence": 2,
        },
        {
            "id": "tr1",
            "chat_id": "chat-1",
            "role": "tool",
            "message_type": "tool_result",
            "content": '{"status":"queued"}',
            "metadata": {"call_id": "call-1", "tool_name": "render_slidev", "result": {"status": "queued"}},
            "parent_id": None,
            "sequence": 3,
        },
    ]

    messages = to_maf_messages(rows)
    assert len(messages) == 3

    tool_call = messages[1].contents[0]
    assert isinstance(tool_call, Content)
    assert tool_call.type == "function_call"
    assert isinstance(tool_call.arguments, str)
    assert '"source"' in tool_call.arguments
    assert '"title"' in tool_call.arguments
