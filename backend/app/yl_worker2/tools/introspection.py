"""L0 ontology introspection tools."""

from __future__ import annotations

from typing import Literal

from agent_framework import tool

from app.yl_worker2.runtime.entity_schema import (
    describe_entity_type as schema_describe,
    list_entity_type_summaries,
)

_ENTITY_NAME = Literal[
    "ProductSKU",
    "Warehouse",
    "InventorySnapshot",
    "AllocationOrder",
    "product",
    "warehouse",
    "sku",
    "site",
    "snapshot",
    "allocation",
]


@tool(
    name="list_entity_types",
    description=(
        "【L0 本体自省】列出 yl-worker2 支持的实体类型摘要。\n"
        "何时调用：不确定某概念对应哪种实体、需要知道 ID 字段或发现类 Tool 时。\n"
        "返回：entity_types[]（name, label, description, id_field, discovery_tools）。\n"
        "与 yl-oip-ontology-core Skill 互补：Skill 讲概念，本 Tool 讲运行时 schema。"
    ),
)
async def list_entity_types() -> dict:
    types = list_entity_type_summaries()
    return {
        "entity_types": types,
        "count": len(types),
        "applied_rule": "introspection.entity_type.list",
    }


@tool(
    name="describe_entity_type",
    description=(
        "【L0 本体自省】返回单一实体类型的运行时 schema。\n"
        "entity_type：ProductSKU | Warehouse | InventorySnapshot | AllocationOrder"
        "（亦可用 product/warehouse/sku/site/snapshot/allocation）。\n"
        "返回：id_field、searchable_fields、discovery_tools、resolution_tools、"
        "related_entities、point_query_requires、hints。\n"
        "何时调用：点查前确认需要哪些标识符；解析失败时查可搜字段与相关 Tool。"
    ),
)
async def describe_entity_type(entity_type: _ENTITY_NAME) -> dict:
    spec = schema_describe(entity_type)
    if spec is None:
        return {
            "entity_type": entity_type,
            "status": "not_found",
            "supported_types": [t["name"] for t in list_entity_type_summaries()],
            "applied_rule": "introspection.entity_type.unknown",
        }
    return {
        "entity_type": spec["name"],
        "status": "ok",
        **spec,
    }
