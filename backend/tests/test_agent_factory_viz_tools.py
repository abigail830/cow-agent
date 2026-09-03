"""Visualization tools must respect profile allowed_tools (not only middleware)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.platform.agent_factory import AgentFactory


def _tool_names(tools: list) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        name = getattr(tool, "name", None)
        if name:
            names.add(name)
    return names


@pytest.mark.asyncio
async def test_viz_tools_omitted_when_not_in_allowed_tools():
    agent_id = UUID("00000000-0000-0000-0000-000000000002")
    mock_row = MagicMock()
    mock_row.model_provider = "azure_anthropic"
    mock_row.model_name = "claude-test"
    mock_row.name = "test-agent"
    mock_row.instructions = "test"
    mock_row.config = {
        "allowed_tools": ["postgres_query_data"],
        "hooks": {"sql_viz": {"auto": False, "min_rows": 3}},
    }

    created: dict = {}

    with (
        patch.object(AgentFactory, "get_agent_row", AsyncMock(return_value=mock_row)),
        patch("app.platform.agent_factory.PostgresHistoryProvider"),
        patch("app.platform.agent_factory.SkillRegistry") as skill_reg_cls,
        patch("app.platform.agent_factory.ToolRegistry") as tool_reg_cls,
        patch("app.platform.agent_factory.McpRegistry") as mcp_reg_cls,
        patch("app.platform.agent_factory.ModelProviderRegistry") as model_reg_cls,
        patch("app.platform.agent_factory.resolve_middleware", return_value=[]),
    ):
        skill_reg_cls.return_value.resolve_provider_for_agent = AsyncMock(return_value=None)
        tool_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[])
        mcp_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[])
        model_reg_cls.return_value.create_agent.side_effect = lambda **kwargs: (
            created.update(kwargs) or MagicMock()
        )

        await AgentFactory(MagicMock()).build(agent_id)

    names = _tool_names(created.get("tools"))
    assert "suggest_visualization" not in names
    assert "list_sql_results" not in names


@pytest.mark.asyncio
async def test_viz_tools_included_when_allowed_and_sql_viz_hook_present():
    agent_id = UUID("00000000-0000-0000-0000-000000000003")
    mock_row = MagicMock()
    mock_row.model_provider = "azure_anthropic"
    mock_row.model_name = "claude-test"
    mock_row.name = "test-agent"
    mock_row.instructions = "test"
    mock_row.config = {
        "allowed_tools": ["list_sql_results", "suggest_visualization"],
        "hooks": {"sql_viz": {"auto": False, "min_rows": 3}},
    }

    created: dict = {}

    with (
        patch.object(AgentFactory, "get_agent_row", AsyncMock(return_value=mock_row)),
        patch("app.platform.agent_factory.PostgresHistoryProvider"),
        patch("app.platform.agent_factory.SkillRegistry") as skill_reg_cls,
        patch("app.platform.agent_factory.ToolRegistry") as tool_reg_cls,
        patch("app.platform.agent_factory.McpRegistry") as mcp_reg_cls,
        patch("app.platform.agent_factory.ModelProviderRegistry") as model_reg_cls,
        patch("app.platform.agent_factory.resolve_middleware", return_value=[]),
    ):
        skill_reg_cls.return_value.resolve_provider_for_agent = AsyncMock(return_value=None)
        tool_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[])
        mcp_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[])
        model_reg_cls.return_value.create_agent.side_effect = lambda **kwargs: (
            created.update(kwargs) or MagicMock()
        )

        await AgentFactory(MagicMock()).build(agent_id)

    names = _tool_names(created.get("tools"))
    assert "suggest_visualization" in names
    assert "list_sql_results" in names
