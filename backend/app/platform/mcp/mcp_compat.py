"""Bridge mcp 1.x (camelCase) and mcp 2.x (snake_case) for agent-framework MCP tools."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_applied = False


def apply_mcp_compat_patches() -> None:
    """Expose protocolVersion on InitializeResult when only protocol_version exists (mcp 2.x)."""
    global _applied
    if _applied:
        return
    _applied = True

    try:
        from mcp import types
    except ImportError:
        return

    init_result = types.InitializeResult
    if hasattr(init_result, "protocolVersion"):
        return
    if not hasattr(init_result, "protocol_version"):
        return

    init_result.protocolVersion = property(lambda self: self.protocol_version)  # type: ignore[attr-defined]
    logger.info("Applied MCP compat patch: InitializeResult.protocolVersion -> protocol_version")
