# 下钻、JOIN 与快照对齐

## 原则

- **先对齐时间再 JOIN**：不同表的 `ds` / `adjust_date` 可能不一致；用 `MAX()` 取最新或用户指定日，避免混日对比。
- **报表优先、明细补全**：缺口/完成率用报表；批次库龄、在途明细、历史计划用事实表。
- **LEFT JOIN 保留驱动侧**：以「要分析的仓×品」为驱动，避免 INNER JOIN 丢缺货仓（无现货行）。

## 标准星型（概念）

```
yl_product ── product_code ──┬── yl_sales_plan
yl_warehouse ─ site_code ────┼── yl_actual_sales
                             ├── yl_spot_inventory
                             ├── yl_sales_warehouse_inventory_report (from_site_code)
                             └── yl_transit_inventory (to_site_code / from_site_code)
```

## 销售仓完整画像（报表 + 主数据）

```sql
SELECT
  r.adjust_date,
  w.site_name,
  w.site_type,
  p.brand,
  p.pro_series,
  p.pack_type,
  r.product_name,
  r.plan_num,
  r.sell_num,
  r.out_put_num,
  r.from_store_num_h,
  r.from_store_transit,
  r.total_unship,
  r.ship_gap,
  r.order_gap,
  r.avg_plan_num,
  r.big_date_num
FROM yl_sales_warehouse_inventory_report r
JOIN yl_warehouse w ON w.site_code = r.from_site_code
JOIN yl_product p ON p.product_code = r.product_code
WHERE r.adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND p.is_delete = 0;
```

## 现货批次 + 在途 + 计划（明细层）

```sql
WITH snap AS (
  SELECT
    (SELECT MAX(ds) FROM yl_spot_inventory) AS spot_ds,
    (SELECT MAX(ds) FROM yl_transit_inventory) AS transit_ds,
    (SELECT MAX(ds) FROM yl_sales_plan) AS plan_ds
)
SELECT
  w.site_name,
  p.product_name,
  sp.produce_date,
  sp.status,
  sp.store_num,
  sp.invetory_deduct_sum,
  COALESCE(tr.in_transit, 0) AS in_transit,
  pl.avg_plan_num
FROM yl_spot_inventory sp
JOIN snap ON sp.ds = snap.spot_ds
JOIN yl_warehouse w ON w.site_code = sp.site_code
JOIN yl_product p ON p.product_code = sp.product_code
LEFT JOIN (
  SELECT to_site_code, product_code, SUM(store_transit) AS in_transit
  FROM yl_transit_inventory ti, snap
  WHERE ti.ds = snap.transit_ds
  GROUP BY to_site_code, product_code
) tr ON tr.to_site_code = sp.site_code AND tr.product_code = sp.product_code
LEFT JOIN yl_sales_plan pl ON pl.site_code = sp.site_code
  AND pl.product_code = sp.product_code
  AND pl.ds = snap.plan_ds
WHERE w.site_type = 1;
```

## 按系列 / 品牌聚合

```sql
SELECT
  p.pro_series,
  p.brand,
  COUNT(DISTINCT r.product_code) AS sku_count,
  SUM(r.from_store_num_h) AS total_qualified,
  SUM(r.total_unship) AS total_unship,
  SUM(r.order_gap) AS sum_order_gap,
  AVG(CASE WHEN r.avg_plan_num > 0
           THEN r.from_store_num_h / r.avg_plan_num END) AS avg_dos_days
FROM yl_sales_warehouse_inventory_report r
JOIN yl_product p ON p.product_code = r.product_code
WHERE r.adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
GROUP BY p.pro_series, p.brand
ORDER BY sum_order_gap ASC;
```

## 用户指定仓名（模糊匹配）

```sql
SELECT site_code, site_name, site_type, remark
FROM yl_warehouse
WHERE site_name ILIKE '%广州%' OR site_desc ILIKE '%广州%';
```

## 用户指定品名

```sql
SELECT product_code, product_name, trade_name, brand, pro_series
FROM yl_product
WHERE is_delete = 0
  AND (product_name ILIKE '%珍护1段%' OR trade_name ILIKE '%珍护1段%');
```

## 常见陷阱

| 陷阱 | 处理 |
|------|------|
| `ds` 为 VARCHAR | 比较时用一致格式或 `::date` |
| 百分比字段 | `REPLACE(col, '%', '')::numeric` |
| 同一品多批次现货 | `SUM()` by site×product；批次分析保留 `produce_date` |
| 全国报表无 `site_code` | 分仓明细回 `sales_warehouse_inventory_report` |
| 礼盒列 | 常规分析忽略 `*_lh_*` |

## 自由探索建议

1. `list_tables` 过滤 `yl_`
2. 对不确定的表 `describe_table`
3. `SELECT * FROM … LIMIT 3` 看样例行
4. 读 `COMMENT ON COLUMN`（`get_schema`）确认口径
5. 再写聚合 SQL；reference 片段仅作起点
