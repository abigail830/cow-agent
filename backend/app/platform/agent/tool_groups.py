"""Builtin tool groups — re-export from agent plugins for tests and legacy imports."""

from __future__ import annotations

from app.agent_specific.content_studio.plugin import CONTENT_STUDIO_TOOL_NAMES
from app.agent_specific.diagram.plugin import DIAGRAM_TOOL_NAMES
from app.agent_specific.proposal.plugin import PROPOSAL_TOOL_NAMES
from app.agent_specific.slide.plugin import SLIDE_TOOL_NAMES
from app.agent_specific.viz.plugin import VIZ_TOOL_NAMES
from app.agent_specific.yl_worker2.tools import YL_WORKER2_TOOL_NAMES
from app.platform.agent.builtin_registry import BUILTIN_TOOLS

__all__ = [
    "PROPOSAL_TOOL_NAMES",
    "VIZ_TOOL_NAMES",
    "DIAGRAM_TOOL_NAMES",
    "SLIDE_TOOL_NAMES",
    "CONTENT_STUDIO_TOOL_NAMES",
    "YL_WORKER2_TOOL_NAMES",
    "resolve_builtin_tools",
]


def resolve_builtin_tools(allowed_tools: list[str], group: frozenset[str]) -> list:
    allowed = set(allowed_tools or [])
    return [BUILTIN_TOOLS[name] for name in group if name in allowed and name in BUILTIN_TOOLS]
