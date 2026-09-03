-- =============================================================================
-- YL Mock 事业部切换：奶粉事业部 → 成人营养品事业部
-- =============================================================================
-- 用途：在已导入原有 mock 数据的库上执行，将事业部维度从「奶粉事业部 / NFBU」
--       整体切换为「成人营养品事业部 / CRYYBU」，与 yl-scm-mockup 前端 mock 对齐。
--
-- 映射：
--   business      : 奶粉事业部        → 成人营养品事业部
--   business_code : NFBU              → CRYYBU
--
-- 涉及表（共 8 张，均含 business 和/或 business_code 字段）：
--   1. yl_product                              — business, business_code
--   2. yl_warehouse                            — business, business_code
--   3. yl_base_warehouse_inventory_report      — business_code
--   4. yl_sales_warehouse_inventory_report     — business_code
--   5. yl_national_sales_warehouse_inventory_report — business_code
--   6. yl_lateral_transfer                     — business, business_code
--   7. yl_forward_transfer                     — business, business_code
--   8. yl_big_date_inventory                   — business, business_code
--
-- 不涉及变更（无事业部字段）：
--   yl_sales_plan, yl_actual_sales, yl_spot_inventory, yl_transit_inventory,
--   yl_tms_gps, yl_wms_waybill
--
-- 补充说明：
--   yl_wms_waybill.customer_name 中含「伊利奶粉*分仓」文案（非事业部字段），
--   若需同步改为「伊利成人营养品*分仓」，见文末可选补丁。
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. 产品主数据 yl_product
-- ---------------------------------------------------------------------------
UPDATE yl_product
SET
    business = '成人营养品事业部',
    business_code = 'CRYYBU',
    update_time = CURRENT_TIMESTAMP
WHERE business = '奶粉事业部'
   OR business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 2. 仓主数据 yl_warehouse
-- ---------------------------------------------------------------------------
UPDATE yl_warehouse
SET
    business = '成人营养品事业部',
    business_code = 'CRYYBU'
WHERE business = '奶粉事业部'
   OR business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 3. 基地仓库存监控报表 yl_base_warehouse_inventory_report
-- ---------------------------------------------------------------------------
UPDATE yl_base_warehouse_inventory_report
SET business_code = 'CRYYBU'
WHERE business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 4. 销售仓库存监控报表 yl_sales_warehouse_inventory_report
-- ---------------------------------------------------------------------------
UPDATE yl_sales_warehouse_inventory_report
SET business_code = 'CRYYBU'
WHERE business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 5. 全国销售仓库存监控报表 yl_national_sales_warehouse_inventory_report
-- ---------------------------------------------------------------------------
UPDATE yl_national_sales_warehouse_inventory_report
SET business_code = 'CRYYBU'
WHERE business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 6. 横向调拨 yl_lateral_transfer
-- ---------------------------------------------------------------------------
UPDATE yl_lateral_transfer
SET
    business = '成人营养品事业部',
    business_code = 'CRYYBU'
WHERE business = '奶粉事业部'
   OR business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 7. 正向调拨 yl_forward_transfer
-- ---------------------------------------------------------------------------
UPDATE yl_forward_transfer
SET
    business = '成人营养品事业部',
    business_code = 'CRYYBU'
WHERE business = '奶粉事业部'
   OR business_code = 'NFBU';

-- ---------------------------------------------------------------------------
-- 8. 大日期库存 yl_big_date_inventory
-- ---------------------------------------------------------------------------
UPDATE yl_big_date_inventory
SET
    business = '成人营养品事业部',
    business_code = 'CRYYBU'
WHERE business = '奶粉事业部'
   OR business_code = 'NFBU';

COMMIT;

-- ---------------------------------------------------------------------------
-- 验证（可选，执行后手动运行）
-- ---------------------------------------------------------------------------
-- SELECT 'yl_product' AS tbl, business, business_code, COUNT(*) AS cnt
-- FROM yl_product GROUP BY business, business_code
-- UNION ALL
-- SELECT 'yl_warehouse', business, business_code, COUNT(*)
-- FROM yl_warehouse GROUP BY business, business_code
-- UNION ALL
-- SELECT 'yl_lateral_transfer', business, business_code, COUNT(*)
-- FROM yl_lateral_transfer GROUP BY business, business_code
-- UNION ALL
-- SELECT 'yl_forward_transfer', business, business_code, COUNT(*)
-- FROM yl_forward_transfer GROUP BY business, business_code
-- UNION ALL
-- SELECT 'yl_big_date_inventory', business, business_code, COUNT(*)
-- FROM yl_big_date_inventory GROUP BY business, business_code;
--
-- SELECT 'report tables' AS scope, business_code, COUNT(*) AS cnt
-- FROM (
--     SELECT business_code FROM yl_base_warehouse_inventory_report
--     UNION ALL SELECT business_code FROM yl_sales_warehouse_inventory_report
--     UNION ALL SELECT business_code FROM yl_national_sales_warehouse_inventory_report
-- ) t
-- GROUP BY business_code;

-- ---------------------------------------------------------------------------
-- 可选补丁：WMS 运单客户名称「伊利奶粉*分仓」→「伊利成人营养品*分仓」
-- （yl_wms_waybill 无 business 字段，仅文案对齐）
-- ---------------------------------------------------------------------------
-- BEGIN;
-- UPDATE yl_wms_waybill
-- SET customer_name = REPLACE(customer_name, '伊利奶粉', '伊利成人营养品')
-- WHERE customer_name LIKE '伊利奶粉%';
-- COMMIT;
