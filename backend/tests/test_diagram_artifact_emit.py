import uuid

from app.diagram.context import init_run_diagram_state, reset_run_diagram_state
from app.proposal.artifact_spec import ArtifactSpec
from app.services.chat_run import _StreamTurnAccumulator, _emit_pending_artifact_events


def test_emit_pending_diagram_artifact_events():
    reset_run_diagram_state()
    chat_id = uuid.uuid4()
    ctx = init_run_diagram_state(chat_id=chat_id)
    spec = ArtifactSpec(
        kind="diagram_svg",
        title="Test diagram",
        format="svg",
        content='<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        filename="test.svg",
        artifact_id="diag-test123",
        source="@startuml\nA -> B\n@enduml",
    )
    ctx.queue_artifact(spec)

    acc = _StreamTurnAccumulator()
    events = _emit_pending_artifact_events(chat_id, acc)
    assert len(events) == 1
    assert events[0]["event"] == "artifact"
    assert events[0]["data"]["spec"]["kind"] == "diagram_svg"
    assert events[0]["data"]["spec"]["source"].startswith("@startuml")
    assert any(row["message_type"] == "artifact" for row in acc._rows)

    reset_run_diagram_state()
