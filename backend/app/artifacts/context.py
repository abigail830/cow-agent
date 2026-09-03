"""Per-run artifact queue for agents that emit chat artifacts (slides, etc.)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.artifacts.spec import ArtifactSpec
from app.sandbox.e2b_session import release_e2b_session, set_e2b_session_key


@dataclass
class RunArtifactState:
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


_run_artifact_state: ContextVar[RunArtifactState | None] = ContextVar(
    "run_artifact_state", default=None
)


def init_run_artifact_state(*, chat_id: uuid.UUID | None = None) -> RunArtifactState:
    ctx = RunArtifactState(chat_id=chat_id)
    _run_artifact_state.set(ctx)
    set_e2b_session_key(str(chat_id) if chat_id is not None else None)
    return ctx


def get_run_artifact_state() -> RunArtifactState | None:
    return _run_artifact_state.get()


def reset_run_artifact_state() -> None:
    ctx = _run_artifact_state.get()
    if ctx is not None and ctx.chat_id is not None:
        from app.slide.build_jobs import reset_slide_build_jobs

        reset_slide_build_jobs(ctx.chat_id)
    release_e2b_session()
    set_e2b_session_key(None)
    _run_artifact_state.set(None)
