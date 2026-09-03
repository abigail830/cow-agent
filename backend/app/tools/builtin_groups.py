"""Builtin tool groups — agents enable via profile allowed_tools."""

from __future__ import annotations

from app.tools import BUILTIN_TOOLS
from app.yl_worker2.tools import YL_WORKER2_TOOL_NAMES

PROPOSAL_TOOL_NAMES = frozenset(
    {
        "list_templates",
        "read_knowledge",
        "list_mdm_packages",
        "get_mdm_package_services",
        "search_mdm_services",
        "list_mdm_packages_for_services",
        "initialize_proposal_draft",
        "get_proposal_draft",
        "patch_proposal_draft",
        "add_package_to_proposal_draft",
        "add_services_to_proposal_draft",
        "remove_fee_rows_from_proposal_draft",
        "enable_proposal_draft_section",
        "render_preview",
        "generate_document",
        "generate_word_document",
    }
)

VIZ_TOOL_NAMES = frozenset(
    {
        "list_sql_results",
        "suggest_visualization",
    }
)

DIAGRAM_TOOL_NAMES = frozenset(
    {
        "render_plantuml",
    }
)

SLIDE_TOOL_NAMES = frozenset(
    {
        "render_slidev",
        "render_html_ppt",
    }
)

# Re-export for agent_factory
__all__ = [
    "PROPOSAL_TOOL_NAMES",
    "VIZ_TOOL_NAMES",
    "DIAGRAM_TOOL_NAMES",
    "SLIDE_TOOL_NAMES",
    "YL_WORKER2_TOOL_NAMES",
    "resolve_builtin_tools",
]


def resolve_builtin_tools(allowed_tools: list[str], group: frozenset[str]) -> list:
    """Return MAF tool callables for allowed names in a builtin group."""
    allowed = set(allowed_tools or [])
    return [BUILTIN_TOOLS[name] for name in group if name in allowed and name in BUILTIN_TOOLS]
