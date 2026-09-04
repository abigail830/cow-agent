"""Visualization tools (enabled via profile sql_viz hook, not slug-bound)."""

from __future__ import annotations

from app.platform.runtime.plugin import AgentPlugin

VIZ_TOOL_NAMES = frozenset({"list_sql_results", "suggest_visualization"})


class VizCapabilityPlugin(AgentPlugin):
    """Not slug-matched; tools resolved when sql_viz hook is present."""

    slug = ""
    tool_names = VIZ_TOOL_NAMES

    def matches(self, agent_slug: str | None) -> bool:
        return False
