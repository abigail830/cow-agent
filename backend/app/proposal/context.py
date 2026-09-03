"""Per-run proposal draft context (mirrors viz RunVizState pattern)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


from app.proposal.artifact_spec import ArtifactSpec


@dataclass
class RunProposalState:
    chat_id: uuid.UUID | None = None
    draft: dict[str, Any] | None = None
    draft_dirty: bool = False
    pending_artifacts: list[ArtifactSpec] = field(default_factory=list)
    emitted_artifacts: list[ArtifactSpec] = field(default_factory=list)

    def mark_draft_dirty(self) -> None:
        self.draft_dirty = True

    def queue_artifact(self, spec: ArtifactSpec) -> bool:
        key = (spec.kind, spec.title, spec.artifact_id)
        for existing in (*self.pending_artifacts, *self.emitted_artifacts):
            if (existing.kind, existing.title, existing.artifact_id) == key:
                return False
        self.pending_artifacts.append(spec)
        return True

    def drain_pending_artifacts(self) -> list[ArtifactSpec]:
        batch = list(self.pending_artifacts)
        self.pending_artifacts.clear()
        self.emitted_artifacts.extend(batch)
        return batch


_run_proposal_state: ContextVar[RunProposalState | None] = ContextVar(
    "run_proposal_state", default=None
)


def init_run_proposal_state(
    *,
    chat_id: uuid.UUID | None = None,
    initial_draft: dict[str, Any] | None = None,
) -> RunProposalState:
    ctx = RunProposalState(chat_id=chat_id, draft=initial_draft)
    _run_proposal_state.set(ctx)
    return ctx


def get_run_proposal_state() -> RunProposalState | None:
    return _run_proposal_state.get()


def reset_run_proposal_state() -> None:
    _run_proposal_state.set(None)


def export_proposal_draft() -> dict[str, Any] | None:
    ctx = get_run_proposal_state()
    if ctx is None:
        return None
    return ctx.draft
