"""Pre-tool SQL validation — MAF equivalent of Claude Agent SDK PreToolUse hook."""

from __future__ import annotations

from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware, MiddlewareTermination
from pydantic import BaseModel

from app.guardrails.sql_rules import validate_sql
from app.middleware.sql_tools import is_sql_run_query


def _extract_query(arguments: Any) -> str | None:
    if isinstance(arguments, dict):
        value = arguments.get("query", arguments.get("sql"))
        return str(value) if value is not None else None
    if isinstance(arguments, BaseModel):
        value = getattr(arguments, "query", None) or getattr(arguments, "sql", None)
        return str(value) if value is not None else None
    return None


def _apply_query(arguments: Any, query: str) -> Any:
    if isinstance(arguments, dict):
        updated = dict(arguments)
        key = "sql" if "sql" in updated and "query" not in updated else "query"
        updated[key] = query
        return updated
    if isinstance(arguments, BaseModel):
        key = "sql" if hasattr(arguments, "sql") and not hasattr(arguments, "query") else "query"
        return arguments.model_copy(update={key: query})
    return arguments


class SqlValidatorMiddleware(FunctionMiddleware):
    """Deny or rewrite SQL run_query calls (postgres / mysql) using guardrails.sql rules."""

    def __init__(self, *, max_rows: int = 2000) -> None:
        self._max_rows = max_rows

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        tool_name = context.function.name
        if not is_sql_run_query(tool_name):
            await call_next()
            return

        query = _extract_query(context.arguments)
        if query is None:
            context.result = {"error": "Missing required argument: query"}
            raise MiddlewareTermination("SQL validator blocked tool: missing query")

        result = validate_sql(query, max_rows=self._max_rows)
        if not result.ok:
            context.result = {
                "ok": False,
                "error": result.reason,
                "hint": (
                    "Submit a single read-only SELECT (WITH/CTE allowed). "
                    "Names like Co-Create belong inside quoted strings, e.g. ILIKE '%co-create%'."
                ),
                "function": tool_name,
            }
            raise MiddlewareTermination(f"SQL validation denied: {result.reason}")

        if result.normalized_sql != query:
            context.arguments = _apply_query(context.arguments, result.normalized_sql)

        await call_next()
