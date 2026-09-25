"""Tests for chat MCP warmup."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.platform.chat.run_service import ChatRunService
from app.platform.mcp.mcp_pool import McpPoolHandle, McpPoolKey


@pytest.mark.asyncio
async def test_warmup_chat_acquires_and_releases_mcp_pool() -> None:
    db = AsyncMock()
    chat = AsyncMock()
    chat.id = uuid.uuid4()
    chat.user_id = uuid.uuid4()
    chat.agent_id = uuid.uuid4()

    pool_key = McpPoolKey(
        user_id=chat.user_id,
        chat_id=chat.id,
        agent_id=chat.agent_id,
        config_fingerprint="fp",
    )
    handle = McpPoolHandle(key=pool_key, tools=[], from_cache=False)

    service = ChatRunService(db)
    service._sessions.get_or_create = AsyncMock()  # type: ignore[method-assign]
    service._factory.get_agent_row = AsyncMock(return_value=AsyncMock(config={}))  # type: ignore[method-assign]
    service._factory._mcp.config_fingerprint = AsyncMock(return_value="fp")  # type: ignore[method-assign]
    service._factory._mcp.resolve_for_agent = AsyncMock(return_value=[])  # type: ignore[method-assign]

    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=handle)
    mock_pool.release = AsyncMock()

    with patch("app.platform.chat.run_service.get_mcp_connection_pool", return_value=mock_pool):
        await service.warmup_chat(chat)

    service._sessions.get_or_create.assert_awaited_once_with(chat.id)
    mock_pool.acquire.assert_awaited_once()
    mock_pool.release.assert_awaited_once_with(handle)
