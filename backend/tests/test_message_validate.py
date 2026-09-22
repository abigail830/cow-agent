from agent_framework import Content, Message

from app.platform.memory.message_validate import (
    assert_no_tool_calls_in_partial_assistant,
    sanitize_messages_for_llm_history,
)


def test_sanitize_strips_incomplete_tool_calls_keeps_text() -> None:
    messages = [
        Message(role="user", contents=[Content.from_text("hello")]),
        Message(
            role="assistant",
            contents=[
                Content.from_text("thinking…"),
                Content.from_function_call(
                    call_id="call_1",
                    name="list_knowledge_bases",
                    arguments="{}",
                ),
            ],
        ),
        Message(role="user", contents=[Content.from_text("next turn")]),
    ]

    sanitized = sanitize_messages_for_llm_history(messages)

    assert len(sanitized) == 3
    assistant = sanitized[1]
    assert assistant.role == "assistant"
    assert len(assistant.contents) == 1
    assert assistant.contents[0].type == "text"


def test_sanitize_leaves_complete_tool_sequences() -> None:
    messages = [
        Message(
            role="assistant",
            contents=[
                Content.from_function_call(call_id="call_1", name="platform_time", arguments="{}")
            ],
        ),
        Message(
            role="tool",
            contents=[Content.from_function_result(call_id="call_1", result='{"ok": true}')],
        ),
    ]

    sanitized = sanitize_messages_for_llm_history(messages)
    assert sanitized == messages


def test_assert_no_tool_calls_in_partial_assistant() -> None:
    body = Message(
        role="assistant",
        contents=[Content.from_function_call(call_id="c1", name="x", arguments="{}")],
        additional_properties={"platform": {"partial": True}},
    ).to_dict()
    try:
        assert_no_tool_calls_in_partial_assistant(body)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "function_call" in str(exc)
