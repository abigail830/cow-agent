"""SQL MCP memory projectors (postgres + mysql)."""

from __future__ import annotations

from typing import Any

from app.memory.memory_config import MemorySlimConfig
from app.memory.projectors.base import SlimCallResult, SlimResult
from app.memory.projectors.utils import (
    ensure_dict,
    extract_row_count,
    is_truncated,
    mark_slimmed,
    preview_json,
    preview_text,
)
from app.middleware.sql_tools import is_sql_run_query


def _sql_from_arguments(arguments: Any) -> str:
    args = ensure_dict(arguments)
    for key in ("sql", "query", "statement"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _table_from_arguments(arguments: Any) -> str:
    args = ensure_dict(arguments)
    for key in ("table", "table_name", "name"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "?"


def is_list_tables_tool(tool_name: str) -> bool:
    return tool_name.endswith("_list_tables") or tool_name in ("list_tables",)


def is_list_databases_tool(tool_name: str) -> bool:
    return tool_name.endswith("_list_databases") or tool_name in ("list_databases",)


def is_describe_table_tool(tool_name: str) -> bool:
    if tool_name.endswith("_describe_table") or tool_name in ("describe_table",):
        return True
    return tool_name.endswith("_get_schema") or tool_name in ("get_schema",)


class SqlRunQueryMemoryProjector:
    name = "sql_run_query"
    DEFAULT_REQUEST_CHARS = 120

    def matches(self, tool_name: str, *, message_type: str) -> bool:
        return is_sql_run_query(tool_name)

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult:
        chars = config.request_chars_for(tool_name, default=self.DEFAULT_REQUEST_CHARS)
        sql = _sql_from_arguments(arguments)
        preview = preview_text(sql, chars, label="SQL: ")
        return SlimCallResult(
            arguments={"_memory_preview": preview},
            metadata=mark_slimmed(metadata, projector=self.name),
        )

    def slim_result(
        self,
        *,
        tool_name: str,
        content: str | None,
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimResult:
        row_count = extract_row_count(content, metadata)
        truncated = is_truncated(content, metadata)
        rows_label = row_count if row_count is not None else "?"
        summary = f"SQL 已执行 | rows={rows_label} | truncated={truncated}"
        return SlimResult(content=summary, metadata=mark_slimmed(metadata, projector=self.name))


class SqlListTablesMemoryProjector:
    name = "sql_list_tables"
    DEFAULT_REQUEST_CHARS = 80

    def matches(self, tool_name: str, *, message_type: str) -> bool:
        return is_list_tables_tool(tool_name) or is_list_databases_tool(tool_name)

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult:
        chars = config.request_chars_for(tool_name, default=self.DEFAULT_REQUEST_CHARS)
        preview = preview_json(arguments, chars)
        return SlimCallResult(
            arguments={"_memory_preview": preview},
            metadata=mark_slimmed(metadata, projector=self.name),
        )

    def slim_result(
        self,
        *,
        tool_name: str,
        content: str | None,
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimResult:
        if is_list_databases_tool(tool_name):
            summary = "已列出数据库"
        else:
            summary = "已列出表"
        return SlimResult(content=summary, metadata=mark_slimmed(metadata, projector=self.name))


class SqlDescribeTableMemoryProjector:
    name = "sql_describe_table"
    DEFAULT_REQUEST_CHARS = 80

    def matches(self, tool_name: str, *, message_type: str) -> bool:
        return is_describe_table_tool(tool_name)

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult:
        chars = config.request_chars_for(tool_name, default=self.DEFAULT_REQUEST_CHARS)
        preview = preview_json(arguments, chars)
        return SlimCallResult(
            arguments={"_memory_preview": preview},
            metadata=mark_slimmed(metadata, projector=self.name),
        )

    def slim_result(
        self,
        *,
        tool_name: str,
        content: str | None,
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimResult:
        table = _table_from_arguments(metadata.get("arguments") or {})
        summary = f"已查看表 {table} 结构"
        return SlimResult(content=summary, metadata=mark_slimmed(metadata, projector=self.name))
