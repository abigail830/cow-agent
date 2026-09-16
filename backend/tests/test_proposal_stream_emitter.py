import uuid

from app.agent_specific.proposal.draft.draft import empty_proposal_draft
from app.agent_specific.proposal.runtime.context import (
    init_run_proposal_state,
    reset_run_proposal_state,
)
from app.agent_specific.proposal.runtime.stream_emitter import ProposalStreamEmitter
from app.platform.chat.run_service import _StreamTurnAccumulator
from app.platform.chat.stream_pipeline import collect_stream_emitters, drain_after_finalize


def test_events_after_finalize_empty_without_run_state():
    reset_run_proposal_state()
    chat_id = uuid.uuid4()
    events = ProposalStreamEmitter().events_after_finalize(chat_id, _StreamTurnAccumulator())
    assert events == []


def test_events_after_finalize_emits_proposal_updated():
    reset_run_proposal_state()
    chat_id = uuid.uuid4()
    init_run_proposal_state(chat_id=chat_id, initial_draft=empty_proposal_draft())
    try:
        events = ProposalStreamEmitter().events_after_finalize(chat_id, _StreamTurnAccumulator())
        assert len(events) == 1
        assert events[0]["event"] == "proposal_updated"
        assert events[0]["data"]["chat_id"] == str(chat_id)
    finally:
        reset_run_proposal_state()


def test_drain_after_finalize_only_for_proposal_composer():
    reset_run_proposal_state()
    chat_id = uuid.uuid4()
    init_run_proposal_state(chat_id=chat_id, initial_draft=empty_proposal_draft())
    acc = _StreamTurnAccumulator()
    try:
        proposal_events = drain_after_finalize(
            collect_stream_emitters("proposal-composer"),
            chat_id,
            acc,
        )
        other_events = drain_after_finalize(
            collect_stream_emitters("content-studio"),
            chat_id,
            acc,
        )
        yl_events = drain_after_finalize(
            collect_stream_emitters("yl-worker2"),
            chat_id,
            acc,
        )
        assert [event["event"] for event in proposal_events] == ["proposal_updated"]
        assert other_events == []
        assert yl_events == []
    finally:
        reset_run_proposal_state()
