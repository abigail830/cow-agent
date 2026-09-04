"""Artifact card SSE events (proposal, diagram, slide, content-studio)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from app.agent_specific.proposal.artifact_spec import ArtifactSpec
from app.agent_specific.proposal.context import get_run_proposal_state
from app.shared.artifacts.context import get_run_artifact_state
from app.platform.runtime.stream_emitter import StreamEmitter

if TYPE_CHECKING:
    from app.platform.chat.run_service import StreamTurnAccumulator


def artifact_spec_payload(spec: ArtifactSpec) -> dict[str, Any]:
    return spec.model_dump(mode="json", exclude_none=True)


class ArtifactStreamEmitter(StreamEmitter):
    def drain_pending(
        self,
        chat_id: uuid.UUID,
        accumulator: StreamTurnAccumulator,
    ) -> list[dict[str, Any]]:
        specs: list[ArtifactSpec] = []
        proposal_ctx = get_run_proposal_state()
        if proposal_ctx is not None:
            specs.extend(proposal_ctx.drain_pending_artifacts())
        artifact_ctx = get_run_artifact_state()
        if artifact_ctx is not None:
            specs.extend(artifact_ctx.drain_pending_artifacts())
        if not specs:
            return []

        events: list[dict[str, Any]] = []
        for spec in specs:
            accumulator.record_artifact(spec)
            events.append(
                {
                    "event": "artifact",
                    "data": {
                        "chat_id": str(chat_id),
                        "spec": artifact_spec_payload(spec),
                    },
                }
            )
        return events
