import hashlib
import json
import logging
import os
import uuid
from typing import Any

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool
from httpx import AsyncClient, Timeout
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AgentMcpServer, McpServer
from app.platform.agent.allowed_tools import mcp_remote_tools_for_server
from app.platform.mcp.mcp_config import resolve_runtime_config_safe
from app.platform.agent.profile_loader import mcp_tool_name
from app.platform.auth.secret_store import SecretStoreError
from app.platform.integrations.token_service import IntegrationTokenService
from app.platform.mcp.native_db import build_mysql_tools, build_postgres_tools

logger = logging.getLogger(__name__)
IS_VERCEL = os.getenv("VERCEL") == "1"


def _mcp_http_client(headers: dict[str, str] | None = None) -> AsyncClient:
    timeout_seconds = float(get_settings().mcp_http_request_timeout)
    return AsyncClient(
        headers=dict(headers or {}),
        follow_redirects=True,
        timeout=Timeout(timeout_seconds, read=timeout_seconds * 10),
    )


def _integration_provider_from_config(config: dict[str, Any]) -> str | None:
    auth_mode = str(config.get("auth") or "").strip().lower()
    integration = str(config.get("integration") or "").strip().lower()
    if auth_mode == "oauth" and integration:
        return integration
    return None


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
        user_id: uuid.UUID | None = None,
    ) -> list[Any]:
        profile_allowed = list((agent_config or {}).get("allowed_tools") or [])
        tools: list[Any] = []
        for row in await self._agent_mcp_server_rows(agent_id):
            tool = await self._build_tool(row, profile_allowed=profile_allowed, user_id=user_id)
            if tool is None:
                continue
            if isinstance(tool, list):
                tools.extend(tool)
            else:
                tools.append(tool)
        return tools

    async def config_fingerprint(self, agent_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> str:
        rows = await self._agent_mcp_server_rows(agent_id)
        if not rows:
            return "none"
        parts: list[str] = []
        token_service = IntegrationTokenService(self._db) if user_id is not None else None
        for row in rows:
            connection = row.connection if isinstance(row.connection, dict) else {}
            parts.append(f"{row.id}:{row.name}:{json.dumps(connection, sort_keys=True, default=str)}")
            if token_service is not None:
                try:
                    config = resolve_runtime_config_safe(connection)
                except SecretStoreError:
                    continue
                provider = _integration_provider_from_config(config)
                if provider:
                    version = await token_service.connection_version(user_id=user_id, provider=provider)
                    parts.append(f"oauth:{provider}:{version}")
        digest = hashlib.sha256("\n".join(parts).encode()).hexdigest()
        return digest[:32]

    async def _agent_mcp_server_rows(self, agent_id: uuid.UUID) -> list[McpServer]:
        result = await self._db.execute(
            select(McpServer)
            .join(AgentMcpServer, AgentMcpServer.mcp_server_id == McpServer.id)
            .where(AgentMcpServer.agent_id == agent_id)
            .order_by(McpServer.name)
        )
        return list(result.scalars().all())

    async def _build_tool(
        self,
        row: McpServer,
        *,
        profile_allowed: list[str] | None = None,
        user_id: uuid.UUID | None = None,
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
        integration_provider = _integration_provider_from_config(config)

        if transport == "http" or config.get("url"):
            url = config.get("url")
            if not url:
                logger.warning("MCP server %s missing url", row.name)
                return None
            request_timeout = get_settings().mcp_http_request_timeout

            if integration_provider:
                if user_id is None:
                    logger.warning("Skipping OAuth MCP server %s — missing user_id", tool_name)
                    return None
                token_service = IntegrationTokenService(self._db)
                access_token = await token_service.get_valid_access_token(
                    user_id=user_id,
                    provider=integration_provider,
                )
                if not access_token:
                    logger.info(
                        "Skipping OAuth MCP server %s — user %s not connected to %s",
                        tool_name,
                        user_id,
                        integration_provider,
                    )
                    return None
                static_headers = {"Authorization": f"Bearer {access_token}"}
                http_client = _mcp_http_client(static_headers)
                return MCPStreamableHTTPTool(
                    name=tool_name,
                    url=url,
                    description=description,
                    allowed_tools=mcp_allowed,
                    request_timeout=request_timeout,
                    http_client=http_client,
                    header_provider=lambda _kwargs, h=static_headers: dict(h),
                )

            headers = config.get("headers")
            if headers:
                static_headers = dict(headers)
                auth = static_headers.get("Authorization", "")
                if not auth.strip():
                    logger.error("MCP server %s has empty Authorization after decrypt", row.name)
                else:
                    logger.info(
                        "MCP server %s auth configured (Authorization length=%d)",
                        row.name,
                        len(auth),
                    )
                http_client = _mcp_http_client(static_headers)
                return MCPStreamableHTTPTool(
                    name=tool_name,
                    url=url,
                    description=description,
                    allowed_tools=mcp_allowed,
                    request_timeout=request_timeout,
                    http_client=http_client,
                    header_provider=lambda _kwargs, h=static_headers: dict(h),
                )
            return MCPStreamableHTTPTool(
                name=tool_name,
                url=url,
                description=description,
                allowed_tools=mcp_allowed,
                request_timeout=request_timeout,
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
