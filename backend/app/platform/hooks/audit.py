"""Structured tool invocation audit logging."""

from __future__ import annotations

import logging
import time
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _tool_kind(context: FunctionInvocationContext) -> str:
    props = context.function.additional_properties or {}
    if props.get("_mcp_remote_name") or props.get("_mcp_normalized_name"):
        return "mcp"
    return "builtin"


def _mcp_audit_fields(context: FunctionInvocationContext) -> dict[str, Any]:
    props = context.function.additional_properties or {}
    fields: dict[str, Any] = {}
    for key in ("_mcp_server_name", "server_name", "_mcp_remote_name", "_mcp_normalized_name"):
        value = props.get(key)
        if isinstance(value, str) and value:
            fields[key.lstrip("_")] = value
    return fields


def _argument_keys(arguments: Any) -> list[str]:
    if isinstance(arguments, dict):
        return sorted(str(k) for k in arguments.keys())
    if hasattr(arguments, "model_dump"):
        try:
            return sorted(str(k) for k in arguments.model_dump().keys())
        except Exception:
            return []
    return []


def _result_ok(result: Any) -> bool:
    if result is None:
        return True
    if isinstance(result, dict):
        if result.get("error"):
            return False
        if result.get("ok") is False:
            return False
    return True


class AuditMiddleware(FunctionMiddleware):
    """Structured audit log for every tool invocation (keys only, no argument values)."""

    def __init__(self, db: AsyncSession, *, chat_id: Any | None) -> None:
        self._db = db
        self._chat_id = chat_id

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        tool_name = context.function.name
        kind = _tool_kind(context)
        arg_keys = _argument_keys(context.arguments)
        audit_base: dict[str, Any] = {
            "audit_event": "tool_invocation",
            "phase": "start",
            "tool_name": tool_name,
            "tool_kind": kind,
            "argument_keys": arg_keys,
        }
        if self._chat_id is not None:
            audit_base["chat_id"] = str(self._chat_id)
        audit_base.update(_mcp_audit_fields(context))

        if kind == "mcp":
            logger.info("tool_invocation_start", extra=audit_base)
        else:
            logger.debug("tool_invocation_start", extra=audit_base)

        started = time.perf_counter()
        await call_next()
        duration_ms = int((time.perf_counter() - started) * 1000)

        if self._chat_id is None:
            return

        finish: dict[str, Any] = {
            **audit_base,
            "phase": "finish",
            "duration_ms": duration_ms,
            "ok": _result_ok(context.result),
        }
        logger.info("tool_invocation_finish", extra=finish)
