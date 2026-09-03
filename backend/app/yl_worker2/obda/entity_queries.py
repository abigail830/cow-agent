"""OBDA queries for entity discovery and resolution."""

from __future__ import annotations

from app.yl_worker2.db import parse_adjust_date, rows_to_dicts, yl_connect
from app.yl_worker2.runtime.entity_aliases import match_aliases
from app.yl_worker2.runtime.entity_resolver import (
    build_resolution,
    parse_site_type_hint,
    score_product_row,
    score_warehouse_row,
)


def _site_type_label(site_type: int | None) -> str:
    if site_type == 0:
        return "base"
    if site_type == 1:
        return "sales"
    return "unknown"


async def fetch_list_products(
    active_only: bool = True,
    business: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conn = await yl_connect()
    try:
        clauses = ["1=1"]
        args: list = []
        if active_only:
            clauses.append("COALESCE(is_delete, 0) = 0")
        if business:
            n = len(args) + 1
            clauses.append(f"(business ILIKE ${n} OR business_code ILIKE ${n})")
            args.append(f"%{business}%")
        if keyword:
            n = len(args) + 1
            clauses.append(
                f"(product_name ILIKE ${n} OR trade_name ILIKE ${n} OR brand ILIKE ${n} "
                f"OR pro_series ILIKE ${n} OR product_code ILIKE ${n})"
            )
            args.append(f"%{keyword}%")
        limit_val = min(max(limit, 1), 200)
        args.append(limit_val)
        lim_n = len(args)
        where = " AND ".join(clauses)
        rows = await conn.fetch(
            f"""
            SELECT product_code, product_name, trade_name, brand, pro_series, business
            FROM yl_product
            WHERE {where}
            ORDER BY sort, product_code
            LIMIT ${lim_n}
            """,
            *args,
        )
        return rows_to_dicts(rows)
    finally:
        await conn.close()


async def fetch_list_warehouses(
    site_type: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conn = await yl_connect()
    try:
        type_val = parse_site_type_hint(site_type)
        clauses: list[str] = []
        args: list = []
        if type_val is not None:
            clauses.append(f"site_type = ${len(args) + 1}")
            args.append(type_val)
        if keyword:
            n = len(args) + 1
            clauses.append(
                f"(site_name ILIKE ${n} OR site_desc ILIKE ${n} OR site_code ILIKE ${n})"
            )
            args.append(f"%{keyword}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_val = min(max(limit, 1), 200)
        args.append(limit_val)
        lim_n = len(args)
        rows = await conn.fetch(
            f"""
            SELECT site_code, site_name, site_desc, site_type
            FROM yl_warehouse
            {where}
            ORDER BY sort, site_code
            LIMIT ${lim_n}
            """,
            *args,
        )
        out = rows_to_dicts(rows)
        for r in out:
            r["site_type_label"] = _site_type_label(r.get("site_type"))
        return out
    finally:
        await conn.close()


def _merge_ranked(
    alias_rows: list[dict],
    fuzzy_rows: list[dict],
    *,
    id_key: str,
    limit: int,
) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in alias_rows + fuzzy_rows:
        key = row[id_key]
        prev = merged.get(key)
        if prev is None or row["confidence"] > prev["confidence"]:
            merged[key] = row
    ranked = sorted(merged.values(), key=lambda r: r["confidence"], reverse=True)
    return ranked[: min(max(limit, 1), 20)]


async def _alias_product_rows(mention: str) -> list[dict]:
    hits = match_aliases(mention, "ProductSKU")
    if not hits:
        return []
    rows = await fetch_list_products(active_only=True, limit=200)
    by_code = {r["product_code"]: r for r in rows}
    out: list[dict] = []
    for hit in hits:
        row = by_code.get(hit["entity_id"])
        if row is None:
            continue
        out.append(
            {
                **row,
                "confidence": hit["confidence"],
                "match_method": hit["match_method"],
                "matched_alias": hit["alias"],
            }
        )
    return out


async def _alias_warehouse_rows(
    mention: str,
    *,
    site_type: str | None = None,
) -> list[dict]:
    hits = match_aliases(mention, "Warehouse", site_type=site_type)
    if not hits:
        return []
    rows = await fetch_list_warehouses(site_type=site_type, limit=200)
    by_code = {r["site_code"]: r for r in rows}
    out: list[dict] = []
    for hit in hits:
        row = by_code.get(hit["entity_id"])
        if row is None:
            continue
        out.append(
            {
                **row,
                "confidence": hit["confidence"],
                "match_method": hit["match_method"],
                "matched_alias": hit["alias"],
            }
        )
    return out


async def fetch_search_products(
    mention: str,
    brand: str | None = None,
    limit: int = 10,
) -> list[dict]:
    rows = await fetch_list_products(active_only=True, limit=200)
    if brand:
        brand_low = brand.lower()
        rows = [r for r in rows if brand_low in str(r.get("brand") or "").lower()]
    ranked: list[dict] = []
    for row in rows:
        conf, method = score_product_row(mention, row)
        if conf > 0:
            ranked.append({**row, "confidence": conf, "match_method": method})
    alias_rows = await _alias_product_rows(mention)
    return _merge_ranked(alias_rows, ranked, id_key="product_code", limit=limit)


async def fetch_search_warehouses(
    mention: str,
    site_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    rows = await fetch_list_warehouses(site_type=site_type, limit=200)
    ranked: list[dict] = []
    for row in rows:
        conf, method = score_warehouse_row(mention, row)
        if conf > 0:
            ranked.append({**row, "confidence": conf, "match_method": method})
    alias_rows = await _alias_warehouse_rows(mention, site_type=site_type)
    return _merge_ranked(alias_rows, ranked, id_key="site_code", limit=limit)


async def fetch_resolve_entity(
    entity_type: str,
    mention: str,
    site_type: str | None = None,
) -> dict:
    et = (entity_type or "").strip().lower()
    if et in ("productsku", "product", "sku"):
        ranked = await fetch_search_products(mention, limit=10)
        result = build_resolution(
            "ProductSKU",
            mention,
            ranked,
            id_key="product_code",
            display_key="product_name",
        )
        if site_type:
            result["context_used"] = {"site_type_hint": site_type}
        return result
    if et in ("warehouse", "site"):
        ranked = await fetch_search_warehouses(mention, site_type=site_type, limit=10)
        result = build_resolution(
            "Warehouse",
            mention,
            ranked,
            id_key="site_code",
            display_key="site_name",
        )
        if site_type:
            result["context_used"] = {"site_type_hint": site_type}
        return result
    return {
        "entity_type": entity_type,
        "mention": mention,
        "status": "not_found",
        "error": "unsupported_entity_type",
        "supported_types": ["ProductSKU", "Warehouse"],
        "applied_rule": "resolve.unsupported_type",
    }


async def fetch_global_snapshot_dates(limit: int = 24) -> list[str]:
    conn = await yl_connect()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT snapshot_date::text AS adjust_date
            FROM warehouse_sku_inventory
            ORDER BY adjust_date DESC
            LIMIT $1
            """,
            limit,
        )
        dates = [r["adjust_date"] for r in rows]
        if dates:
            return dates
        rows = await conn.fetch(
            """
            SELECT DISTINCT adjust_date::text AS adjust_date
            FROM yl_sales_warehouse_inventory_report
            ORDER BY adjust_date DESC
            LIMIT $1
            """,
            limit,
        )
        return [r["adjust_date"] for r in rows]
    finally:
        await conn.close()


async def fetch_snapshot_coverage(
    adjust_date: str,
    product_code: str | None = None,
    limit: int = 500,
) -> list[dict]:
    conn = await yl_connect()
    try:
        if product_code:
            rows = await conn.fetch(
                """
                SELECT
                    r.sku_code AS product_code,
                    r.warehouse_code AS site_code,
                    COALESCE(w.site_name, w.site_desc) AS site_name
                FROM warehouse_sku_inventory r
                LEFT JOIN yl_warehouse w ON w.site_code = r.warehouse_code
                WHERE r.sku_code = $1
                  AND r.snapshot_date = $2::date
                ORDER BY r.warehouse_code
                LIMIT $3
                """,
                product_code,
                parse_adjust_date(adjust_date),
                limit,
            )
            if not rows:
                rows = await conn.fetch(
                    """
                    SELECT
                        r.product_code,
                        r.from_site_code AS site_code,
                        COALESCE(w.site_name, r.from_site_name) AS site_name
                    FROM yl_sales_warehouse_inventory_report r
                    LEFT JOIN yl_warehouse w ON w.site_code = r.from_site_code
                    WHERE r.product_code = $1
                      AND r.adjust_date = $2::date
                    ORDER BY r.from_site_code
                    LIMIT $3
                    """,
                    product_code,
                    parse_adjust_date(adjust_date),
                    limit,
                )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    r.sku_code AS product_code,
                    r.warehouse_code AS site_code,
                    COALESCE(w.site_name, w.site_desc) AS site_name
                FROM warehouse_sku_inventory r
                LEFT JOIN yl_warehouse w ON w.site_code = r.warehouse_code
                WHERE r.snapshot_date = $1::date
                ORDER BY r.sku_code, r.warehouse_code
                LIMIT $2
                """,
                parse_adjust_date(adjust_date),
                limit,
            )
            if not rows:
                rows = await conn.fetch(
                    """
                    SELECT
                        r.product_code,
                        r.from_site_code AS site_code,
                        COALESCE(w.site_name, r.from_site_name) AS site_name
                    FROM yl_sales_warehouse_inventory_report r
                    LEFT JOIN yl_warehouse w ON w.site_code = r.from_site_code
                    WHERE r.adjust_date = $1::date
                    ORDER BY r.product_code, r.from_site_code
                    LIMIT $2
                    """,
                    parse_adjust_date(adjust_date),
                    limit,
                )
        return rows_to_dicts(rows)
    finally:
        await conn.close()


async def fetch_distinct_products_on_date(adjust_date: str, limit: int = 100) -> list[dict]:
    conn = await yl_connect()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                r.sku_code AS product_code,
                COALESCE(p.product_name, p.brand) AS product_name
            FROM warehouse_sku_inventory r
            LEFT JOIN yl_product p ON p.product_code = r.sku_code
            WHERE r.snapshot_date = $1::date
            ORDER BY r.sku_code
            LIMIT $2
            """,
            parse_adjust_date(adjust_date),
            limit,
        )
        if not rows:
            rows = await conn.fetch(
                """
                SELECT DISTINCT
                    r.product_code,
                    COALESCE(p.product_name, r.product_name) AS product_name
                FROM yl_sales_warehouse_inventory_report r
                LEFT JOIN yl_product p ON p.product_code = r.product_code
                WHERE r.adjust_date = $1::date
                ORDER BY r.product_code
                LIMIT $2
                """,
                parse_adjust_date(adjust_date),
                limit,
            )
        return rows_to_dicts(rows)
    finally:
        await conn.close()
