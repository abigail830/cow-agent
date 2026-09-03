import pytest
from agent_framework import Content, Message

from app.memory.compaction import PlatformSlimCompactionStrategy, build_platform_compaction
from app.memory.maf_mapping import maf_messages_to_projection_rows, to_maf_messages
from app.memory.memory_config import parse_memory_config
from app.memory.slimmer import HistoryProjection


def _sql_history_rows() -> list[dict]:
    return [
        {
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "sequence": 1,
            "metadata": {
                "call_id": "c1",
                "tool_name": "postgres_query_data",
                "arguments": {"sql": "SELECT " + "x" * 200},
            },
        },
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": '{"rows": [1, 2, 3], "row_count": 3}',
            "sequence": 2,
            "metadata": {
                "call_id": "c1",
                "tool_name": "postgres_query_data",
                "result": {"row_count": 3, "truncated": False},
            },
        },
    ]


@pytest.mark.asyncio
async def test_platform_slim_compaction_survives_user_turn_round_trip():
    """Second chat turn compacts tool-heavy history; projected rows omit chat_id."""
    memory_config = parse_memory_config({})
    strategy = PlatformSlimCompactionStrategy(memory_config)
    rows = [
        {
            "chat_id": "11111111-1111-1111-1111-111111111111",
            "role": "user",
            "message_type": "text",
            "content": "帮我列一下需要紧急补货的销售分仓",
            "metadata": {},
            "sequence": 1,
        },
        {
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "sequence": 2,
            "metadata": {
                "call_id": "c1",
                "tool_name": "postgres_query_data",
                "arguments": {"query": "SELECT " + "x" * 200},
            },
        },
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": '{"rows": []}',
            "sequence": 3,
            "metadata": {
                "call_id": "c1",
                "tool_name": "postgres_query_data",
                "result": {"row_count": 0},
            },
        },
        {
            "role": "assistant",
            "message_type": "text",
            "content": "摘要：当前无红色缺口。",
            "metadata": {},
            "sequence": 4,
        },
    ]
    messages = to_maf_messages(rows)

    changed = await strategy(messages)
    assert changed is True
    assert messages[0].role == "user"
    assert messages[0].contents[0].text == rows[0]["content"]
    assert len(messages) >= 3


@pytest.mark.asyncio
async def test_platform_slim_compaction_strategy_slims_tool_history():
    memory_config = parse_memory_config({})
    strategy = PlatformSlimCompactionStrategy(memory_config)
    messages = to_maf_messages(_sql_history_rows())

    changed = await strategy(messages)
    assert changed is True

    rows = maf_messages_to_projection_rows(messages)
    assert rows[0]["metadata"]["arguments"]["_memory_preview"].startswith("SQL:")
    assert rows[1]["content"] == "SQL 已执行 | rows=3 | truncated=False"


@pytest.mark.asyncio
async def test_platform_slim_compaction_noop_when_disabled():
    memory_config = parse_memory_config({"memory": {"slim": {"enabled": False}}})
    strategy = PlatformSlimCompactionStrategy(memory_config)
    original = to_maf_messages(_sql_history_rows())
    messages = list(original)

    changed = await strategy(messages)
    assert changed is False
    assert maf_messages_to_projection_rows(messages) == maf_messages_to_projection_rows(original)


def test_build_platform_compaction_disabled_returns_none():
    memory_config = parse_memory_config({"memory": {"slim": {"enabled": False}}})
    strategy, provider = build_platform_compaction(memory_config)
    assert strategy is None
    assert provider is None


def test_maf_round_trip_preserves_skill_metadata():
    rows = [
        {
            "role": "tool",
            "message_type": "skill_load",
            "content": "SKILL.md body",
            "sequence": 1,
            "metadata": {
                "tool_name": "load_skill",
                "arguments": {"skill_name": "topic-daily-analysis"},
            },
        }
    ]
    messages = to_maf_messages(rows)
    rebuilt = maf_messages_to_projection_rows(messages)
    assert rebuilt[0]["message_type"] == "skill_load"
    assert rebuilt[0]["metadata"]["tool_name"] == "load_skill"


@pytest.mark.asyncio
async def test_platform_slim_compaction_skill_row():
    memory_config = parse_memory_config({})
    strategy = PlatformSlimCompactionStrategy(memory_config)
    rows = [
        {
            "role": "tool",
            "message_type": "skill_load",
            "content": "SKILL.md body",
            "sequence": 1,
            "metadata": {
                "tool_name": "load_skill",
                "arguments": {"skill_name": "topic-daily-analysis"},
            },
        }
    ]
    messages = to_maf_messages(rows)
    await strategy(messages)
    assert maf_messages_to_projection_rows(messages)[0]["content"] == "已加载 Skill: topic-daily-analysis"


def test_function_call_arguments_slimmed_in_assistant_message():
    memory_config = parse_memory_config({})
    messages = [
        Message(
            role="assistant",
            contents=[
                Content.from_function_call(
                    call_id="c1",
                    name="postgres_query_data",
                    arguments={"sql": "SELECT " + "y" * 200},
                )
            ],
            additional_properties={
                "platform_message_type": "tool_call",
                "platform_metadata": {"call_id": "c1", "tool_name": "postgres_query_data"},
            },
        )
    ]
    rows = maf_messages_to_projection_rows(messages)
    projected = HistoryProjection().project_rows(rows, memory_config)
    assert projected[0]["metadata"]["arguments"]["_memory_preview"].startswith("SQL:")
