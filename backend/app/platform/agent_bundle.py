from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from agent_framework import Agent


@dataclass
class AgentBundle:
    """Agent plus MCP lifecycle — enter before run, exit after."""

    agent: Agent
    _stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    async def __aenter__(self) -> Agent:
        for mcp_tool in self.agent.mcp_tools:
            await self._stack.enter_async_context(mcp_tool)
        return self.agent

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._stack.aclose()
