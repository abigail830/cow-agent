"""Shared artifact run context for slide and content-studio agents."""

from __future__ import annotations

from app.shared.artifacts.context import init_run_artifact_state, reset_run_artifact_state
from app.platform.runtime.plugin import AgentPlugin, RunContext

_ARTIFACT_NAMESPACES: dict[str, str] = {
    "slide-studio": "slidev",
    "content-studio": "content-studio",
}


class ArtifactRuntimePlugin(AgentPlugin):
    slugs = frozenset(_ARTIFACT_NAMESPACES.keys())

    async def on_run_start(self, ctx: RunContext) -> None:
        namespace = _ARTIFACT_NAMESPACES.get(ctx.agent_slug or "")
        if namespace is None:
            return
        init_run_artifact_state(chat_id=ctx.chat_id, e2b_namespace=namespace)

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_run_artifact_state()
