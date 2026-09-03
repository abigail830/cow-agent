"""Platform hook catalog — reusable across agents; agents override params in profile.yaml."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from agent_framework import FunctionMiddleware

from app.middleware.proposal_persist import ProposalPersistMiddleware
from app.middleware.result_truncator import (
    DEFAULT_MAX_OBSERVATION_BYTES,
    ResultTruncatorMiddleware,
)
from app.middleware.sql_validator import SqlValidatorMiddleware
from app.middleware.sql_viz import SqlVizMiddleware
from app.platform.hook_context import HookBuildContext

logger = logging.getLogger(__name__)

HookFactory = Callable[[dict[str, Any], HookBuildContext], FunctionMiddleware | None]


@dataclass(frozen=True)
class HookSpec:
    description: str
    defaults: dict[str, Any] = field(default_factory=dict)
    factory: HookFactory | None = None
    requires_chat: bool = False
    requires_session_store: bool = False


def _build_sql_validator(params: dict[str, Any], _ctx: HookBuildContext) -> FunctionMiddleware:
    return SqlValidatorMiddleware(max_rows=int(params["max_rows"]))


def _build_result_truncator(params: dict[str, Any], _ctx: HookBuildContext) -> FunctionMiddleware:
    return ResultTruncatorMiddleware(max_observation_bytes=int(params["max_observation_bytes"]))


def _build_sql_viz(params: dict[str, Any], _ctx: HookBuildContext) -> FunctionMiddleware:
    return SqlVizMiddleware(
        auto=bool(params.get("auto", False)),
        min_rows=int(params.get("min_rows", 3)),
    )


def _build_proposal_persist(_params: dict[str, Any], ctx: HookBuildContext) -> FunctionMiddleware | None:
    if ctx.db is None or ctx.chat_id is None or ctx.session_store is None:
        logger.warning("proposal_persist hook skipped — missing db, chat_id, or session_store")
        return None
    return ProposalPersistMiddleware(ctx.db, ctx.session_store, chat_id=ctx.chat_id)


# Register platform hooks here. Agents enable by name in profile.yaml hooks: section.
HOOK_CATALOG: dict[str, HookSpec] = {
    "sql_validator": HookSpec(
        description="Pre-tool: read-only SQL validation and LIMIT injection for SQL run_query tools",
        defaults={"max_rows": 2000},
        factory=_build_sql_validator,
    ),
    "result_truncator": HookSpec(
        description="Post-tool: truncate large SQL run_query results for the model",
        defaults={"max_observation_bytes": DEFAULT_MAX_OBSERVATION_BYTES},
        factory=_build_result_truncator,
    ),
    "sql_viz": HookSpec(
        description=(
            "Post-tool (register last in hooks): cache SQL rows for visualization tools. "
            "Charts render only when the model calls suggest_visualization "
            "(set auto: true to also auto-queue after each query). "
            "Requires list_sql_results and suggest_visualization in allowed_tools."
        ),
        defaults={"auto": False, "min_rows": 3},
        factory=_build_sql_viz,
    ),
    "proposal_persist": HookSpec(
        description=(
            "Post-tool: persist proposal_draft to chat session after draft write tools, "
            "render_preview, or generate_document."
        ),
        defaults={},
        factory=_build_proposal_persist,
        requires_chat=True,
        requires_session_store=True,
    ),
}


def merge_hook_params(name: str, overrides: dict[str, Any] | None) -> dict[str, Any]:
    spec = HOOK_CATALOG.get(name)
    if spec is None:
        return dict(overrides or {})
    merged = dict(spec.defaults)
    if overrides:
        merged.update(overrides)
    return merged


def build_hook_middleware(
    name: str,
    params: dict[str, Any],
    ctx: HookBuildContext | None = None,
) -> FunctionMiddleware | None:
    spec = HOOK_CATALOG.get(name)
    if spec is None or spec.factory is None:
        return None
    build_ctx = ctx or HookBuildContext()
    if spec.requires_chat and (build_ctx.db is None or build_ctx.chat_id is None):
        logger.warning("Hook %r skipped — requires chat db context", name)
        return None
    if spec.requires_session_store and build_ctx.session_store is None:
        logger.warning("Hook %r skipped — requires session_store", name)
        return None
    return spec.factory(params, build_ctx)
