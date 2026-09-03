"""Entity discovery and resolution ontology tools (L1/L2)."""

from __future__ import annotations

from typing import Literal

from agent_framework import tool

from app.yl_worker2.obda import entity_queries as entity_obda
from app.yl_worker2.obda import queries as obda

_ENTITY_TYPE = Literal["ProductSKU", "Warehouse", "product", "warehouse"]


@tool(
    name="list_products",
    description=(
        "【ProductSKU 主数据】枚举/筛选产品目录，无需 product_code。即用户所说的「产品目录」「有哪些品项」。\n"
        "何时调用：用户问「有哪些产品」「列一下 SKU」「牛奶片有哪些」；"
        "或 search_products 后需看全量范围。\n"
        "输入：active_only（默认 true）、business（事业部模糊）、keyword（品名/品牌/系列模糊，可选）、limit。\n"
        "返回：products[]、count。用户问「有多少个产品」时直接报 count。"
    ),
)
async def list_products(
    active_only: bool = True,
    business: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> dict:
    rows = await entity_obda.fetch_list_products(
        active_only=active_only, business=business, keyword=keyword, limit=limit
    )
    return {
        "products": rows,
        "count": len(rows),
        "applied_rule": "discovery.product.master_data",
    }


@tool(
    name="list_warehouses",
    description=(
        "【Warehouse 主数据】枚举/筛选仓网，无需 site_code。即用户所说的「仓网主数据」「有哪些仓」。\n"
        "何时调用：用户问「有哪些仓」「多少基地仓/销售仓」「列一下分仓」；"
        "问数量时分别调用 site_type=base 与 site_type=sales 后汇总 count。\n"
        "输入：site_type（base|sales|基地|销售，可选）、keyword（仓名/描述/城市模糊，可选）、limit。\n"
        "返回：warehouses[]（site_code, site_name, site_type_label）、count。"
    ),
)
async def list_warehouses(
    site_type: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> dict:
    rows = await entity_obda.fetch_list_warehouses(
        site_type=site_type, keyword=keyword, limit=limit
    )
    return {
        "warehouses": rows,
        "count": len(rows),
        "site_type_filter": site_type,
        "applied_rule": "discovery.warehouse.master_data",
    }


@tool(
    name="search_products",
    description=(
        "【ProductSKU 模糊搜索】在品名/品牌/系列/编码中搜索，无需 product_code。\n"
        "何时调用：用户说「牛奶片」「金领冠」「珍护」等关键词找产品；优先于 list_products。\n"
        "输入：mention（必填）、brand（可选）、limit。\n"
        "返回：candidates[]（product_code, product_name, confidence, match_method）；"
        "多候选时请用 resolve_entity 或向经理确认。"
    ),
)
async def search_products(
    mention: str,
    brand: str | None = None,
    limit: int = 10,
) -> dict:
    rows = await entity_obda.fetch_search_products(mention, brand=brand, limit=limit)
    return {
        "mention": mention,
        "candidates": rows,
        "count": len(rows),
        "applied_rule": "resolve.product.search_ranked",
    }


@tool(
    name="search_warehouses",
    description=(
        "【Warehouse 模糊搜索】在仓名/描述/编码/城市中搜索，无需 site_code。\n"
        "何时调用：用户说「郑州」「天津基地」「合肥仓」等；优先匹配 entity_aliases.yaml 别名。\n"
        "输入：mention（必填）、site_type（base|sales 可选，缩小基地/销售范围）、limit。\n"
        "返回：candidates[]（site_code, site_name, site_type_label, confidence, match_method）。"
    ),
)
async def search_warehouses(
    mention: str,
    site_type: str | None = None,
    limit: int = 10,
) -> dict:
    rows = await entity_obda.fetch_search_warehouses(
        mention, site_type=site_type, limit=limit
    )
    return {
        "mention": mention,
        "site_type_filter": site_type,
        "candidates": rows,
        "count": len(rows),
        "applied_rule": "resolve.warehouse.search_ranked",
    }


@tool(
    name="resolve_entity",
    description=(
        "【实体解析统一入口】将用户业务说法链接为 canonical ID；"
        "优先查 entity_aliases.yaml 别名，再模糊匹配主数据。\n"
        "entity_type：ProductSKU 或 Warehouse（亦可用 product/warehouse）。\n"
        "何时调用：用户给业务名、未给 ID；在 query_inventory_snapshot / get_order_gap 等点查之前。\n"
        "返回：status（resolved|ambiguous|not_found）、resolved_id、display_name、confidence、candidates[]。\n"
        "规则：status=ambiguous 时禁止调用需 ID 的 Metric Tool，须向经理展示 candidates 确认。\n"
        "site_type：仅 Warehouse 时可选（base|sales），用于「基地」「销售仓」消歧。"
    ),
)
async def resolve_entity(
    entity_type: _ENTITY_TYPE,
    mention: str,
    site_type: str | None = None,
) -> dict:
    return await entity_obda.fetch_resolve_entity(entity_type, mention, site_type=site_type)


@tool(
    name="query_snapshot_catalog",
    description=(
        "【InventorySnapshot 目录】发现可用快照日与分仓覆盖，product_code 可选。\n"
        "模式：\n"
        "  无参 → 全局最新快照日 + 当日有数据的品项与 sku×仓覆盖；\n"
        "  仅 adjust_date → 该日全品项覆盖；\n"
        "  product_code（± adjust_date）→ 该 SKU 的可用日与分仓列表。\n"
        "何时调用：不确定日期/覆盖范围时；在点查快照之前。\n"
        "返回：latest_adjust_date, recommended_adjust_date, available_dates, "
        "products_with_snapshot, snapshot_coverage, sites_with_snapshot, warehouse_master。"
    ),
)
async def query_snapshot_catalog(
    product_code: str | None = None,
    adjust_date: str | None = None,
) -> dict:
    return await obda.fetch_snapshot_catalog(product_code, adjust_date)
