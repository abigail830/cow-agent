#!/usr/bin/env python3
"""Generate 1-year mockup SQL for MOCK_YLP001 (珍护1段)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

PRODUCT_CODE = "MOCK_YLP001"
PRODUCT_NAME = "金领冠珍护1段婴儿配方奶粉(测试)"
PRO_SERIES = "金领冠珍护系列"
BUSINESS_CODE = "NFBU"
BUSINESS = "奶粉事业部"

START = date(2025, 7, 1)
MONTHS = 12

SALES_WAREHOUSES = [
    ("MOCK_WH_S01", "合肥销售仓", "east", 5500, 0.42, 0.58),
    ("MOCK_WH_S02", "天津销售仓", "north", 6000, 0.55, 0.45),
    ("MOCK_WH_S03", "广州销售仓", "south", 10000, 0.35, 0.65),
    ("MOCK_WH_S04", "郑州销售仓", "central", 7000, 0.62, 0.38),
    ("MOCK_WH_S05", "成都销售仓", "west", 6000, 0.48, 0.52),
    ("MOCK_WH_S06", "武汉销售仓", "central", 6800, 0.50, 0.50),
    ("MOCK_WH_S07", "呼市销售仓", "north", 4500, 0.58, 0.42),
    ("MOCK_WH_S08", "济南销售仓", "east", 7500, 0.52, 0.48),
    ("MOCK_WH_S09", "柳州销售仓", "south", 3500, 0.60, 0.40),
]

BASE_WAREHOUSES = [
    ("MOCK_WH_B01", "呼市基地仓", 52000),
    ("MOCK_WH_B02", "天津基地仓", 28000),
    ("MOCK_WH_B03", "杜蒙基地仓", 35000),
    ("MOCK_WH_B04", "武汉基地仓", 30000),
]

# 销仓 -> 主供基地仓
PRIMARY_BASE = {
    "MOCK_WH_S01": "MOCK_WH_B04",
    "MOCK_WH_S02": "MOCK_WH_B02",
    "MOCK_WH_S03": "MOCK_WH_B01",
    "MOCK_WH_S04": "MOCK_WH_B01",
    "MOCK_WH_S05": "MOCK_WH_B04",
    "MOCK_WH_S06": "MOCK_WH_B04",
    "MOCK_WH_S07": "MOCK_WH_B01",
    "MOCK_WH_S08": "MOCK_WH_B02",
    "MOCK_WH_S09": "MOCK_WH_B04",
}

BASE_NAME = {c: n for c, n, _ in BASE_WAREHOUSES}
SALES_NAME = {c: n for c, n, *_ in SALES_WAREHOUSES}

SEASON = {
    1: 1.35, 2: 1.20, 3: 0.95, 4: 0.90, 5: 1.25, 6: 1.45,
    7: 0.85, 8: 0.90, 9: 1.00, 10: 1.05, 11: 1.40, 12: 1.15,
}

REGION_ACTUAL = {
    "south": 1.02, "east": 0.98, "north": 0.88, "central": 1.00, "west": 1.05,
}

# 基地仓 mock 特性：待检比例、批次切分、生产节奏
BASE_PROFILE = {
    "MOCK_WH_B01": {"pending_ratio": 0.10, "batches": 3, "fresh_days": 25, "note": "全国主供仓-批次多待检高"},
    "MOCK_WH_B02": {"pending_ratio": 0.06, "batches": 2, "fresh_days": 20, "note": "华北区域仓-同城双仓"},
    "MOCK_WH_B03": {"pending_ratio": 0.05, "batches": 2, "fresh_days": 30, "note": "黄金奶源带-大宗入库"},
    "MOCK_WH_B04": {"pending_ratio": 0.07, "batches": 2, "fresh_days": 22, "note": "华中枢纽-多向分拨"},
}

SALES_ADDRESS = {
    "MOCK_WH_S01": ("伊利奶粉合肥分仓", "安徽省合肥市蜀山区物流园8号库"),
    "MOCK_WH_S02": ("伊利奶粉天津分仓", "天津市东丽区物流枢纽2号库"),
    "MOCK_WH_S03": ("伊利奶粉广州分仓", "广东省广州市白云区物流园3号库"),
    "MOCK_WH_S04": ("伊利奶粉郑州分仓", "河南省郑州市中牟县物流港2号库"),
    "MOCK_WH_S05": ("伊利奶粉成都分仓", "四川省成都市青白江区物流园5号库"),
    "MOCK_WH_S06": ("伊利奶粉武汉分仓", "湖北省武汉市东西湖区物流园1号库"),
    "MOCK_WH_S07": ("伊利奶粉呼市分仓", "内蒙古呼和浩特市玉泉区仓储中心"),
    "MOCK_WH_S08": ("伊利奶粉济南分仓", "山东省济南市历城区冷链物流园"),
    "MOCK_WH_S09": ("伊利奶粉柳州分仓", "广西柳州市阳和工业新区物流仓"),
}

# 分仓基准库存天数 / 在途天数（× avg_plan_num → 件数；DOS ≈ 两者之和）
# 故事线见 default_stock_transit_days() 与 compute_snapshot() 硬编码分支
WH_DOS_BASE: dict[str, float] = {
    "MOCK_WH_S01": 22.0,  # 合肥 · 华东枢纽，中等周转
    "MOCK_WH_S02": 26.0,  # 天津 · 华北主仓（7-8月压仓故事另覆盖）
    "MOCK_WH_S03": 19.0,  # 广州 · 华南大仓快周转
    "MOCK_WH_S04": 24.0,  # 郑州 · 中原
    "MOCK_WH_S05": 33.0,  # 成都 · 西部远距，安全库存偏高
    "MOCK_WH_S06": 23.0,  # 武汉 · 华中枢纽
    "MOCK_WH_S07": 29.0,  # 呼市 · 北方小仓 + 淡季波动
    "MOCK_WH_S08": 21.0,  # 济南 · 华东北部
    "MOCK_WH_S09": 31.0,  # 柳州 · 华南边远 + 补货周期长
}
WH_TRANSIT_BASE: dict[str, float] = {
    "MOCK_WH_S01": 2.8,   # 武汉基地 → 合肥
    "MOCK_WH_S02": 1.2,   # 天津基地同城
    "MOCK_WH_S03": 4.8,   # 呼市 → 广州干线
    "MOCK_WH_S04": 3.0,   # 呼市 → 郑州
    "MOCK_WH_S05": 5.5,   # 武汉 → 成都远距
    "MOCK_WH_S06": 1.0,   # 武汉同城
    "MOCK_WH_S07": 1.0,   # 呼市同城
    "MOCK_WH_S08": 2.0,   # 天津 → 济南
    "MOCK_WH_S09": 4.0,   # 武汉 → 柳州
}


@dataclass(frozen=True)
class Route:
    lead_days: int
    distance_km: int
    cost_tier: str  # 低/中/高
    carrier: str
    mode: str
    mid_location: str
    mid_lng: float
    mid_lat: float
    total_mileage_km: float


def _route(
    lead: int, dist: int, cost: str, carrier: str, mode: str,
    loc: str, lng: float, lat: float, mileage: float | None = None,
) -> Route:
    return Route(lead, dist, cost, carrier, mode, loc, lng, lat, mileage or float(dist))


# 基地/销仓 -> 销仓 路线参数（Lead Time / 距离 / 成本档）
ROUTES: dict[tuple[str, str], Route] = {
    ("MOCK_WH_B01", "MOCK_WH_S03"): _route(5, 2280, "高", "远洋物流有限责任公司", "铁路+公路", "湖南省韶关市京港澳高速段", 113.59, 24.81, 2280),
    ("MOCK_WH_B01", "MOCK_WH_S04"): _route(3, 920, "中", "中铁快运股份有限公司", "公路干线", "河北省张家口市京藏高速段", 114.88, 40.82, 920),
    ("MOCK_WH_B01", "MOCK_WH_S07"): _route(1, 15, "低", "内蒙古本地配送", "同城", "呼和浩特市玉泉区", 111.67, 40.81, 15),
    ("MOCK_WH_B02", "MOCK_WH_S02"): _route(1, 25, "低", "天津同城配送", "同城", "天津市东丽区", 117.35, 39.08, 25),
    ("MOCK_WH_B02", "MOCK_WH_S08"): _route(2, 420, "中", "德邦物流股份有限公司", "公路", "山东省德州市京沪高速段", 116.36, 37.45, 420),
    ("MOCK_WH_B03", "MOCK_WH_S02"): _route(3, 980, "中", "黑龙江发运专线", "公路", "辽宁省锦州市京哈高速段", 121.13, 41.10, 980),
    ("MOCK_WH_B03", "MOCK_WH_S07"): _route(2, 680, "中", "黑龙江发运专线", "公路", "内蒙古乌兰察布市", 113.13, 41.00, 680),
    ("MOCK_WH_B04", "MOCK_WH_S01"): _route(2, 380, "中", "华中区域配送", "公路", "安徽省安庆市沪渝高速段", 117.05, 30.52, 380),
    ("MOCK_WH_B04", "MOCK_WH_S05"): _route(4, 1180, "高", "德邦物流股份有限公司", "公路干线", "重庆市万州区沪蓉高速段", 108.39, 30.81, 1180),
    ("MOCK_WH_B04", "MOCK_WH_S06"): _route(1, 20, "低", "武汉同城配送", "同城", "武汉市东西湖区", 114.13, 30.62, 20),
    ("MOCK_WH_B04", "MOCK_WH_S09"): _route(3, 860, "中", "华南区域配送", "公路", "广西桂林市泉南高速段", 110.28, 25.27, 860),
    ("MOCK_WH_S02", "MOCK_WH_S04"): _route(1, 680, "中", "德邦物流股份有限公司", "公路", "河北省邯郸市京港澳高速段", 114.54, 36.62, 680),
    ("MOCK_WH_S08", "MOCK_WH_S01"): _route(2, 720, "中", "华东区域配送", "公路", "江苏省徐州市连霍高速段", 117.18, 34.26, 720),
}


def route_for(from_code: str, to_code: str) -> Route:
    if (from_code, to_code) in ROUTES:
        return ROUTES[(from_code, to_code)]
    return _route(3, 800, "中", "德邦物流股份有限公司", "公路", "途中国道枢纽", 112.0, 34.0, 800)


@dataclass
class MonthRow:
    year: int
    month: int
    site_code: str
    site_name: str
    region: str
    plan_num: int
    avg_plan: float
    next_plan: int
    next_avg: float
    sell_num: int
    out_put: int
    unship: int
    ec_ratio: float


@dataclass
class Snapshot:
    row: MonthRow
    adjust_date: str
    stock_h: int
    pending: int
    transit: int
    ship_gap: int
    order_gap: int
    deduct_sum: int
    produce_fresh: date
    produce_old: date | None
    old_batch_qty: int
    big_date_num: int


@dataclass
class BaseSnapshot:
    year: int
    month: int
    site_code: str
    site_name: str
    adjust_date: str
    qualified: int
    pending: int
    outbound_transit: int
    month_in: int
    now_in: int
    produce_dates: list[date]
    batch_shares: list[float]


@dataclass
class ForwardTransfer:
    adjust_date: str
    from_code: str
    from_name: str
    to_code: str
    to_name: str
    trans_num: int
    from_available: int
    reason: str
    push_user: str = "AI_SCHEDULER"


@dataclass
class LateralTransfer:
    adjust_date: str
    from_code: str
    from_name: str
    to_code: str
    to_name: str
    trans_num: int
    from_stock_before: int
    from_plan: int
    to_stock_before: int
    to_plan: int
    reason: str


def month_iter():
    y, m = START.year, START.month
    for _ in range(MONTHS):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def days_in_month(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


def month_end(y: int, m: int) -> str:
    return f"{y}-{m:02d}-{days_in_month(y, m):02d}"


def actual_multiplier(y: int, m: int, region: str, ec_ratio: float) -> float:
    base = REGION_ACTUAL[region]
    if m in (5, 6) and region == "south":
        base = 1.18 if m == 5 else 1.32
    elif m == 11 and ec_ratio >= 0.5:
        base = 1.25
    elif m in (7, 8) and region == "north":
        base = 0.72
    elif m in (1, 2):
        base *= 1.08
    return base


def compute_fulfillment(
    code: str, y: int, m: int, region: str, ec_r: float, plan: int, sell: int,
) -> tuple[int, int]:
    """(out_put, unship)。unship = 已接单未发货量；out_put = 本月已出库。"""
    dim = days_in_month(y, m)

    # 618 广州严重缺货（故事线）
    if code == "MOCK_WH_S03" and y == 2026 and m == 5:
        out_put = int(round(sell * 0.68))
        return out_put, sell - out_put

    # 618 柳州横向援广州后本地发货紧张
    if code == "MOCK_WH_S09" and y == 2026 and m == 5:
        out_put = int(round(sell * 0.72))
        return out_put, sell - out_put

    # 618 武汉援华南后出库受限
    if code == "MOCK_WH_S06" and y == 2026 and m == 5:
        out_put = int(round(sell * 0.78))
        return out_put, sell - out_put

    # 618 后广州仍消化 backlog
    if code == "MOCK_WH_S03" and y == 2026 and m == 6:
        unship = 1200
        return max(0, sell - unship), unship

    # 双11 电商仓订单挤压
    if m == 11 and ec_r >= 0.48:
        unship = int(round(sell * (0.04 + ec_r * 0.05)))
        return sell - unship, unship

    # 518/618 前置：华南电商仓轻度积压
    if m in (5, 6) and region == "south" and ec_r >= 0.55 and not (y == 2026 and m == 5 and code == "MOCK_WH_S03"):
        unship = int(round(sell * 0.03))
        return sell - unship, unship

    # 常态 backlog：约 1.5~3.5 天日均计划（电商仓略高）
    daily = plan / dim if dim else 0
    backlog_days = 1.8 + ec_r * 1.8
    if region == "north" and m in (7, 8):
        backlog_days *= 0.45
    unship = int(round(daily * backlog_days))
    unship = max(60, min(unship, int(round(sell * 0.06)))) if plan >= 3000 else max(0, unship)

    out_put = sell - unship
    return out_put, unship


def default_stock_transit_days(r: MonthRow) -> tuple[float, float]:
    """按区域/季节/节庆/渠道调节基准库存天数与在途天数。"""
    code, m, region = r.site_code, r.month, r.region
    stock_d = WH_DOS_BASE[code]
    transit_d = WH_TRANSIT_BASE[code]
    ec_r = r.ec_ratio

    # 春节 1-2 月：销区备货
    if m in (1, 2):
        stock_d += 5 if region in ("south", "east", "central") else 3
        transit_d += 0.5
    # 518/618：华南动销前置，现货 lean、在途加大
    elif m in (5, 6) and region == "south":
        stock_d -= 3
        transit_d += 2.0 if m == 5 else 1.5
    # 华北 7-8 月淡季：现货偏高、在途减少
    elif m in (7, 8) and region == "north":
        stock_d += 9
        transit_d *= 0.35
    # 双11：电商仓现货 lean、在途前置
    elif m == 11:
        if ec_r >= 0.48:
            stock_d -= 2
        transit_d += 1.5
    # 12 月：年末缓冲
    elif m == 12:
        stock_d += 3

    # 电商占比高的仓在途略增（618/双11 以外）
    if ec_r >= 0.55 and m not in (7, 8):
        transit_d += 0.7

    return stock_d, transit_d


def build_rows() -> list[MonthRow]:
    rows: list[MonthRow] = []
    timeline = list(month_iter())
    for i, (y, m) in enumerate(timeline):
        dim = days_in_month(y, m)
        next_y, next_m = timeline[i + 1] if i + 1 < len(timeline) else (
            y + (1 if m == 12 else 0), 1 if m == 12 else m + 1
        )
        next_dim = days_in_month(next_y, next_m)
        for code, name, region, base, offline_r, ec_r in SALES_WAREHOUSES:
            plan = int(round(base * SEASON[m]))
            nplan = int(round(base * SEASON[next_m]))
            avg = round(plan / dim, 5)
            navg = round(nplan / next_dim, 5)
            mult = actual_multiplier(y, m, region, ec_r)
            sell = int(round(plan * mult))
            out_put, unship = compute_fulfillment(code, y, m, region, ec_r, plan, sell)
            rows.append(MonthRow(y, m, code, name, region, plan, avg, nplan, navg, sell, out_put, unship, ec_r))
    return rows


def compute_snapshot(r: MonthRow) -> Snapshot:
    stock_days, transit_days = default_stock_transit_days(r)
    stock_h = int(round(r.avg_plan * stock_days))
    transit = int(round(r.avg_plan * transit_days))
    produce_fresh = date(r.year, r.month, 10) - timedelta(days=60)
    produce_old = None
    old_batch_qty = 0
    big_date_num = 0

    # ---- 硬编码故事线（覆盖默认值）----
    if r.site_code == "MOCK_WH_S03" and r.year == 2026 and r.month == 5:
        # 618 广州严重缺货：现货极低 + 基地紧急直发在途
        stock_h = 200
        transit = 8000
        produce_fresh = date(2026, 3, 10)
    elif r.site_code == "MOCK_WH_S09" and r.year == 2026 and r.month == 5:
        # 618 柳州横向调拨 1800 件救广州后自身红灯
        stock_h = 380
        transit = int(round(r.avg_plan * 2))
    elif r.site_code == "MOCK_WH_S06" and r.year == 2026 and r.month == 5:
        # 618 武汉横向调拨 2500 件援广州后库存告急
        stock_h = 1100
        transit = int(round(r.avg_plan * 1.6))
    elif r.site_code == "MOCK_WH_S03" and r.year == 2026 and r.month == 6:
        # 618 后基地+计划双轨过补 → 压仓
        stock_h = 24000
        transit = 6000
        produce_fresh = date(2026, 4, 11)
        produce_old = date(2026, 2, 20)
        old_batch_qty = 4200
        big_date_num = 4200
    elif r.site_code == "MOCK_WH_S09" and r.year == 2026 and r.month == 6:
        # 柳州：5 月失血后 6 月又被过补 → 压仓
        stock_h = 11000
        transit = 2500
    elif r.site_code == "MOCK_WH_S08" and r.year == 2026 and r.month == 6:
        # 济南：华北货误投华南线后滞留 → 压仓
        stock_h = 20000
        transit = 2500
    elif r.site_code == "MOCK_WH_S05" and r.year == 2026 and r.month == 6:
        # 成都：西部动销稳但货源被华南挤占 → 黄灯偏低
        stock_h = 3000
        transit = 900
    elif r.site_code == "MOCK_WH_S06" and r.year == 2026 and r.month == 6:
        # 武汉：5 月援桂后 6 月仅部分恢复 → 黄灯
        stock_h = 3600
        transit = 900
    elif r.site_code == "MOCK_WH_S02" and r.year == 2025 and r.month in (7, 8):
        # 天津华北淡季压仓 + 大日期
        stock_h = int(round(r.avg_plan * 55))
        transit = 0
        produce_old = date(2025, 2, 15)
        old_batch_qty = stock_h
        big_date_num = stock_h
    elif r.site_code == "MOCK_WH_S02" and r.year == 2025 and r.month >= 9:
        stock_h = int(round(r.avg_plan * 38))
        produce_old = date(2025, 2, 15)
        old_batch_qty = int(stock_h * 0.6)
        big_date_num = old_batch_qty if r.month <= 11 else int(old_batch_qty * 0.8)
    elif r.site_code == "MOCK_WH_S02" and r.year == 2026 and r.month <= 3:
        stock_h = int(round(r.avg_plan * 32))
        produce_old = date(2025, 2, 15)
        old_batch_qty = int(stock_h * 0.5)
        big_date_num = old_batch_qty
    elif r.site_code == "MOCK_WH_S07" and r.month in (7, 8):
        # 呼市北方小仓淡季偏高
        stock_h = int(round(r.avg_plan * (WH_DOS_BASE[r.site_code] + 12)))
        transit = int(round(r.avg_plan * 0.6))
    elif r.site_code == "MOCK_WH_S05" and m_in_peak_west(r):
        # 成都西部远距：双11/春节前补货窗口在途加大
        transit = int(round(r.avg_plan * (WH_TRANSIT_BASE[r.site_code] + 2)))

    pending = int(round(stock_h * 0.05)) if stock_h > 500 else 0
    if r.site_code == "MOCK_WH_S03" and r.year == 2026 and r.month == 5:
        pending = 0

    # 高未发时略增在途（调度响应）；618 故事仓除外
    _story_no_transit_boost = (
        (r.site_code == "MOCK_WH_S03" and r.year == 2026 and r.month == 5)
        or (r.site_code in ("MOCK_WH_S09", "MOCK_WH_S06") and r.year == 2026 and r.month == 5)
        or (
            r.year == 2026
            and r.month == 6
            and r.site_code in ("MOCK_WH_S03", "MOCK_WH_S09", "MOCK_WH_S08", "MOCK_WH_S05", "MOCK_WH_S06")
        )
    )
    if r.unship > 500 and not _story_no_transit_boost:
        transit = max(transit, int(round(r.avg_plan * 4)))

    deduct_sum = stock_h - r.unship
    ship_gap = stock_h - r.unship
    order_gap = stock_h + transit - r.unship

    return Snapshot(
        row=r, adjust_date=month_end(r.year, r.month),
        stock_h=stock_h, pending=pending, transit=transit,
        ship_gap=ship_gap, order_gap=order_gap, deduct_sum=deduct_sum,
        produce_fresh=produce_fresh, produce_old=produce_old,
        old_batch_qty=old_batch_qty, big_date_num=big_date_num,
    )


def m_in_peak_west(r: MonthRow) -> bool:
    return r.month in (1, 2, 11) and r.region == "west"


def compute_base_snapshots(rows: list[MonthRow]) -> list[BaseSnapshot]:
    by_month: dict[tuple[int, int], int] = {}
    for r in rows:
        by_month[(r.year, r.month)] = by_month.get((r.year, r.month), 0) + r.plan_num

    out: list[BaseSnapshot] = []
    for (y, m), total_demand in sorted(by_month.items()):
        adj = month_end(y, m)
        dim = days_in_month(y, m)
        season = SEASON[m]
        anchor = date(y, m, min(15, dim))
        for code, name, cap in BASE_WAREHOUSES:
            prof = BASE_PROFILE[code]
            share = {"MOCK_WH_B01": 0.38, "MOCK_WH_B02": 0.18, "MOCK_WH_B03": 0.24, "MOCK_WH_B04": 0.20}[code]
            qualified = int(round(cap * (0.75 + 0.15 * season)))
            pending = int(round(qualified * prof["pending_ratio"]))
            outbound = int(round(total_demand * share * 0.12))
            month_in = int(round(total_demand * share * 1.05))
            now_in = int(round(month_in / dim))
            n_batches = prof["batches"]
            if n_batches == 3:
                shares = [0.50, 0.35, 0.15]
                offsets = [prof["fresh_days"], prof["fresh_days"] + 35, prof["fresh_days"] + 70]
            else:
                shares = [0.65, 0.35]
                offsets = [prof["fresh_days"], prof["fresh_days"] + 45]
            produce_dates = [anchor - timedelta(days=d) for d in offsets]
            out.append(BaseSnapshot(
                y, m, code, name, adj, qualified, pending, outbound, month_in, now_in,
                produce_dates, shares[:n_batches],
            ))
    return out


def build_snapshots(rows: list[MonthRow]) -> dict[tuple[int, int, str], Snapshot]:
    return {(s.row.year, s.row.month, s.row.site_code): s for s in (compute_snapshot(r) for r in rows)}


def sql_num(n: float | int) -> str:
    return f"{float(n):.5f}"


def emit_sales_plan(rows: list[MonthRow]) -> list[str]:
    lines = [
        "-- =============================================================================",
        "-- 珍护1段 · 全国销售仓 · 12个月销售计划 (yl_sales_plan)",
        "-- =============================================================================",
        "DELETE FROM yl_sales_plan WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_sales_plan (",
        "    ds, plan_year, plan_month, product_code, product_name, site_code, site_name, site_type,",
        "    plan_num, next_plan_num, avg_plan_num, next_avg_plan_num, remark",
        ") VALUES",
    ]
    vals = []
    for r in rows:
        ds = f"{r.year}-{r.month:02d}-01"
        vals.append(
            f"('{ds}', {r.year}, {r.month}, '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
            f"'{r.site_code}', '{r.site_name}', 1, "
            f"{sql_num(r.plan_num)}, {sql_num(r.next_plan)}, {sql_num(r.avg_plan)}, {sql_num(r.next_avg)}, "
            f"'{r.year}年{r.month}月{r.site_name}计划')"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_actual_sales(rows: list[MonthRow]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- 珍护1段 · 全国销售仓 · 12个月实际销量 (yl_actual_sales)",
        "-- =============================================================================",
        "DELETE FROM yl_actual_sales WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_actual_sales (",
        "    ds, sell_year, sell_month, product_code, product_name, site_code, site_name, site_type,",
        "    sell_num, out_put_num, sell_num_avg, available_quantity, remark, pick_store, unshipped_orders",
        ") VALUES",
    ]
    vals = []
    for r in rows:
        dim = days_in_month(r.year, r.month)
        ds = month_end(r.year, r.month)
        vals.append(
            f"('{ds}', {r.year}, {r.month}, '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
            f"'{r.site_code}', '{r.site_name}', 1, "
            f"{sql_num(r.sell_num)}, {sql_num(r.out_put)}, {sql_num(round(r.sell_num / dim, 5))}, "
            f"{sql_num(max(0, r.unship))}, '{r.year}年{r.month}月{r.site_name}实绩', "
            f"{sql_num(r.out_put)}, {sql_num(r.unship)})"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_base_reports(rows: list[MonthRow]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- 珍护1段 · 4个基地仓 · 月末库存监控 (yl_base_warehouse_inventory_report)",
        "-- =============================================================================",
        "DELETE FROM yl_base_warehouse_inventory_report WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_base_warehouse_inventory_report (",
        "    adjust_date, business_code, product_code, product_name, weight, pro_series,",
        "    from_site_code, from_site_name, month_store_in, now_store_in,",
        "    big_date, big_date_num, days_list, from_store_transit, from_store_num_d, from_store_num_h,",
        "    to_jd_site_list, months_list",
        ") VALUES",
    ]
    by_month: dict[tuple[int, int], int] = {}
    for r in rows:
        by_month[(r.year, r.month)] = by_month.get((r.year, r.month), 0) + r.plan_num
    vals = []
    for (y, m), total_demand in sorted(by_month.items()):
        adj = month_end(y, m)
        season = SEASON[m]
        for code, name, cap in BASE_WAREHOUSES:
            share = {"MOCK_WH_B01": 0.38, "MOCK_WH_B02": 0.18, "MOCK_WH_B03": 0.24, "MOCK_WH_B04": 0.20}[code]
            qualified = int(round(cap * (0.75 + 0.15 * season)))
            pending = int(round(qualified * 0.08))
            transit = int(round(total_demand * share * 0.12))
            month_in = int(round(total_demand * share * 1.05))
            vals.append(
                f"('{adj}', '{BUSINESS_CODE}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
                f"{sql_num(qualified * 0.005)}, '{PRO_SERIES}', '{code}', '{name}', "
                f"{sql_num(month_in)}, {sql_num(int(round(month_in / days_in_month(y, m))))}, "
                f"'{y}-{m:02d}-15', 0.00000, '待检:{pending},合格:{qualified}', "
                f"{sql_num(transit)}, {sql_num(pending)}, {sql_num(qualified)}, "
                f"'MOCK_WH_S03,MOCK_WH_S06', '{y}-{m:02d}:{month_in}')"
            )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_sales_reports(snapshots: list[Snapshot]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- 珍护1段 · 9个销售仓 · 月末库存监控 (yl_sales_warehouse_inventory_report)",
        "-- =============================================================================",
        "DELETE FROM yl_sales_warehouse_inventory_report WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_sales_warehouse_inventory_report (",
        "    adjust_date, business_code, product_code, product_name, weight, pro_series,",
        "    from_site_code, from_site_name, area_plan, order_completion_rate, sell_completion_rate,",
        "    out_put_num, out_put_area, out_put_ec, from_store_transit, from_store_num_d, from_store_num_h,",
        "    from_store_num_lh_d, from_store_num_lh_h, total_unship, ship_gap, order_gap,",
        "    plan_num, sell_num, next_plan_num, avg_plan_num, next_avg_plan_num, big_date, big_date_num",
        ") VALUES",
    ]
    wh_lookup = {c: (o, e) for c, _, _, _, o, e in SALES_WAREHOUSES}
    vals = []
    for s in snapshots:
        r = s.row
        offline_r, ec_r = wh_lookup[r.site_code]
        ocr = min(150, round((r.unship + r.out_put) / r.plan_num * 100, 1)) if r.plan_num else 100
        scr = min(150, round(r.out_put / r.plan_num * 100, 1)) if r.plan_num else 100
        bd = s.produce_old.isoformat() if s.big_date_num > 0 and s.produce_old else "无"
        vals.append(
            f"('{s.adjust_date}', '{BUSINESS_CODE}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
            f"{sql_num(s.stock_h * 0.005)}, '{PRO_SERIES}', '{r.site_code}', '{r.site_name}', "
            f"{sql_num(r.plan_num)}, '{ocr}%', '{scr}%', "
            f"{sql_num(r.out_put)}, {sql_num(round(r.out_put * offline_r, 5))}, {sql_num(round(r.out_put * ec_r, 5))}, "
            f"{sql_num(s.transit)}, {sql_num(s.pending)}, {sql_num(s.stock_h)}, "
            f"0.00000, 0.00000, {sql_num(r.unship)}, {sql_num(s.ship_gap)}, {sql_num(s.order_gap)}, "
            f"{sql_num(r.plan_num)}, {sql_num(r.sell_num)}, {sql_num(r.next_plan)}, "
            f"{sql_num(r.avg_plan)}, {sql_num(r.next_avg)}, '{bd}', {sql_num(s.big_date_num)})"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_national_reports(snapshots: list[Snapshot]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- 珍护1段 · 全国销售仓大盘 · 月末汇总 (yl_national_sales_warehouse_inventory_report)",
        "-- =============================================================================",
        "DELETE FROM yl_national_sales_warehouse_inventory_report WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_national_sales_warehouse_inventory_report (",
        "    adjust_date, business_code, product_code, product_name, weight, pro_series,",
        "    area_plan, order_completion_rate, sell_completion_rate,",
        "    out_put_num, out_put_area, out_put_ec, from_store_transit,",
        "    from_store_num_d, from_store_num_h, from_store_num_lh_d, from_store_num_lh_h,",
        "    total_unship, ship_gap, order_gap, avg_plan_num, next_avg_plan_num,",
        "    sell_num, plan_num, next_plan_num, xs_big_date_num, jd_big_date_num",
        ") VALUES",
    ]
    by_month: dict[tuple[int, int], list[Snapshot]] = {}
    for s in snapshots:
        by_month.setdefault((s.row.year, s.row.month), []).append(s)
    vals = []
    for (y, m), slist in sorted(by_month.items()):
        adj = month_end(y, m)
        dim = days_in_month(y, m)
        plan = sum(x.row.plan_num for x in slist)
        sell = sum(x.row.sell_num for x in slist)
        out_put = sum(x.row.out_put for x in slist)
        unship = sum(x.row.unship for x in slist)
        nplan = sum(x.row.next_plan for x in slist)
        stock_h = sum(x.stock_h for x in slist)
        transit = sum(x.transit for x in slist)
        pending = sum(x.pending for x in slist)
        xs_big = sum(x.big_date_num for x in slist)
        ocr = round((unship + out_put) / plan * 100, 1) if plan else 100
        scr = round(out_put / plan * 100, 1) if plan else 100
        vals.append(
            f"('{adj}', '{BUSINESS_CODE}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', {sql_num(stock_h * 0.005)}, '{PRO_SERIES}', "
            f"{sql_num(plan)}, '{ocr}%', '{scr}%', "
            f"{sql_num(out_put)}, {sql_num(round(out_put * 0.52, 5))}, {sql_num(round(out_put * 0.48, 5))}, "
            f"{sql_num(transit)}, {sql_num(pending)}, {sql_num(stock_h)}, 0.00000, 0.00000, "
            f"{sql_num(unship)}, {sql_num(stock_h - unship)}, {sql_num(stock_h + transit - unship)}, "
            f"{sql_num(round(plan / dim, 5))}, {sql_num(round(nplan / days_in_month(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1), 5))}, "
            f"{sql_num(sell)}, {sql_num(plan)}, {sql_num(nplan)}, {sql_num(xs_big)}, 0.00000)"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def _spot_fresh_deduct(s: Snapshot) -> int:
    """现货表合格批次 invetory_deduct_sum（与 emit_spot_inventory 一致）。"""
    r = s.row
    fresh_qty = s.stock_h - s.old_batch_qty
    if s.old_batch_qty > 0 and fresh_qty > 0:
        return max(0, fresh_qty - max(0, r.unship - s.old_batch_qty))
    if s.old_batch_qty > 0 and fresh_qty == 0:
        return s.deduct_sum
    return s.deduct_sum


def emit_unship_patch(rows: list[MonthRow], snapshots: list[Snapshot]) -> list[str]:
    """独立补丁：只更新未发/履约衍生字段，无需重跑 batch1/batch2 全量 DELETE+INSERT。"""
    wh_lookup = {c: (o, e) for c, _, _, _, o, e in SALES_WAREHOUSES}

    lines = [
        "-- =============================================================================",
        "-- 珍护1段(MOCK_YLP001) · 未发订单/履约字段 · 独立补丁",
        "-- 生成: generate_yl_zhenhu1_year.py",
        "-- 用途: 在已导入 batch1 + batch2 后单独执行，刷新 total_unship / ship_gap 等",
        "-- 执行: psql $YL_DATABASE_URL -f backend/migrations/sql/yl_zhenhu1_year_unship_patch.sql",
        "-- =============================================================================",
        "BEGIN;",
        "",
        "-- ---- yl_actual_sales ----",
    ]

    for r in rows:
        dim = days_in_month(r.year, r.month)
        ds = month_end(r.year, r.month)
        lines.append(
            f"UPDATE yl_actual_sales SET "
            f"out_put_num = {sql_num(r.out_put)}, "
            f"unshipped_orders = {sql_num(r.unship)}, "
            f"available_quantity = {sql_num(max(0, r.unship))}, "
            f"pick_store = {sql_num(r.out_put)} "
            f"WHERE product_code = '{PRODUCT_CODE}' AND site_code = '{r.site_code}' "
            f"AND sell_year = {r.year} AND sell_month = {r.month};"
        )

    lines.extend(["", "-- ---- yl_sales_warehouse_inventory_report ----"])
    for s in snapshots:
        r = s.row
        offline_r, ec_r = wh_lookup[r.site_code]
        ocr = min(150, round((r.unship + r.out_put) / r.plan_num * 100, 1)) if r.plan_num else 100
        scr = min(150, round(r.out_put / r.plan_num * 100, 1)) if r.plan_num else 100
        lines.append(
            f"UPDATE yl_sales_warehouse_inventory_report SET "
            f"out_put_num = {sql_num(r.out_put)}, "
            f"out_put_area = {sql_num(round(r.out_put * offline_r, 5))}, "
            f"out_put_ec = {sql_num(round(r.out_put * ec_r, 5))}, "
            f"from_store_transit = {sql_num(s.transit)}, "
            f"total_unship = {sql_num(r.unship)}, "
            f"ship_gap = {sql_num(s.ship_gap)}, "
            f"order_gap = {sql_num(s.order_gap)}, "
            f"order_completion_rate = '{ocr}%', "
            f"sell_completion_rate = '{scr}%' "
            f"WHERE product_code = '{PRODUCT_CODE}' AND from_site_code = '{r.site_code}' "
            f"AND adjust_date = '{s.adjust_date}';"
        )

    lines.extend(["", "-- ---- yl_national_sales_warehouse_inventory_report ----"])
    by_month: dict[tuple[int, int], list[Snapshot]] = {}
    for s in snapshots:
        by_month.setdefault((s.row.year, s.row.month), []).append(s)
    for (y, m), slist in sorted(by_month.items()):
        adj = month_end(y, m)
        dim = days_in_month(y, m)
        plan = sum(x.row.plan_num for x in slist)
        sell = sum(x.row.sell_num for x in slist)
        out_put = sum(x.row.out_put for x in slist)
        unship = sum(x.row.unship for x in slist)
        nplan = sum(x.row.next_plan for x in slist)
        stock_h = sum(x.stock_h for x in slist)
        transit = sum(x.transit for x in slist)
        pending = sum(x.pending for x in slist)
        xs_big = sum(x.big_date_num for x in slist)
        ocr = round((unship + out_put) / plan * 100, 1) if plan else 100
        scr = round(out_put / plan * 100, 1) if plan else 100
        next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
        lines.append(
            f"UPDATE yl_national_sales_warehouse_inventory_report SET "
            f"out_put_num = {sql_num(out_put)}, "
            f"out_put_area = {sql_num(round(out_put * 0.52, 5))}, "
            f"out_put_ec = {sql_num(round(out_put * 0.48, 5))}, "
            f"from_store_transit = {sql_num(transit)}, "
            f"from_store_num_d = {sql_num(pending)}, "
            f"from_store_num_h = {sql_num(stock_h)}, "
            f"total_unship = {sql_num(unship)}, "
            f"ship_gap = {sql_num(stock_h - unship)}, "
            f"order_gap = {sql_num(stock_h + transit - unship)}, "
            f"order_completion_rate = '{ocr}%', "
            f"sell_completion_rate = '{scr}%', "
            f"sell_num = {sql_num(sell)}, "
            f"plan_num = {sql_num(plan)}, "
            f"next_plan_num = {sql_num(nplan)}, "
            f"xs_big_date_num = {sql_num(xs_big)} "
            f"WHERE product_code = '{PRODUCT_CODE}' AND adjust_date = '{adj}';"
        )

    lines.extend(["", "-- ---- yl_spot_inventory（销售仓合格批次抵扣量） ----"])
    for s in snapshots:
        r = s.row
        fresh_qty = s.stock_h - s.old_batch_qty
        deduct = _spot_fresh_deduct(s)
        if s.old_batch_qty > 0 and fresh_qty > 0:
            lines.append(
                f"UPDATE yl_spot_inventory SET invetory_deduct_sum = {sql_num(deduct)} "
                f"WHERE product_code = '{PRODUCT_CODE}' AND site_code = '{r.site_code}' "
                f"AND ds = '{s.adjust_date}' AND status = '合格' "
                f"AND produce_date = '{s.produce_fresh.isoformat()}';"
            )
        elif s.old_batch_qty == 0 or fresh_qty == 0:
            prod = s.produce_old.isoformat() if s.old_batch_qty > 0 and fresh_qty == 0 else s.produce_fresh.isoformat()
            lines.append(
                f"UPDATE yl_spot_inventory SET invetory_deduct_sum = {sql_num(deduct)} "
                f"WHERE product_code = '{PRODUCT_CODE}' AND site_code = '{r.site_code}' "
                f"AND ds = '{s.adjust_date}' AND status = '合格' "
                f"AND produce_date = '{prod}';"
            )

    lines.extend([
        "",
        "COMMIT;",
        "",
        "-- 验证（2026-06 末快照应各仓 total_unship > 0，广州约 1200）:",
        "-- SELECT from_site_name, total_unship, ship_gap, from_store_num_h",
        "-- FROM yl_sales_warehouse_inventory_report",
        "-- WHERE product_code = 'MOCK_YLP001' AND adjust_date = '2026-06-30'",
        "-- ORDER BY total_unship DESC;",
    ])
    return lines


def emit_inventory_dos_patch(snapshots: list[Snapshot]) -> list[str]:
    """独立补丁：分仓差异化库存天数 / 在途 / 现货明细。"""
    lines = [
        "-- =============================================================================",
        "-- 珍护1段(MOCK_YLP001) · 库存天数(DOS)差异化 · 独立补丁",
        "-- 生成: generate_yl_zhenhu1_year.py",
        "-- 故事线: 618柳州/武汉横向救广州→周边缺货→6月华南过补压仓 + 西部黄灯",
        "-- 用途: 已导入 batch1+batch2 后执行，打破「全仓 25.9 天」假象",
        "-- 执行: psql $YL_DATABASE_URL -f backend/migrations/sql/yl_zhenhu1_year_inventory_dos_patch.sql",
        "-- 建议: 若未跑 unship 补丁，先跑 yl_zhenhu1_year_unship_patch.sql",
        "-- =============================================================================",
        "BEGIN;",
        "",
        "-- ---- yl_sales_warehouse_inventory_report ----",
    ]

    for s in snapshots:
        r = s.row
        bd = s.produce_old.isoformat() if s.big_date_num > 0 and s.produce_old else "无"
        lines.append(
            f"UPDATE yl_sales_warehouse_inventory_report SET "
            f"from_store_num_h = {sql_num(s.stock_h)}, "
            f"from_store_num_d = {sql_num(s.pending)}, "
            f"from_store_transit = {sql_num(s.transit)}, "
            f"ship_gap = {sql_num(s.ship_gap)}, "
            f"order_gap = {sql_num(s.order_gap)}, "
            f"big_date = '{bd}', "
            f"big_date_num = {sql_num(s.big_date_num)} "
            f"WHERE product_code = '{PRODUCT_CODE}' AND from_site_code = '{r.site_code}' "
            f"AND adjust_date = '{s.adjust_date}';"
        )

    lines.extend(["", "-- ---- yl_national_sales_warehouse_inventory_report ----"])
    by_month: dict[tuple[int, int], list[Snapshot]] = {}
    for s in snapshots:
        by_month.setdefault((s.row.year, s.row.month), []).append(s)
    for (y, m), slist in sorted(by_month.items()):
        adj = month_end(y, m)
        stock_h = sum(x.stock_h for x in slist)
        transit = sum(x.transit for x in slist)
        pending = sum(x.pending for x in slist)
        unship = sum(x.row.unship for x in slist)
        xs_big = sum(x.big_date_num for x in slist)
        lines.append(
            f"UPDATE yl_national_sales_warehouse_inventory_report SET "
            f"from_store_num_h = {sql_num(stock_h)}, "
            f"from_store_num_d = {sql_num(pending)}, "
            f"from_store_transit = {sql_num(transit)}, "
            f"ship_gap = {sql_num(stock_h - unship)}, "
            f"order_gap = {sql_num(stock_h + transit - unship)}, "
            f"xs_big_date_num = {sql_num(xs_big)} "
            f"WHERE product_code = '{PRODUCT_CODE}' AND adjust_date = '{adj}';"
        )

    lines.extend(["", "-- ---- yl_spot_inventory（销售仓合格/待检批次） ----"])
    for s in snapshots:
        r = s.row
        fresh_qty = s.stock_h - s.old_batch_qty
        fresh_deduct = _spot_fresh_deduct(s)
        dim = days_in_month(r.year, r.month)
        if s.old_batch_qty > 0 and fresh_qty > 0:
            for prod, qty, deduct in (
                (s.produce_fresh.isoformat(), fresh_qty, fresh_deduct),
                (s.produce_old.isoformat(), s.old_batch_qty, s.old_batch_qty),
            ):
                lines.append(
                    f"UPDATE yl_spot_inventory SET "
                    f"store_num = {sql_num(qty)}, invetory_deduct_sum = {sql_num(deduct)}, "
                    f"actual_num = {sql_num(qty)} "
                    f"WHERE product_code = '{PRODUCT_CODE}' AND site_code = '{r.site_code}' "
                    f"AND ds = '{s.adjust_date}' AND status = '合格' AND produce_date = '{prod}';"
                )
        else:
            prod = s.produce_old.isoformat() if s.old_batch_qty > 0 and fresh_qty == 0 else s.produce_fresh.isoformat()
            lines.append(
                f"UPDATE yl_spot_inventory SET "
                f"store_num = {sql_num(s.stock_h)}, invetory_deduct_sum = {sql_num(s.deduct_sum)}, "
                f"actual_num = {sql_num(s.stock_h)}, "
                f"inventory_month_num = {sql_num(r.out_put)} "
                f"WHERE product_code = '{PRODUCT_CODE}' AND site_code = '{r.site_code}' "
                f"AND ds = '{s.adjust_date}' AND status = '合格' AND produce_date = '{prod}';"
            )
        if s.pending > 0:
            lines.append(
                f"UPDATE yl_spot_inventory SET "
                f"store_num = {sql_num(s.pending)}, invetory_deduct_sum = {sql_num(s.pending)}, "
                f"actual_num = {sql_num(s.pending)} "
                f"WHERE product_code = '{PRODUCT_CODE}' AND site_code = '{r.site_code}' "
                f"AND ds = '{s.adjust_date}' AND status = '待检';"
            )

    lines.extend(["", "-- ---- yl_transit_inventory（月末基地→销仓在途快照） ----"])
    for s in snapshots:
        if s.transit <= 0:
            continue
        r = s.row
        base = PRIMARY_BASE[r.site_code]
        lines.append(
            f"UPDATE yl_transit_inventory SET store_transit = {sql_num(s.transit)} "
            f"WHERE product_code = '{PRODUCT_CODE}' AND ds = '{s.adjust_date}' "
            f"AND from_site_code = '{base}' AND to_site_code = '{r.site_code}';"
        )

    lines.extend([
        "",
        "COMMIT;",
        "",
        "-- 验证 2026-06 末快照 DOS 应分仓差异（广州/柳州/济南>60蓝，成都/武汉7-14黄）:",
        "-- 验证 2026-05 末：广州/柳州/武汉应有 618 横向+缺货信号（柳州/武汉 DOS<7）:",
        "-- SELECT from_site_name, from_store_num_h, from_store_transit, avg_plan_num,",
        "--   ROUND((from_store_num_h + from_store_transit) / NULLIF(avg_plan_num, 0), 1) AS dos_days",
        "-- FROM yl_sales_warehouse_inventory_report",
        "-- WHERE product_code = 'MOCK_YLP001' AND adjust_date = '2026-06-30'",
        "-- ORDER BY dos_days;",
    ])
    return lines


def emit_spot_inventory(snapshots: list[Snapshot], base_snapshots: list[BaseSnapshot]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- Batch2: 珍护1段 · 现货库存批次明细 (yl_spot_inventory)",
        "-- 与报表 from_store_num_h / invetory_deduct_sum 对齐",
        "-- =============================================================================",
        "DELETE FROM yl_spot_inventory WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_spot_inventory (",
        "    ds, product_code, product_name, site_code, site_name, site_type, produce_date, status,",
        "    store_num, invetory_deduct_sum, actual_order, actual_num, invetory_box_sum, inventory_month_num, inventory_yes_num",
        ") VALUES",
    ]
    vals = []
    # 销售仓：每月末快照
    for s in snapshots:
        r = s.row
        fresh_qty = s.stock_h - s.old_batch_qty
        if s.old_batch_qty > 0 and fresh_qty > 0:
            fresh_deduct = max(0, fresh_qty - max(0, r.unship - s.old_batch_qty))
            vals.append(
                f"('{s.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{r.site_code}', '{r.site_name}', 1, "
                f"'{s.produce_fresh.isoformat()}', '合格', {sql_num(fresh_qty)}, {sql_num(fresh_deduct)}, "
                f"{sql_num(fresh_qty)}, {sql_num(fresh_qty)}, 0.00000, {sql_num(r.out_put)}, {sql_num(int(r.out_put / days_in_month(r.year, r.month)))})"
            )
            vals.append(
                f"('{s.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{r.site_code}', '{r.site_name}', 1, "
                f"'{s.produce_old.isoformat()}', '合格', {sql_num(s.old_batch_qty)}, {sql_num(s.old_batch_qty)}, "
                f"{sql_num(s.old_batch_qty)}, {sql_num(s.old_batch_qty)}, 0.00000, 0.00000, 0.00000)"
            )
        elif s.old_batch_qty > 0 and fresh_qty == 0:
            vals.append(
                f"('{s.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{r.site_code}', '{r.site_name}', 1, "
                f"'{s.produce_old.isoformat()}', '合格', {sql_num(s.stock_h)}, {sql_num(s.deduct_sum)}, "
                f"{sql_num(s.stock_h)}, {sql_num(s.stock_h)}, 0.00000, {sql_num(r.out_put)}, {sql_num(int(r.out_put / days_in_month(r.year, r.month)))})"
            )
        else:
            vals.append(
                f"('{s.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{r.site_code}', '{r.site_name}', 1, "
                f"'{s.produce_fresh.isoformat()}', '合格', {sql_num(s.stock_h)}, {sql_num(s.deduct_sum)}, "
                f"{sql_num(s.stock_h)}, {sql_num(s.stock_h)}, 0.00000, {sql_num(r.out_put)}, {sql_num(int(r.out_put / days_in_month(r.year, r.month)))})"
            )
        if s.pending > 0:
            vals.append(
                f"('{s.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{r.site_code}', '{r.site_name}', 1, "
                f"'{s.produce_fresh.isoformat()}', '待检', {sql_num(s.pending)}, {sql_num(s.pending)}, "
                f"{sql_num(s.pending)}, {sql_num(s.pending)}, 0.00000, 0.00000, 0.00000)"
            )

    # 基地仓：12个月 × 4仓，多批次 + 待检池（与 base_warehouse_inventory_report 对齐）
    for bs in base_snapshots:
        batch_total = bs.qualified - bs.pending
        running = 0
        for i, (pd, share) in enumerate(zip(bs.produce_dates, bs.batch_shares)):
            qty = int(round(batch_total * share))
            if i == len(bs.batch_shares) - 1:
                qty = batch_total - running
            running += qty
            if qty <= 0:
                continue
            vals.append(
                f"('{bs.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{bs.site_code}', '{bs.site_name}', 0, "
                f"'{pd.isoformat()}', '合格', {sql_num(qty)}, {sql_num(qty)}, "
                f"{sql_num(qty)}, {sql_num(qty)}, 0.00000, {sql_num(bs.month_in if i == 0 else 0)}, "
                f"{sql_num(bs.now_in if i == 0 else 0)})"
            )
        if bs.pending > 0:
            vals.append(
                f"('{bs.adjust_date}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', '{bs.site_code}', '{bs.site_name}', 0, "
                f"'{bs.produce_dates[0].isoformat()}', '待检', {sql_num(bs.pending)}, {sql_num(bs.pending)}, "
                f"{sql_num(bs.pending)}, {sql_num(bs.pending)}, 0.00000, 0.00000, 0.00000)"
            )

    lines.append(",\n".join(vals) + ";")
    return lines


def _transit_remark(route: Route) -> str:
    cost_hint = {"低": "约0.8元/件·百公里", "中": "约1.2元/件·百公里", "高": "约1.8元/件·百公里"}
    return (
        f"预计{route.lead_days}天到达|{route.mode}|{route.distance_km}km|"
        f"运费档:{route.cost_tier}({cost_hint[route.cost_tier]})"
    )


def build_transfers(snapshots: list[Snapshot]) -> tuple[list[ForwardTransfer], list[LateralTransfer]]:
    snap_map = {(s.row.year, s.row.month, s.row.site_code): s for s in snapshots}
    forwards: list[ForwardTransfer] = []
    laterals: list[LateralTransfer] = []

    for s in snapshots:
        r = s.row
        y, m = r.year, r.month
        base = PRIMARY_BASE[r.site_code]
        # 常规月度正向补货：按计划的 12%
        routine = max(500, int(round(r.plan_num * 0.12)))
        if not (y == 2026 and m == 5 and r.site_code == "MOCK_WH_S03"):
            forwards.append(ForwardTransfer(
                adjust_date=f"{y}-{m:02d}-05", from_code=base, from_name=BASE_NAME[base],
                to_code=r.site_code, to_name=r.site_name, trans_num=routine,
                from_available=int(round(routine * 8)), reason=f"常规月度正向补货-{r.site_name}",
            ))

    # 2026-05 广州618缺货：5月底紧急下单，6月初发运
    forwards.append(ForwardTransfer(
        adjust_date="2026-06-02", from_code="MOCK_WH_B01", from_name="呼市基地仓",
        to_code="MOCK_WH_S03", to_name="广州销售仓", trans_num=8000,
        from_available=38000, reason="拉式响应：华南618高爆发，基地仓大吨位正向直发补货",
        push_user="AI_SCHEDULER",
    ))

    # 2026-05 618 华南横向共济（柳州/武汉 → 广州，致周边缺货）
    laterals.append(LateralTransfer(
        adjust_date="2026-05-18",
        from_code="MOCK_WH_S09", from_name="柳州销售仓",
        to_code="MOCK_WH_S03", to_name="广州销售仓",
        trans_num=1800,
        from_stock_before=2180, from_plan=4375,
        to_stock_before=850, to_plan=12500,
        reason="618应急：柳州横向调拨支援广州电商爆单（致柳州本地库存告急）",
    ))
    laterals.append(LateralTransfer(
        adjust_date="2026-05-22",
        from_code="MOCK_WH_S06", from_name="武汉销售仓",
        to_code="MOCK_WH_S03", to_name="广州销售仓",
        trans_num=2500,
        from_stock_before=3600, from_plan=8500,
        to_stock_before=1200, to_plan=12500,
        reason="618应急：华中枢纽横向援华南（武汉库存被抽调）",
    ))

    # 2026-06 二次误判正向补货（加剧广州压仓）
    forwards.append(ForwardTransfer(
        adjust_date="2026-06-15", from_code="MOCK_WH_B04", from_name="武汉基地仓",
        to_code="MOCK_WH_S03", to_name="广州销售仓", trans_num=3000,
        from_available=22000, reason="618后动销误判：二次正向补货（实际已转淡）",
        push_user="AI_SCHEDULER",
    ))

    # 2026-06 618 后纠偏：广州压仓调出 → 成都
    gz_jun = snap_map[(2026, 6, "MOCK_WH_S03")]
    cd_jun = snap_map[(2026, 6, "MOCK_WH_S05")]
    laterals.append(LateralTransfer(
        adjust_date="2026-06-22",
        from_code="MOCK_WH_S03", from_name="广州销售仓",
        to_code="MOCK_WH_S05", to_name="成都销售仓",
        trans_num=3500,
        from_stock_before=gz_jun.stock_h, from_plan=gz_jun.row.plan_num,
        to_stock_before=cd_jun.stock_h, to_plan=cd_jun.row.plan_num,
        reason="AI纠偏：618后华南压仓，横向调出支援西部缺口",
    ))

    # 2025-07~08 天津压仓 -> 郑州横向调拨
    for y, m, qty in [(2025, 7, 2500), (2025, 8, 2000), (2026, 6, 2500)]:
        tj = snap_map[(y, m, "MOCK_WH_S02")]
        zz = snap_map[(y, m, "MOCK_WH_S04")]
        laterals.append(LateralTransfer(
            adjust_date=f"{y}-{m:02d}-08" if m != 6 else "2026-06-02",
            from_code="MOCK_WH_S02", from_name="天津销售仓",
            to_code="MOCK_WH_S04", to_name="郑州销售仓",
            trans_num=qty, from_stock_before=tj.stock_h, from_plan=tj.row.plan_num,
            to_stock_before=zz.stock_h, to_plan=zz.row.plan_num,
            reason="AI纠偏：平调华北过剩库存支持中原市场",
        ))

    # 2025-11 济南盈余 -> 合肥
    jn = snap_map[(2025, 11, "MOCK_WH_S08")]
    hf = snap_map[(2025, 11, "MOCK_WH_S01")]
    laterals.append(LateralTransfer(
        adjust_date="2025-11-12", from_code="MOCK_WH_S08", from_name="济南销售仓",
        to_code="MOCK_WH_S01", to_name="合肥销售仓", trans_num=1800,
        from_stock_before=jn.stock_h, from_plan=jn.row.plan_num,
        to_stock_before=hf.stock_h, to_plan=hf.row.plan_num,
        reason="双11后华东仓间均衡调拨",
    ))

    return forwards, laterals


def emit_transit_inventory(
    snapshots: list[Snapshot],
    base_snapshots: list[BaseSnapshot],
    forwards: list[ForwardTransfer],
    laterals: list[LateralTransfer],
) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- Batch2: 珍护1段 · 在途库存 (yl_transit_inventory) · 全年",
        "-- 月末快照与报表 from_store_transit 对齐；remark 含 Lead Time / 距离 / 运费档",
        "-- =============================================================================",
        "DELETE FROM yl_transit_inventory WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_transit_inventory (",
        "    ds, product_code, product_name, from_site_code, from_site_name, from_site_type,",
        "    to_site_code, to_site_name, to_site_type, store_transit, remark,",
        "    issued_not_dispatched, trans_order_not_dispatched",
        ") VALUES",
    ]
    vals: list[str] = []
    seen: set[tuple] = set()

    def add_transit(ds: str, fc: str, fn: str, ft: int, tc: str, tn: str, tt: int, qty: float, remark: str):
        key = (ds, fc, tc, qty)
        if key in seen:
            return
        seen.add(key)
        vals.append(
            f"('{ds}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
            f"'{fc}', '{fn}', {ft}, '{tc}', '{tn}', {tt}, "
            f"{sql_num(qty)}, '{remark}', 0.00000, 0.00000)"
        )

    # 1) 销仓月末在途（全年 9仓 × 12月，qty=0 的跳过）
    for s in snapshots:
        if s.transit <= 0:
            continue
        r = s.row
        base = PRIMARY_BASE[r.site_code]
        rt = route_for(base, r.site_code)
        add_transit(
            s.adjust_date, base, BASE_NAME[base], 0,
            r.site_code, r.site_name, 1, s.transit, _transit_remark(rt),
        )

    # 2) 正向/横向调拨发运次日（与 forward_transfer / lateral_transfer 衔接）
    for f in forwards:
        ship = (date.fromisoformat(f.adjust_date) + timedelta(days=1)).isoformat()
        rt = route_for(f.from_code, f.to_code)
        to_type = 0 if f.to_code.startswith("MOCK_WH_B") else 1
        from_type = 0 if f.from_code.startswith("MOCK_WH_B") else 1
        add_transit(
            ship, f.from_code, f.from_name, from_type,
            f.to_code, f.to_name, to_type, f.trans_num,
            f"调拨在途|{_transit_remark(rt)}",
        )

    # 3) 横向调拨发运次日
    for lat in laterals:
        ship = (date.fromisoformat(lat.adjust_date) + timedelta(days=1)).isoformat()
        rt = route_for(lat.from_code, lat.to_code)
        add_transit(
            ship, lat.from_code, lat.from_name, 1,
            lat.to_code, lat.to_name, 1, lat.trans_num,
            f"横向调拨在途|{_transit_remark(rt)}",
        )

    lines.append(",\n".join(vals) + ";")
    return lines


def emit_forward_transfer(forwards: list[ForwardTransfer]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- Batch3: 珍护1段 · 正向调拨单 (yl_forward_transfer)",
        "-- =============================================================================",
        "DELETE FROM yl_forward_transfer WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_forward_transfer (",
        "    adjust_date, business, business_code, product_code, product_name,",
        "    from_site_code, from_site_name, from_store_num_h, from_available,",
        "    to_site_code, to_site_name, trans_num_jh, trans_num, push_num, reason, push_user",
        ") VALUES",
    ]
    vals = []
    for f in forwards:
        vals.append(
            f"('{f.adjust_date}', '{BUSINESS}', '{BUSINESS_CODE}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
            f"'{f.from_code}', '{f.from_name}', {sql_num(f.from_available + f.trans_num)}, {sql_num(f.from_available)}, "
            f"'{f.to_code}', '{f.to_name}', {sql_num(f.trans_num)}, {sql_num(f.trans_num)}, {sql_num(f.trans_num)}, "
            f"'{f.reason}', '{f.push_user}')"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_lateral_transfer(laterals: list[LateralTransfer]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- Batch3: 珍护1段 · 横向调拨单 (yl_lateral_transfer)",
        "-- =============================================================================",
        "DELETE FROM yl_lateral_transfer WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_lateral_transfer (",
        "    adjust_date, business, business_code, product_code, product_name,",
        "    from_site_code, from_site_name, from_store_num, from_plan_num, from_stock_rate_before, from_stock_rate_after,",
        "    to_site_code, to_site_name, trans_num_jh, trans_num, push_num, to_store_num, to_plan_num, reason, push_user",
        ") VALUES",
    ]
    vals = []
    for lat in laterals:
        from_rate = round((lat.from_stock_before / lat.from_plan) * 100) if lat.from_plan else 100
        to_rate = round((lat.to_stock_before / lat.to_plan) * 100) if lat.to_plan else 50
        from_after = round(((lat.from_stock_before - lat.trans_num) / lat.from_plan) * 100) if lat.from_plan else 80
        vals.append(
            f"('{lat.adjust_date}', '{BUSINESS}', '{BUSINESS_CODE}', '{PRODUCT_CODE}', '{PRODUCT_NAME}', "
            f"'{lat.from_code}', '{lat.from_name}', {sql_num(lat.from_stock_before)}, {sql_num(lat.from_plan)}, "
            f"'{from_rate}%', '{from_after}%', "
            f"'{lat.to_code}', '{lat.to_name}', {sql_num(lat.trans_num)}, {sql_num(lat.trans_num)}, {sql_num(lat.trans_num)}, "
            f"{sql_num(lat.to_stock_before)}, {sql_num(lat.to_plan)}, '{lat.reason}', 'AI_SYSTEM')"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_big_date_inventory(snapshots: list[Snapshot]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- Batch4: 珍护1段 · 大日期库存监控 (yl_big_date_inventory)",
        "-- =============================================================================",
        "DELETE FROM yl_big_date_inventory WHERE product_code = 'MOCK_YLP001';",
        "",
        "INSERT INTO yl_big_date_inventory (",
        "    business, business_code, site_type, site_code, site_name, product_code, product_name, big_date_num, remark",
        ") VALUES",
    ]
    vals = []
    seen = set()
    for s in snapshots:
        if s.big_date_num <= 0:
            continue
        key = (s.row.site_code, s.row.year, s.row.month)
        if key in seen:
            continue
        seen.add(key)
        remark = (
            f"{s.row.year}年{s.row.month}月：库龄批次生产日期{s.produce_old}，"
            f"月销{s.row.out_put}件，压仓风险需促销或横向调出"
        )
        vals.append(
            f"('{BUSINESS}', '{BUSINESS_CODE}', 1, '{s.row.site_code}', '{s.row.site_name}', "
            f"'{PRODUCT_CODE}', '{PRODUCT_NAME}', {sql_num(s.big_date_num)}, '{remark}')"
        )
    lines.append(",\n".join(vals) + ";")
    return lines


def emit_wms_tms(forwards: list[ForwardTransfer], laterals: list[LateralTransfer]) -> list[str]:
    lines = [
        "",
        "-- =============================================================================",
        "-- Batch4: 物流辅助 · WMS运单 + TMS轨迹 · 全年（与调拨单/在途衔接）",
        "-- =============================================================================",
        "DELETE FROM yl_wms_waybill WHERE erp_order_no LIKE 'ERP-YLP001-%';",
        "DELETE FROM yl_tms_gps WHERE plate_no LIKE '蒙%YLP001%';",
        "",
        "INSERT INTO yl_wms_waybill (waybill_no, customer_name, erp_order_no, customer_address, carrier_name) VALUES",
    ]
    wb_vals: list[str] = []
    gps_vals: list[str] = []
    gps_seq = 0
    plate_by_base = {
        "MOCK_WH_B01": "蒙A·YLP001",
        "MOCK_WH_B02": "津B·YLP002",
        "MOCK_WH_B03": "黑M·YLP003",
        "MOCK_WH_B04": "鄂A·YLP004",
    }
    drivers = ["张师傅", "李师傅", "王师傅", "赵师傅"]

    def add_logistics(idx: int, adj: str, fc: str, tc: str, qty: int, kind: str):
        nonlocal gps_seq
        rt = route_for(fc, tc)
        cust, addr = SALES_ADDRESS.get(tc, (SALES_NAME.get(tc, tc), "目的地地址"))
        erp = f"ERP-YLP001-{kind}-{adj.replace('-', '')}-{fc[-3:]}-{tc[-3]}"
        wb_no = f"WB{adj.replace('-', '')}{idx:04d}"
        wb_vals.append(
            f"('{wb_no}', '{cust}', '{erp}', '{addr}', '{rt.carrier}')"
        )
        if rt.distance_km >= 400:
            gps_seq += 1
            ship_dt = date.fromisoformat(adj) + timedelta(days=1)
            plate = plate_by_base.get(fc, "鄂A·YLP004")
            driver = drivers[idx % len(drivers)]
            progress = 0.35 if rt.distance_km >= 1500 else 0.55
            gps_vals.append(
                f"({gps_seq}, '{ship_dt.isoformat()} 10:30:00', 76.00000, {sql_num(rt.total_mileage_km)}, "
                f"{sql_num(rt.total_mileage_km * progress)}, '运输中', "
                f"'{rt.mid_location}', {sql_num(rt.mid_lng)}, {sql_num(rt.mid_lat)}, '晴', "
                f"'{plate}', '{driver}', '1388888{idx:04d}', '{BASE_NAME.get(fc, SALES_NAME.get(fc, fc))}')"
            )
            if rt.distance_km >= 1500:
                gps_seq += 1
                gps_vals.append(
                    f"({gps_seq}, '{ship_dt.isoformat()} 16:45:00', 74.00000, {sql_num(rt.total_mileage_km)}, "
                    f"{sql_num(rt.total_mileage_km * 0.72)}, '运输中', "
                    f"'{rt.mid_location}', {sql_num(rt.mid_lng + 0.5)}, {sql_num(rt.mid_lat - 2.0)}, '多云', "
                    f"'{plate}', '{driver}', '1388888{idx:04d}', '{BASE_NAME.get(fc, SALES_NAME.get(fc, fc))}')"
                )

    for i, f in enumerate(forwards):
        add_logistics(i + 1, f.adjust_date, f.from_code, f.to_code, f.trans_num, "FWD")
    for i, lat in enumerate(laterals):
        add_logistics(1000 + i, lat.adjust_date, lat.from_code, lat.to_code, lat.trans_num, "LAT")

    lines.append(",\n".join(wb_vals) + ";")
    lines.extend([
        "",
        "INSERT INTO yl_tms_gps (",
        "    seq_no, location_time, speed_kmh, mileage_km, driving_mileage_km, status,",
        "    location, longitude, latitude, weather, plate_no, driver, driver_phone, warehouse",
        ") VALUES",
        ",\n".join(gps_vals) + ";" if gps_vals else "-- (无长途GPS记录);",
    ])
    return lines


def main():
    rows = build_rows()
    snapshots = [compute_snapshot(r) for r in rows]
    base_snapshots = compute_base_snapshots(rows)
    forwards, laterals = build_transfers(snapshots)

    batch1: list[str] = [
        "-- =============================================================================",
        "-- 珍护1段(MOCK_YLP001) · 1年全国仓储与销售 Mock 数据 · Batch 1",
        "-- 生成: generate_yl_zhenhu1_year.py",
        "-- =============================================================================",
    ]
    batch1.extend(emit_sales_plan(rows))
    batch1.extend(emit_actual_sales(rows))
    batch1.extend(emit_base_reports(rows))
    batch1.extend(emit_sales_reports(snapshots))
    batch1.extend(emit_national_reports(snapshots))

    batch234: list[str] = [
        "-- =============================================================================",
        "-- 珍护1段(MOCK_YLP001) · 周边辅助表 Mock · Batch 2/3/4",
        "-- 与 batch1 共用 compute_snapshot / compute_base_snapshots",
        "-- =============================================================================",
    ]
    batch234.extend(emit_spot_inventory(snapshots, base_snapshots))
    batch234.extend(emit_transit_inventory(snapshots, base_snapshots, forwards, laterals))
    batch234.extend(emit_forward_transfer(forwards))
    batch234.extend(emit_lateral_transfer(laterals))
    batch234.extend(emit_big_date_inventory(snapshots))
    batch234.extend(emit_wms_tms(forwards, laterals))

    p1 = Path(__file__).with_name("yl_zhenhu1_year_batch1_warehouse.sql")
    p2 = Path(__file__).with_name("yl_zhenhu1_year_batch2_3_4_auxiliary.sql")
    p3 = Path(__file__).with_name("yl_zhenhu1_year_unship_patch.sql")
    p4 = Path(__file__).with_name("yl_zhenhu1_year_inventory_dos_patch.sql")
    p1.write_text("\n".join(batch1) + "\n", encoding="utf-8")
    p2.write_text("\n".join(batch234) + "\n", encoding="utf-8")
    p3.write_text("\n".join(emit_unship_patch(rows, snapshots)) + "\n", encoding="utf-8")
    p4.write_text("\n".join(emit_inventory_dos_patch(snapshots)) + "\n", encoding="utf-8")
    print(f"Wrote {p1}")
    print(
        f"Wrote {p2}: base_spot={len(base_snapshots)}, forwards={len(forwards)}, "
        f"laterals={len(laterals)}, sales_snapshots={len(snapshots)}"
    )
    print(f"Wrote {p3} (独立未发订单补丁, {len(rows)} actual + {len(snapshots)} report updates)")
    print(f"Wrote {p4} (独立库存DOS补丁, {len(snapshots)} 仓×月快照)")


if __name__ == "__main__":
    main()
