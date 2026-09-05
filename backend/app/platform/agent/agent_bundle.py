import logging
from dataclasses import dataclass, field
from contextlib import AsyncExitStack

from agent_framework import Agent

logger = logging.getLogger(__name__)


@dataclass
class AgentBundle:
    """Agent plus MCP lifecycle — enter before run, exit after."""

    agent: Agent
    mcp_pool_handle: object | None = None
    _stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    @property
    def mcp_from_cache(self) -> bool:
        handle = self.mcp_pool_handle
        return bool(handle and getattr(handle, "from_cache", False))

    async def __aenter__(self) -> Agent:
        if self.mcp_pool_handle is not None:
            return self.agent
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
        if self.mcp_pool_handle is not None:
            from app.platform.mcp.mcp_pool import get_mcp_connection_pool

            await get_mcp_connection_pool().release(self.mcp_pool_handle)
            return
        await self._stack.aclose()
