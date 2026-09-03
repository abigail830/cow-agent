from app.memory.memory_config import parse_memory_config
from app.memory.slimmer import HistoryProjection
from app.tools.sql.memory import (
    SqlDescribeTableMemoryProjector,
    SqlListTablesMemoryProjector,
    SqlRunQueryMemoryProjector,
)


def test_sql_run_query_projector():
    cfg = parse_memory_config({}).slim
    projector = SqlRunQueryMemoryProjector()

    call = projector.slim_call(
        tool_name="postgres_query_data",
        arguments={"sql": "SELECT " + "x" * 200},
        metadata={"tool_name": "postgres_query_data"},
        config=cfg,
    )
    assert call.arguments["_memory_preview"].startswith("SQL:")
    assert len(call.arguments["_memory_preview"]) <= 130

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
    assert projected[0]["metadata"]["arguments"]["_memory_preview"].startswith("SQL:")
    assert projected[1]["content"] == "SQL 已执行 | rows=3 | truncated=False"
