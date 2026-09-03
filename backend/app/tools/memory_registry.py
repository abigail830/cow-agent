"""Register tool-family memory projectors at startup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.tools.sql.memory import (
    SqlDescribeTableMemoryProjector,
    SqlListTablesMemoryProjector,
    SqlRunQueryMemoryProjector,
    is_describe_table_tool,
    is_list_tables_tool,
)

if TYPE_CHECKING:
    from app.memory.projector_registry import MemoryProjectorRegistry


def register_tool_memory_projectors(registry: MemoryProjectorRegistry) -> None:
    sql_query = SqlRunQueryMemoryProjector()
    sql_list = SqlListTablesMemoryProjector()
    sql_describe = SqlDescribeTableMemoryProjector()

    from app.middleware.sql_tools import is_sql_run_query

    registry.register_predicate(is_sql_run_query, sql_query)
    registry.register_predicate(is_list_tables_tool, sql_list)
    registry.register_predicate(is_describe_table_tool, sql_describe)
