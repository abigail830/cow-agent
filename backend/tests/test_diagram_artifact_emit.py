import uuid

from app.shared.artifacts.context import init_run_artifact_state, reset_run_artifact_state
from app.shared.artifacts.spec import ArtifactSpec
from app.platform.chat.run_service import _StreamTurnAccumulator, _emit_pending_artifact_events


def test_emit_pending_diagram_artifact_events():
    reset_run_artifact_state()
    chat_id = uuid.uuid4()
    ctx = init_run_artifact_state(chat_id=chat_id)
    ctx.queue_artifact(
        ArtifactSpec(
            kind="diagram_svg",
            title="Test diagram",
            format="svg",
            content="<svg/>",
            filename="test.svg",
            artifact_id="diag-test",
        )
    )
    accumulator = _StreamTurnAccumulator()
    events = _emit_pending_artifact_events(chat_id, accumulator)
    assert len(events) == 1
    assert events[0]["event"] == "artifact"
    assert events[0]["data"]["spec"]["kind"] == "diagram_svg"
    assert len(accumulator._rows) == 1
    assert accumulator._rows[0]["message_type"] == "artifact"
    reset_run_artifact_state()
