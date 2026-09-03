# 定价与金额分析

> **PostgreSQL**：JSON 用 `::jsonb` + `jsonb_array_elements`；正则用 `~`；勿用 `JSON_TABLE` / `REGEXP` / `JSON_KEYS`。

## 指标定义

| 指标 | 数据源 |
|------|--------|
| 行项目金额 | `services[].amount`, `one_off_fee`, `annual_fee`, `recurring_fee` |
| 首单合计 | `first_total_invoice[].total` / `price` |
| 目录标准价 | `service_and_fee_au_incorp.hubspot_price`, `standard_pricing` |
| 覆盖定价 | `pricing_overrides`（对象，按路径对照 Skill §proposalState） |

JSON 中金额常为 **字符串**，分析时用 `CAST(... AS numeric(18,2))` 并过滤非数字。若 `amount` 为空，可改查 `one_off_fee` / `recurring_fee` / `annual_fee`。

## 行项目金额分布（按 SKU）

```sql
SELECT
  svc_elem->>'sku' AS sku,
  COUNT(*) AS n,
  MIN(CAST(svc_elem->>'amount' AS numeric(18,2))) AS min_amount,
  MAX(CAST(svc_elem->>'amount' AS numeric(18,2))) AS max_amount,
  AVG(CAST(svc_elem->>'amount' AS numeric(18,2))) AS avg_amount
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(st.state::jsonb->'business_case_services'->'business_cases', '[]'::jsonb)
) AS bc(bc_elem)
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(bc_elem->'services', '[]'::jsonb)
) AS svc(svc_elem)
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_au_advisory', 'incorp_au_audit')
  AND cs.created_at >= NOW() - INTERVAL '90 days'
  AND svc_elem->>'amount' ~ '^[0-9]+(\.[0-9]+)?$'
GROUP BY svc_elem->>'sku'
HAVING COUNT(*) >= 5
ORDER BY n DESC
LIMIT 100;
```

## 首单发票总额分布

```sql
SELECT
  inv_elem->>'currency' AS currency,
  COUNT(*) AS lines,
  AVG(CAST(inv_elem->>'total' AS numeric(18,2))) AS avg_total,
  MIN(CAST(inv_elem->>'total' AS numeric(18,2))) AS min_total,
  MAX(CAST(inv_elem->>'total' AS numeric(18,2))) AS max_total
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(st.state::jsonb->'first_total_invoice', '[]'::jsonb)
) AS inv(inv_elem)
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '90 days'
  AND inv_elem->>'total' ~ '^[0-9]+(\.[0-9]+)?$'
GROUP BY inv_elem->>'currency'
LIMIT 200;
```

## 报价金额 vs 目录价（抽样核对）

```sql
SELECT
  svc_elem->>'sku' AS sku,
  CAST(svc_elem->>'amount' AS numeric(18,2)) AS quoted_amount,
  cat.hubspot_price AS catalog_price,
  cs.id AS session_id
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(st.state::jsonb->'business_case_services'->'business_cases', '[]'::jsonb)
) AS bc(bc_elem)
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(bc_elem->'services', '[]'::jsonb)
) AS svc(svc_elem)
JOIN service_and_fee_au_incorp cat ON cat.sku = svc_elem->>'sku' AND cat.is_active IS TRUE
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '30 days'
  AND svc_elem->>'amount' ~ '^[0-9]+(\.[0-9]+)?$'
LIMIT 500;
```

在应用层或二次查询中统计：报价高于/低于目录价的占比（SQL 中可用 `quoted_amount - catalog_price`）。

## 有 pricing_overrides 的会话占比

```sql
SELECT
  COUNT(*) FILTER (
    WHERE jsonb_typeof(st.state::jsonb->'pricing_overrides') = 'object'
      AND st.state::jsonb->'pricing_overrides' <> '{}'::jsonb
  ) AS with_overrides,
  COUNT(*) AS total
FROM chat_states st
JOIN chat_sessions cs ON cs.id = st.session_id
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '60 days'
LIMIT 2000;
```

## 注意

- 动态定价建议 = **推断**，需写明样本量与时间段
- 勿在报告中罗列单笔客户报价明细，用区间与占比
- `deal_info.amount` 为 varchar，deal 级金额见 [deal-analytics.md](deal-analytics.md)
