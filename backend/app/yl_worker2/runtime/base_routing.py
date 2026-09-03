"""Base warehouse lead-time hints for routing (mock/OIP narrative)."""

from __future__ import annotations

# (base_site, sales_site) -> lead time days (lower = faster)
BASE_TO_SALES_LEAD_TIME_DAYS: dict[tuple[str, str], int] = {
    ("MOCK_WH_B02", "MOCK_WH_S04"): 2,  # 天津基地 → 郑州（Script1 时效最优）
    ("MOCK_WH_B01", "MOCK_WH_S04"): 4,  # 呼市基地 → 郑州
    ("MOCK_WH_B04", "MOCK_WH_S04"): 3,  # 武汉基地 → 郑州
    ("MOCK_WH_B03", "MOCK_WH_S04"): 5,  # 杜蒙基地 → 郑州
    ("MOCK_WH_B02", "MOCK_WH_S07"): 3,  # 天津基地 → 呼市
    ("MOCK_WH_B01", "MOCK_WH_S07"): 2,  # 呼市基地 → 呼市销售
    ("MOCK_WH_B02", "MOCK_WH_S02"): 1,  # 天津基地 → 天津销售（同城）
}


def lead_time_days(base_site_code: str, to_site_code: str | None) -> int | None:
    if not to_site_code:
        return None
    return BASE_TO_SALES_LEAD_TIME_DAYS.get((base_site_code, to_site_code))


def enrich_base_rows(rows: list[dict], to_site_code: str | None) -> list[dict]:
    if not to_site_code:
        return rows
    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        days = lead_time_days(str(item.get("from_site_code") or ""), to_site_code)
        item["to_site_code"] = to_site_code
        item["lead_time_days"] = days
        enriched.append(item)
    enriched.sort(key=lambda r: (r.get("lead_time_days") is None, r.get("lead_time_days") or 999))
    return enriched
