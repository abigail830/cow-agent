"""In-process database tools for serverless runtimes (Vercel) where stdio MCP is unavailable."""

from __future__ import annotations

from typing import Any

from agent_framework import tool

from app.db.readonly_sql import (
    MAX_ROWS,
    mysql_query_data,
    postgres_describe_table,
    postgres_get_schema,
    postgres_list_tables,
    postgres_query_data,
)


def _remote_allowed(remote: str, allowed_remote_tools: list[str] | None) -> bool:
    return allowed_remote_tools is None or remote in allowed_remote_tools


def build_postgres_tools(
    env: dict[str, str],
    *,
    allowed_remote_tools: list[str] | None,
) -> list[Any]:
    tools: list[Any] = []
    db_env = dict(env)

    if _remote_allowed("list_tables", allowed_remote_tools):

        @tool(name="postgres_list_tables", description="List tables and views in the database.")
        async def postgres_list_tables_tool(schema: str = "public") -> str:
            return await postgres_list_tables(db_env, schema)

        tools.append(postgres_list_tables_tool)

    if _remote_allowed("describe_table", allowed_remote_tools):

        @tool(name="postgres_describe_table", description="Describe columns for a table.")
        async def postgres_describe_table_tool(
            table_name: str,
            schema: str = "public",
        ) -> str:
            return await postgres_describe_table(db_env, table_name, schema)

        tools.append(postgres_describe_table_tool)

    if _remote_allowed("get_schema", allowed_remote_tools):

        @tool(name="postgres_get_schema", description="Return table and column schema metadata.")
        async def postgres_get_schema_tool(schema: str = "public") -> str:
            return await postgres_get_schema(db_env, schema)

        tools.append(postgres_get_schema_tool)

    if _remote_allowed("query_data", allowed_remote_tools):

        @tool(name="postgres_query_data", description="Execute a read-only SQL query.")
        async def postgres_query_data_tool(query: str, max_rows: int = MAX_ROWS) -> str:
            return await postgres_query_data(db_env, query, max_rows)

        tools.append(postgres_query_data_tool)

    return tools


def build_mysql_tools(
    env: dict[str, str],
    *,
    allowed_remote_tools: list[str] | None,
) -> list[Any]:
    if not _remote_allowed("mysql_query", allowed_remote_tools):
        return []

    mysql_env = dict(env)

    @tool(name="mysql_query", description="Execute a read-only MySQL query.")
    def mysql_query_tool(query: str, max_rows: int = MAX_ROWS) -> str:
        return mysql_query_data(mysql_env, query, max_rows)

    return [mysql_query_tool]
