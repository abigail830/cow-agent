"""Capture SQL results; optionally auto-queue charts when auto is enabled."""

from __future__ import annotations

import logging
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware

from app.middleware.sql_tools import is_sql_run_query
from app.viz.context import get_run_viz_state, new_call_id
from app.viz.pipeline import build_viz_from_rows
from app.viz.sql_parse import parse_sql_tool_result

logger = logging.getLogger(__name__)


class SqlVizMiddleware(FunctionMiddleware):
    """Post-tool: cache full SQL rows; auto-queue charts only when auto=True."""

    def __init__(self, *, auto: bool = False, min_rows: int = 3) -> None:
        self._auto = auto
        self._min_rows = min_rows
        self._call_ids: dict[int, str] = {}

    def _call_key(self, context: FunctionInvocationContext) -> int:
        return id(context)

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        if not is_sql_run_query(context.function.name):
            await call_next()
            return

        call_key = self._call_key(context)
        call_id = getattr(context, "call_id", None) or self._call_ids.get(call_key) or new_call_id()
        self._call_ids[call_key] = str(call_id)

        await call_next()

        state = get_run_viz_state()
        if state is None:
            return

        try:
            rows, columns = parse_sql_tool_result(context.result)
            if not rows:
                return

            state.store_sql(
                call_id=str(call_id),
                tool_name=context.function.name,
                rows=rows,
                columns=columns,
            )

            if not self._auto or len(rows) < self._min_rows:
                return

            result = build_viz_from_rows(rows, columns, intent="auto")
            if result.status != "skipped":
                state.queue_viz(result, source_call_id=str(call_id))
        except Exception:
            logger.exception("SqlVizMiddleware failed for %s", context.function.name)
        finally:
            self._call_ids.pop(call_key, None)
