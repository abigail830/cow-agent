"""Per-user, per-chat MCP connection pool."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600.0

McpToolFactory = Callable[[], Awaitable[list[Any]]]


@dataclass(frozen=True, slots=True)
class McpPoolKey:
    user_id: uuid.UUID
    chat_id: uuid.UUID
    agent_id: uuid.UUID
    config_fingerprint: str


@dataclass(slots=True)
class McpPoolHandle:
    key: McpPoolKey
    tools: list[Any]
    from_cache: bool


@dataclass(slots=True)
class _PoolEntry:
    tools: list[Any]
    last_used_at: float


class McpConnectionPool:
    """Reuse connected MCP tools within one user + chat + agent scope."""

    def __init__(self, *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[McpPoolKey, _PoolEntry] = {}
        self._locks: dict[McpPoolKey, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def acquire(self, key: McpPoolKey, factory: McpToolFactory) -> McpPoolHandle:
        lock = await self._lock_for(key)
        await lock.acquire()
        try:
            entry = self._entries.get(key)
            if entry is not None and not self._expired(entry) and self._tools_connected(entry.tools):
                entry.last_used_at = time.monotonic()
                logger.debug(
                    "MCP pool hit user=%s chat=%s agent=%s",
                    key.user_id,
                    key.chat_id,
                    key.agent_id,
                )
                return McpPoolHandle(key=key, tools=entry.tools, from_cache=True)

            if entry is not None:
                await self._disconnect_tools(entry.tools)
                self._entries.pop(key, None)

            tools = list(await factory())
            if tools:
                await self._connect_tools(tools)
            self._entries[key] = _PoolEntry(tools=tools, last_used_at=time.monotonic())
            logger.info(
                "MCP pool miss user=%s chat=%s agent=%s servers=%d",
                key.user_id,
                key.chat_id,
                key.agent_id,
                len(tools),
            )
            return McpPoolHandle(key=key, tools=tools, from_cache=False)
        except Exception:
            if lock.locked():
                lock.release()
            raise

    async def release(self, handle: McpPoolHandle) -> None:
        entry = self._entries.get(handle.key)
        if entry is not None:
            entry.last_used_at = time.monotonic()
        lock = self._locks.get(handle.key)
        if lock is not None and lock.locked():
            lock.release()

    async def invalidate(self, key: McpPoolKey) -> None:
        lock = await self._lock_for(key)
        async with lock:
            entry = self._entries.pop(key, None)
            if entry is not None:
                await self._disconnect_tools(entry.tools)

    async def invalidate_chat(self, chat_id: uuid.UUID) -> None:
        keys = [key for key in self._entries if key.chat_id == chat_id]
        for key in keys:
            await self.invalidate(key)

    async def _lock_for(self, key: McpPoolKey) -> asyncio.Lock:
        async with self._global_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def _expired(self, entry: _PoolEntry) -> bool:
        return (time.monotonic() - entry.last_used_at) > self._ttl_seconds

    @staticmethod
    def _tools_connected(tools: list[Any]) -> bool:
        if not tools:
            return True
        return all(getattr(tool, "is_connected", False) for tool in tools)

    @staticmethod
    async def _connect_tools(tools: list[Any]) -> None:
        async def connect_one(tool: Any) -> None:
            if getattr(tool, "is_connected", False):
                return
            connect = getattr(tool, "connect", None)
            if connect is None:
                await tool.__aenter__()
                return
            await connect()

        await asyncio.gather(*(connect_one(tool) for tool in tools))

    @staticmethod
    async def _disconnect_tools(tools: list[Any]) -> None:
        for tool in reversed(tools):
            close = getattr(tool, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()
                continue
            with contextlib.suppress(Exception):
                await tool.__aexit__(None, None, None)


_pool: McpConnectionPool | None = None


def get_mcp_connection_pool() -> McpConnectionPool:
    global _pool
    if _pool is None:
        _pool = McpConnectionPool()
    return _pool


def reset_mcp_connection_pool() -> None:
    global _pool
    _pool = None
