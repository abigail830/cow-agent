import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from agent_framework import Agent

logger = logging.getLogger(__name__)


@dataclass
class AgentBundle:
    """Agent plus MCP lifecycle — enter before run, exit after."""

    agent: Agent
    _stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    async def __aenter__(self) -> Agent:
        for mcp_tool in self.agent.mcp_tools:
            name = getattr(mcp_tool, "name", type(mcp_tool).__name__)
            url = getattr(mcp_tool, "url", None)
            if url:
                logger.info("Connecting MCP server %s (%s)", name, url)
            else:
                logger.info("Connecting MCP server %s", name)
            await self._stack.enter_async_context(mcp_tool)
            logger.info("Connected MCP server %s", name)
        return self.agent

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._stack.aclose()
