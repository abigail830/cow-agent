# Deal、CRM 与 Pipeline 分析

> **PostgreSQL**：布尔计数用 `COUNT(*) FILTER`；JSON 用 `jsonb_array_elements`；勿用 `SUM(布尔)` / `JSON_TABLE`。

## 背景

- 部分 Proposal 先在 **HubSpot** 建 deal，再在工具中继续（`deal_info.deal_id` 非空）
- 部分无 CRM，仅在 `deal_info` 记录本地 pipeline / 来源层级（`deal_source_layer_*`）

关联：`deal_info.session_id = chat_sessions.id`（或 `proposal_id` 与业务主键，以 `postgres_describe_table` 查询结果为准）。

## 有/无 CRM deal 占比

```sql
SELECT
  COUNT(*) FILTER (WHERE di.deal_id IS NOT NULL AND di.deal_id <> '') AS with_hubspot_deal,
  COUNT(*) FILTER (WHERE di.deal_id IS NULL OR di.deal_id = '') AS without_hubspot_deal,
  COUNT(*) AS total_deal_rows
FROM deal_info di
JOIN chat_sessions cs ON cs.id = di.session_id
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '90 days'
LIMIT 2000;
```

## Pipeline 分布

```sql
SELECT
  di.pipeline_name,
  COUNT(*) AS cnt
FROM deal_info di
JOIN chat_sessions cs ON cs.id = di.session_id
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '90 days'
  AND di.pipeline_name IS NOT NULL AND di.pipeline_name <> ''
GROUP BY di.pipeline_name
ORDER BY cnt DESC
LIMIT 100;
```

## 来源层级（Layer 1）

```sql
SELECT
  di.deal_source_layer_1,
  di.deal_source_layer_2,
  COUNT(*) AS cnt
FROM deal_info di
JOIN chat_sessions cs ON cs.id = di.session_id
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '90 days'
GROUP BY di.deal_source_layer_1, di.deal_source_layer_2
ORDER BY cnt DESC
LIMIT 100;
```

## 有 deal 记录的 Proposal 完成率

```sql
SELECT
  COUNT(DISTINCT di.session_id) AS sessions_with_deal_info,
  COUNT(DISTINCT CASE WHEN ssv.is_proposal_generated IS TRUE THEN di.session_id END) AS generated_with_deal
FROM deal_info di
JOIN chat_sessions cs ON cs.id = di.session_id
LEFT JOIN session_state_version ssv
  ON ssv.session_id = di.session_id AND ssv.is_proposal_generated IS TRUE
WHERE NOT cs.is_template
  AND cs.created_at >= NOW() - INTERVAL '90 days'
LIMIT 2000;
```

## line_items JSON（HubSpot 行项目）

`deal_info.line_items` 为 JSON 数组；结构与 HubSpot 同步字段相关。分析前：

1. `postgres_describe_table` 确认列类型
2. 小样本 `SELECT line_items FROM deal_info WHERE line_items IS NOT NULL LIMIT 5`
3. 用 `jsonb_array_elements` 展开（键名以样本为准）：

```sql
SELECT
  di.session_id,
  li_elem->>'name' AS item_name,
  li_elem->>'sku' AS sku,
  li_elem->>'price' AS price
FROM deal_info di
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(di.line_items::jsonb, '[]'::jsonb)
) AS li(li_elem)
WHERE di.line_items IS NOT NULL
LIMIT 200;
```

## 注意

- 正文用「CRM 商机」「pipeline」「来源渠道」，不写 `deal_source_layer_1`
- `contact_email` / `company_name` 仅用于内部分组，默认不出现在用户报告
- 无 `deal_info` 行的会话 = 未登记 pipeline，与「无 HubSpot deal」区分说明
