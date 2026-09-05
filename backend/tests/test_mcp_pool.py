"""MCP connection pool tests."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.platform.mcp.mcp_pool import McpConnectionPool, McpPoolKey, reset_mcp_connection_pool


class FakeMcpTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_connected = False
        self.connect_calls = 0
        self.close_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1
        self.is_connected = True

    async def close(self) -> None:
        self.close_calls += 1
        self.is_connected = False


@pytest.fixture(autouse=True)
def _reset_pool() -> None:
    reset_mcp_connection_pool()
    yield
    reset_mcp_connection_pool()


def _key(suffix: str = "a") -> McpPoolKey:
    return McpPoolKey(
        user_id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        config_fingerprint=f"fp-{suffix}",
    )


@pytest.mark.asyncio
async def test_pool_reuses_tools_within_same_scope() -> None:
    pool = McpConnectionPool(ttl_seconds=600)
    key = _key()
    created: list[FakeMcpTool] = []

    async def factory() -> list[FakeMcpTool]:
        tool = FakeMcpTool("hybrid-search")
        created.append(tool)
        return [tool]

    first = await pool.acquire(key, factory)
    await pool.release(first)

    second = await pool.acquire(key, factory)
    await pool.release(second)

    assert first.from_cache is False
    assert second.from_cache is True
    assert len(created) == 1
    assert created[0].connect_calls == 1
    assert created[0].close_calls == 0


@pytest.mark.asyncio
async def test_pool_does_not_reuse_across_chats() -> None:
    pool = McpConnectionPool(ttl_seconds=600)
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    key_a = McpPoolKey(user_id, uuid.uuid4(), agent_id, "fp")
    key_b = McpPoolKey(user_id, uuid.uuid4(), agent_id, "fp")
    created: list[FakeMcpTool] = []

    async def factory() -> list[FakeMcpTool]:
        tool = FakeMcpTool("hybrid-search")
        created.append(tool)
        return [tool]

    handle_a = await pool.acquire(key_a, factory)
    await pool.release(handle_a)
    handle_b = await pool.acquire(key_b, factory)
    await pool.release(handle_b)

    assert handle_b.from_cache is False
    assert len(created) == 2


@pytest.mark.asyncio
async def test_pool_does_not_reuse_across_users() -> None:
    pool = McpConnectionPool(ttl_seconds=600)
    chat_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    key_a = McpPoolKey(uuid.uuid4(), chat_id, agent_id, "fp")
    key_b = McpPoolKey(uuid.uuid4(), chat_id, agent_id, "fp")
    created: list[FakeMcpTool] = []

    async def factory() -> list[FakeMcpTool]:
        created.append(FakeMcpTool("hybrid-search"))
        return created[-1:]

    await pool.release(await pool.acquire(key_a, factory))
    second = await pool.acquire(key_b, factory)
    await pool.release(second)

    assert second.from_cache is False
    assert len(created) == 2


@pytest.mark.asyncio
async def test_invalidate_closes_tools() -> None:
    pool = McpConnectionPool(ttl_seconds=600)
    key = _key()
    tool = FakeMcpTool("zhipu")

    async def factory() -> list[FakeMcpTool]:
        return [tool]

    handle = await pool.acquire(key, factory)
    await pool.release(handle)
    await pool.invalidate(key)

    assert tool.close_calls == 1
    assert tool.is_connected is False

    handle2 = await pool.acquire(key, factory)
    await pool.release(handle2)
    assert handle2.from_cache is False
    assert tool.connect_calls == 2


@pytest.mark.asyncio
async def test_parallel_connect_on_miss() -> None:
    pool = McpConnectionPool(ttl_seconds=600)
    key = _key()
    tools = [FakeMcpTool("a"), FakeMcpTool("b")]

    async def factory() -> list[FakeMcpTool]:
        return tools

    started = asyncio.get_event_loop().time()
    handle = await pool.acquire(key, factory)
    elapsed = asyncio.get_event_loop().time() - started
    await pool.release(handle)

    assert all(tool.is_connected for tool in tools)
    assert elapsed < 0.5
