"""Runtime ontology entity type schema for L0 introspection tools."""

from __future__ import annotations

from typing import Any

ENTITY_TYPES: dict[str, dict[str, Any]] = {
    "ProductSKU": {
        "name": "ProductSKU",
        "label": "产品 SKU",
        "description": "补调最小品项；主数据来自 yl_product。",
        "id_field": "product_code",
        "display_field": "product_name",
        "searchable_fields": [
            "product_code",
            "product_name",
            "trade_name",
            "brand",
            "pro_series",
        ],
        "discovery_tools": ["list_products", "search_products"],
        "resolution_tools": ["resolve_entity", "search_products"],
        "related_entities": ["Warehouse", "InventorySnapshot", "SalesPlan"],
        "point_query_requires": ["product_code"],
    },
    "Warehouse": {
        "name": "Warehouse",
        "label": "仓库",
        "description": "基地仓（Base）或销售仓（Sales）；主数据来自 yl_warehouse。",
        "id_field": "site_code",
        "display_field": "site_name",
        "searchable_fields": ["site_code", "site_name", "site_desc"],
        "discovery_tools": ["list_warehouses", "search_warehouses"],
        "resolution_tools": ["resolve_entity", "search_warehouses"],
        "related_entities": ["ProductSKU", "InventorySnapshot", "TransitInventory"],
        "point_query_requires": ["site_code"],
        "hints": {"site_type": "base|sales 用于基地/销售消歧"},
    },
    "InventorySnapshot": {
        "name": "InventorySnapshot",
        "label": "库存快照",
        "description": "某日某仓某品的监控状态；数据来自分仓报表与 VIEW。",
        "id_field": None,
        "composite_key": ["product_code", "site_code", "adjust_date"],
        "display_field": None,
        "searchable_fields": ["product_code", "site_code", "adjust_date"],
        "discovery_tools": ["query_snapshot_catalog"],
        "resolution_tools": ["query_snapshot_catalog"],
        "related_entities": ["ProductSKU", "Warehouse"],
        "point_query_requires": ["product_code", "site_code", "adjust_date"],
        "hints": {
            "adjust_date": "须为报表中存在的 YYYY-MM-DD；不确定时用 query_snapshot_catalog"
        },
    },
    "AllocationOrder": {
        "name": "AllocationOrder",
        "label": "调拨单",
        "description": "正向/横向调拨建议与草案；读写 yl_forward_transfer / yl_lateral_transfer。",
        "id_field": "order_id",
        "display_field": None,
        "searchable_fields": ["product_code", "from_site_code", "to_site_code", "adjust_date"],
        "discovery_tools": ["list_pending_allocation_orders"],
        "resolution_tools": [],
        "related_entities": ["ProductSKU", "Warehouse", "ReplenishmentOrder"],
        "point_query_requires": ["product_code", "adjust_date"],
    },
}


def list_entity_type_summaries() -> list[dict[str, Any]]:
    return [
        {
            "name": spec["name"],
            "label": spec["label"],
            "description": spec["description"],
            "id_field": spec.get("id_field"),
            "composite_key": spec.get("composite_key"),
            "discovery_tools": spec.get("discovery_tools") or [],
        }
        for spec in ENTITY_TYPES.values()
    ]


def describe_entity_type(name: str) -> dict[str, Any] | None:
    key = (name or "").strip()
    if not key:
        return None
    for spec in ENTITY_TYPES.values():
        if spec["name"].lower() == key.lower():
            return {**spec, "applied_rule": "introspection.entity_type.describe"}
    aliases = {
        "product": "ProductSKU",
        "sku": "ProductSKU",
        "warehouse": "Warehouse",
        "site": "Warehouse",
        "snapshot": "InventorySnapshot",
        "inventorysnapshot": "InventorySnapshot",
        "allocation": "AllocationOrder",
    }
    mapped = aliases.get(key.lower())
    if mapped:
        return describe_entity_type(mapped)
    return None
