"""Objective Assets ontology tools — inventory queries."""

from __future__ import annotations

from agent_framework import tool

from app.yl_worker2.obda import queries as obda
from app.yl_worker2.runtime.parse import parse_qty, parse_rate
from app.yl_worker2.runtime.policy_evaluator import (
    eval_national_supply_status,
    monthly_supply_from_national,
)


@tool(
    name="query_inventory_snapshot",
    description=(
        "【InventorySnapshot @ Warehouse×SKU】读取分仓库存监控快照。\n"
        "业务含义：Dashboard 异常判断的 A-Box 入口，含计划/现货/在途/未发/缺口/备货率/大日期。\n"
        "数据源：优先 warehouse_sku_inventory，回退 yl_sales_warehouse_inventory_report。\n"
        "何时调用：巡检第一步定位异常仓；Script2 订单突变后复核。\n"
        "输入：product_code, site_code, adjust_date（YYYY-MM-DD）。\n"
        "返回：found, plan_num, store_num, store_transit, total_unship, order_gap, "
        "stock_rate_before_pct, order_completion_rate_pct, big_date_num。"
    ),
)
async def query_inventory_snapshot(
    product_code: str,
    site_code: str,
    adjust_date: str,
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"found": False, "product_code": product_code, "site_code": site_code}
    snap["found"] = True
    snap["stock_rate_before_pct"] = parse_rate(snap.get("stock_rate_before"))
    if snap["stock_rate_before_pct"] is not None:
        snap["stock_rate_before_pct"] = round(snap["stock_rate_before_pct"] * 100, 1)
    snap["order_completion_rate_pct"] = parse_rate(snap.get("order_completion_rate"))
    if snap["order_completion_rate_pct"] is not None:
        snap["order_completion_rate_pct"] = round(snap["order_completion_rate_pct"] * 100, 1)
    return snap


@tool(
    name="query_batch_big_date_inventory",
    description=(
        "【BatchInventory】查询大日期/临期批次库存明细。\n"
        "数据源：yl_big_date_inventory（批次行）；无行时回退 warehouse_sku_inventory.aging_inventory_qty。\n"
        "汇总口径 big_date_num 也可从 query_inventory_snapshot 读取。\n"
        "何时调用：需要批次明细、生产日期、调出方案时；仅看总量可先读 snapshot。\n"
        "输入：product_code, site_code。\n"
        "返回：batches[], total_big_date_num, batch_count。"
    ),
)
async def query_batch_big_date_inventory(
    product_code: str,
    site_code: str,
) -> dict:
    rows = await obda.fetch_batch_big_date_inventory(product_code, site_code)
    total = sum(parse_qty(r.get("big_date_num")) for r in rows)
    return {
        "product_code": product_code,
        "site_code": site_code,
        "batches": rows,
        "total_big_date_num": round(total, 2),
        "batch_count": len(rows),
    }


@tool(
    name="query_base_warehouse_availability",
    description=(
        "【基地仓 from_available】查询各基地仓可发量与路由时效。\n"
        "业务含义：正向补货选基地仓；规则：时效优先（lead_time_days 越小越优），其次可发量。\n"
        "数据源：当日正向草案 from_available；无草案时回退基地现货。\n"
        "何时调用：Script1 正向补货选天津/呼市/武汉等基地。\n"
        "输入：product_code, adjust_date, to_site_code（可选，用于计算 lead_time_days）。\n"
        "返回：warehouses[] 含 from_available, lead_time_days（提供 to_site_code 时），按时效排序。"
    ),
)
async def query_base_warehouse_availability(
    product_code: str,
    adjust_date: str,
    to_site_code: str | None = None,
) -> dict:
    rows = await obda.fetch_base_warehouse_availability(
        product_code, adjust_date, to_site_code=to_site_code
    )
    return {
        "product_code": product_code,
        "adjust_date": adjust_date,
        "to_site_code": to_site_code,
        "warehouses": rows,
        "count": len(rows),
    }


@tool(
    name="query_national_inventory_summary",
    description=(
        "【全国报表聚合】读取全国销售仓库存监控汇总。\n"
        "业务含义：支撑 eval_national_supply_status 的供应/需求输入。\n"
        "规则：月度供应=现库+在途+累出；月度需求=plan_num；±5% 判三态。\n"
        "何时调用：计算目标备货率前先判全国充足/持平/不足。\n"
        "输入：product_code, adjust_date。\n"
        "返回：summary, monthly_supply, monthly_demand, status, applied_rule。"
    ),
)
async def query_national_inventory_summary(
    product_code: str,
    adjust_date: str,
) -> dict:
    summary = await obda.fetch_national_summary(product_code, adjust_date)
    if summary is None:
        return {"found": False, "product_code": product_code}
    supply = monthly_supply_from_national(
        parse_qty(summary.get("from_store_num_h")),
        parse_qty(summary.get("from_store_transit")),
        parse_qty(summary.get("out_put_num")),
    )
    demand = parse_qty(summary.get("plan_num"))
    status = eval_national_supply_status(supply, demand)
    return {
        "found": True,
        "product_code": product_code,
        "adjust_date": adjust_date,
        "summary": summary,
        "monthly_supply": supply,
        "monthly_demand": demand,
        **status,
    }
