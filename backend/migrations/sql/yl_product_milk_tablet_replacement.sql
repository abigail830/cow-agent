-- =============================================================================
-- YL Mock 产品信息替换：婴幼儿奶粉 → 伊利牛奶片/牛奶贝
-- =============================================================================
-- 用途：在已导入原有 mock 数据的库上执行，将 8 个 MOCK_YLP00x SKU 的产品描述
--       等量替换为牛奶片系列，保留 product_code（MOCK_YLP001~008）及所有业务数量。
--
-- 映射关系（原最详数据 MOCK_YLP001 → 伊利牛奶片32g原味(袋装)）：
--   MOCK_YLP001 → YL-MP-001  伊利牛奶片32g原味(袋装)
--   MOCK_YLP002 → YL-MP-002  伊利牛奶片32g草莓味(袋装)
--   MOCK_YLP003 → YL-MP-003  伊利牛奶片160g原味(盒装)
--   MOCK_YLP004 → YL-MP-004  伊利牛奶片160g草莓味(盒装)
--   MOCK_YLP005 → YL-MP-005  伊小粒牛奶片(盒装)144g
--   MOCK_YLP006 → YL-MP-006  伊小粒DHA牛奶片(盒装)144g
--   MOCK_YLP007 → YL-MP-007  伊利牛奶贝(盒装)144g
--   MOCK_YLP008 → YL-MP-008  伊利牛奶贝144g原味(盒装)
--
-- 涉及表（按 product_code 关联）：
--   1. yl_product                              — 产品主数据（全字段）
--   2. yl_sales_plan                           — product_name
--   3. yl_actual_sales                         — product_name
--   4. yl_spot_inventory                       — product_name
--   5. yl_transit_inventory                    — product_name
--   6. yl_base_warehouse_inventory_report      — product_name, pro_series, weight
--   7. yl_sales_warehouse_inventory_report     — product_name, pro_series, weight
--   8. yl_national_sales_warehouse_inventory_report — product_name, pro_series, weight
--   9. yl_lateral_transfer                     — product_name
--  10. yl_forward_transfer                     — product_name
--  11. yl_big_date_inventory                   — product_name
--
-- 不涉及变更：yl_warehouse, yl_tms_gps, yl_wms_waybill（无产品维度）
--
-- 报表 weight 字段按新/旧箱重比例重算（原 weight = 库存件数 × 旧箱重吨）。
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. 产品主数据 yl_product
-- ---------------------------------------------------------------------------
UPDATE yl_product SET
    product_name = '伊利牛奶片32g原味(袋装)',
    trade_name = '牛奶片(原味)',
    brand = '伊利',
    weight_unit = 32.00000,
    specification = 100,
    weight = 0.00320000,
    sort = 10,
    remark = '基础原味袋装',
    pack_type = '袋装',
    volume = '1×100×32g',
    pro_series = '经典牛奶片系列',
    price = 88.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP001';

UPDATE yl_product SET
    product_name = '伊利牛奶片32g草莓味(袋装)',
    trade_name = '牛奶片(草莓味)',
    brand = '伊利',
    weight_unit = 32.00000,
    specification = 100,
    weight = 0.00320000,
    sort = 11,
    remark = '经典草莓味袋装',
    pack_type = '袋装',
    volume = '1×100×32g',
    pro_series = '经典牛奶片系列',
    price = 88.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP002';

UPDATE yl_product SET
    product_name = '伊利牛奶片160g原味(盒装)',
    trade_name = '牛奶片(原味)',
    brand = '伊利',
    weight_unit = 160.00000,
    specification = 12,
    weight = 0.00192000,
    sort = 12,
    remark = '大容量原味盒装',
    pack_type = '盒装',
    volume = '1×12×160g',
    pro_series = '经典牛奶片系列',
    price = 168.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP003';

UPDATE yl_product SET
    product_name = '伊利牛奶片160g草莓味(盒装)',
    trade_name = '牛奶片(草莓味)',
    brand = '伊利',
    weight_unit = 160.00000,
    specification = 12,
    weight = 0.00192000,
    sort = 13,
    remark = '大容量草莓味盒装',
    pack_type = '盒装',
    volume = '1×12×160g',
    pro_series = '经典牛奶片系列',
    price = 168.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP004';

UPDATE yl_product SET
    product_name = '伊小粒牛奶片(盒装)144g',
    trade_name = '伊小粒牛奶片',
    brand = '伊利',
    weight_unit = 144.00000,
    specification = 12,
    weight = 0.00172800,
    sort = 20,
    remark = '儿童/趣味小粒奶片',
    pack_type = '盒装',
    volume = '1×12×144g',
    pro_series = '伊小粒系列',
    price = 158.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP005';

UPDATE yl_product SET
    product_name = '伊小粒DHA牛奶片(盒装)144g',
    trade_name = '伊小粒DHA牛奶片',
    brand = '伊利',
    weight_unit = 144.00000,
    specification = 12,
    weight = 0.00172800,
    sort = 30,
    remark = '营养强化添加DHA',
    pack_type = '盒装',
    volume = '1×12×144g',
    pro_series = '伊小粒系列',
    price = 178.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP006';

UPDATE yl_product SET
    product_name = '伊利牛奶贝(盒装)144g',
    trade_name = '牛奶贝',
    brand = '伊利',
    weight_unit = 144.00000,
    specification = 12,
    weight = 0.00172800,
    sort = 40,
    remark = '经典牛奶贝混批/标准款',
    pack_type = '盒装',
    volume = '1×12×144g',
    pro_series = '牛奶贝系列',
    price = 148.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP007';

UPDATE yl_product SET
    product_name = '伊利牛奶贝144g原味(盒装)',
    trade_name = '牛奶贝(原味)',
    brand = '伊利',
    weight_unit = 144.00000,
    specification = 12,
    weight = 0.00172800,
    sort = 50,
    remark = '原味牛奶贝',
    pack_type = '盒装',
    volume = '1×12×144g',
    pro_series = '牛奶贝系列',
    price = 148.00000,
    update_time = CURRENT_TIMESTAMP
WHERE product_code = 'MOCK_YLP008';

-- ---------------------------------------------------------------------------
-- 2. 业务表 product_name 批量更新
-- ---------------------------------------------------------------------------
UPDATE yl_sales_plan SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_sales_plan SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_sales_plan SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_sales_plan SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_sales_plan SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_sales_plan SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_sales_plan SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_sales_plan SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

UPDATE yl_actual_sales SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_actual_sales SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_actual_sales SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_actual_sales SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_actual_sales SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_actual_sales SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_actual_sales SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_actual_sales SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

UPDATE yl_spot_inventory SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_spot_inventory SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_spot_inventory SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_spot_inventory SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_spot_inventory SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_spot_inventory SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_spot_inventory SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_spot_inventory SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

UPDATE yl_transit_inventory SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_transit_inventory SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_transit_inventory SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_transit_inventory SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_transit_inventory SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_transit_inventory SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_transit_inventory SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_transit_inventory SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

UPDATE yl_lateral_transfer SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_lateral_transfer SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_lateral_transfer SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_lateral_transfer SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_lateral_transfer SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_lateral_transfer SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_lateral_transfer SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_lateral_transfer SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

UPDATE yl_forward_transfer SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_forward_transfer SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_forward_transfer SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_forward_transfer SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_forward_transfer SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_forward_transfer SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_forward_transfer SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_forward_transfer SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

UPDATE yl_big_date_inventory SET product_name = '伊利牛奶片32g原味(袋装)' WHERE product_code = 'MOCK_YLP001';
UPDATE yl_big_date_inventory SET product_name = '伊利牛奶片32g草莓味(袋装)' WHERE product_code = 'MOCK_YLP002';
UPDATE yl_big_date_inventory SET product_name = '伊利牛奶片160g原味(盒装)' WHERE product_code = 'MOCK_YLP003';
UPDATE yl_big_date_inventory SET product_name = '伊利牛奶片160g草莓味(盒装)' WHERE product_code = 'MOCK_YLP004';
UPDATE yl_big_date_inventory SET product_name = '伊小粒牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP005';
UPDATE yl_big_date_inventory SET product_name = '伊小粒DHA牛奶片(盒装)144g' WHERE product_code = 'MOCK_YLP006';
UPDATE yl_big_date_inventory SET product_name = '伊利牛奶贝(盒装)144g' WHERE product_code = 'MOCK_YLP007';
UPDATE yl_big_date_inventory SET product_name = '伊利牛奶贝144g原味(盒装)' WHERE product_code = 'MOCK_YLP008';

-- ---------------------------------------------------------------------------
-- 3. 库存监控报表：product_name + pro_series + weight（按箱重比例重算）
--    旧箱重(吨): YLP001/002/003/005=0.0054, YLP004/006/007/008=0.0048
--    新箱重(吨): YLP001/002=0.0032, YLP003/004=0.00192, YLP005~008=0.001728
-- ---------------------------------------------------------------------------

-- yl_base_warehouse_inventory_report
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊利牛奶片32g原味(袋装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00320000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP001';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊利牛奶片32g草莓味(袋装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00320000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP002';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊利牛奶片160g原味(盒装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00192000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP003';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊利牛奶片160g草莓味(盒装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00192000 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP004';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊小粒牛奶片(盒装)144g', pro_series = '伊小粒系列',
    weight = ROUND(weight * 0.00172800 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP005';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊小粒DHA牛奶片(盒装)144g', pro_series = '伊小粒系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP006';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊利牛奶贝(盒装)144g', pro_series = '牛奶贝系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP007';
UPDATE yl_base_warehouse_inventory_report SET
    product_name = '伊利牛奶贝144g原味(盒装)', pro_series = '牛奶贝系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP008';

-- yl_sales_warehouse_inventory_report
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片32g原味(袋装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00320000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP001';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片32g草莓味(袋装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00320000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP002';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片160g原味(盒装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00192000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP003';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片160g草莓味(盒装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00192000 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP004';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊小粒牛奶片(盒装)144g', pro_series = '伊小粒系列',
    weight = ROUND(weight * 0.00172800 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP005';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊小粒DHA牛奶片(盒装)144g', pro_series = '伊小粒系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP006';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶贝(盒装)144g', pro_series = '牛奶贝系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP007';
UPDATE yl_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶贝144g原味(盒装)', pro_series = '牛奶贝系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP008';

-- yl_national_sales_warehouse_inventory_report
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片32g原味(袋装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00320000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP001';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片32g草莓味(袋装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00320000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP002';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片160g原味(盒装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00192000 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP003';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶片160g草莓味(盒装)', pro_series = '经典牛奶片系列',
    weight = ROUND(weight * 0.00192000 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP004';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊小粒牛奶片(盒装)144g', pro_series = '伊小粒系列',
    weight = ROUND(weight * 0.00172800 / 0.00540000, 5)
WHERE product_code = 'MOCK_YLP005';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊小粒DHA牛奶片(盒装)144g', pro_series = '伊小粒系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP006';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶贝(盒装)144g', pro_series = '牛奶贝系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP007';
UPDATE yl_national_sales_warehouse_inventory_report SET
    product_name = '伊利牛奶贝144g原味(盒装)', pro_series = '牛奶贝系列',
    weight = ROUND(weight * 0.00172800 / 0.00480000, 5)
WHERE product_code = 'MOCK_YLP008';

COMMIT;

-- ---------------------------------------------------------------------------
-- 验证（可选，执行后手动运行）
-- ---------------------------------------------------------------------------
-- SELECT product_code, product_name, trade_name, brand, pro_series, weight_unit, specification, weight, pack_type, volume
-- FROM yl_product WHERE product_code LIKE 'MOCK_YLP%' ORDER BY sort;
--
-- SELECT product_code, COUNT(*) AS cnt, MIN(product_name) AS sample_name
-- FROM (
--     SELECT product_code, product_name FROM yl_sales_plan
--     UNION ALL SELECT product_code, product_name FROM yl_actual_sales
--     UNION ALL SELECT product_code, product_name FROM yl_spot_inventory
--     UNION ALL SELECT product_code, product_name FROM yl_transit_inventory
--     UNION ALL SELECT product_code, product_name FROM yl_lateral_transfer
--     UNION ALL SELECT product_code, product_name FROM yl_forward_transfer
--     UNION ALL SELECT product_code, product_name FROM yl_big_date_inventory
--     UNION ALL SELECT product_code, product_name FROM yl_base_warehouse_inventory_report
--     UNION ALL SELECT product_code, product_name FROM yl_sales_warehouse_inventory_report
--     UNION ALL SELECT product_code, product_name FROM yl_national_sales_warehouse_inventory_report
-- ) t
-- WHERE product_code LIKE 'MOCK_YLP%'
-- GROUP BY product_code ORDER BY product_code;
