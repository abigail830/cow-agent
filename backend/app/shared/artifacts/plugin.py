"""Shared artifact run context and diagram capability for chat agents."""

from __future__ import annotations

from app.db.models import AgentModel
from app.shared.artifacts.context import init_run_artifact_state, reset_run_artifact_state
from app.shared.artifacts.diagram_tools import DIAGRAM_TOOL_NAMES
from app.shared.artifacts.publish_tools import PUBLISH_TOOL_NAMES
from app.shared.sandbox.tools import SANDBOX_TOOL_NAMES
from app.platform.runtime.plugin import AgentPlugin, RunContext

SANDBOX_ARTIFACT_TOOL_NAMES = SANDBOX_TOOL_NAMES | PUBLISH_TOOL_NAMES

# Agents that always use the shared artifact queue (+ optional E2B sandbox namespace).
_ARTIFACT_E2B_NAMESPACE: dict[str, str | None] = {
    "slide-studio": "slidev",
    "content-studio": "content-studio",
    "napkin-architect": None,
}


class ArtifactRuntimePlugin(AgentPlugin):
    """Initialize shared RunArtifactState for slide, content, and diagram agents."""

    def matches(self, agent_slug: str | None) -> bool:
        return True

    async def on_run_start(self, ctx: RunContext) -> None:
        namespace = _ARTIFACT_E2B_NAMESPACE.get(ctx.agent_slug or "")
        if ctx.agent_slug in _ARTIFACT_E2B_NAMESPACE:
            init_run_artifact_state(chat_id=ctx.chat_id, e2b_namespace=namespace)
            return

        agent = await ctx.db.get(AgentModel, ctx.chat.agent_id)
        if agent is None:
            return
        allowed = list((agent.config or {}).get("allowed_tools") or [])
        if "render_plantuml" in allowed:
            init_run_artifact_state(chat_id=ctx.chat_id, e2b_namespace=None)

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_run_artifact_state()


class DiagramArtifactPlugin(AgentPlugin):
    """Expose render_plantuml to any agent that lists it in profile allowed_tools."""

    tool_names = DIAGRAM_TOOL_NAMES

    def matches(self, agent_slug: str | None) -> bool:
        return True


class SandboxArtifactPlugin(AgentPlugin):
    """Expose sandbox I/O and publish_artifact to any agent that lists them in allowed_tools."""

    tool_names = SANDBOX_ARTIFACT_TOOL_NAMES

    def matches(self, agent_slug: str | None) -> bool:
        return True
