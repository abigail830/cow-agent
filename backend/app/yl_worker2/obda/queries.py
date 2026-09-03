"""OBDA SQL — semantic queries mapped to yl_* tables."""

from __future__ import annotations

from app.yl_worker2.db import parse_adjust_date, row_to_dict, rows_to_dicts, yl_connect
from app.yl_worker2.obda import entity_queries as entity_obda
from app.yl_worker2.runtime.base_routing import enrich_base_rows

_WAREHOUSE_SKU_INVENTORY_SNAPSHOT_SQL = """
    SELECT
        sku_code AS product_code,
        warehouse_code AS site_code,
        snapshot_date AS adjust_date,
        monthly_sales_plan AS plan_num,
        out_put_num,
        spot_inventory AS store_num,
        in_transit_inventory AS store_transit,
        total_unship,
        order_gap,
        ship_gap,
        order_completion_rate,
        current_stock_rate AS stock_rate_before,
        COALESCE(aging_inventory_qty, 0) AS big_date_num
    FROM warehouse_sku_inventory
    WHERE sku_code = $1
      AND warehouse_code = $2
      AND snapshot_date = $3::date
    LIMIT 1
"""

_SALES_WAREHOUSE_REPORT_SNAPSHOT_SQL = """
    SELECT
        product_code,
        from_site_code AS site_code,
        adjust_date,
        plan_num,
        out_put_num,
        from_store_num_h AS store_num,
        from_store_transit AS store_transit,
        total_unship,
        order_gap,
        ship_gap,
        order_completion_rate,
        from_stock_rate_before AS stock_rate_before,
        COALESCE(big_date_num, 0) AS big_date_num
    FROM yl_sales_warehouse_inventory_report
    WHERE product_code = $1
      AND from_site_code = $2
      AND adjust_date = $3::date
    LIMIT 1
"""


async def fetch_inventory_snapshot(
    product_code: str,
    site_code: str,
    adjust_date: str,
) -> dict | None:
    conn = await yl_connect()
    try:
        row = await conn.fetchrow(
            _WAREHOUSE_SKU_INVENTORY_SNAPSHOT_SQL,
            product_code,
            site_code,
            parse_adjust_date(adjust_date),
        )
        if row is None:
            row = await conn.fetchrow(
                _SALES_WAREHOUSE_REPORT_SNAPSHOT_SQL,
                product_code,
                site_code,
                parse_adjust_date(adjust_date),
            )
        return row_to_dict(row)
    finally:
        await conn.close()


async def fetch_national_summary(product_code: str, adjust_date: str) -> dict | None:
    conn = await yl_connect()
    try:
        row = await conn.fetchrow(
            """
            SELECT
                product_code,
                adjust_date,
                plan_num,
                out_put_num,
                from_store_num_h,
                from_store_transit,
                total_unship,
                order_completion_rate,
                sell_completion_rate
            FROM yl_national_sales_warehouse_inventory_report
            WHERE product_code = $1
              AND adjust_date = $2::date
            LIMIT 1
            """,
            product_code,
            parse_adjust_date(adjust_date),
        )
        return row_to_dict(row)
    finally:
        await conn.close()


async def fetch_snapshot_catalog(
    product_code: str | None = None,
    adjust_date: str | None = None,
) -> dict:
    global_dates = await entity_obda.fetch_global_snapshot_dates()
    latest = global_dates[0] if global_dates else None
    warehouse_master = await entity_obda.fetch_list_warehouses(limit=200)

    if product_code is None and adjust_date is None:
        resolved_date = latest
        products_on_date = (
            await entity_obda.fetch_distinct_products_on_date(resolved_date)
            if resolved_date
            else []
        )
        coverage = (
            await entity_obda.fetch_snapshot_coverage(resolved_date)
            if resolved_date
            else []
        )
        return {
            "product_code": None,
            "latest_adjust_date": latest,
            "recommended_adjust_date": latest,
            "available_dates": global_dates,
            "requested_adjust_date": None,
            "products_with_snapshot": products_on_date,
            "snapshot_coverage": coverage,
            "sites_with_snapshot": [],
            "warehouse_master": warehouse_master,
            "applied_rule": "catalog.global_latest_date",
        }

    if product_code is None and adjust_date:
        products_on_date = await entity_obda.fetch_distinct_products_on_date(adjust_date)
        coverage = await entity_obda.fetch_snapshot_coverage(adjust_date)
        return {
            "product_code": None,
            "latest_adjust_date": latest,
            "recommended_adjust_date": adjust_date,
            "available_dates": global_dates,
            "requested_adjust_date": adjust_date,
            "products_with_snapshot": products_on_date,
            "snapshot_coverage": coverage,
            "sites_with_snapshot": [],
            "warehouse_master": warehouse_master,
            "applied_rule": "catalog.by_date_all_products",
        }

    conn = await yl_connect()
    try:
        date_rows = await conn.fetch(
            """
            SELECT DISTINCT snapshot_date::text AS adjust_date
            FROM warehouse_sku_inventory
            WHERE sku_code = $1
            ORDER BY adjust_date DESC
            LIMIT 24
            """,
            product_code,
        )
        available_dates = [r["adjust_date"] for r in date_rows]
        if not available_dates:
            date_rows = await conn.fetch(
                """
                SELECT DISTINCT adjust_date::text AS adjust_date
                FROM yl_sales_warehouse_inventory_report
                WHERE product_code = $1
                ORDER BY adjust_date DESC
                LIMIT 24
                """,
                product_code,
            )
            available_dates = [r["adjust_date"] for r in date_rows]

        resolved_date = adjust_date
        sites_with_snapshot: list[dict] = []
        if resolved_date:
            if resolved_date in available_dates or resolved_date in global_dates:
                sites_with_snapshot = await entity_obda.fetch_snapshot_coverage(
                    resolved_date, product_code=product_code
                )
        elif available_dates:
            resolved_date = available_dates[0]
            sites_with_snapshot = await entity_obda.fetch_snapshot_coverage(
                resolved_date, product_code=product_code
            )

        sku_latest = available_dates[0] if available_dates else None
        recommended = sku_latest or latest

        return {
            "product_code": product_code,
            "latest_adjust_date": sku_latest or latest,
            "recommended_adjust_date": recommended,
            "available_dates": available_dates or global_dates,
            "requested_adjust_date": adjust_date,
            "sites_with_snapshot": sites_with_snapshot,
            "warehouse_master": warehouse_master,
            "applied_rule": "catalog.warehouse_sku_inventory.by_product",
        }
    finally:
        await conn.close()


async def fetch_batch_big_date_inventory(
    product_code: str,
    site_code: str,
) -> list[dict]:
    conn = await yl_connect()
    try:
        rows = await conn.fetch(
            """
            SELECT
                id,
                product_code,
                site_code,
                site_name,
                big_date_num,
                remark
            FROM yl_big_date_inventory
            WHERE product_code = $1
              AND site_code = $2
              AND big_date_num > 0
            ORDER BY big_date_num DESC
            """,
            product_code,
            site_code,
        )
        if rows:
            enriched = rows_to_dicts(rows)
            sku_row = await conn.fetchrow(
                """
                SELECT produce_date, snapshot_date
                FROM warehouse_sku_inventory
                WHERE sku_code = $1
                  AND warehouse_code = $2
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                product_code,
                site_code,
            )
            produce_date = sku_row["produce_date"] if sku_row else None
            for item in enriched:
                if produce_date:
                    item["produce_date"] = produce_date
            return enriched

        sku_row = await conn.fetchrow(
            """
            SELECT
                aging_inventory_qty AS big_date_num,
                produce_date,
                snapshot_date,
                inventory_status
            FROM warehouse_sku_inventory
            WHERE sku_code = $1
              AND warehouse_code = $2
              AND COALESCE(aging_inventory_qty, 0) > 0
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            product_code,
            site_code,
        )
        if sku_row is None:
            return []
        return [
            {
                "id": None,
                "product_code": product_code,
                "site_code": site_code,
                "site_name": None,
                "big_date_num": sku_row["big_date_num"],
                "produce_date": sku_row["produce_date"],
                "remark": sku_row["inventory_status"],
                "snapshot_date": sku_row["snapshot_date"],
                "applied_rule": "big_date.fallback.warehouse_sku_inventory",
            }
        ]
    finally:
        await conn.close()


async def fetch_base_warehouse_availability(
    product_code: str,
    adjust_date: str,
    to_site_code: str | None = None,
) -> list[dict]:
    conn = await yl_connect()
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (from_site_code)
                from_site_code,
                from_site_name,
                from_store_num_h,
                from_available,
                trans_num,
                to_site_code,
                to_site_name,
                reason,
                remark
            FROM yl_forward_transfer
            WHERE product_code = $1
              AND adjust_date = $2::date
              AND from_site_code LIKE 'MOCK_WH_B%'
            ORDER BY from_site_code,
                     (from_available IS NOT NULL) DESC,
                     id DESC
            """,
            product_code,
            parse_adjust_date(adjust_date),
        )
        if rows:
            return enrich_base_rows(rows_to_dicts(rows), to_site_code)

        rows = await conn.fetch(
            """
            SELECT
                r.warehouse_code AS from_site_code,
                COALESCE(w.site_name, r.warehouse_code) AS from_site_name,
                COALESCE(r.spot_inventory, 0) AS from_store_num_h,
                COALESCE(r.spot_inventory, 0) AS from_available
            FROM warehouse_sku_inventory r
            LEFT JOIN yl_warehouse w ON w.site_code = r.warehouse_code
            WHERE r.sku_code = $1
              AND r.snapshot_date = $2::date
              AND r.warehouse_code LIKE 'MOCK_WH_B%'
            ORDER BY r.warehouse_code
            """,
            product_code,
            parse_adjust_date(adjust_date),
        )
        if rows:
            return enrich_base_rows(rows_to_dicts(rows), to_site_code)

        rows = await conn.fetch(
            """
            SELECT
                w.site_code AS from_site_code,
                w.site_name AS from_site_name,
                COALESCE(i.store_num, 0) AS from_store_num_h,
                COALESCE(i.store_num, 0) AS from_available
            FROM yl_warehouse w
            LEFT JOIN yl_spot_inventory i
              ON i.site_code = w.site_code
             AND i.product_code = $1
             AND i.ds::date = $2::date
             AND i.status = '合格'
             AND COALESCE(i.is_delete, 0) = 0
            WHERE w.site_type = 0
              AND w.site_code LIKE 'MOCK_WH_B%'
            ORDER BY w.site_code
            """,
            product_code,
            parse_adjust_date(adjust_date),
        )
        return enrich_base_rows(rows_to_dicts(rows), to_site_code)
    finally:
        await conn.close()


async def fetch_pending_forward_orders(
    product_code: str,
    adjust_date: str | None = None,
) -> list[dict]:
    conn = await yl_connect()
    try:
        if adjust_date:
            rows = await conn.fetch(
                """
                SELECT *, 'forward' AS allocation_type
                FROM yl_forward_transfer
                WHERE product_code = $1
                  AND adjust_date = $2::date
                  AND push_num IS NULL
                  AND (remark IS NULL OR remark NOT LIKE '%[已作废]%')
                ORDER BY id
                """,
                product_code,
                parse_adjust_date(adjust_date),
            )
        else:
            rows = await conn.fetch(
                """
                SELECT *, 'forward' AS allocation_type
                FROM yl_forward_transfer
                WHERE product_code = $1
                  AND push_num IS NULL
                  AND (remark IS NULL OR remark NOT LIKE '%[已作废]%')
                ORDER BY adjust_date DESC, id
                """,
                product_code,
            )
        return rows_to_dicts(rows)
    finally:
        await conn.close()


async def fetch_pending_lateral_orders(
    product_code: str,
    adjust_date: str | None = None,
) -> list[dict]:
    conn = await yl_connect()
    try:
        if adjust_date:
            rows = await conn.fetch(
                """
                SELECT *, 'lateral' AS allocation_type
                FROM yl_lateral_transfer
                WHERE product_code = $1
                  AND adjust_date = $2::date
                  AND push_num IS NULL
                  AND COALESCE(is_delete, 0) = 0
                ORDER BY id
                """,
                product_code,
                parse_adjust_date(adjust_date),
            )
        else:
            rows = await conn.fetch(
                """
                SELECT *, 'lateral' AS allocation_type
                FROM yl_lateral_transfer
                WHERE product_code = $1
                  AND push_num IS NULL
                  AND COALESCE(is_delete, 0) = 0
                ORDER BY adjust_date DESC, id
                """,
                product_code,
            )
        return rows_to_dicts(rows)
    finally:
        await conn.close()


async def fetch_forward_order_by_id(order_id: int) -> dict | None:
    conn = await yl_connect()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM yl_forward_transfer WHERE id = $1",
            order_id,
        )
        return row_to_dict(row)
    finally:
        await conn.close()


async def fetch_lateral_order_by_id(order_id: int) -> dict | None:
    conn = await yl_connect()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM yl_lateral_transfer WHERE id = $1",
            order_id,
        )
        return row_to_dict(row)
    finally:
        await conn.close()
