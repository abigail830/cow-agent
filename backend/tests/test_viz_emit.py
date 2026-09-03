import uuid

from app.services.chat_run import _StreamTurnAccumulator, _emit_pending_viz_events
from app.viz.context import init_run_viz_state, reset_run_viz_state
from app.viz.pipeline import build_viz_from_rows


def test_emit_pending_viz_events_persists_viz_row():
    chat_id = uuid.uuid4()
    init_run_viz_state()
    try:
        rows = [
            {"d": "2026-05-01", "n": 1},
            {"d": "2026-05-02", "n": 2},
            {"d": "2026-05-03", "n": 3},
        ]
        result = build_viz_from_rows(rows, ["d", "n"], intent="trend", title="Trend")
        from app.viz.context import get_run_viz_state

        state = get_run_viz_state()
        assert state is not None
        state.queue_viz(result)

        acc = _StreamTurnAccumulator()
        events = _emit_pending_viz_events(chat_id, acc)
        assert len(events) == 1
        assert events[0]["event"] == "viz"
        assert events[0]["data"]["spec"]["title"] == "Trend"

        acc.finalize()
        viz_rows = [r for r in acc._rows if r["message_type"] == "viz"]
        assert len(viz_rows) == 1
        assert viz_rows[0]["metadata"]["spec"]["kind"] in ("line", "bar", "combo")
    finally:
        reset_run_viz_state()
