import pytest
from agent_framework import Content, Message

from app.platform.memory.compaction import PlatformSlimCompactionStrategy
from app.platform.memory.maf_mapping import maf_messages_to_projection_rows, to_maf_messages
from app.platform.memory.memory_config import MemoryConfig
from app.platform.memory.slimmer import HistoryProjection
from app.platform.llm.openai_compatible_client import OpenAICompatibleReasoningClient


class _FakeClient(OpenAICompatibleReasoningClient):
    def __init__(self) -> None:
        self._function_invocation_configuration = None


def _assistant_tool_call_with_reasoning(*, props_only: bool = False) -> Message:
    contents = [
        Content.from_function_call(call_id="call_1", name="list_knowledge_bases", arguments="{}"),
    ]
    if not props_only:
        contents.insert(0, Content.from_text_reasoning(text="need to list KBs"))
    return Message(
        role="assistant",
        contents=contents,
        additional_properties={"reasoning_content": "need to list KBs"},
    )


def _prepared_tool_call_reasoning(messages: list[Message]) -> str | None:
    client = _FakeClient()
    prepared = client._prepare_messages_for_openai(
        [
            *messages,
            Message(
                role="tool",
                contents=[Content.from_function_result(call_id="call_1", result='["LRQ"]')],
            ),
        ]
    )
    assistant = [row for row in prepared if row.get("role") == "assistant" and row.get("tool_calls")]
    return assistant[0].get("reasoning_content") if assistant else None


def test_slim_roundtrip_preserves_text_reasoning_for_deepseek() -> None:
    rows = maf_messages_to_projection_rows([_assistant_tool_call_with_reasoning()])
    projected = HistoryProjection().project_rows(rows, MemoryConfig())
    rebuilt = to_maf_messages(projected, model_provider="deepseek")
    assert _prepared_tool_call_reasoning(rebuilt) == "need to list KBs"


def test_slim_roundtrip_without_model_provider_still_replays_reasoning_content() -> None:
    rows = maf_messages_to_projection_rows([_assistant_tool_call_with_reasoning()])
    projected = HistoryProjection().project_rows(rows, MemoryConfig())
    rebuilt = to_maf_messages(projected)
    assert rebuilt[0].contents[0].type == "text"
    assert rebuilt[0].additional_properties["reasoning_content"] == "need to list KBs"
    assert _prepared_tool_call_reasoning(rebuilt) == "need to list KBs"


def test_slim_roundtrip_preserves_reasoning_content_in_additional_properties() -> None:
    rows = maf_messages_to_projection_rows([_assistant_tool_call_with_reasoning(props_only=True)])
    projected = HistoryProjection().project_rows(rows, MemoryConfig())
    rebuilt = to_maf_messages(projected, model_provider="deepseek")
    assert _prepared_tool_call_reasoning(rebuilt) == "need to list KBs"


@pytest.mark.asyncio
async def test_platform_slim_compaction_strategy_passes_model_provider() -> None:
    working = [_assistant_tool_call_with_reasoning()]
    strategy = PlatformSlimCompactionStrategy(MemoryConfig(), model_provider="deepseek")
    changed = await strategy(working)
    assert changed is True
    assert _prepared_tool_call_reasoning(working) == "need to list KBs"
