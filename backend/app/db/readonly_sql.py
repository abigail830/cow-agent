"""Shared read-only SQL helpers for MCP servers and in-process database tools."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg
import pymysql

MAX_ROWS = int(os.getenv("MCP_MAX_ROWS", "2000"))


def json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def json_result(value: Any) -> str:
    return json.dumps(value, default=json_default, ensure_ascii=False)


def sql_tool_error_result(exc: BaseException, *, query: str | None = None) -> str:
    """Return a structured JSON error payload for SQL tools (kept as tool success)."""
    message = str(exc).strip() or repr(exc)
    lowered = message.lower()
    hint = "Use postgres_describe_table or postgres_get_schema to verify columns, fix SQL, then retry."
    if "does not exist" in lowered and "column" in lowered:
        hint = (
            "Column name is wrong. Call postgres_describe_table on the referenced table(s), "
            "then rewrite SQL. Common pitfalls: users has no role (use chat_messages.role); "
            "chat_states is a separate table (JOIN chat_states st ON st.session_id = cs.id)."
        )
    elif "does not exist" in lowered and "relation" in lowered:
        hint = "Table name is wrong. Call postgres_list_tables or postgres_get_schema, then retry."
    elif "syntax error" in lowered:
        hint = "PostgreSQL syntax error. Remove MySQL-only constructs (JSON_TABLE, REGEXP, DATE_SUB) and retry."
    payload: dict[str, Any] = {
        "ok": False,
        "error_type": type(exc).__name__,
        "error": message,
        "hint": hint,
    }
    if query:
        payload["query_preview"] = query.strip()[:500]
    return json_result(payload)


def readonly_query(sql: str, *, mysql: bool = False) -> str:
    query = sql.strip().rstrip(";")
    if ";" in query:
        raise ValueError("Only one read-only SQL statement is allowed")
    lowered = query.lower().lstrip("(\n\t ")
    if mysql:
        allowed = ("select", "with", "show", "describe", "explain")
    else:
        allowed = ("select", "with", "explain")
    if not lowered.startswith(allowed):
        raise ValueError("Only read-only SQL queries are allowed")
    return query


def limited_query(query: str, limit: int) -> str:
    lowered = query.lower().lstrip("(\n\t ")
    if lowered.startswith(("select", "with")):
        return f"select * from ({query}) as _mcp_query limit {limit}"
    return query


def _postgres_has_config(env: dict[str, str]) -> bool:
    if env.get("DATABASE_URL", "").strip():
        return True
    return bool(
        env.get("DB_HOST")
        or env.get("POSTGRES_HOST")
        or env.get("DB_USER")
        or env.get("POSTGRES_USER")
    )


def _postgres_ssl_mode(env: dict[str, str], host: str) -> str | bool | None:
    ssl_mode = (env.get("DB_SSL_MODE") or env.get("POSTGRES_SSL_MODE") or "").strip().lower()
    if ssl_mode in {"require", "verify-full", "verify-ca"}:
        return "require"
    if ssl_mode in {"disable", "false", "0", "prefer", "allow"}:
        return False
    if "postgres.database.azure.com" in host:
        return "require"
    return None


async def postgres_connect_from_env(env: dict[str, str]) -> asyncpg.Connection:
    host = env.get("DB_HOST") or env.get("POSTGRES_HOST")
    user = env.get("DB_USER") or env.get("POSTGRES_USER")
    if host or user:
        connect_host = host or "localhost"
        ssl = _postgres_ssl_mode(env, connect_host)
        kwargs: dict[str, Any] = {
            "host": connect_host,
            "port": int(env.get("DB_PORT") or env.get("POSTGRES_PORT") or "5432"),
            "user": user or "postgres",
            "password": env.get("DB_PASSWORD") or env.get("POSTGRES_PASSWORD") or "",
            "database": env.get("DB_NAME") or env.get("POSTGRES_DB") or "postgres",
        }
        if ssl is not None:
            kwargs["ssl"] = ssl
        return await asyncpg.connect(**kwargs)

    database_url = env.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL or DB_HOST/DB_USER is required")
    return await asyncpg.connect(database_url)


async def postgres_connect(database_url: str) -> asyncpg.Connection:
    return await postgres_connect_from_env({"DATABASE_URL": database_url})


async def postgres_list_tables(env: dict[str, str], schema: str = "public") -> str:
    conn = await postgres_connect_from_env(env)
    try:
        rows = await conn.fetch(
            """
            select table_schema, table_name, table_type
            from information_schema.tables
            where table_schema = $1
            order by table_schema, table_name
            """,
            schema,
        )
        return json_result({"tables": [dict(row) for row in rows]})
    finally:
        await conn.close()


async def postgres_describe_table(
    env: dict[str, str],
    table_name: str,
    schema: str = "public",
) -> str:
    conn = await postgres_connect_from_env(env)
    try:
        rows = await conn.fetch(
            """
            select column_name, data_type, is_nullable, column_default
            from information_schema.columns
            where table_schema = $1 and table_name = $2
            order by ordinal_position
            """,
            schema,
            table_name,
        )
        return json_result(
            {"schema": schema, "table": table_name, "columns": [dict(row) for row in rows]}
        )
    finally:
        await conn.close()


async def postgres_get_schema(env: dict[str, str], schema: str = "public") -> str:
    conn = await postgres_connect_from_env(env)
    try:
        rows = await conn.fetch(
            """
            select table_name, column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = $1
            order by table_name, ordinal_position
            """,
            schema,
        )
        tables: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            item = dict(row)
            table = item.pop("table_name")
            tables.setdefault(table, []).append(item)
        return json_result({"schema": schema, "tables": tables})
    finally:
        await conn.close()


async def postgres_query_data(
    env: dict[str, str],
    query: str,
    max_rows: int = MAX_ROWS,
) -> str:
    try:
        readonly = readonly_query(query)
    except ValueError as exc:
        return sql_tool_error_result(exc, query=query)

    limit = max(1, min(int(max_rows or MAX_ROWS), MAX_ROWS))
    sql = limited_query(readonly, limit)
    conn = await postgres_connect_from_env(env)
    try:
        async with conn.transaction():
            await conn.execute("set transaction read only")
            rows = await conn.fetch(sql, timeout=30)
        return json_result({"ok": True, "row_count": len(rows), "rows": [dict(row) for row in rows]})
    except Exception as exc:
        return sql_tool_error_result(exc, query=query)
    finally:
        await conn.close()


def mysql_connect(env: dict[str, str]) -> pymysql.connections.Connection:
    ssl = {"ssl": {}} if env.get("MYSQL_SSL", "").lower() in {"1", "true", "yes"} else {}
    return pymysql.connect(
        host=env.get("MYSQL_HOST"),
        port=int(env.get("MYSQL_PORT", "3306")),
        user=env.get("MYSQL_USER"),
        password=env.get("MYSQL_PASS"),
        database=env.get("MYSQL_DB") or None,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
        autocommit=False,
        **ssl,
    )


def mysql_query_data(env: dict[str, str], query: str, max_rows: int = MAX_ROWS) -> str:
    readonly = readonly_query(query, mysql=True)
    limit = max(1, min(int(max_rows or MAX_ROWS), MAX_ROWS))
    sql = limited_query(readonly, limit)
    conn = mysql_connect(env)
    try:
        with conn.cursor() as cursor:
            cursor.execute("start transaction read only")
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.execute("rollback")
        return json_result({"row_count": len(rows), "rows": rows})
    finally:
        conn.close()
