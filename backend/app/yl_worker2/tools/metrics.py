"""SupplyChainMetrics ontology tools."""

from __future__ import annotations

from typing import Literal

from agent_framework import tool

from app.yl_worker2.obda import queries as obda
from app.yl_worker2.runtime.parse import parse_qty, parse_rate
from app.yl_worker2.runtime.policy_evaluator import (
    calc_current_stock_rate,
    calc_order_gap,
    calc_order_progress,
    calc_replenishment_quantity,
    calc_ship_gap,
    eval_national_supply_status,
    eval_target_stock_rate,
    monthly_supply_from_national,
)

_PERIOD = Literal["early_month", "mid_month", "late_month"]


@tool(
    name="get_order_gap",
    description=(
        "【SupplyChainMetrics.get_order_gap】计算分仓发货缺口。\n"
        "公式：发货缺口 = 现货库存 + 在途库存 − 未发订单。\n"
        "输入：product_code, site_code, adjust_date（YYYY-MM-DD）。\n"
        "何时调用：巡检 Dashboard 异常仓、判断断货风险时。\n"
        "返回：order_gap, store_num, store_transit, total_unship, applied_rule。"
    ),
)
async def get_order_gap(
    product_code: str,
    site_code: str,
    adjust_date: str,
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found", "product_code": product_code, "site_code": site_code}
    store = parse_qty(snap.get("store_num"))
    transit = parse_qty(snap.get("store_transit"))
    unship = parse_qty(snap.get("total_unship"))
    gap = calc_order_gap(store, transit, unship)
    return {
        "product_code": product_code,
        "site_code": site_code,
        "adjust_date": adjust_date,
        "order_gap": round(gap, 2),
        "store_num": store,
        "store_transit": transit,
        "total_unship": unship,
        "applied_rule": "metrics.order_gap.store_plus_transit_minus_unship",
    }


@tool(
    name="get_ship_gap",
    description=(
        "【SupplyChainMetrics.get_ship_gap】计算仅基于现货的发货缺口。\n"
        "公式：发货缺口 = 现货库存 − 未发订单。\n"
        "输入：product_code, site_code, adjust_date。\n"
        "返回：ship_gap, store_num, total_unship, applied_rule。"
    ),
)
async def get_ship_gap(
    product_code: str,
    site_code: str,
    adjust_date: str,
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found"}
    store = parse_qty(snap.get("store_num"))
    unship = parse_qty(snap.get("total_unship"))
    gap = calc_ship_gap(store, unship)
    return {
        "product_code": product_code,
        "site_code": site_code,
        "adjust_date": adjust_date,
        "ship_gap": round(gap, 2),
        "store_num": store,
        "total_unship": unship,
        "applied_rule": "metrics.ship_gap.store_minus_unship",
    }


@tool(
    name="get_order_progress",
    description=(
        "【SupplyChainMetrics.get_order_progress】订单完成率。\n"
        "公式：(当月未发货量 + 本月累出) / 销售计划。\n"
        "输入：product_code, site_code, adjust_date。\n"
        "返回：order_progress（0-1）, order_progress_pct, plan_num, applied_rule。"
    ),
)
async def get_order_progress(
    product_code: str,
    site_code: str,
    adjust_date: str,
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found"}
    plan = parse_qty(snap.get("plan_num"))
    output = parse_qty(snap.get("out_put_num"))
    unship = parse_qty(snap.get("total_unship"))
    progress = calc_order_progress(unship, output, plan)
    stored = parse_rate(snap.get("order_completion_rate"))
    return {
        "product_code": product_code,
        "site_code": site_code,
        "adjust_date": adjust_date,
        "order_progress": round(progress, 4),
        "order_progress_pct": round(progress * 100, 1),
        "plan_num": plan,
        "reported_order_completion_rate": stored,
        "applied_rule": "metrics.order_progress.unship_plus_output_over_plan",
    }


@tool(
    name="get_current_stock_rate",
    description=(
        "【SupplyChainMetrics.get_current_stock_rate】当前生产备货率。\n"
        "公式：(现货 + 在途 + 本月累出) / 销售计划。\n"
        "输入：product_code, site_code, adjust_date。\n"
        "返回：stock_rate（0-1）, stock_rate_pct, applied_rule。"
    ),
)
async def get_current_stock_rate(
    product_code: str,
    site_code: str,
    adjust_date: str,
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found"}
    plan = parse_qty(snap.get("plan_num"))
    store = parse_qty(snap.get("store_num"))
    transit = parse_qty(snap.get("store_transit"))
    output = parse_qty(snap.get("out_put_num"))
    rate = calc_current_stock_rate(store, transit, output, plan)
    stored = parse_rate(snap.get("stock_rate_before"))
    return {
        "product_code": product_code,
        "site_code": site_code,
        "adjust_date": adjust_date,
        "stock_rate": round(rate, 4),
        "stock_rate_pct": round(rate * 100, 1),
        "reported_stock_rate": stored,
        "applied_rule": "metrics.stock_rate.store_transit_output_over_plan",
    }


async def _national_supply_result(product_code: str, adjust_date: str) -> dict:
    summary = await obda.fetch_national_summary(product_code, adjust_date)
    if summary is None:
        return {"error": "national_summary_not_found", "product_code": product_code}
    supply = monthly_supply_from_national(
        parse_qty(summary.get("from_store_num_h")),
        parse_qty(summary.get("from_store_transit")),
        parse_qty(summary.get("out_put_num")),
    )
    demand = parse_qty(summary.get("plan_num"))
    result = eval_national_supply_status(supply, demand)
    return {"product_code": product_code, "adjust_date": adjust_date, **result}


@tool(
    name="eval_national_supply_status",
    description=(
        "【SupplyChainMetrics.eval_national_supply_status】全国供应状态判定。\n"
        "规则：月度供应 vs 月度需求（销售计划），±5% 为持平带。\n"
        "  PLENTIFUL：供应 > 需求×1.05\n"
        "  BALANCED：需求×0.95 ≤ 供应 ≤ 需求×1.05\n"
        "  DEFICIT：供应 < 需求×0.95\n"
        "月度供应 = 全国现库 + 在途 + 当月累出。\n"
        "输入：product_code, adjust_date。\n"
        "返回：status, monthly_supply, monthly_demand, supply_demand_ratio, applied_rule。"
    ),
)
async def eval_national_supply_status_tool(
    product_code: str,
    adjust_date: str,
) -> dict:
    return await _national_supply_result(product_code, adjust_date)


async def _eval_target_stock_rate(
    product_code: str,
    site_code: str,
    adjust_date: str,
    period: _PERIOD = "mid_month",
) -> dict:
    national = await _national_supply_result(product_code, adjust_date)
    if national.get("error"):
        return national
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found"}
    plan = parse_qty(snap.get("plan_num"))
    output = parse_qty(snap.get("out_put_num"))
    unship = parse_qty(snap.get("total_unship"))
    order_progress = calc_order_progress(unship, output, plan)
    target = eval_target_stock_rate(
        national["status"],
        order_progress,
        period,
    )
    return {
        "product_code": product_code,
        "site_code": site_code,
        "adjust_date": adjust_date,
        "period": period,
        "national_status": national["status"],
        **target,
    }


@tool(
    name="eval_target_stock_rate",
    description=(
        "【StandardPolicyMatrix + SupplyChainMetrics】目标生产备货率。\n"
        "输入：product_code, site_code, adjust_date, period（early_month|mid_month|late_month）。\n"
        "须先理解全国状态（内部会调 eval_national_supply_status 逻辑）。\n"
        "规则摘要：\n"
        "  充足态+中旬：订单进度>标准进度(50%)时，目标=min(订单进度+20%, 100%)；否则按标准进度。\n"
        "  持平态：目标=min(订单进度+20%, 100%)。\n"
        "  不足态：优先满足订单，目标=订单进度，不超前备货。\n"
        "返回：target_rate, target_rate_pct, applied_rule, inputs_used。"
    ),
)
async def eval_target_stock_rate_tool(
    product_code: str,
    site_code: str,
    adjust_date: str,
    period: _PERIOD = "mid_month",
) -> dict:
    return await _eval_target_stock_rate(product_code, site_code, adjust_date, period)


@tool(
    name="calc_replenishment_quantity",
    description=(
        "【派生计算】建议补货量。\n"
        "公式：目标口径库存 − 当前口径库存；目标口径 = 销售计划 × 目标备货率。\n"
        "当前口径 = 现货 + 在途 + 本月累出（与备货率分子一致）。\n"
        "输入：product_code, site_code, adjust_date, period。\n"
        "内部会先求 eval_target_stock_rate。\n"
        "返回：replenishment_qty, target_basis, current_basis, applied_rule。"
    ),
)
async def calc_replenishment_quantity_tool(
    product_code: str,
    site_code: str,
    adjust_date: str,
    period: _PERIOD = "mid_month",
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found"}
    target_result = await _eval_target_stock_rate(
        product_code, site_code, adjust_date, period
    )
    if target_result.get("error"):
        return target_result
    plan = parse_qty(snap.get("plan_num"))
    current = (
        parse_qty(snap.get("store_num"))
        + parse_qty(snap.get("store_transit"))
        + parse_qty(snap.get("out_put_num"))
    )
    calc = calc_replenishment_quantity(plan, target_result["target_rate"], current)
    return {
        "product_code": product_code,
        "site_code": site_code,
        "adjust_date": adjust_date,
        "period": period,
        "target_stock_rate": target_result["target_rate"],
        "target_stock_rate_pct": target_result["target_rate_pct"],
        "applied_target_rule": target_result["applied_rule"],
        **calc,
    }
