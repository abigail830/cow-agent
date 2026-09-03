"""Assemble agent middleware pipeline from profile config."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from agent_framework import FunctionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.allowed_tools import AllowedToolsMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.stop_requested import StopRequestedMiddleware
from app.platform.allowed_tools import runtime_function_allowlist
from app.platform.hook_catalog import HOOK_CATALOG, build_hook_middleware
from app.platform.hook_config import normalize_hooks
from app.platform.hook_context import HookBuildContext
from app.platform.session_store import SessionStore

logger = logging.getLogger(__name__)


def resolve_middleware(
    config: dict[str, Any] | None,
    db: AsyncSession,
    *,
    chat_id: uuid.UUID | None,
    session_store: SessionStore | None = None,
    extra_allowed_tools: set[str] | None = None,
    stop_event: asyncio.Event | None = None,
) -> list:
    cfg = config or {}
    middleware: list = []
    hook_ctx = HookBuildContext(db=db, chat_id=chat_id, session_store=session_store)

    if stop_event is not None:
        middleware.append(StopRequestedMiddleware(stop_event))

    allowed_entries = list(cfg.get("allowed_tools") or [])
    allowlist = runtime_function_allowlist(allowed_entries)
    if allowlist is not None:
        if extra_allowed_tools:
            allowlist = set(allowlist) | extra_allowed_tools
        middleware.append(AllowedToolsMiddleware(allowlist))

    legacy_guardrails = cfg.get("guardrails")
    for hook_name, params in normalize_hooks(cfg.get("hooks"), legacy_guardrails=legacy_guardrails):
        if hook_name not in HOOK_CATALOG:
            logger.warning("Unknown hook %r — add it to app.platform.hook_catalog.HOOK_CATALOG", hook_name)
            continue
        built = build_hook_middleware(hook_name, params, hook_ctx)
        if built is not None:
            middleware.append(built)

    if chat_id is not None:
        middleware.append(AuditMiddleware(db, chat_id=chat_id))

    return middleware
