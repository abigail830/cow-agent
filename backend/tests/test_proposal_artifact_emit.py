import uuid

from app.proposal.artifact_spec import ArtifactSpec
from app.services.chat_run import _StreamTurnAccumulator, _emit_pending_artifact_events


def test_emit_pending_artifact_events():
    from app.proposal.context import get_run_proposal_state, init_run_proposal_state, reset_run_proposal_state

    reset_run_proposal_state()
    chat_id = uuid.uuid4()
    ctx = init_run_proposal_state(chat_id=chat_id)
    spec = ArtifactSpec(
        kind="proposal_preview",
        title="Preview",
        content="# Hello",
        filename="hello.md",
        artifact_id="prop-test123",
    )
    ctx.queue_artifact(spec)

    acc = _StreamTurnAccumulator()
    events = _emit_pending_artifact_events(chat_id, acc)
    assert len(events) == 1
    assert events[0]["event"] == "artifact"
    assert events[0]["data"]["spec"]["title"] == "Preview"
    assert any(row["message_type"] == "artifact" for row in acc._rows)

    reset_run_proposal_state()
