"""OBDA — generic source table query and ref traversal."""

from __future__ import annotations

import re
from typing import Any

from app.yl_worker2.db import rows_to_dicts, yl_connect
from app.yl_worker2.runtime.ontology_config import (
    get_table_column_aliases,
    load_sources_config,
    resolve_ref_rule,
    resolve_table_column,
    table_allowed,
)
from app.yl_worker2.runtime.query_compiler import QueryCompileError, compile_where
from app.yl_worker2.runtime.schema_introspect import fetch_describe_table

_TABLE_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_table_ident(name: str) -> str | None:
    n = (name or "").strip().lower()
    if not n or not _TABLE_IDENT.match(n):
        return None
    if not table_allowed(n):
        return None
    return n


async def _allowed_columns(table_name: str) -> set[str]:
    desc = await fetch_describe_table(table_name)
    if desc.get("status") != "ok":
        return set()
    return {c["column_name"] for c in desc.get("columns") or []}


async def fetch_query_source(
    table: str,
    *,
    where: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> dict:
    table_name = _validate_table_ident(table)
    if not table_name:
        return {
            "table": table,
            "status": "error",
            "error": "table_not_in_whitelist",
        }

    allowed = await _allowed_columns(table_name)
    if not allowed:
        return {"table": table_name, "status": "error", "error": "table_not_found_or_empty"}

    column_aliases = get_table_column_aliases(table_name, allowed)
    cfg = load_sources_config()
    lim = min(max(limit or cfg["default_limit"], 1), cfg["max_limit"])

    if select:
        cols = []
        for c in select:
            resolved = resolve_table_column(
                table_name, c, allowed, column_aliases=column_aliases
            )
            if resolved not in allowed:
                return {
                    "table": table_name,
                    "status": "error",
                    "error": f"invalid_select_column:{c}",
                }
            cols.append(resolved)
        select_sql = ", ".join(cols)
    else:
        select_sql = "*"

    try:
        where_sql, args, _ = compile_where(
            where, allowed, column_aliases=column_aliases
        )
    except QueryCompileError as exc:
        return {"table": table_name, "status": "error", "error": str(exc)}

    order_clause = ""
    if order_by:
        ob = order_by.strip()
        col = ob.lstrip("-")
        resolved = resolve_table_column(
            table_name, col, allowed, column_aliases=column_aliases
        )
        if resolved not in allowed:
            return {
                "table": table_name,
                "status": "error",
                "error": f"invalid_order_by:{order_by}",
            }
        direction = "DESC" if ob.startswith("-") else "ASC"
        order_clause = f" ORDER BY {resolved} {direction}"

    sql = f"SELECT {select_sql} FROM {table_name} WHERE {where_sql}{order_clause} LIMIT {lim}"

    conn = await yl_connect()
    try:
        rows = await conn.fetch(sql, *args)
        data = rows_to_dicts(rows)
        return {
            "table": table_name,
            "status": "ok",
            "count": len(data),
            "rows": data,
            "limit": lim,
            "applied_rule": "ontology.query_source.compiled_select",
        }
    finally:
        await conn.close()


async def fetch_follow_ref(
    from_table: str,
    from_row: dict[str, Any],
    ref_column: str,
) -> dict:
    table_name = _validate_table_ident(from_table)
    if not table_name:
        return {"status": "error", "error": "from_table_not_in_whitelist"}

    rule = resolve_ref_rule(ref_column)
    if rule is None:
        return {"status": "error", "error": f"no_ref_rule_for_column:{ref_column}"}

    target_table = _validate_table_ident(str(rule.get("target_table") or ""))
    target_column = str(rule.get("target_column") or "").strip()
    if not target_table or target_column not in (await _allowed_columns(target_table)):
        return {"status": "error", "error": "invalid_ref_target"}

    ref_value = from_row.get(ref_column)
    if ref_value is None:
        return {"status": "error", "error": f"missing_ref_value:{ref_column}"}

    display_cols = list(rule.get("display_columns") or [])
    target_allowed = await _allowed_columns(target_table)
    select_cols = [target_column]
    for c in display_cols:
        if c in target_allowed and c not in select_cols:
            select_cols.append(c)
    select_sql = ", ".join(select_cols)

    conn = await yl_connect()
    try:
        rows = await conn.fetch(
            f"SELECT {select_sql} FROM {target_table} WHERE {target_column} = $1 LIMIT 5",
            ref_value,
        )
        data = rows_to_dicts(rows)
        status = "resolved" if len(data) == 1 else "ambiguous" if data else "not_found"
        return {
            "status": status,
            "from_table": table_name,
            "ref_column": ref_column,
            "ref_value": ref_value,
            "target_table": target_table,
            "target_column": target_column,
            "role": rule.get("role"),
            "rows": data,
            "count": len(data),
            "applied_rule": "ontology.follow_ref.yaml_rule",
        }
    finally:
        await conn.close()
