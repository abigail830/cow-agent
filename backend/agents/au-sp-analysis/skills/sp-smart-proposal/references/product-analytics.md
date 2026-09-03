# 产品、SKU 与组合分析

> **PostgreSQL**：`state` 用 `::jsonb` + `jsonb_array_elements` 展开；勿使用 MySQL `JSON_TABLE`。

## 指标定义

| 指标 | 定义 |
|------|------|
| SKU 出现次数 | 从 `chat_states.state` 展开 `business_cases[].services[]`，按 `sku` 计数 |
| 套餐/方案 | `business_cases[].name` 分布 |
| Cross-sell 共现 | 同一会话内 SKU 对 (A,B) 共现次数 |
| 目录对照 | `service_and_fee_au_incorp` 补充 `service_name`、`is_package` |

默认统计**最新态** `chat_states`，时间过滤在 `chat_sessions` 上。

## Top SKU（出现次数）

```sql
SELECT
  svc_elem->>'sku' AS sku,
  svc_elem->>'service_name' AS service_name,
  COUNT(*) AS proposal_lines,
  COUNT(DISTINCT cs.id) AS proposal_count
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
  AND cs.created_at >= NOW() - INTERVAL '60 days'
  AND svc_elem->>'sku' IS NOT NULL AND svc_elem->>'sku' <> ''
GROUP BY svc_elem->>'sku', svc_elem->>'service_name'
ORDER BY proposal_count DESC, proposal_lines DESC
LIMIT 100;
```

## 业务方案 / 套餐名分布

```sql
SELECT
  bc_elem->>'name' AS case_name,
  COUNT(DISTINCT cs.id) AS proposal_count
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(st.state::jsonb->'business_case_services'->'business_cases', '[]'::jsonb)
) AS bc(bc_elem)
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_au_advisory', 'incorp_au_audit')
  AND cs.created_at >= NOW() - INTERVAL '60 days'
GROUP BY bc_elem->>'name'
ORDER BY proposal_count DESC
LIMIT 100;
```

## SKU 共现（Cross-sell 信号）

先取每会话 SKU 集合，再自连接（示例：Top SKU 两两共现）：

```sql
WITH session_skus AS (
  SELECT DISTINCT
    cs.id AS session_id,
    svc_elem->>'sku' AS sku
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
    AND svc_elem->>'sku' IS NOT NULL AND svc_elem->>'sku' <> ''
)
SELECT
  a.sku AS sku_a,
  b.sku AS sku_b,
  COUNT(*) AS co_occurrence_sessions
FROM session_skus a
JOIN session_skus b
  ON a.session_id = b.session_id AND a.sku < b.sku
GROUP BY a.sku, b.sku
HAVING COUNT(*) >= 3
ORDER BY co_occurrence_sessions DESC
LIMIT 100;
```

## 对照产品目录（套餐标记）

```sql
SELECT
  cat.sku,
  cat.service_name,
  cat.is_package,
  cat.hubspot_price,
  usage_stats.proposal_count
FROM service_and_fee_au_incorp cat
LEFT JOIN (
  SELECT svc_elem->>'sku' AS sku, COUNT(DISTINCT cs.id) AS proposal_count
  FROM chat_sessions cs
  JOIN chat_states st ON st.session_id = cs.id
  CROSS JOIN LATERAL jsonb_array_elements(
    COALESCE(st.state::jsonb->'business_case_services'->'business_cases', '[]'::jsonb)
  ) AS bc(bc_elem)
  CROSS JOIN LATERAL jsonb_array_elements(
    COALESCE(bc_elem->'services', '[]'::jsonb)
  ) AS svc(svc_elem)
  WHERE NOT cs.is_template
    AND cs.created_at >= NOW() - INTERVAL '60 days'
  GROUP BY svc_elem->>'sku'
) AS usage_stats ON usage_stats.sku = cat.sku
WHERE cat.is_active IS TRUE
ORDER BY usage_stats.proposal_count DESC NULLS LAST
LIMIT 200;
```

## 注意

- `amount` / fee 字段在 JSON 中可能是字符串，定价专题见 [pricing-analytics.md](pricing-analytics.md)
- Cross-sell 结论写「常一起出现在同一份报价中」，避免因果表述
