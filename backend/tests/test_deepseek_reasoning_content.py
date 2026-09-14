from types import SimpleNamespace
from unittest.mock import patch

from agent_framework import Content, Message

from app.platform.llm.deepseek_client import PlatformDeepSeekClient, _reasoning_content_from


class _FakeDeepSeekClient(PlatformDeepSeekClient):
    def __init__(self) -> None:
        self._function_invocation_configuration = None


def test_prepare_attaches_reasoning_content_to_tool_call_message() -> None:
    client = _FakeDeepSeekClient()
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
    assert _reasoning_content_from(SimpleNamespace(reasoning_content="abc")) == "abc"
    assert (
        _reasoning_content_from(SimpleNamespace(reasoning_content=None, model_extra={"reasoning_content": "xyz"}))
        == "xyz"
    )
    assert _reasoning_content_from(SimpleNamespace()) is None


def test_parse_response_injects_reasoning_content() -> None:
    client = _FakeDeepSeekClient()
    parsed = SimpleNamespace(
        messages=[
            Message(
                "assistant",
                [Content.from_function_call(call_id="call_1", name="platform_time", arguments="{}")],
            )
        ]
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(reasoning_content="thinking about the three images"))]
    )

    def _super_parse(self, _response, _options):
        return parsed

    with patch.object(PlatformDeepSeekClient.__bases__[0], "_parse_response_from_openai", _super_parse):
        out = client._parse_response_from_openai(response, {})
    reasoning = next(content for content in out.messages[0].contents if content.type == "text_reasoning")
    assert reasoning.text == "thinking about the three images"


def test_parse_stream_update_injects_reasoning_content() -> None:
    client = _FakeDeepSeekClient()
    parsed = SimpleNamespace(contents=[])
    chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(reasoning_content="step 1"))]
    )

    def _super_parse(self, _chunk):
        return parsed

    with patch.object(PlatformDeepSeekClient.__bases__[0], "_parse_response_update_from_openai", _super_parse):
        update = client._parse_response_update_from_openai(chunk)
    reasoning = [content for content in update.contents if content.type == "text_reasoning"]
    assert len(reasoning) == 1
    assert reasoning[0].text == "step 1"
