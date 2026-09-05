"""Helpers for connecting MCP tools during long-lived SSE streams."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from app.platform.agent.agent_bundle import AgentBundle

logger = logging.getLogger(__name__)


async def iter_mcp_connect_keepalive(
    bundle: AgentBundle,
    *,
    interval_seconds: float = 12.0,
) -> AsyncIterator[dict[str, object]]:
    """Yield SSE keepalive events while MCP servers connect.

    Vercel and other proxies may drop idle streaming responses. Content Studio
    connects two remote MCP servers sequentially, which can take 10–30s before
    the first model token — emit periodic pings during that window.
    """
    if bundle.mcp_pool_handle is not None:
        return
    servers = [getattr(tool, "name", type(tool).__name__) for tool in bundle.agent.mcp_tools]
    if servers:
        yield {
            "event": "status",
            "data": {"phase": "connecting_mcp", "servers": servers},
        }

    connect_task = asyncio.create_task(bundle.__aenter__())
    try:
        while not connect_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(connect_task), timeout=interval_seconds)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": {"phase": "connecting_mcp"}}
        connect_task.result()
    except BaseException:
        if not connect_task.done():
            connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connect_task
        with contextlib.suppress(Exception):
            await bundle.__aexit__(None, None, None)
        raise


async def disconnect_bundle(bundle: AgentBundle) -> None:
    await bundle.__aexit__(None, None, None)
