"""MCP tools must be registered on Agent.mcp_tools so run() exposes postgres_* functions."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from agent_framework import MCPStdioTool

from app.platform.agent_factory import AgentFactory


@pytest.mark.asyncio
async def test_build_attaches_mcp_tools_to_agent():
    agent_id = UUID("00000000-0000-0000-0000-000000000001")
    mcp_tool = MCPStdioTool(
        name="postgres",
        command="echo",
        args=["ok"],
        description="test postgres mcp",
        allowed_tools=["run_query"],
    )

    mock_row = MagicMock()
    mock_row.model_provider = "azure_anthropic"
    mock_row.model_name = "claude-test"
    mock_row.name = "test-agent"
    mock_row.instructions = "test"
    mock_row.config = {"allowed_tools": ["postgres_run_query"]}

    mock_agent = MagicMock()
    mock_agent.mcp_tools = []

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
        mcp_reg_cls.return_value.resolve_for_agent = AsyncMock(return_value=[mcp_tool])

        created: dict = {}

        def capture_create_agent(**kwargs):
            created.update(kwargs)
            agent = MagicMock()
            tools = kwargs.get("tools") or []
            agent.mcp_tools = [t for t in tools if isinstance(t, MCPStdioTool)]
            return agent

        model_reg_cls.return_value.create_agent.side_effect = capture_create_agent

        db = MagicMock()
        bundle = await AgentFactory(db).build(agent_id)

    assert mcp_tool in created.get("tools", [])
    assert bundle.agent.mcp_tools == [mcp_tool]
