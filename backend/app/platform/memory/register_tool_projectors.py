"""Register tool-family memory projectors at startup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.platform.memory.projectors.attachment_pull import AttachmentPullMemoryProjector
from app.platform.memory.sql_tool_projectors import (
    SqlDescribeTableMemoryProjector,
    SqlListTablesMemoryProjector,
    SqlRunQueryMemoryProjector,
    is_describe_table_tool,
    is_list_tables_tool,
)
from app.platform.attachments.tool_result_slim import is_attachment_pull_tool

if TYPE_CHECKING:
    from app.platform.memory.projector_registry import MemoryProjectorRegistry


def register_tool_memory_projectors(registry: MemoryProjectorRegistry) -> None:
    attachment_pull = AttachmentPullMemoryProjector()
    sql_query = SqlRunQueryMemoryProjector()
    sql_list = SqlListTablesMemoryProjector()
    sql_describe = SqlDescribeTableMemoryProjector()

    from app.platform.hooks.sql_tools import is_sql_run_query

    registry.register_predicate(is_attachment_pull_tool, attachment_pull)
    registry.register_predicate(is_sql_run_query, sql_query)
    registry.register_predicate(is_list_tables_tool, sql_list)
    registry.register_predicate(is_describe_table_tool, sql_describe)
