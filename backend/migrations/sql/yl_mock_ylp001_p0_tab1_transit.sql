-- =============================================================================
-- MOCK_YLP001 Tab1 基地库存形态校准 (P0 v2)
-- 品项：伊利牛奶片32g原味(袋装) | 事业部：成人营养品事业部 (CRYYBU)
-- Tab 默认快照日：2026-06-30
-- 正向分货批次：2026-06-05
--
-- 反思（mock v1 → prod 差距）：
--   v1 将 transit_inventory 按基地 cap 等比灌入 forward.from_store_transit，
--   导致「正向/中转调拨在途」数千件，而 prod 同品项基地行在途通常为 0。
--   prod 典型形态：待检 1.5k~5k（约合格量 8%~12%），合格 2.5w~4.5w 为主体，
--   不可发预占≈0，可发量按基地差异分布（杜蒙可为 0）。
--
-- 本脚本（对齐 prod 伊利牛奶片32g原味 2026-06 快照）：
--   1. 基地报表 month_store_in / 待检 / 合格 / 在途 字段
--   2. forward 在途归零 + 可发量 prod 值
--   3. spot 预占归零（Tab 不可发列≈0）
--   4. forward 区域 6 指标 + sales.issued_not_dispatched（保留 OIP 叙事所需）
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. 基地仓报表：对齐 prod 四基地快照（2026-06-30）
--    prod 参考：呼市3286/5031/45279/13920 | 天津1556/1625/25465/10440
--              杜蒙2075/1693/32169/0     | 武汉1729/2032/26993/9464
-- ---------------------------------------------------------------------------
UPDATE yl_base_warehouse_inventory_report
SET
    month_store_in     = v.month_in,
    from_store_transit = 0.00000,
    from_store_num_d   = v.pending,
    from_store_num_h   = v.qualified,
    days_list          = '待检:' || v.pending::text || ',合格:' || v.qualified::text
FROM (VALUES
    ('MOCK_WH_B01', 3286.00000, 5031.00000, 45279.00000),
    ('MOCK_WH_B02', 1556.00000, 1625.00000, 25465.00000),
    ('MOCK_WH_B03', 2075.00000, 1693.00000, 32169.00000),
    ('MOCK_WH_B04', 1729.00000, 2032.00000, 26993.00000)
) AS v(site_code, month_in, pending, qualified)
WHERE product_code = 'MOCK_YLP001'
  AND adjust_date = '2026-06-30'
  AND from_site_code = v.site_code;

-- ---------------------------------------------------------------------------
-- 2. forward 基地侧：在途归零（prod 常态为 0，不再从 transit_inventory 灌入）
-- ---------------------------------------------------------------------------
UPDATE yl_forward_transfer
SET
    from_store_transit    = 0.00000,
    from_store_transit_zt = 0.00000
WHERE product_code = 'MOCK_YLP001'
  AND adjust_date = '2026-06-05';

-- 各基地可发量 + 现货合格量（from_store_num_h 与 spot 合格合计一致）
UPDATE yl_forward_transfer ft
SET
    from_store_num_h = v.qualified,
    from_available   = v.available
FROM (VALUES
    ('MOCK_WH_B01', 45279.00000, 13920.00000),
    ('MOCK_WH_B02', 25465.00000, 10440.00000),
    ('MOCK_WH_B03', 32169.00000,     0.00000),
    ('MOCK_WH_B04', 26993.00000,  9464.00000)
) AS v(from_site_code, qualified, available)
WHERE ft.product_code = 'MOCK_YLP001'
  AND ft.adjust_date = '2026-06-05'
  AND ft.from_site_code = v.from_site_code;

-- 杜蒙基地：补 B03 路线（6 月批次原无杜蒙发运行）
INSERT INTO yl_forward_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num_h, from_store_transit,
    from_store_transit_zt, from_available,
    to_site_code, to_site_name, trans_num_jh, trans_num, push_num, reason, push_user
)
SELECT
    '2026-06-05', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_B03', '杜蒙基地仓', 32169.00000, 0.00000, 0.00000, 0.00000,
    'MOCK_WH_S06', '武汉销售仓', 520.00000, 520.00000, 520.00000,
    '常规月度正向补货-武汉销售仓(杜蒙发运)', 'AI_SCHEDULER'
WHERE NOT EXISTS (
    SELECT 1 FROM yl_forward_transfer
    WHERE product_code = 'MOCK_YLP001'
      AND adjust_date = '2026-06-05'
      AND from_site_code = 'MOCK_WH_B03'
);

-- ---------------------------------------------------------------------------
-- 3. forward 行同步销仓 6/30 快照 + 计算区域 6 指标
-- ---------------------------------------------------------------------------
UPDATE yl_forward_transfer ft
SET
    to_plan_num              = sw.plan_num,
    to_store_num             = sw.from_store_num_h,
    to_store_transit         = sw.from_store_transit,
    to_out_put_num           = sw.out_put_num,
    to_available_quantity    = sw.total_unship,
    to_avg_plan_num          = sw.avg_plan_num,
    to_next_avg_plan_num     = sw.next_avg_plan_num,
    to_stock_rate_before     = TO_CHAR(
        ROUND((sw.from_store_num_h + sw.from_store_transit + sw.out_put_num)
              / NULLIF(sw.plan_num, 0) * 100, 1),
        'FM999.0') || '%',
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
  AND sw.from_site_code = ft.to_site_code;

-- 杜蒙新行 to_* 字段（INSERT 后单独补）
UPDATE yl_forward_transfer ft
SET
    to_plan_num              = sw.plan_num,
    to_store_num             = sw.from_store_num_h,
    to_store_transit         = sw.from_store_transit,
    to_out_put_num           = sw.out_put_num,
    to_available_quantity    = sw.total_unship,
    to_avg_plan_num          = sw.avg_plan_num,
    to_next_avg_plan_num     = sw.next_avg_plan_num,
    to_stock_rate_before     = '92.0%',
    to_stock_rate_after      = '100.0%',
    to_order_completion_rate = sw.order_completion_rate,
    to_store_day_after       = '18.5天',
    to_store_day_next        = '33.2天'
FROM yl_sales_warehouse_inventory_report sw
WHERE ft.product_code = 'MOCK_YLP001'
  AND ft.adjust_date = '2026-06-05'
  AND ft.from_site_code = 'MOCK_WH_B03'
  AND sw.product_code = 'MOCK_YLP001'
  AND sw.adjust_date = '2026-06-30'
  AND sw.from_site_code = 'MOCK_WH_S06';

-- ---------------------------------------------------------------------------
-- 4. 已下发未发货（Tab 区域列 join sales_report）
-- ---------------------------------------------------------------------------
UPDATE yl_sales_warehouse_inventory_report sw
SET issued_not_dispatched = v.issued
FROM (VALUES
    ('MOCK_WH_S01', 186.00000),
    ('MOCK_WH_S02', 209.00000),
    ('MOCK_WH_S03', 348.00000),
    ('MOCK_WH_S04', 244.00000),
    ('MOCK_WH_S05', 218.00000),
    ('MOCK_WH_S06', 236.00000),
    ('MOCK_WH_S07', 138.00000),
    ('MOCK_WH_S08', 261.00000),
    ('MOCK_WH_S09', 182.00000)
) AS v(site_code, issued)
WHERE sw.product_code = 'MOCK_YLP001'
  AND sw.adjust_date = '2026-06-30'
  AND sw.from_site_code = v.site_code;

-- ---------------------------------------------------------------------------
-- 5. spot 基地仓：确认待检/合格 prod 值 + 预占归零（不可发≈0）
--    种子 batch2 已接近 prod；此处显式锁定并清除 oms/wms/tms 预占
-- ---------------------------------------------------------------------------
UPDATE yl_spot_inventory si
SET
    store_num    = v.qty,
    actual_num   = v.qty,
    oms_dist_num = 0.00000,
    wms_dist_num = 0.00000,
    tms_dist_num = 0.00000,
    update_time  = CURRENT_TIMESTAMP
FROM (VALUES
    ('MOCK_WH_B01', '待检', 5031.00000),
    ('MOCK_WH_B02', '待检', 1625.00000),
    ('MOCK_WH_B03', '待检', 1693.00000),
    ('MOCK_WH_B04', '待检', 2032.00000)
) AS v(site_code, status, qty)
WHERE si.product_code = 'MOCK_YLP001'
  AND si.ds = '2026-06-30'
  AND si.site_type = 0
  AND si.is_delete = 0
  AND si.site_code = v.site_code
  AND si.status = v.status;

UPDATE yl_spot_inventory si
SET
    oms_dist_num = 0.00000,
    wms_dist_num = 0.00000,
    tms_dist_num = 0.00000,
    update_time  = CURRENT_TIMESTAMP
WHERE si.product_code = 'MOCK_YLP001'
  AND si.ds = '2026-06-30'
  AND si.site_type = 0
  AND si.is_delete = 0
  AND si.status = '合格';

COMMIT;
