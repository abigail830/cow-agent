"""Per-run diagram artifact context (mirrors proposal RunProposalState pattern)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.proposal.artifact_spec import ArtifactSpec


@dataclass
class RunDiagramState:
    chat_id: uuid.UUID | None = None
    pending_artifacts: list[ArtifactSpec] = field(default_factory=list)
    emitted_artifacts: list[ArtifactSpec] = field(default_factory=list)
    last_source: str | None = None

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


_run_diagram_state: ContextVar[RunDiagramState | None] = ContextVar(
    "run_diagram_state", default=None
)


def init_run_diagram_state(*, chat_id: uuid.UUID | None = None) -> RunDiagramState:
    ctx = RunDiagramState(chat_id=chat_id)
    _run_diagram_state.set(ctx)
    return ctx


def get_run_diagram_state() -> RunDiagramState | None:
    return _run_diagram_state.get()


def reset_run_diagram_state() -> None:
    _run_diagram_state.set(None)
