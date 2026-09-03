import logging
import os
import uuid
from typing import Any

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentMcpServer, McpServer
from app.platform.allowed_tools import mcp_remote_tools_for_server
from app.platform.mcp_config import resolve_runtime_config_safe
from app.platform.profile_loader import mcp_tool_name
from app.platform.secret_store import SecretStoreError
from app.tools.database import build_mysql_tools, build_postgres_tools

logger = logging.getLogger(__name__)
IS_VERCEL = os.getenv("VERCEL") == "1"


class McpRegistry:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_servers(self) -> list[McpServer]:
        result = await self._db.execute(select(McpServer).order_by(McpServer.name))
        return list(result.scalars().all())

    async def resolve_for_agent(
        self,
        agent_id: uuid.UUID,
        *,
        agent_config: dict | None = None,
    ) -> list[Any]:
        profile_allowed = list((agent_config or {}).get("allowed_tools") or [])
        result = await self._db.execute(
            select(McpServer)
            .join(AgentMcpServer, AgentMcpServer.mcp_server_id == McpServer.id)
            .where(AgentMcpServer.agent_id == agent_id)
            .order_by(McpServer.name)
        )
        tools: list[Any] = []
        for row in result.scalars().all():
            tool = self._build_tool(row, profile_allowed=profile_allowed)
            if tool is None:
                continue
            if isinstance(tool, list):
                tools.extend(tool)
            else:
                tools.append(tool)
        return tools

    def _build_tool(
        self,
        row: McpServer,
        *,
        profile_allowed: list[str] | None = None,
    ) -> MCPStdioTool | MCPStreamableHTTPTool | list[Any] | None:
        try:
            config = resolve_runtime_config_safe(row.connection or {})
        except SecretStoreError:
            logger.exception("MCP server %s has invalid or undecryptable connection", row.name)
            return None

        transport = row.transport or ("http" if config.get("url") else "stdio")
        tool_name = mcp_tool_name(row.name, row.connection)
        description = row.description or f"MCP server: {tool_name}"
        mcp_allowed = mcp_remote_tools_for_server(profile_allowed or [], tool_name)

        if transport == "http" or config.get("url"):
            url = config.get("url")
            if not url:
                logger.warning("MCP server %s missing url", row.name)
                return None
            headers = config.get("headers")
            if headers:
                static_headers = dict(headers)
                return MCPStreamableHTTPTool(
                    name=tool_name,
                    url=url,
                    description=description,
                    allowed_tools=mcp_allowed,
                    header_provider=lambda _kwargs, h=static_headers: dict(h),
                )
            return MCPStreamableHTTPTool(
                name=tool_name,
                url=url,
                description=description,
                allowed_tools=mcp_allowed,
            )

        native = _build_native_db_tools(tool_name, config.get("env") or {}, mcp_allowed)
        if native:
            logger.info(
                "Using in-process database tools%s for MCP server %s",
                " on Vercel" if IS_VERCEL else "",
                tool_name,
            )
            return native

        if IS_VERCEL:
            logger.warning(
                "No in-process database tool mapping for MCP server %s on Vercel",
                tool_name,
            )
            return None

        command = config.get("command")
        if not command:
            logger.warning("MCP server %s missing command", row.name)
            return None
        return MCPStdioTool(
            name=tool_name,
            command=str(command),
            args=list(config.get("args") or []),
            env=config.get("env"),
            description=description,
            allowed_tools=mcp_allowed,
        )


def _build_native_db_tools(
    server_name: str,
    env: dict[str, str],
    allowed_remote_tools: list[str] | None,
) -> list[Any] | None:
    if server_name == "postgres":
        from app.db.readonly_sql import _postgres_has_config

        if not _postgres_has_config(env):
            return None
        return build_postgres_tools(env, allowed_remote_tools=allowed_remote_tools)
    if server_name == "mysql":
        if not env.get("MYSQL_HOST"):
            return None
        return build_mysql_tools(env, allowed_remote_tools=allowed_remote_tools)
    return None
