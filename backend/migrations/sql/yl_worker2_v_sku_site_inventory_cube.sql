-- Optional VIEW: SKU × site inventory cube for yl-worker2 OBDA
-- Run: psql $YL_DATABASE_URL -f backend/migrations/sql/yl_worker2_v_sku_site_inventory_cube.sql

CREATE OR REPLACE VIEW v_sku_site_inventory_cube AS
SELECT
    r.product_code,
    r.from_site_code AS site_code,
    r.adjust_date,
    r.plan_num,
    r.out_put_num,
    r.from_store_num_h AS store_num,
    r.from_store_transit AS store_transit,
    r.total_unship,
    r.order_gap,
    r.ship_gap,
    r.order_completion_rate,
    r.from_stock_rate_before AS stock_rate_before,
    COALESCE(b.big_date_total, 0) AS big_date_num
FROM yl_sales_warehouse_inventory_report r
LEFT JOIN LATERAL (
    SELECT SUM(bdi.big_date_num) AS big_date_total
    FROM yl_big_date_inventory bdi
    WHERE bdi.product_code = r.product_code
      AND bdi.site_code = r.from_site_code
) b ON true;

COMMENT ON VIEW v_sku_site_inventory_cube IS 'yl-worker2 optional pre-aggregated SKU×site inventory cube';
