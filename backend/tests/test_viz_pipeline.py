import json

from app.viz.pipeline import build_viz_from_rows
from app.viz.sql_parse import parse_sql_tool_result


def test_parse_sql_tool_result_rows():
    payload = json.dumps(
        {
            "rows": [
                {"week_start": "2026-05-01", "sessions": 10},
                {"week_start": "2026-05-08", "sessions": 15},
            ],
            "row_count": 2,
        }
    )
    rows, columns = parse_sql_tool_result(payload)
    assert len(rows) == 2
    assert "week_start" in columns
    assert "sessions" in columns


def test_auto_trend_line_chart():
    rows = [
        {"chat_created_at": "2026-05-01", "sessions": 10},
        {"chat_created_at": "2026-05-02", "sessions": 12},
        {"chat_created_at": "2026-05-03", "sessions": 8},
    ]
    columns = ["chat_created_at", "sessions"]
    result = build_viz_from_rows(rows, columns, intent="auto", title="Daily sessions")
    assert result.status in ("rendered", "repaired")
    assert result.spec is not None
    assert result.spec.kind in ("line", "bar", "combo")


def test_matrix_heatmap():
    rows = [
        {"service": "tax", "intent": "policy", "cnt": 5},
        {"service": "tax", "intent": "cost", "cnt": 3},
        {"service": "hr", "intent": "policy", "cnt": 2},
        {"service": "hr", "intent": "cost", "cnt": 1},
    ]
    columns = ["service", "intent", "cnt"]
    result = build_viz_from_rows(rows, columns, intent="matrix", title="Intent x Service")
    assert result.spec is not None
    assert result.spec.kind == "heatmap"
    assert len(result.spec.heatmap_rows) >= 2
    assert len(result.spec.heatmap_cols) >= 2


def test_invalid_heatmap_degrades_to_table():
    rows = [{"a": "only", "b": 1}]
    columns = ["a", "b"]
    result = build_viz_from_rows(rows, columns, intent="matrix", title="Too small")
    assert result.status == "degraded"
    assert result.spec is not None
    assert result.spec.kind == "table"
    assert result.spec.fallback is True


def test_none_intent_skips():
    rows = [{"a": 1}]
    result = build_viz_from_rows([{"a": 1}], ["a"], intent="none")
    assert result.status == "skipped"


def test_auto_title_from_columns():
    rows = [
        {"week_start": "2026-05-01", "sessions": 10},
        {"week_start": "2026-05-08", "sessions": 15},
    ]
    result = build_viz_from_rows(rows, ["week_start", "sessions"], intent="auto")
    assert result.spec is not None
    assert result.spec.title == "sessions by week_start"


def test_multiple_sql_calls_not_deduped():
    from app.viz.context import RunVizState

    state = RunVizState()
    rows_a = [{"d": "2026-05-01", "n": 1}, {"d": "2026-05-02", "n": 2}, {"d": "2026-05-03", "n": 3}]
    rows_b = [{"region": "HK", "cnt": 5}, {"region": "SG", "cnt": 3}, {"region": "VN", "cnt": 2}]
    r1 = build_viz_from_rows(rows_a, ["d", "n"], intent="auto")
    r2 = build_viz_from_rows(rows_b, ["region", "cnt"], intent="auto")
    assert state.queue_viz(r1, source_call_id="call-a")
    assert state.queue_viz(r2, source_call_id="call-b")
    assert len(state.pending_specs) == 2


def test_same_call_deduped():
    from app.viz.context import RunVizState

    state = RunVizState()
    rows = [{"d": "2026-05-01", "n": 1}, {"d": "2026-05-02", "n": 2}, {"d": "2026-05-03", "n": 3}]
    result = build_viz_from_rows(rows, ["d", "n"], intent="auto")
    assert state.queue_viz(result, source_call_id="call-1")
    assert not state.queue_viz(result, source_call_id="call-1")
    assert len(state.pending_specs) == 1


def test_list_sql_results_returns_cached_entries():
    from app.tools.viz import list_sql_results
    from app.viz.context import get_run_viz_state, init_run_viz_state, reset_run_viz_state

    init_run_viz_state()
    try:
        state = get_run_viz_state()
        assert state is not None
        state.store_sql(
            call_id="call-1",
            tool_name="postgres_query_data",
            rows=[{"a": 1}],
            columns=["a"],
        )
        state.store_sql(
            call_id="call-2",
            tool_name="postgres_query_data",
            rows=[{"b": 2}, {"b": 3}],
            columns=["b"],
        )

        out = list_sql_results()
        assert len(out["results"]) == 2
        assert out["results"][0]["source_call_id"] == "call-1"
        assert out["results"][1]["row_count"] == 2
        assert out["latest_call_id"] == "call-2"
    finally:
        reset_run_viz_state()
