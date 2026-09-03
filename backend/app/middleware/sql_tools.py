"""Detect SQL-executing MCP tools across database backends (postgres, mysql, …)."""

from __future__ import annotations


def is_postgres_run_query(tool_name: str) -> bool:
    """Match postgres MCP SQL tools across naming conventions."""
    if tool_name in (
        "query_data",
        "postgres_query_data",
        "query",
        "postgres_query",
        "mcp__postgres__query",
        "mcp__postgres__query_data",
        "mcp__postgres__run_query",
        "postgres_run_query",
    ):
        return True
    return ("postgres" in tool_name) and (
        tool_name.endswith("_query_data")
        or tool_name.endswith("__query_data")
        or tool_name.endswith("_query")
        or tool_name.endswith("__query")
        or tool_name.endswith("_run_query")
        or tool_name.endswith("__run_query")
    )


def is_mysql_run_query(tool_name: str) -> bool:
    """Match MySQL MCP query tools across naming conventions."""
    if tool_name in (
        "mysql_query",
        "execute_query",
        "mysql_execute_query",
        "mysql_mysql_query",
        "mcp__mysql__mysql_query",
        "mcp__mysql__execute_query",
    ):
        return True
    return ("mysql" in tool_name) and (
        tool_name.endswith("_mysql_query")
        or tool_name.endswith("__mysql_query")
        or tool_name.endswith("_execute_query")
        or tool_name.endswith("__execute_query")
    )


def is_sql_run_query(tool_name: str) -> bool:
    """True when the tool executes a SQL string (subject to sql_validator / truncator)."""
    return is_postgres_run_query(tool_name) or is_mysql_run_query(tool_name)
