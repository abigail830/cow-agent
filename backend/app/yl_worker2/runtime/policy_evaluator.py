"""StandardPolicyMatrix and SupplyChainMetrics rules (pure functions)."""

from __future__ import annotations

from typing import Literal

NationalSupplyStatus = Literal["PLENTIFUL", "BALANCED", "DEFICIT"]
Period = Literal["early_month", "mid_month", "late_month"]

NATIONAL_SUPPLY_TOLERANCE = 0.05
TARGET_RATE_BOOST = 0.20

STANDARD_PERIOD_PROGRESS: dict[Period, float] = {
    "early_month": 0.33,
    "mid_month": 0.50,
    "late_month": 0.83,
}


def eval_national_supply_status(
    monthly_supply: float,
    monthly_demand: float,
    *,
    tolerance: float = NATIONAL_SUPPLY_TOLERANCE,
) -> dict:
    """National supply vs monthly demand (±tolerance band)."""
    if monthly_demand <= 0:
        return {
            "status": "BALANCED",
            "monthly_supply": monthly_supply,
            "monthly_demand": monthly_demand,
            "supply_demand_ratio": None,
            "applied_rule": "national.zero_demand_fallback",
        }
    ratio = monthly_supply / monthly_demand
    upper = 1.0 + tolerance
    lower = 1.0 - tolerance
    if ratio > upper:
        status: NationalSupplyStatus = "PLENTIFUL"
        rule = "national.supply_above_demand_plus_tolerance"
    elif ratio < lower:
        status = "DEFICIT"
        rule = "national.supply_below_demand_minus_tolerance"
    else:
        status = "BALANCED"
        rule = "national.supply_within_tolerance"
    return {
        "status": status,
        "monthly_supply": monthly_supply,
        "monthly_demand": monthly_demand,
        "supply_demand_ratio": round(ratio, 4),
        "applied_rule": rule,
    }


def eval_target_stock_rate(
    national_status: NationalSupplyStatus,
    order_progress: float,
    period: Period,
) -> dict:
    """StandardPolicyMatrix: target production stock rate for a warehouse."""
    standard = STANDARD_PERIOD_PROGRESS[period]
    order_above_standard = order_progress > standard

    if national_status == "PLENTIFUL":
        if period == "mid_month" and order_above_standard:
            target = min(order_progress + TARGET_RATE_BOOST, 1.0)
            rule = "plentiful.mid_month.order_above_standard"
        elif period == "mid_month":
            target = standard
            rule = "plentiful.mid_month.order_at_or_below_standard"
        elif order_above_standard:
            target = min(order_progress + TARGET_RATE_BOOST, 1.0)
            rule = f"plentiful.{period}.order_above_standard"
        else:
            target = standard
            rule = f"plentiful.{period}.order_at_or_below_standard"
    elif national_status == "BALANCED":
        target = min(order_progress + TARGET_RATE_BOOST, 1.0)
        rule = f"balanced.{period}.order_progress_plus_boost"
    else:
        target = min(order_progress, 1.0)
        rule = f"deficit.{period}.meet_order_only"

    return {
        "target_rate": round(target, 4),
        "target_rate_pct": round(target * 100, 1),
        "applied_rule": rule,
        "inputs_used": {
            "national_status": national_status,
            "order_progress": round(order_progress, 4),
            "order_progress_pct": round(order_progress * 100, 1),
            "period": period,
            "standard_period_progress": standard,
            "order_above_standard": order_above_standard,
        },
    }


def calc_order_gap(store: float, transit: float, unshipped: float) -> float:
    """发货缺口 = 现货 + 在途 − 未发订单."""
    return store + transit - unshipped


def calc_ship_gap(store: float, unshipped: float) -> float:
    """发货缺口（仅现货）= 现货 − 未发订单."""
    return store - unshipped


def calc_order_progress(unshipped: float, monthly_output: float, plan: float) -> float:
    """订单完成率 = (未发货 + 本月累出) / 销售计划."""
    if plan <= 0:
        return 0.0
    return (unshipped + monthly_output) / plan


def calc_current_stock_rate(store: float, transit: float, monthly_output: float, plan: float) -> float:
    """生产备货率 = (现货 + 在途 + 本月累出) / 销售计划."""
    if plan <= 0:
        return 0.0
    return (store + transit + monthly_output) / plan


def calc_replenishment_quantity(plan: float, target_rate: float, current_basis: float) -> dict:
    """建议补货量 = 目标口径库存 − 当前口径库存."""
    target_basis = plan * target_rate
    qty = max(0.0, target_basis - current_basis)
    return {
        "replenishment_qty": round(qty, 2),
        "target_basis": round(target_basis, 2),
        "current_basis": round(current_basis, 2),
        "plan_num": plan,
        "target_rate": target_rate,
        "applied_rule": "replenishment.target_basis_minus_current",
    }


def monthly_supply_from_national(
    store: float,
    transit: float,
    monthly_output: float,
) -> float:
    """全国月度供应 = 现库 + 在途 + 当月累出（OIP 口径）."""
    return store + transit + monthly_output
