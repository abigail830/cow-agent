# 需求、计划与履约偏离

## 原则

- **销售计划是需求输入**：补货决策的上游；计划与实绩偏离揭示需求突变或推式滞后。
- **三维对比**：计划（该卖多少）→ 订单/销量（客户要多少）→ 出库（实际发多少）；三者不一致处即问题点。
- **未发订单是履约瓶颈**：高销量 + 低出库 + 高未发 = 缺货压制履约，而非需求不足。

## 计划 vs 销量 vs 出库（单仓）

```sql
SELECT
  s.adjust_date,
  s.from_site_name,
  s.product_name,
  s.plan_num,
  s.sell_num,
  s.out_put_num,
  s.total_unship,
  s.sell_completion_rate,
  s.order_completion_rate,
  s.out_put_area,
  s.out_put_ec,
  s.avg_plan_num,
  s.next_plan_num,
  s.next_avg_plan_num
FROM yl_sales_warehouse_inventory_report s
WHERE s.adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND s.from_site_code = 'MOCK_WH_S03'  -- 按用户指定仓替换
ORDER BY s.product_code;
```

## 计划达成排名（全国品项）

```sql
SELECT
  product_name,
  plan_num,
  sell_num,
  out_put_num,
  total_unship,
  sell_completion_rate,
  order_completion_rate,
  CASE WHEN plan_num > 0 THEN sell_num / plan_num END AS sell_achievement_ratio
FROM yl_national_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_national_sales_warehouse_inventory_report)
ORDER BY sell_achievement_ratio ASC NULLS LAST;
```

## 推式分货滞后信号（销 > 出，且未发堆积）

```sql
SELECT
  from_site_name,
  product_name,
  sell_num,
  out_put_num,
  sell_num - out_put_num AS sell_output_gap,
  total_unship,
  ship_gap,
  from_stock_rate_before
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND sell_num > out_put_num
  AND total_unship > 0
ORDER BY total_unship DESC;
```

## 推式过量信号（低完成率 + 高现货）

```sql
SELECT
  from_site_name,
  product_name,
  plan_num,
  out_put_num,
  from_store_num_h,
  sell_completion_rate,
  ship_gap
FROM yl_sales_warehouse_inventory_report
WHERE adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND REPLACE(sell_completion_rate, '%', '')::numeric < 70
  AND from_store_num_h > COALESCE(avg_plan_num, 0) * 30
ORDER BY from_store_num_h DESC;
```

## 跨月计划趋势（需求输入变化）

```sql
SELECT
  plan_year,
  plan_month,
  site_name,
  product_name,
  plan_num,
  avg_plan_num,
  next_plan_num,
  next_avg_plan_num,
  remark
FROM yl_sales_plan
WHERE product_code = 'MOCK_YLP001'
  AND site_code = 'MOCK_WH_S03'
ORDER BY plan_year, plan_month;
```

## 实际销量表（月度归档）

```sql
SELECT
  ds,
  site_name,
  product_name,
  sell_num,
  out_put_num,
  unshipped_orders,
  available_quantity,
  sell_num_avg,
  remark
FROM yl_actual_sales
WHERE sell_year = 2026 AND sell_month = 5
ORDER BY unshipped_orders DESC NULLS LAST;
```

## 解读提示

- `sell_num >> plan_num`：需求爆发，推式计划跟不上——拉式补货信号
- `out_put_num << sell_num`：有单无货
- `from_stock_rate_before` 高但 `sell_completion_rate` 低：货在错误的地方
- 渠道拆分：`out_put_ec / NULLIF(out_put_num, 0)` 看电商占比是否解释区域爆发
