"""Central registry of MAF builtin tool callables (synced to DB via platform_sync)."""

from __future__ import annotations

from typing import Any, Callable

from app.shared.artifacts.diagram_tools import DIAGRAM_BUILTIN_TOOLS
from app.shared.artifacts.publish_tools import PUBLISH_BUILTIN_TOOLS
from app.shared.sandbox.tools import SANDBOX_BUILTIN_TOOLS
from app.agent_specific.proposal.mdm.tools import MDM_BUILTIN_TOOLS
from app.agent_specific.proposal.tools import PROPOSAL_BUILTIN_TOOLS
from app.agent_specific.slide.tools import SLIDE_BUILTIN_TOOLS
from app.agent_specific.viz.tools import VIZ_BUILTIN_TOOLS
from app.agent_specific.yl_worker2.tools import YL_WORKER2_TOOLS
from app.platform.agent.platform_time import platform_time

_TOOL_FRAGMENTS: tuple[dict[str, Callable[..., Any]], ...] = (
    PROPOSAL_BUILTIN_TOOLS,
    MDM_BUILTIN_TOOLS,
    DIAGRAM_BUILTIN_TOOLS,
    SLIDE_BUILTIN_TOOLS,
    SANDBOX_BUILTIN_TOOLS,
    PUBLISH_BUILTIN_TOOLS,
    VIZ_BUILTIN_TOOLS,
    YL_WORKER2_TOOLS,
)


def _merge_tool_fragments() -> dict[str, Callable[..., Any]]:
    merged: dict[str, Callable[..., Any]] = {"platform_time": platform_time}
    for fragment in _TOOL_FRAGMENTS:
        merged.update(fragment)
    return merged


BUILTIN_TOOLS = _merge_tool_fragments()
