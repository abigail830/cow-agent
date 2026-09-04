"""Proposal draft preview SSE events."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from app.agent_specific.proposal.runtime.context import get_run_proposal_state
from app.agent_specific.proposal.draft.draft import build_draft_preview
from app.platform.runtime.stream_emitter import StreamEmitter

if TYPE_CHECKING:
    from app.platform.chat.run_service import StreamTurnAccumulator

PROPOSAL_DRAFT_TOOL_NAMES = frozenset(
    {
        "initialize_proposal_draft",
        "patch_proposal_draft",
        "add_package_to_proposal_draft",
        "add_services_to_proposal_draft",
        "remove_fee_rows_from_proposal_draft",
        "enable_proposal_draft_section",
    }
)


def proposal_updated_event(chat_id: uuid.UUID) -> dict[str, Any] | None:
    ctx = get_run_proposal_state()
    if ctx is None or ctx.draft is None:
        return None
    data = build_draft_preview(ctx.draft)
    data["chat_id"] = str(chat_id)
    return {"event": "proposal_updated", "data": data}


class ProposalStreamEmitter(StreamEmitter):
    slug = "proposal-composer"

    def matches_slug(self, agent_slug: str | None) -> bool:
        return agent_slug == self.slug

    def events_for_tool_result(
        self,
        chat_id: uuid.UUID,
        tool_name: str,
        accumulator: StreamTurnAccumulator,
    ) -> list[dict[str, Any]]:
        if tool_name not in PROPOSAL_DRAFT_TOOL_NAMES:
            return []
        event = proposal_updated_event(chat_id)
        return [event] if event is not None else []
