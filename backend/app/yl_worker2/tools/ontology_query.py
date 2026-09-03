"""Generic ontology source exploration tools (list/describe/query/follow_ref)."""

from __future__ import annotations

from typing import Any

from agent_framework import tool

from app.yl_worker2.obda import source_queries as source_obda
from app.yl_worker2.runtime.schema_introspect import fetch_describe_table, fetch_list_sources


@tool(
    name="list_sources",
    description=(
        "【本体数据源目录】列出 Agent 可查询的 yl_* / warehouse_sku_inventory 等表（白名单 ontology_sources.yaml）。\n"
        "何时调用：不确定数据在哪张表；探索前先看有哪些 source。\n"
        "返回：sources[]（table_name, relation_type, table_comment）。"
    ),
)
async def list_sources() -> dict:
    rows = await fetch_list_sources()
    return {
        "sources": rows,
        "count": len(rows),
        "applied_rule": "ontology.list_sources.whitelist",
    }


@tool(
    name="describe_table",
    description=(
        "【表结构自省】每次实时查 PG，返回列名、类型、中文 COMMENT、suggested_dimensions、ref_candidates、column_aliases。\n"
        "column_aliases：语义列名→物理列名（如 site_code→from_site_code），query_source 会自动解析。\n"
        "何时调用：query_source 前确认有哪些列；用户问「这张表有什么字段」。\n"
        "输入：table（如 yl_transit_inventory、yl_product）。\n"
        "返回：columns[], suggested_dimensions[], ref_candidates[]（可接 follow_ref）。"
    ),
)
async def describe_table(table: str) -> dict:
    return await fetch_describe_table(table)


@tool(
    name="query_source",
    description=(
        "【单表读取】在白名单表上按结构化条件查询，无需 product_code 等预置 Tool。\n"
        "when 语法（JSON）：eq / contains / gte / lte / is_null / and / or。\n"
        "示例：where={\"and\":[{\"eq\":{\"to_site_code\":\"MOCK_WH_S04\"}},{\"eq\":{\"product_code\":\"MOCK_YLP001\"}}]}\n"
        "或 contains：where={\"contains\":{\"product_name\":\"牛奶片\"}}\n"
        "何时调用：describe_table 后读明细；在途来源、计划、主数据筛选等。\n"
        "指标口径（order_gap 等）须用 get_* / eval_*，禁止在此自算。\n"
        "输入：table, where?, select?, order_by?, limit?。\n"
        "返回：rows[], count, limit。"
    ),
)
async def query_source(
    table: str,
    where: dict[str, Any] | None = None,
    select: list[str] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> dict:
    return await source_obda.fetch_query_source(
        table,
        where=where,
        select=select,
        order_by=order_by,
        limit=limit,
    )


@tool(
    name="follow_ref",
    description=(
        "【引用跳转】按 ontology_refs.yaml 将行内编码列解析到主数据表（如 from_site_code → yl_warehouse）。\n"
        "何时调用：query_source 拿到在途行后，查「从哪个基地发出」；或解析 product_code / site_code。\n"
        "输入：from_table, from_row（query_source 返回的单行 dict）, ref_column。\n"
        "返回：status（resolved|ambiguous|not_found）, target_table, rows[]。"
    ),
)
async def follow_ref(
    from_table: str,
    from_row: dict[str, Any],
    ref_column: str,
) -> dict:
    return await source_obda.fetch_follow_ref(from_table, from_row, ref_column)
