"""PostgreSQL schema introspection for ontology query tools."""

from __future__ import annotations

import re

from app.yl_worker2.db import rows_to_dicts, yl_connect
from app.yl_worker2.runtime.ontology_config import get_table_column_aliases, suggest_dimensions, table_allowed

_TABLE_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_table_ident(name: str) -> str | None:
    n = (name or "").strip().lower()
    if not n or not _TABLE_IDENT.match(n):
        return None
    if not table_allowed(n):
        return None
    return n


async def fetch_list_sources() -> list[dict]:
    conn = await yl_connect()
    try:
        rows = await conn.fetch(
            """
            SELECT
                c.relname AS table_name,
                CASE c.relkind WHEN 'v' THEN 'view' ELSE 'table' END AS relation_type,
                obj_description(c.oid) AS table_comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'v')
            ORDER BY c.relname
            """
        )
        out = []
        for row in rows:
            name = row["table_name"]
            if table_allowed(name):
                out.append(
                    {
                        "table_name": name,
                        "relation_type": row["relation_type"],
                        "table_comment": row["table_comment"],
                    }
                )
        return out
    finally:
        await conn.close()


async def fetch_describe_table(table_name: str) -> dict:
    safe = _validate_table_ident(table_name)
    if not safe:
        return {
            "table_name": table_name,
            "status": "not_allowed",
            "error": "table_not_in_whitelist",
        }

    conn = await yl_connect()
    try:
        meta = await conn.fetchrow(
            """
            SELECT
                c.relname AS table_name,
                CASE c.relkind WHEN 'v' THEN 'view' ELSE 'table' END AS relation_type,
                obj_description(c.oid) AS table_comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = $1
            LIMIT 1
            """,
            safe,
        )
        if meta is None:
            return {"table_name": safe, "status": "not_found"}

        col_rows = await conn.fetch(
            """
            SELECT
                a.attname AS column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                NOT a.attnotnull AS nullable,
                col_description(a.attrelid, a.attnum) AS column_comment
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = $1
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            safe,
        )
        columns = rows_to_dicts(col_rows)
        col_names = [c["column_name"] for c in columns]
        allowed = set(col_names)
        ref_candidates = [c for c in col_names if c.endswith("_code") or c in ("product_code", "site_code")]
        return {
            "table_name": safe,
            "status": "ok",
            "relation_type": meta["relation_type"],
            "table_comment": meta["table_comment"],
            "columns": columns,
            "suggested_dimensions": suggest_dimensions(col_names),
            "ref_candidates": ref_candidates,
            "column_aliases": get_table_column_aliases(safe, allowed),
            "applied_rule": "ontology.describe_table.pg_catalog",
        }
    finally:
        await conn.close()
