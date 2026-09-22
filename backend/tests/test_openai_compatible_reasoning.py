from types import SimpleNamespace
from unittest.mock import patch

from agent_framework import ChatResponse, ChatResponseUpdate, Content, Message

from app.platform.llm.openai_compatible_client import OpenAICompatibleReasoningClient
from app.platform.llm.reasoning_content_mixin import reasoning_content_from
from app.platform.memory.message_validate import message_from_body, validate_message_body


class _FakeClient(OpenAICompatibleReasoningClient):
    def __init__(self) -> None:
        self._function_invocation_configuration = None


def test_prepare_merges_split_reasoning_into_following_tool_call_message() -> None:
    client = _FakeClient()
    prepared = client._prepare_messages_for_openai(
        [
            Message("assistant", [Content.from_text_reasoning(text="need to list knowledge bases")]),
            Message(
                "assistant",
                [Content.from_function_call(call_id="call_1", name="list_knowledge_bases", arguments="{}")],
            ),
        ]
    )
    assert len(prepared) == 1
    assert prepared[0]["role"] == "assistant"
    assert prepared[0]["reasoning_content"] == "need to list knowledge bases"
    assert "tool_calls" in prepared[0]


def test_prepare_attaches_reasoning_content_to_tool_call_message() -> None:
    client = _FakeClient()
    prepared = client._prepare_message_for_openai(
        Message(
            "assistant",
            [
                Content.from_text_reasoning(text="need to inspect the slides"),
                Content.from_function_call(call_id="call_1", name="platform_time", arguments="{}"),
            ],
        )
    )
    assert len(prepared) == 1
    assert prepared[0]["role"] == "assistant"
    assert prepared[0]["reasoning_content"] == "need to inspect the slides"
    assert "tool_calls" in prepared[0]
    assert "reasoning_details" not in prepared[0]


def test_reasoning_content_from_message_and_extra() -> None:
    assert reasoning_content_from(SimpleNamespace(reasoning_content="abc")) == "abc"
    assert (
        reasoning_content_from(SimpleNamespace(reasoning_content=None, model_extra={"reasoning_content": "xyz"}))
        == "xyz"
    )
    assert reasoning_content_from(SimpleNamespace()) is None


def test_parse_response_injects_reasoning_content() -> None:
    client = _FakeClient()
    parsed = SimpleNamespace(
        messages=[
            Message(
                "assistant",
                [Content.from_function_call(call_id="call_1", name="platform_time", arguments="{}")],
            )
        ],
        additional_properties={},
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(reasoning_content="thinking about the three images"))]
    )

    def _super_parse(self, _response, _options):
        return parsed

    with patch.object(OpenAICompatibleReasoningClient.__bases__[1], "_parse_response_from_openai", _super_parse):
        out = client._parse_response_from_openai(response, {})
    reasoning = next(content for content in out.messages[0].contents if content.type == "text_reasoning")
    assert reasoning.text == "thinking about the three images"


def test_finalize_merges_orphan_response_reasoning_into_tool_call_message() -> None:
    client = _FakeClient()
    response = client._finalize_response_updates(
        [
            ChatResponseUpdate(
                role="assistant",
                contents=[Content.from_function_call(call_id="call_1", name="list_knowledge_bases", arguments="{}")],
                additional_properties={"reasoning_content": "need to list knowledge bases"},
            )
        ]
    )
    assert len(response.messages) == 1
    assert response.messages[0].additional_properties["reasoning_content"] == "need to list knowledge bases"
    prepared = client._prepare_messages_for_openai(response.messages)
    assert prepared[0]["reasoning_content"] == "need to list knowledge bases"
    assert "tool_calls" in prepared[0]


def test_finalize_merges_split_reasoning_and_tool_messages() -> None:
    client = _FakeClient()
    response = client._finalize_response_updates(
        [
            ChatResponseUpdate(
                role="assistant",
                contents=[Content.from_text_reasoning(text="thinking about KBs")],
                message_id="resp-1",
            ),
            ChatResponseUpdate(
                role="assistant",
                contents=[Content.from_function_call(call_id="call_1", name="list_knowledge_bases", arguments="{}")],
                message_id="resp-2",
            ),
        ]
    )
    assert len(response.messages) == 1
    prepared = client._prepare_messages_for_openai(response.messages)
    assert len(prepared) == 1
    assert prepared[0]["reasoning_content"] == "thinking about KBs"


def test_normalize_survives_pg_roundtrip_for_tool_loop_reload() -> None:
    client = _FakeClient()
    response = client._finalize_response_updates(
        [
            ChatResponseUpdate(
                role="assistant",
                contents=[Content.from_function_call(call_id="call_1", name="list_knowledge_bases", arguments="{}")],
                additional_properties={"reasoning_content": "persist me"},
            )
        ]
    )
    body = validate_message_body(response.messages[0].to_dict())
    reloaded = message_from_body(body)
    prepared = client._prepare_messages_for_openai(
        [
            Message(role="user", contents=[Content.from_text("what KBs?")]),
            reloaded,
            Message(
                role="tool",
                contents=[Content.from_function_result(call_id="call_1", result='["kb-a"]')],
            ),
        ]
    )
    assistant_rows = [row for row in prepared if row.get("role") == "assistant" and row.get("tool_calls")]
    assert len(assistant_rows) == 1
    assert assistant_rows[0]["reasoning_content"] == "persist me"


def test_prepare_promotes_demoted_text_on_tool_call_rows() -> None:
    client = _FakeClient()
    prepared = client._prepare_messages_for_openai(
        [
            Message(
                role="assistant",
                contents=[
                    Content.from_text("need to inspect the KB"),
                    Content.from_function_call(call_id="call_1", name="load_skill", arguments="{}"),
                ],
            )
        ]
    )
    assert len(prepared) == 1
    assert prepared[0]["reasoning_content"] == "need to inspect the KB"
    assert prepared[0].get("content") in ("", None)
    assert "tool_calls" in prepared[0]


def test_prepare_coalesces_split_rows_from_pg_history() -> None:
    client = _FakeClient()
    prepared = client._prepare_messages_for_openai(
        [
            Message(role="user", contents=[Content.from_text("diagram")]),
            Message(role="assistant", contents=[Content.from_text_reasoning(text="R1")]),
            Message(
                role="assistant",
                contents=[Content.from_function_call(call_id="call_1", name="load_skill", arguments="{}")],
            ),
            Message(
                role="tool",
                contents=[Content.from_function_result(call_id="call_1", result="ok")],
            ),
        ]
    )
    tool_rows = [row for row in prepared if row.get("role") == "assistant" and row.get("tool_calls")]
    assert len(tool_rows) == 1
    assert tool_rows[0]["reasoning_content"] == "R1"


def test_parse_text_skips_thinking_duplicated_in_content_with_tool_calls() -> None:
    client = _FakeClient()
    choice = SimpleNamespace(
        delta=SimpleNamespace(
            content="Hmm - need to be careful.",
            reasoning_content="Hmm - need to be careful.",
            tool_calls=[SimpleNamespace(id="call_1", function=SimpleNamespace(name="load_skill", arguments="{}"))],
        )
    )
    assert client._parse_text_from_openai(choice) is None


def test_parse_stream_update_injects_reasoning_content() -> None:
    client = _FakeClient()
    parsed = SimpleNamespace(contents=[], additional_properties={})
    chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(reasoning_content="step 1"))]
    )

    def _super_parse(self, _chunk):
        return parsed

    with patch.object(OpenAICompatibleReasoningClient.__bases__[1], "_parse_response_update_from_openai", _super_parse):
        update = client._parse_response_update_from_openai(chunk)
    reasoning = [content for content in update.contents if content.type == "text_reasoning"]
    assert len(reasoning) == 1
    assert reasoning[0].text == "step 1"
