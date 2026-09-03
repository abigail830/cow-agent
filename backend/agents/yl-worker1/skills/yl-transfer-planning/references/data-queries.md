# 调拨方案 · 查数 SQL

> 复制整段，只改 `product_code`、仓码、`adjust_date`。**每个** SQL 代码块 = **一次** `query_data` 调用；下方有多段时须分次提交，禁止合并。

## 方案输入包（一仓一行 · 必跑）

```sql
WITH snap AS (
  SELECT
    from_site_code,
    from_site_name,
    product_code,
    product_name,
    plan_num,
    avg_plan_num,
    out_put_num,
    from_store_num_h,
    from_store_transit,
    total_unship,
    ship_gap,
    order_gap,
    big_date_num,
    sell_completion_rate,
    order_completion_rate,
    REPLACE(sell_completion_rate, '%', '')::numeric AS sell_pct,
    (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0))
      / NULLIF(avg_plan_num, 0) AS dos_days,
    (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0) + COALESCE(out_put_num, 0))
      / NULLIF(plan_num, 0) AS stock_prep_rate_full,
    (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0))
      / NULLIF(plan_num, 0) AS stock_prep_rate_simple,
    GREATEST(0, from_store_num_h - COALESCE(total_unship, 0)) AS available_lateral,
    avg_plan_num * 14 AS safety_stock,
    GREATEST(
      0,
      COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0)
        - avg_plan_num * 14 - COALESCE(total_unship, 0)
    ) AS transferable_surplus,
    GREATEST(0, -order_gap) AS inbound_need,
    COALESCE(total_unship, 0) + GREATEST(0, -order_gap) AS urgency
  FROM yl_sales_warehouse_inventory_report
  WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
    AND product_code = 'MOCK_YLP001'
)
SELECT *,
  CASE
    WHEN dos_days < 7 AND (from_store_num_h + from_store_transit) < avg_plan_num * 7 THEN 'RED'
    WHEN dos_days < 14 THEN 'YELLOW'
    WHEN dos_days > 60 THEN 'BLUE'
    ELSE 'OK'
  END AS gap_level
FROM snap
ORDER BY urgency DESC, dos_days ASC NULLS FIRST;
```

## 全网均衡目标备货率

```sql
SELECT
  SUM(from_store_num_h + from_store_transit) / NULLIF(SUM(plan_num), 0) AS target_prep_rate_simple,
  SUM(from_store_num_h + from_store_transit + out_put_num) / NULLIF(SUM(plan_num), 0) AS target_prep_rate_full
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND product_code = 'MOCK_YLP001';
```

## 基地可分配（正向补货上限）

```sql
SELECT
  b.from_site_code,
  b.from_site_name,
  b.from_store_num_h,
  b.from_store_transit,
  b.from_store_num_d
FROM yl_base_warehouse_inventory_report b
WHERE b.adjust_date = (SELECT MAX(adjust_date) FROM yl_base_warehouse_inventory_report)
  AND b.product_code = 'MOCK_YLP001'
ORDER BY b.from_store_num_h DESC;
```

```sql
-- 最近正向单上的 from_available（历史参考）
SELECT adjust_date, from_site_name, to_site_name, from_available, trans_num, reason
FROM yl_forward_transfer
WHERE product_code = 'MOCK_YLP001'
ORDER BY adjust_date DESC
LIMIT 20;
```

## 在途路线 · 时效与运费档

```sql
SELECT
  from_site_name,
  to_site_name,
  store_transit,
  remark
FROM yl_transit_inventory
WHERE ds = (SELECT MAX(ds) FROM yl_transit_inventory)
  AND product_code = 'MOCK_YLP001'
  AND store_transit > 0
ORDER BY store_transit DESC;
```

`remark` 示例：`预计5天到达|铁路+公路|2280km|运费档:高(约1.8元/件·百公里)`

## 盈余 ↔ 缺口配对（均衡/时效起点）

```sql
WITH wh AS (
  SELECT
    from_site_code,
    from_site_name,
    order_gap,
    avg_plan_num,
    from_store_num_h,
    from_store_transit,
    total_unship,
    big_date_num,
    plan_num,
    out_put_num,
    (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0)) / NULLIF(avg_plan_num, 0) AS dos_days,
    GREATEST(
      0,
      COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0)
        - avg_plan_num * 14 - COALESCE(total_unship, 0)
    ) AS transferable_surplus
  FROM yl_sales_warehouse_inventory_report
  WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
    AND product_code = 'MOCK_YLP001'
)
SELECT
  d.from_site_name AS need_warehouse,
  s.from_site_name AS surplus_warehouse,
  d.order_gap AS need_order_gap,
  s.transferable_surplus AS surplus_qty
FROM wh d
JOIN wh s ON d.from_site_code <> s.from_site_code
WHERE (d.order_gap < 0 OR d.dos_days < 14)
  AND s.transferable_surplus > 500
ORDER BY d.order_gap ASC, s.transferable_surplus DESC;
```

## 新鲜度 · 批次库龄（方案 C 下钻）

```sql
SELECT
  site_name,
  produce_date,
  ds::date - produce_date AS age_days,
  store_num,
  status
FROM yl_spot_inventory
WHERE ds = (SELECT MAX(ds) FROM yl_spot_inventory)
  AND product_code = 'MOCK_YLP001'
  AND site_type = 1
  AND status = '合格'
ORDER BY site_name, age_days DESC;
```

## 历史调拨（方案对照 / 618 故事线）

```sql
SELECT
  adjust_date,
  from_site_name,
  to_site_name,
  trans_num,
  from_stock_rate_before,
  from_stock_rate_after,
  to_stock_rate_before,
  to_stock_rate_after,
  reason
FROM yl_lateral_transfer
WHERE product_code = 'MOCK_YLP001' AND is_delete = 0
ORDER BY adjust_date DESC
LIMIT 15;
```

更多仓间/在途片段见 `yl-supply-chain-analytics` → [cross-warehouse-balance.md](../../yl-supply-chain-analytics/references/cross-warehouse-balance.md)。
