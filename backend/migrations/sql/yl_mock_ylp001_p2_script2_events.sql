-- =============================================================================
-- MOCK_YLP001 OIP Script 2 事件驱动补调 (P2)
-- Tab 默认快照日：2026-06-30（主快照不变；事件以同日时间戳叙事）
--
-- 仓映射（OIP → Mock）：
--   事件1 工厂入库延期 → 天津基地仓 MOCK_WH_B02 from_available 8000→3200
--                        影响 Script1 郑州正向方案 4700→3200 + 天津销售横调郑州 1200 + 武汉基地补尾差 300
--   事件2 大客户追加订单 → 呼市销售仓 MOCK_WH_S07 total_unship +2800
--
-- 本脚本：
--   1. 基地可发量下调 + 销仓订单追加
--   2. 作废/变更 6/30 OIP-S1 草案，写入 OIP-S2 临时方案
--   3. TMS GPS 在途轨迹（郑州/呼市方向）
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. 事件1：天津基地入库延期 — 可发量 8000 → 3200
-- ---------------------------------------------------------------------------
UPDATE yl_forward_transfer
SET from_available = 3200.00000,
    remark = COALESCE(remark, '') || '|OIP-S2:入库延期可发量下调2026-06-30T10:30'
WHERE product_code = 'MOCK_YLP001'
  AND from_site_code = 'MOCK_WH_B02'
  AND adjust_date IN ('2026-06-05', '2026-06-30');

-- ---------------------------------------------------------------------------
-- 2. 事件2：呼市销售仓大客户追加订单 +2800（T 日 14:20）
-- ---------------------------------------------------------------------------
UPDATE yl_sales_warehouse_inventory_report
SET
    total_unship           = total_unship + 2800.00000,
    order_gap              = order_gap - 2800.00000,
    ship_gap               = ship_gap - 2800.00000,
    order_completion_rate  = '114.0%'
WHERE product_code = 'MOCK_YLP001'
  AND from_site_code = 'MOCK_WH_S07'
  AND adjust_date = '2026-06-30';

UPDATE yl_actual_sales
SET
    unshipped_orders   = unshipped_orders + 2800.00000,
    available_quantity = available_quantity + 2800.00000,
    remark = COALESCE(remark, '') || '|OIP-S2:追加订单2800'
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S07'
  AND sell_year = 2026
  AND sell_month = 6;

-- ---------------------------------------------------------------------------
-- 3. Script2 临时补调方案（2026-06-30，替换 S1 郑州正向草案）
-- ---------------------------------------------------------------------------
UPDATE yl_forward_transfer
SET
    trans_num_jh = 3200.00000,
    trans_num    = 3200.00000,
    to_stock_rate_after = '77.0%',
    reason = 'OIP-S2事件1：天津入库延期，郑州正向由4700下调至3200（可发量上限）',
    remark = 'OIP-S2:正向补货变更|JD-TJ→XS-ZZ|已确认临时方案',
    push_num = 3200.00000,
    push_time = TIMESTAMP '2026-06-30 10:45:00',
    push_user = '补调经理'
WHERE product_code = 'MOCK_YLP001'
  AND adjust_date = '2026-06-30'
  AND remark LIKE 'OIP-S1:正向补货草案|JD-TJ→XS-ZZ%';

INSERT INTO yl_lateral_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num, from_plan_num,
    from_stock_rate_before, from_stock_rate_after,
    to_site_code, to_site_name,
    trans_num_jh, trans_num, push_num,
    to_store_num, to_plan_num, to_stock_rate_before, to_stock_rate_after,
    reason, remark, push_time, push_user
)
SELECT
    '2026-06-30', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_S02', '天津销售仓', 12200.00000, 8700.00000,
    '157.5%', '103.0%',
    'MOCK_WH_S04', '郑州销售仓',
    1200.00000, 1200.00000, 1200.00000,
    1200.00000, 10000.00000, '45.0%', '89.0%',
    'OIP-S2事件1：天津基地不足，天津销售仓临时横调郑州1200件T+1',
    'OIP-S2:临时横调|XS-TJ→XS-ZZ|10:45确认',
    TIMESTAMP '2026-06-30 10:45:00', '补调经理'
WHERE NOT EXISTS (
    SELECT 1 FROM yl_lateral_transfer
    WHERE product_code = 'MOCK_YLP001'
      AND adjust_date = '2026-06-30'
      AND remark LIKE 'OIP-S2:临时横调|XS-TJ→XS-ZZ%'
);

INSERT INTO yl_forward_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num_h, from_available,
    to_site_code, to_site_name,
    trans_num_jh, trans_num, push_num,
    to_plan_num, to_store_num, to_out_put_num, to_available_quantity,
    to_stock_rate_before, to_stock_rate_after, to_order_completion_rate,
    reason, remark, push_time, push_user
)
SELECT
    '2026-06-30', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_B04', '武汉基地仓', 9448.00000, 7656.00000,
    'MOCK_WH_S04', '郑州销售仓',
    300.00000, 300.00000, 300.00000,
    10000.00000, 1200.00000, 3000.00000, 4200.00000,
    '45.0%', '92.0%', '72.0%',
    'OIP-S2事件1：武汉基地补尾差300件，凑足郑州目标备货率',
    'OIP-S2:正向补尾差|JD-WH→XS-ZZ|10:45确认',
    TIMESTAMP '2026-06-30 10:45:00', '补调经理'
WHERE NOT EXISTS (
    SELECT 1 FROM yl_forward_transfer
    WHERE product_code = 'MOCK_YLP001'
      AND adjust_date = '2026-06-30'
      AND remark LIKE 'OIP-S2:正向补尾差|JD-WH→XS-ZZ%'
);

-- Script2 事件2：呼市追加订单后临时补货 900（基地武汉发运）
INSERT INTO yl_forward_transfer (
    adjust_date, business, business_code, product_code, product_name,
    from_site_code, from_site_name, from_store_num_h, from_available,
    to_site_code, to_site_name,
    trans_num_jh, trans_num, push_num,
    to_plan_num, to_store_num, to_store_transit, to_out_put_num,
    to_stock_rate_before, to_order_completion_rate,
    reason, remark, push_time, push_user
)
SELECT
    '2026-06-30', '成人营养品事业部', 'CRYYBU', 'MOCK_YLP001', '伊利牛奶片32g原味(袋装)',
    'MOCK_WH_B04', '武汉基地仓', 9448.00000, 7356.00000,
    'MOCK_WH_S07', '呼市销售仓',
    900.00000, 900.00000, 900.00000,
    6525.00000, 600.00000, 300.00000, 2800.00000,
    '56.7%', '114.0%',
    'OIP-S2事件2：大客户追加2800后呼市缺口900，武汉基地紧急正向',
    'OIP-S2:临时正向|JD-WH→XS-HS|14:35确认',
    TIMESTAMP '2026-06-30 14:35:00', '补调经理'
WHERE NOT EXISTS (
    SELECT 1 FROM yl_forward_transfer
    WHERE product_code = 'MOCK_YLP001'
      AND adjust_date = '2026-06-30'
      AND remark LIKE 'OIP-S2:临时正向|JD-WH→XS-HS%'
);

-- 同步 6/05 郑州路线区域列（事件1 后郑州备货率约 92%）
UPDATE yl_forward_transfer ft
SET
    to_available_quantity    = sw.total_unship,
    to_order_completion_rate = sw.order_completion_rate,
    to_store_day_after       = '19.2天'
FROM yl_sales_warehouse_inventory_report sw
WHERE ft.product_code = 'MOCK_YLP001'
  AND ft.adjust_date = '2026-06-05'
  AND ft.to_site_code = 'MOCK_WH_S04'
  AND sw.product_code = 'MOCK_YLP001'
  AND sw.adjust_date = '2026-06-30'
  AND sw.from_site_code = 'MOCK_WH_S04';

UPDATE yl_forward_transfer ft
SET
    to_available_quantity    = sw.total_unship,
    to_order_completion_rate = sw.order_completion_rate,
    to_store_day_after       = '8.5天'
FROM yl_sales_warehouse_inventory_report sw
WHERE ft.product_code = 'MOCK_YLP001'
  AND ft.adjust_date = '2026-06-05'
  AND ft.to_site_code = 'MOCK_WH_S07'
  AND sw.product_code = 'MOCK_YLP001'
  AND sw.adjust_date = '2026-06-30'
  AND sw.from_site_code = 'MOCK_WH_S07';

-- ---------------------------------------------------------------------------
-- 4. TMS GPS：在途车辆轨迹（MOCK_YLP001 郑州/呼市方向）
-- ---------------------------------------------------------------------------
DELETE FROM yl_tms_gps
WHERE plate_no IN ('蒙A·OIP001', '蒙A·OIP002')
  AND location_time >= TIMESTAMP '2026-06-30 08:00:00';

INSERT INTO yl_tms_gps (
    seq_no, location_time, speed_kmh, mileage_km, driving_mileage_km,
    status, location, longitude, latitude, weather,
    plate_no, driver, driver_phone, warehouse
) VALUES
(1, TIMESTAMP '2026-06-30 09:15:00', 62.00000, 1280.00000, 1280.00000,
 '在途', '京港澳高速邯郸服务区附近', 114.53900000, 36.62500000, '晴',
 '蒙A·OIP001', '张师傅', '13800001001', '天津基地仓→郑州销售仓'),
(2, TIMESTAMP '2026-06-30 11:20:00', 58.00000, 1560.00000, 1560.00000,
 '在途', '京港澳高速新乡段', 113.88300000, 35.30200000, '晴',
 '蒙A·OIP001', '张师傅', '13800001001', '天津基地仓→郑州销售仓'),
(3, TIMESTAMP '2026-06-30 14:40:00', 55.00000, 980.00000, 980.00000,
 '在途', '连霍高速洛阳段', 112.45400000, 34.61900000, '多云',
 '蒙A·OIP002', '李师傅', '13800001002', '武汉基地仓→呼市销售仓');

COMMIT;
