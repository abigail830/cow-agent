"""Tests for PlatformAnthropicClient."""

from __future__ import annotations

from unittest.mock import patch

from app.platform.anthropic_client import PlatformAnthropicClient


def test_prepare_options_strips_conversation_id() -> None:
    client = PlatformAnthropicClient.__new__(PlatformAnthropicClient)
    client.model = "claude-test"

    with patch.object(
        PlatformAnthropicClient.__bases__[0],
        "_prepare_options",
        return_value={"model": "claude-test", "messages": []},
    ) as mock_super:
        client._prepare_options(
            [],
            {"max_tokens": 100, "conversation_id": "thread-abc"},
            conversation_id="thread-abc",
            middleware=None,
        )

    args, kwargs = mock_super.call_args
    passed_options = args[1]
    assert "conversation_id" not in passed_options
    assert "conversation_id" not in kwargs
    assert passed_options["max_tokens"] == 100
