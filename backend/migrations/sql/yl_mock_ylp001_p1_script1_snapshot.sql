-- =============================================================================
-- MOCK_YLP001 OIP Script 1 异常快照 (P1)
-- Tab 默认快照日：2026-06-30（与 P0 一致）
-- 演示叙事：T 日 09:00 日前例行补调 Dashboard 异常
--
-- 仓映射（OIP → Mock）：
--   异常 A 低备货+高订单 → 郑州销售仓 MOCK_WH_S04（正向：天津/呼市基地）
--   异常 B 大日期调出   → 天津销售仓 MOCK_WH_S02
--   异常 B 缺口调入     → 呼市销售仓 MOCK_WH_S07
--
-- 本脚本：
--   1. 调整 6/30 销仓报表 + spot 使三仓指标自洽
--   2. 整理天津大日期库存
--   3. 写入 OIP 建议单（forward / lateral，adjust_date=2026-06-30，待经理确认 push_num=NULL）
--   4. 同步 6/05 forward 区域列（郑州/天津/呼市路线）
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. 异常 A：郑州销售仓 — 订单完成率 72%，备货率 45%，发货缺口 -2700
--    口径：store 1200 + transit 300 + out 3000 = 4500 → 45.0% of plan 10000
-- ---------------------------------------------------------------------------
UPDATE yl_sales_warehouse_inventory_report
SET
    plan_num               = 10000.00000,
    out_put_num            = 3000.00000,
    from_store_num_h       = 1200.00000,
    from_store_transit     = 300.00000,
    total_unship           = 4200.00000,
    order_gap              = -2700.00000,
    ship_gap               = -2700.00000,
    order_completion_rate  = '72.0%',
    from_stock_rate_before = '45.0%'
WHERE product_code = 'MOCK_YLP001'
  AND from_site_code = 'MOCK_WH_S04'
  AND adjust_date = '2026-06-30';

UPDATE yl_spot_inventory
SET store_num = 1200.00000, invetory_deduct_sum = -3000.00000, actual_num = 1200.00000
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S04'
  AND ds = '2026-06-30'
  AND status = '合格'
  AND is_delete = 0;

UPDATE yl_spot_inventory
SET store_num = 60.00000
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S04'
  AND ds = '2026-06-30'
  AND status = '待检'
  AND is_delete = 0;

-- ---------------------------------------------------------------------------
-- 2. 异常 B 调出：天津销售仓 — 备货率 158%，大日期 3200
-- ---------------------------------------------------------------------------
UPDATE yl_sales_warehouse_inventory_report
SET
    out_put_num            = 1500.00000,
    from_store_num_h       = 12200.00000,
    from_store_transit     = 0.00000,
    total_unship           = 600.00000,
    order_gap              = 11600.00000,
    ship_gap               = 11600.00000,
    order_completion_rate  = '24.1%',
    from_stock_rate_before = '157.5%'
WHERE product_code = 'MOCK_YLP001'
  AND from_site_code = 'MOCK_WH_S02'
  AND adjust_date = '2026-06-30';

UPDATE yl_spot_inventory
SET store_num = 12200.00000, invetory_deduct_sum = 11600.00000, actual_num = 12200.00000
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S02'
  AND ds = '2026-06-30'
  AND status = '合格'
  AND is_delete = 0;

-- 大日期：保留一条主记录 3200，其余天津行归零（避免重复累加）
UPDATE yl_big_date_inventory
SET big_date_num = 0.00000,
    remark = 'P1: 大日期已合并至主记录'
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S02'
  AND id NOT IN (
      SELECT MIN(id) FROM yl_big_date_inventory
      WHERE product_code = 'MOCK_YLP001' AND site_code = 'MOCK_WH_S02'
  );

UPDATE yl_big_date_inventory
SET big_date_num = 3200.00000,
    remark = 'OIP Script1 异常B：天津大日期积压，建议横向调出消化'
WHERE id = (
    SELECT MIN(id) FROM yl_big_date_inventory
    WHERE product_code = 'MOCK_YLP001' AND site_code = 'MOCK_WH_S02'
);

-- ---------------------------------------------------------------------------
-- 3. 异常 B 调入：呼市销售仓 — 备货率 58%，订单完成率 71%
-- ---------------------------------------------------------------------------
UPDATE yl_sales_warehouse_inventory_report
SET
    out_put_num            = 2800.00000,
    from_store_num_h       = 600.00000,
    from_store_transit     = 300.00000,
    total_unship           = 1833.00000,
    order_gap              = -933.00000,
    ship_gap               = -933.00000,
    order_completion_rate  = '71.0%',
    from_stock_rate_before = '56.7%'
WHERE product_code = 'MOCK_YLP001'
  AND from_site_code = 'MOCK_WH_S07'
  AND adjust_date = '2026-06-30';

UPDATE yl_spot_inventory
SET store_num = 600.00000, invetory_deduct_sum = -1233.00000, actual_num = 600.00000
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S07'
  AND ds = '2026-06-30'
  AND status = '合格'
  AND is_delete = 0;

-- ---------------------------------------------------------------------------
-- 4. OIP Script1 建议单（2026-06-30，待确认）
-- ---------------------------------------------------------------------------
DELETE FROM yl_forward_transfer
WHERE product_code = 'MOCK_YLP001'
  AND adjust_date = '2026-06-30'
  AND remark LIKE 'OIP-S1:%';

DELETE FROM yl_lateral_transfer
WHERE product_code = 'MOCK_YLP001'
  AND adjust_date = '2026-06-30'
  AND remark LIKE 'OIP-S1:%';

-- 异常 A：天津基地 → 郑州，建议正向 4700
INSERT INTO yl_forward_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num_h, from_available,
    to_site_code, to_site_name,
    trans_num_jh, trans_num,
    to_plan_num, to_store_num, to_store_transit, to_out_put_num, to_available_quantity,
    to_stock_rate_before, to_stock_rate_after, to_order_completion_rate,
    to_store_day_after, to_store_day_next,
    reason, remark, push_user
) VALUES (
    '2026-06-30', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_B02', '天津基地仓', 8913.00000, 8000.00000,
    'MOCK_WH_S04', '郑州销售仓',
    4700.00000, 4700.00000,
    10000.00000, 1200.00000, 300.00000, 3000.00000, 4200.00000,
    '45.0%', '92.0%', '72.0%',
    '21.5天', '38.8天',
    'OIP异常A：郑州订单进度72%备货率仅45%，目标提升至92%',
    'OIP-S1:正向补货草案|JD-TJ→XS-ZZ|待经理确认',
    'AGENTOS'
);

-- 异常 B：天津销售 → 呼市销售，横向 2500（大日期消化）
INSERT INTO yl_lateral_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num, from_big_date_num,
    from_out_put_num, from_plan_num, from_stock_rate_before, from_stock_rate_after,
    to_site_code, to_site_name,
    trans_num_jh, trans_num,
    to_store_num, to_store_transit, to_out_put_num, to_plan_num,
    to_stock_rate_before, to_stock_rate_after,
    reason, remark, push_user
) VALUES (
    '2026-06-30', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_S02', '天津销售仓', 12200.00000, 3200.00000,
    1500.00000, 8700.00000, '157.5%', '117.0%',
    'MOCK_WH_S07', '呼市销售仓',
    2500.00000, 2500.00000,
    600.00000, 300.00000, 2800.00000, 6525.00000,
    '56.7%', '90.5%',
    'OIP异常B：天津大日期3200件，横向消化2500件缓解呼市缺口',
    'OIP-S1:横向调拨草案|XS-TJ→XS-HS|待经理确认',
    'AGENTOS'
);

-- 异常 B：天津基地 → 呼市销售，正向 1600（横调后仍缺，经理可改 1600→1800 凑车）
INSERT INTO yl_forward_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num_h, from_available,
    to_site_code, to_site_name,
    trans_num_jh, trans_num,
    to_plan_num, to_store_num, to_store_transit, to_out_put_num, to_available_quantity,
    to_stock_rate_before, to_stock_rate_after, to_order_completion_rate,
    reason, remark, push_user
) VALUES (
    '2026-06-30', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_B02', '天津基地仓', 8913.00000, 8000.00000,
    'MOCK_WH_S07', '呼市销售仓',
    1600.00000, 1600.00000,
    6525.00000, 600.00000, 300.00000, 2800.00000, 1833.00000,
    '56.7%', '90.5%', '71.0%',
    'OIP异常B：横调后呼市仍低于目标备货率，基地正向补足',
    'OIP-S1:正向补货草案|JD-TJ→XS-HS|待经理确认',
    'AGENTOS'
);

-- ---------------------------------------------------------------------------
-- 5. 同步 6/05 forward 区域列（Tab1 仍读 6/05 批次）
-- ---------------------------------------------------------------------------
UPDATE yl_forward_transfer ft
SET
    to_plan_num              = sw.plan_num,
    to_store_num             = sw.from_store_num_h,
    to_store_transit         = sw.from_store_transit,
    to_out_put_num           = sw.out_put_num,
    to_available_quantity    = sw.total_unship,
    to_stock_rate_before     = sw.from_stock_rate_before,
    to_stock_rate_after      = TO_CHAR(
        ROUND((sw.from_store_num_h + sw.from_store_transit + sw.out_put_num + ft.trans_num)
              / NULLIF(sw.plan_num, 0) * 100, 1),
        'FM999.0') || '%',
    to_order_completion_rate = sw.order_completion_rate,
    to_store_day_after       = TO_CHAR(
        ROUND((sw.from_store_num_h + sw.from_store_transit + ft.trans_num - sw.total_unship)
              / NULLIF(sw.avg_plan_num, 0), 1),
        'FM999.0') || '天',
    to_store_day_next        = TO_CHAR(
        ROUND((sw.from_store_num_h + sw.from_store_transit + ft.trans_num - sw.total_unship)
              / NULLIF(sw.next_avg_plan_num, 0), 1),
        'FM999.0') || '天'
FROM yl_sales_warehouse_inventory_report sw
WHERE ft.product_code = 'MOCK_YLP001'
  AND ft.adjust_date = '2026-06-05'
  AND sw.product_code = 'MOCK_YLP001'
  AND sw.adjust_date = '2026-06-30'
  AND sw.from_site_code = ft.to_site_code
  AND ft.to_site_code IN ('MOCK_WH_S02', 'MOCK_WH_S04', 'MOCK_WH_S07');

COMMIT;
