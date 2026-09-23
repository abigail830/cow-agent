"""platform_time is injected into every agent build."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.platform.agent.agent_factory import AgentFactory
from app.platform.doc_retrieval.tools import DOC_RETRIEVAL_TOOL_NAMES
from app.platform.hooks.allowed_tools import AllowedToolsMiddleware
from app.platform.hooks.hook_registry import resolve_middleware


def _tool_names(tools: list) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        name = getattr(tool, "name", None)
        if name:
            names.add(name)
    return names


@pytest.mark.asyncio
async def test_agent_factory_injects_platform_time():
    agent_id = UUID("00000000-0000-0000-0000-000000000099")
    mock_row = MagicMock()
    mock_row.model_provider = "azure_anthropic"
    mock_row.model_name = "claude-test"
    mock_row.name = "test-agent"
    mock_row.slug = "content-studio"
    mock_row.instructions = "test"
    mock_row.config = {"allowed_tools": ["sandbox_run_command"]}

    created: dict = {}
    middleware_kwargs: dict = {}

    def capture_middleware(*args, **kwargs):
        middleware_kwargs.update(kwargs)
        return []

    with (
        patch.object(AgentFactory, "get_agent_row", AsyncMock(return_value=mock_row)),
        patch(
            "app.platform.agent.agent_factory.create_postgres_history_provider",
            return_value=MagicMock(),
        ),
        patch("app.platform.agent.agent_factory.SkillRegistry") as skill_reg_cls,
        patch("app.platform.agent.agent_factory.ToolRegistry") as tool_reg_cls,
        patch("app.platform.agent.agent_factory.McpRegistry") as mcp_reg_cls,
        patch("app.platform.agent.agent_factory.ModelProviderRegistry") as model_reg_cls,
        patch("app.platform.agent.agent_factory.resolve_middleware", side_effect=capture_middleware),
    ):
        skill_reg_cls.return_value.resolve_provider_for_agent = AsyncMock(return_value=None)
        tool_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[])
        mcp_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[])
        model_reg_cls.return_value.create_agent.side_effect = lambda **kwargs: (
            created.update(kwargs) or MagicMock()
        )

        await AgentFactory(MagicMock()).build(
            agent_id,
            chat_id=UUID("11111111-1111-1111-1111-111111111111"),
        )

    names = _tool_names(created.get("tools"))
    assert "platform_time" in names
    assert "platform_time" in middleware_kwargs.get("extra_allowed_tools", set())
    assert DOC_RETRIEVAL_TOOL_NAMES.issubset(names)
    assert DOC_RETRIEVAL_TOOL_NAMES.issubset(middleware_kwargs.get("extra_allowed_tools", set()))
    assert "analyze_image" not in names
    assert "inline_attachment" not in names
    assert "read_attachment" not in names


def test_platform_time_in_allowlist_with_profile_tools():
    chain = resolve_middleware(
        {"allowed_tools": ["web_search_prime"]},
        db=MagicMock(),
        chat_id=None,
        extra_allowed_tools={"platform_time"},
    )
    allowed = [m for m in chain if isinstance(m, AllowedToolsMiddleware)]
    assert len(allowed) == 1
    assert "platform_time" in allowed[0]._allowed
    assert "web_search_prime" in allowed[0]._allowed
