"""Verify yl-worker2 tools are registered in BUILTIN_TOOLS."""

from app.tools import BUILTIN_TOOLS
from app.yl_worker2.tools import YL_WORKER2_TOOL_NAMES, YL_WORKER2_TOOLS


def test_yl_worker2_tool_names_match_registry():
    assert YL_WORKER2_TOOL_NAMES == frozenset(YL_WORKER2_TOOLS.keys())


def test_all_yl_worker2_tools_in_builtin_tools():
    missing = YL_WORKER2_TOOL_NAMES - set(BUILTIN_TOOLS.keys())
    assert not missing, f"Missing from BUILTIN_TOOLS: {missing}"


def test_profile_allowed_tools_subset():
    from app.platform.profile_loader import AGENTS_ROOT, load_agent_profile

    profile = load_agent_profile(AGENTS_ROOT / "yl-worker2")
    allowed = set((profile.extra_config or {}).get("allowed_tools") or [])
    assert allowed == YL_WORKER2_TOOL_NAMES
