# 库存新鲜度、大日期与结构

## 原则

- **奶粉新鲜度是硬约束**：长库龄/大日期与缺货一样需要预警；B 端拒收与临期风险会放大积压后果。
- **合格 ≠ 可售**：待检库存不能计入可发；分析缺口时拆分 `from_store_num_d` / `from_store_num_h`。
- **批次级下钻**：报表给汇总大日期；要追生产日期分布时用 `yl_spot_inventory`。

## 大日期监控清单

```sql
SELECT
  b.site_name,
  b.site_type,
  b.product_name,
  b.big_date_num,
  b.remark
FROM yl_big_date_inventory b
WHERE b.big_date_num > 0
ORDER BY b.big_date_num DESC;
```

## 报表层大日期（全国 / 分仓）

```sql
SELECT
  product_name,
  xs_big_date,
  xs_big_date_num,
  jd_big_date,
  jd_big_date_num,
  from_store_num_h,
  avg_plan_num,
  CASE WHEN avg_plan_num > 0 THEN from_store_num_h / avg_plan_num END AS dos_days
FROM yl_national_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_national_sales_warehouse_inventory_report)
  AND (COALESCE(xs_big_date_num, 0) > 0 OR COALESCE(jd_big_date_num, 0) > 0);
```

```sql
-- 分仓
SELECT from_site_name, product_name, big_date, big_date_num,
       from_store_num_h, avg_plan_num, sell_completion_rate
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND COALESCE(big_date_num, 0) > 0
ORDER BY big_date_num DESC;
```

## 库龄（批次现货）

```sql
SELECT
  si.site_name,
  si.product_name,
  si.produce_date,
  si.ds::date - si.produce_date AS age_days,
  si.status,
  si.store_num,
  si.invetory_deduct_sum
FROM yl_spot_inventory si
WHERE si.ds = (SELECT MAX(ds) FROM yl_spot_inventory)
  AND si.site_type = 1
  AND si.status = '合格'
ORDER BY age_days DESC;
```

## 待检 vs 合格结构（分仓）

```sql
SELECT
  from_site_name,
  product_name,
  from_store_num_d AS pending_qc,
  from_store_num_h AS qualified,
  CASE WHEN (from_store_num_d + from_store_num_h) > 0
       THEN from_store_num_d / (from_store_num_d + from_store_num_h) END AS pending_ratio
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND (COALESCE(from_store_num_d, 0) > 0 OR COALESCE(from_store_num_h, 0) > 0)
ORDER BY pending_ratio DESC NULLS LAST;
```

## 大日期消化周期估算（原则）

```
预计消化月数 ≈ big_date_num / NULLIF(avg_plan_num * 30, 0)
```

在 SQL 或解读中计算；`avg_plan_num` 为 0 或极小时标注「需求极低，过期风险需人工评估」。

## 解读提示

- 大日期 + 低 DOS 以外的低周转：典型滞销（如成人奶粉区域市场）
- 大日期 + 高未发：优先发新批次，避免旧批次继续积压
- 基地 `days_list` / `months_list` 为文本聚合字段——展示用，统计优先用数值列
