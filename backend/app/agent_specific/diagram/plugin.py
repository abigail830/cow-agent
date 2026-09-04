"""Napkin Architect (diagram) runtime plugin."""

from __future__ import annotations

from app.agent_specific.diagram.context import init_run_diagram_state, reset_run_diagram_state
from app.platform.runtime.plugin import AgentPlugin, RunContext

DIAGRAM_TOOL_NAMES = frozenset({"render_plantuml"})


class DiagramPlugin(AgentPlugin):
    slug = "napkin-architect"
    tool_names = DIAGRAM_TOOL_NAMES

    async def on_run_start(self, ctx: RunContext) -> None:
        init_run_diagram_state(chat_id=ctx.chat_id)

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_run_diagram_state()
