from app.platform.memory.memory_config import parse_memory_config
from app.platform.memory.projectors.default import DefaultMemoryProjector
from app.platform.memory.projectors.utils import truncate_long_strings, truncate_named_string_fields
from app.platform.memory.slimmer import HistoryProjection
from app.platform.memory.sql_tool_projectors import (
    SqlDescribeTableMemoryProjector,
    SqlListTablesMemoryProjector,
    SqlRunQueryMemoryProjector,
)


def test_truncate_long_strings_only_touches_oversized_strings():
    kb_id = "17c7b7fc-f535-467c-a535-73badd2aab22"
    slimmed = truncate_long_strings(
        {
            "query": "CB Name 是什么 报告 命名 " + ("x" * 400),
            "top_k": 12,
            "kb_ids": [kb_id],
            "note": "short",
        },
        120,
    )
    assert set(slimmed) == {"query", "top_k", "kb_ids", "note"}
    assert "_memory_preview" not in slimmed
    assert slimmed["top_k"] == 12
    assert slimmed["kb_ids"] == [kb_id]
    assert slimmed["note"] == "short"
    assert slimmed["query"].endswith("…")
    assert len(slimmed["query"]) <= 121


def test_truncate_named_string_fields_focuses_on_sql_key():
    slimmed = truncate_named_string_fields(
        {
            "sql": "SELECT " + "x" * 200,
            "limit": 50,
            "timeout_ms": 1000,
        },
        ("sql", "query", "statement"),
        120,
    )
    assert slimmed["limit"] == 50
    assert slimmed["timeout_ms"] == 1000
    assert slimmed["sql"].startswith("SELECT")
    assert slimmed["sql"].endswith("…")
    assert len(slimmed["sql"]) <= 121


def test_default_projector_preserves_hybrid_search_keys():
    cfg = parse_memory_config({}).slim
    projector = DefaultMemoryProjector()
    call = projector.slim_call(
        tool_name="hybrid-search_hybrid_search",
        arguments={
            "query": "CB Name " + ("详" * 300),
            "top_k": 12,
            "kb_ids": ["17c7b7fc-f535-467c-a535-73badd2aab22"],
        },
        metadata={"tool_name": "hybrid-search_hybrid_search"},
        config=cfg,
    )
    assert "_memory_preview" not in call.arguments
    assert call.arguments["top_k"] == 12
    assert call.arguments["kb_ids"] == ["17c7b7fc-f535-467c-a535-73badd2aab22"]
    assert call.arguments["query"].endswith("…")
    assert call.metadata.get("memory_slimmed") is True


def test_sql_run_query_projector():
    cfg = parse_memory_config({}).slim
    projector = SqlRunQueryMemoryProjector()

    call = projector.slim_call(
        tool_name="postgres_query_data",
        arguments={"sql": "SELECT " + "x" * 200, "limit": 20},
        metadata={"tool_name": "postgres_query_data"},
        config=cfg,
    )
    assert "_memory_preview" not in call.arguments
    assert call.arguments["limit"] == 20
    assert call.arguments["sql"].startswith("SELECT")
    assert len(call.arguments["sql"]) <= 121
    assert call.arguments["sql"].endswith("…")

    result = projector.slim_result(
        tool_name="postgres_query_data",
        content='{"row_count": 15, "truncated": true}',
        metadata={"tool_name": "postgres_query_data", "result": {"row_count": 15, "truncated": True}},
        config=cfg,
    )
    assert result.content == "SQL 已执行 | rows=15 | truncated=True"


def test_sql_list_tables_projector():
    cfg = parse_memory_config({}).slim
    projector = SqlListTablesMemoryProjector()
    result = projector.slim_result(
        tool_name="postgres_list_tables",
        content='[{"table": "users"}]' * 100,
        metadata={"tool_name": "postgres_list_tables"},
        config=cfg,
    )
    assert result.content == "已列出表"


def test_sql_describe_table_projector():
    cfg = parse_memory_config({}).slim
    projector = SqlDescribeTableMemoryProjector()
    result = projector.slim_result(
        tool_name="postgres_describe_table",
        content='{"columns": []}',
        metadata={
            "tool_name": "postgres_describe_table",
            "arguments": {"table": "orders"},
        },
        config=cfg,
    )
    assert result.content == "已查看表 orders 结构"


def test_history_projection_pairs_call_and_result():
    memory_config = parse_memory_config({})
    projection = HistoryProjection()
    rows = [
        {
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "sequence": 1,
            "metadata": {
                "call_id": "c1",
                "tool_name": "postgres_query_data",
                "arguments": {"sql": "SELECT 1"},
            },
        },
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": '{"rows": [1, 2, 3], "row_count": 3}',
            "sequence": 2,
            "metadata": {"call_id": "c1", "tool_name": "postgres_query_data", "result": {"row_count": 3}},
        },
    ]
    projected = projection.project_rows(rows, memory_config)
    assert projected[0]["metadata"]["arguments"] == {"sql": "SELECT 1"}
    assert "_memory_preview" not in projected[0]["metadata"]["arguments"]
    assert projected[1]["content"] == "SQL 已执行 | rows=3 | truncated=False"
