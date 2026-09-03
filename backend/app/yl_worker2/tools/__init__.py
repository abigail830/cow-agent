"""yl-worker2 MAF tool registry."""

from __future__ import annotations

from app.yl_worker2.tools.allocation import (
    activate_allocation_and_push,
    cancel_allocation_order,
    list_pending_allocation_orders,
    save_forward_allocation_draft,
    save_lateral_allocation_draft,
    simulate_allocation_effect,
    update_allocation_quantity,
)
from app.yl_worker2.tools.discovery import (
    list_products,
    list_warehouses,
    query_snapshot_catalog,
    resolve_entity,
    search_products,
    search_warehouses,
)
from app.yl_worker2.tools.fulfillment_proposal import propose_fulfillment_forms
from app.yl_worker2.tools.introspection import (
    describe_entity_type,
    list_entity_types,
)
from app.yl_worker2.tools.ontology_query import (
    describe_table,
    follow_ref,
    list_sources,
    query_source,
)
from app.yl_worker2.tools.inventory import (
    query_base_warehouse_availability,
    query_batch_big_date_inventory,
    query_inventory_snapshot,
    query_national_inventory_summary,
)
from app.yl_worker2.tools.metrics import (
    calc_replenishment_quantity_tool,
    eval_national_supply_status_tool,
    eval_target_stock_rate_tool,
    get_current_stock_rate,
    get_order_gap,
    get_order_progress,
    get_ship_gap,
)

YL_WORKER2_TOOL_NAMES = frozenset(
    {
        "get_order_gap",
        "get_ship_gap",
        "get_order_progress",
        "get_current_stock_rate",
        "eval_national_supply_status",
        "eval_target_stock_rate",
        "calc_replenishment_quantity",
        "query_inventory_snapshot",
        "query_batch_big_date_inventory",
        "query_base_warehouse_availability",
        "query_national_inventory_summary",
        "query_snapshot_catalog",
        "list_products",
        "list_warehouses",
        "search_products",
        "search_warehouses",
        "resolve_entity",
        "list_entity_types",
        "describe_entity_type",
        "list_sources",
        "describe_table",
        "query_source",
        "follow_ref",
        "propose_fulfillment_forms",
        "list_pending_allocation_orders",
        "simulate_allocation_effect",
        "save_forward_allocation_draft",
        "save_lateral_allocation_draft",
        "update_allocation_quantity",
        "activate_allocation_and_push",
        "cancel_allocation_order",
    }
)

YL_WORKER2_TOOLS = {
    "get_order_gap": get_order_gap,
    "get_ship_gap": get_ship_gap,
    "get_order_progress": get_order_progress,
    "get_current_stock_rate": get_current_stock_rate,
    "eval_national_supply_status": eval_national_supply_status_tool,
    "eval_target_stock_rate": eval_target_stock_rate_tool,
    "calc_replenishment_quantity": calc_replenishment_quantity_tool,
    "query_inventory_snapshot": query_inventory_snapshot,
    "query_batch_big_date_inventory": query_batch_big_date_inventory,
    "query_base_warehouse_availability": query_base_warehouse_availability,
    "query_national_inventory_summary": query_national_inventory_summary,
    "query_snapshot_catalog": query_snapshot_catalog,
    "list_products": list_products,
    "list_warehouses": list_warehouses,
    "search_products": search_products,
    "search_warehouses": search_warehouses,
    "resolve_entity": resolve_entity,
    "list_entity_types": list_entity_types,
    "describe_entity_type": describe_entity_type,
    "list_sources": list_sources,
    "describe_table": describe_table,
    "query_source": query_source,
    "follow_ref": follow_ref,
    "propose_fulfillment_forms": propose_fulfillment_forms,
    "list_pending_allocation_orders": list_pending_allocation_orders,
    "simulate_allocation_effect": simulate_allocation_effect,
    "save_forward_allocation_draft": save_forward_allocation_draft,
    "save_lateral_allocation_draft": save_lateral_allocation_draft,
    "update_allocation_quantity": update_allocation_quantity,
    "activate_allocation_and_push": activate_allocation_and_push,
    "cancel_allocation_order": cancel_allocation_order,
}
