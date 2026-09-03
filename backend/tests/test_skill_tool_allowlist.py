"""Skill tools are auto-allowed when agent has skills — skill name is not a tool name."""

from unittest.mock import MagicMock

from app.middleware.allowed_tools import AllowedToolsMiddleware
from app.platform.hook_registry import resolve_middleware


def _allowed_middleware(
    profile_allowed: list[str],
    *,
    extra: set[str] | None = None,
) -> AllowedToolsMiddleware:
    chain = resolve_middleware(
        {"allowed_tools": profile_allowed},
        db=MagicMock(),
        chat_id=None,
        extra_allowed_tools=extra,
    )
    allowed = [m for m in chain if isinstance(m, AllowedToolsMiddleware)]
    assert len(allowed) == 1
    return allowed[0]


def test_skill_name_in_profile_does_not_allow_load_skill():
    """topic-daily-analysis is a skill name (load_skill argument), not a MAF tool."""
    mw = _allowed_middleware(["topic-daily-analysis", "postgres_run_query"])
    assert "postgres_run_query" in mw._allowed
    assert "topic-daily-analysis" in mw._allowed
    assert "load_skill" not in mw._allowed


def test_platform_merges_skill_tools_when_agent_has_skills():
    """AgentFactory passes load_skill/read_skill_resource via extra_allowed_tools."""
    mw = _allowed_middleware(
        ["postgres_run_query"],
        extra={"load_skill", "read_skill_resource"},
    )
    assert "postgres_run_query" in mw._allowed
    assert "load_skill" in mw._allowed
    assert "read_skill_resource" in mw._allowed


def test_empty_allowed_tools_skips_middleware_entirely():
    chain = resolve_middleware(
        {"allowed_tools": []},
        db=MagicMock(),
        chat_id=None,
        extra_allowed_tools={"load_skill"},
    )
    assert not any(isinstance(m, AllowedToolsMiddleware) for m in chain)
