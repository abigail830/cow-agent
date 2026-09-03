# 仓间均衡、在途与调拨

## 原则

- **旱涝不均是分仓补货的核心矛盾**：一仓缺货、一仓压仓时，全国总量可能平衡——先看分布再看总量。
- **在途是缓冲，不是消除缺口**：在途到达前未发订单仍压制履约；标注预计缓解时需结合 `transit_inventory` 与调拨单。
- **调拨记录看执行**：建议量 vs 下发量、调拨前后备货率变化，用于复盘而非替代实时缺口计算。

## 仓间对比：同品项多仓快照

```sql
SELECT
  from_site_name,
  product_name,
  from_store_num_h,
  from_store_transit,
  total_unship,
  ship_gap,
  order_gap,
  avg_plan_num,
  CASE WHEN avg_plan_num > 0
       THEN (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0)) / avg_plan_num
       END AS dos_days,
  sell_completion_rate
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND product_code = 'MOCK_YLP001'
ORDER BY dos_days ASC NULLS FIRST;
```

## 配对机会：盈余仓 vs 缺口仓（启发式）

```sql
WITH wh AS (
  SELECT
    from_site_code,
    from_site_name,
    product_code,
    product_name,
    from_store_num_h,
    from_store_transit,
    total_unship,
    order_gap,
    avg_plan_num,
    CASE WHEN avg_plan_num > 0
         THEN (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0)) / avg_plan_num
         END AS dos_days
  FROM yl_sales_warehouse_inventory_report
  WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
),
surplus AS (
  SELECT * FROM wh WHERE dos_days > 45 AND order_gap > 0
),
deficit AS (
  SELECT * FROM wh WHERE order_gap < 0 OR (dos_days IS NOT NULL AND dos_days < 7)
)
SELECT
  s.from_site_name AS surplus_warehouse,
  d.from_site_name AS deficit_warehouse,
  s.product_name,
  s.from_store_num_h AS surplus_stock,
  s.order_gap AS surplus_order_gap,
  d.order_gap AS deficit_order_gap,
  d.total_unship AS deficit_unship
FROM surplus s
JOIN deficit d ON s.product_code = d.product_code AND s.from_site_code <> d.from_site_code
ORDER BY d.order_gap ASC, s.order_gap DESC;
```

## 在途流向

```sql
SELECT
  ti.ds,
  ti.product_name,
  ti.from_site_name,
  ti.from_site_type,
  ti.to_site_name,
  ti.to_site_type,
  ti.store_transit,
  ti.issued_not_dispatched,
  ti.trans_order_not_dispatched
FROM yl_transit_inventory ti
WHERE ti.ds = (SELECT MAX(ds) FROM yl_transit_inventory)
ORDER BY ti.store_transit DESC;
```

## 横向调拨单

```sql
SELECT
  adjust_date,
  product_name,
  from_site_name,
  to_site_name,
  trans_num_jh,
  trans_num,
  push_num,
  from_stock_rate_before,
  from_stock_rate_after,
  to_stock_rate_before,
  to_stock_rate_after,
  reason,
  push_user
FROM yl_lateral_transfer
WHERE is_delete = 0
ORDER BY adjust_date DESC;
```

## 正向调拨（基地 → 销售仓）

```sql
SELECT
  adjust_date,
  product_name,
  from_site_name,
  to_site_name,
  from_available,
  trans_num_jh,
  trans_num,
  push_num,
  to_store_day_after,
  to_order_completion_rate,
  reason,
  push_user
FROM yl_forward_transfer
ORDER BY adjust_date DESC;
```

## 销仓可调拨量（横向调拨备选仓）

> **注意**：`from_store_transit` 是在途列的正确名；`total_unship` 是未发订单列；两者均无 `_num_` 中缀变体。

```sql
-- 找出同品项可横向调出的销售仓（可调拨 = 合格现货 − 未发订单，需 > 0）
SELECT
  from_site_code,
  from_site_name,
  product_code,
  product_name,
  from_store_num_h                                           AS qualified_stock,
  from_store_transit                                         AS in_transit,
  total_unship                                               AS unshipped_orders,
  from_store_num_h - COALESCE(total_unship, 0)              AS available_for_transfer,
  order_gap,
  avg_plan_num
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND product_name ILIKE '%珍护%1%'
  AND from_store_num_h - COALESCE(total_unship, 0) > 0
ORDER BY available_for_transfer DESC;
```

## 基地可分配 vs 销仓缺口（拉式补货）

```sql
-- 同品：基地可发 vs 销仓订单缺口
WITH base AS (
  SELECT product_code, product_name,
         SUM(from_store_num_h) AS base_qualified
  FROM yl_base_warehouse_inventory_report
  WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_base_warehouse_inventory_report)
  GROUP BY product_code, product_name
),
sales AS (
  SELECT product_code, product_name,
         SUM(from_store_num_h) AS sales_qualified,
         SUM(total_unship) AS total_unship,
         SUM(CASE WHEN order_gap < 0 THEN ABS(order_gap) ELSE 0 END) AS aggregate_shortfall
  FROM yl_sales_warehouse_inventory_report
  WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  GROUP BY product_code, product_name
)
SELECT
  s.product_name,
  b.base_qualified,
  s.sales_qualified,
  s.total_unship,
  s.aggregate_shortfall,
  b.base_qualified - s.aggregate_shortfall AS base_after_cover_shortfall
FROM sales s
JOIN base b USING (product_code, product_name)
WHERE s.aggregate_shortfall > 0
ORDER BY s.aggregate_shortfall DESC;
```

## 解读提示

- 横向调拨适合 **销仓间** DOS 悬殊、运输半径可接受
- 正向调拨适合 **基地有货、销仓断粮**
- `from_available` 为基地扣除已分配后的可发——正向调拨上限参考
- TMS/WMS 表数据稀疏，仅作「在途佐证」，不可替代 `transit_inventory` 量化
