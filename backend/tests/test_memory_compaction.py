import uuid

import pytest
from agent_framework import Content, Message

from app.platform.attachments.materialize import is_attachment_materialization_text
from app.platform.memory.compaction import PlatformSlimCompactionStrategy, build_platform_compaction
from app.platform.memory.maf_mapping import maf_messages_to_projection_rows, to_maf_messages
from app.platform.memory.memory_config import parse_memory_config
from app.platform.memory.slimmer import HistoryProjection


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
async def test_platform_slim_compaction_preserves_user_attachment_inline(monkeypatch):
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "nova-system-analysis.md",
        "mime_type": "text/markdown",
        "size_bytes": 128,
        "provider": "deepseek",
        "provider_file_id": f"inline:{att_id}",
    }
    monkeypatch.setattr(
        "app.platform.attachments.materialize.load_attachment_bytes",
        lambda *_args, **_kwargs: b"# Nova analysis\n\nbody",
    )
    memory_config = parse_memory_config({})
    strategy = PlatformSlimCompactionStrategy(
        memory_config,
        chat_id=chat_id,
        model_id="deepseek-flash",
        model_provider="deepseek",
    )
    rows = [
        {
            "chat_id": str(chat_id),
            "role": "user",
            "message_type": "text",
            "content": "跟这个文档印证一下",
            "metadata": {"attachments": [attachment]},
            "sequence": 1,
        },
        {
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "sequence": 2,
            "metadata": {
                "call_id": "c1",
                "tool_name": "hybrid_search",
                "arguments": {"query": "nova " + "x" * 200},
            },
        },
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": '{"hits": 1}',
            "sequence": 3,
            "metadata": {
                "call_id": "c1",
                "tool_name": "hybrid_search",
                "result": {"hits": 1},
            },
        },
    ]
    messages = to_maf_messages(rows)

    changed = await strategy(messages)
    assert changed is True

    user = next(message for message in messages if message.role == "user")
    attachment_blocks = [
        content.text
        for content in user.contents or []
        if getattr(content, "type", None) == "text"
        and is_attachment_materialization_text(getattr(content, "text", "") or "")
    ]
    assert attachment_blocks
    assert "nova-system-analysis.md" in attachment_blocks[0]
    assert "Nova analysis" in attachment_blocks[0]


@pytest.mark.asyncio
async def test_platform_slim_compaction_survives_user_turn_round_trip():
    """Second chat turn compacts tool-heavy history without losing user prompt text."""
    memory_config = parse_memory_config({})
    chat_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    strategy = PlatformSlimCompactionStrategy(memory_config, chat_id=chat_id)
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
    assert "sql" in rows[0]["metadata"]["arguments"]
    assert rows[0]["metadata"]["arguments"]["sql"].startswith("SELECT")
    assert "_memory_preview" not in rows[0]["metadata"]["arguments"]
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
    memory_config = parse_memory_config(
        {"memory": {"slim": {"enabled": False}, "compaction": {"enabled": False}}}
    )
    in_run, provider = build_platform_compaction(memory_config)
    assert in_run is None
    assert provider is None


def test_build_platform_compaction_returns_in_run_when_enabled():
    memory_config = parse_memory_config({"memory": {"slim": {"enabled": False}}})
    in_run, provider = build_platform_compaction(memory_config)
    assert in_run is not None
    assert provider is not None


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
    assert "sql" in projected[0]["metadata"]["arguments"]
    assert projected[0]["metadata"]["arguments"]["sql"].startswith("SELECT")
    assert "_memory_preview" not in projected[0]["metadata"]["arguments"]
