# 供需缺口与全国全景

> SQL 写法与指标口径见 [SKILL.md](../SKILL.md)。下文为缺口分级等扩展片段。

## 原则

- **先全国后分仓**：全国盘子不够时，分仓补货只是挪货；全国够但分仓缺是分配/调拨问题。
- **缺口看「可履约能力」**：合格现货 + 在途（± 业务定义的已分配量）对比需求窗口内的计划消耗。
- **分级是排序工具**：红/黄/蓝用于优先级，不是替代业务审批；输出时附缺口量与 DOS 便于调度决策。

## 全国：货源 vs 14 日需求（品项级）

优先读全国报表；需自行汇总基地可分配量时可 JOIN 基地报表。

```sql
-- 全国销售仓大盘：单 SKU 供需摘要（最新快照）
SELECT
  n.adjust_date,
  n.product_code,
  n.product_name,
  n.pro_series,
  n.from_store_num_h          AS sales_qualified_stock,
  n.from_store_transit        AS sales_in_transit,
  n.total_unship              AS unshipped_orders,
  n.ship_gap,
  n.order_gap,
  n.plan_num,
  n.avg_plan_num,
  n.avg_plan_num * 14         AS demand_14d,
  n.avg_plan_num * 7          AS demand_7d,
  CASE WHEN n.avg_plan_num > 0
       THEN (n.from_store_num_h + COALESCE(n.from_store_transit, 0)) / n.avg_plan_num
       END                    AS dos_days,
  n.sell_completion_rate,
  n.order_completion_rate,
  n.xs_big_date_num,
  n.jd_big_date_num
FROM yl_national_sales_warehouse_inventory_report n
WHERE n.adjust_date = (SELECT MAX(adjust_date) FROM yl_national_sales_warehouse_inventory_report)
ORDER BY n.order_gap ASC NULLS FIRST;  -- 订单缺口越小（负值越大）越紧急
```

## 全国：基地可分配货源汇总

```sql
-- 各基地仓合格+待检现货（最新快照）
SELECT
  b.adjust_date,
  b.from_site_code,
  b.from_site_name,
  b.product_code,
  b.product_name,
  b.from_store_num_h          AS qualified,
  b.from_store_num_d          AS pending_qc,
  b.from_store_transit        AS in_transit,
  b.from_store_num_h + COALESCE(b.from_store_num_d, 0) + COALESCE(b.from_store_transit, 0) AS total_supply_side
FROM yl_base_warehouse_inventory_report b
WHERE b.adjust_date = (SELECT MAX(adjust_date) FROM yl_base_warehouse_inventory_report)
ORDER BY b.product_code, b.from_site_name;
```

## 分仓：缺口分级清单（红 / 黄 / 蓝）

```sql
WITH latest AS (
  SELECT MAX(adjust_date) AS d FROM yl_sales_warehouse_inventory_report
),
wh AS (
  SELECT
    s.adjust_date,
    s.from_site_code,
    s.from_site_name,
    s.product_code,
    s.product_name,
    s.pro_series,
    s.from_store_num_h,
    s.from_store_transit,
    s.total_unship,
    s.ship_gap,
    s.order_gap,
    s.avg_plan_num,
    s.plan_num,
    s.big_date_num,
    CASE WHEN s.avg_plan_num > 0
         THEN (COALESCE(s.from_store_num_h, 0) + COALESCE(s.from_store_transit, 0)) / s.avg_plan_num
         END AS dos_days,
    CASE WHEN s.avg_plan_num > 0
         THEN s.avg_plan_num * 7
         END AS demand_7d
  FROM yl_sales_warehouse_inventory_report s
  JOIN latest l ON s.adjust_date = l.d
)
SELECT
  *,
  CASE
    WHEN dos_days IS NOT NULL AND dos_days < 7
         AND (COALESCE(from_store_num_h, 0) + COALESCE(from_store_transit, 0)) < demand_7d
      THEN 'RED'
    WHEN dos_days IS NOT NULL AND dos_days >= 7 AND dos_days < 14
      THEN 'YELLOW'
    WHEN dos_days IS NOT NULL AND dos_days > 60
      THEN 'BLUE'
    ELSE 'NORMAL'
  END AS gap_level
FROM wh
ORDER BY
  CASE gap_level WHEN 'RED' THEN 1 WHEN 'YELLOW' THEN 2 WHEN 'BLUE' THEN 3 ELSE 4 END,
  order_gap ASC NULLS FIRST;
```

## 分仓：从明细表构造缺口（报表缺失时）

```sql
-- 销售仓：现货 + 在途 - 未发（需对齐同一 ds）
WITH snap AS (SELECT MAX(ds) AS d FROM yl_spot_inventory),
spot AS (
  SELECT site_code, product_code,
         SUM(CASE WHEN status = '合格' THEN store_num ELSE 0 END) AS qualified,
         SUM(invetory_deduct_sum) AS after_deduct
  FROM yl_spot_inventory, snap
  WHERE ds = snap.d AND site_type = 1
  GROUP BY site_code, product_code
),
trans AS (
  SELECT to_site_code AS site_code, product_code, SUM(store_transit) AS in_transit
  FROM yl_transit_inventory, snap
  WHERE ds = snap.d AND to_site_type = 1
  GROUP BY to_site_code, product_code
),
plan AS (
  SELECT site_code, product_code, avg_plan_num
  FROM yl_sales_plan sp, snap
  WHERE sp.ds = (SELECT MAX(ds) FROM yl_sales_plan)
)
SELECT
  w.site_name,
  p.product_name,
  s.qualified,
  t.in_transit,
  pl.avg_plan_num,
  pl.avg_plan_num * 14 AS demand_14d,
  COALESCE(s.qualified, 0) + COALESCE(t.in_transit, 0) - pl.avg_plan_num * 14 AS supply_minus_demand_14d
FROM spot s
FULL JOIN trans t USING (site_code, product_code)
JOIN plan pl USING (site_code, product_code)
JOIN yl_warehouse w ON w.site_code = COALESCE(s.site_code, t.site_code)
JOIN yl_product p ON p.product_code = COALESCE(s.product_code, t.product_code)
WHERE w.site_type = 1;
```

## 积压预警表（蓝色）

```sql
SELECT
  s.from_site_name,
  s.product_name,
  s.pro_series,
  s.from_store_num_h,
  s.avg_plan_num,
  CASE WHEN s.avg_plan_num > 0
       THEN s.from_store_num_h / s.avg_plan_num END AS dos_days,
  s.big_date_num,
  s.ship_gap,
  REPLACE(s.sell_completion_rate, '%', '')::numeric AS sell_completion_pct
FROM yl_sales_warehouse_inventory_report s
WHERE s.adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND s.avg_plan_num > 0
  AND s.from_store_num_h / s.avg_plan_num > 60
ORDER BY dos_days DESC;
```

## 解读提示（对内）

- `order_gap < 0`：即使算上在途仍盖不住未发——紧急度高
- `ship_gap < 0`：现货层面已断粮
- 全国 `order_gap` 为正但分仓有红：结构性错配，查横向调拨或分货规则
- 百分比字符串排序前需去 `%` 转 numeric
