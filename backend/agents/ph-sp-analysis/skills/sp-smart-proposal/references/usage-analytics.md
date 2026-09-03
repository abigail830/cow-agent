# 使用情况与漏斗分析

> **PostgreSQL**：时间用 `NOW() - INTERVAL 'N days'`；布尔计数用 `COUNT(*) FILTER`；勿用 `SUM(布尔表达式)`。

## 指标定义

| 指标 | 定义 |
|------|------|
| 新建 Proposal 数 | 时间窗内 `chat_sessions` 计数（`NOT is_template`） |
| 活跃用户数 | 时间窗内 `COUNT(DISTINCT user_id)` 或 `user_mail` |
| 互动深度 | 每会话 `chat_messages` 条数、用户消息占比 |
| 生成 Proposal | `session_state_version.is_proposal_generated IS TRUE` 的会话（去重 `session_id`） |
| 漏斗 | 新建 → 有消息 → 有非空 `business_case_services` → `is_proposal_generated` |

时间窗默认：`chat_sessions.created_at` 或 `last_activity_at >= NOW() - INTERVAL '30 days'`。

## 新建与活跃

```sql
SELECT
  COUNT(*) AS new_proposals,
  COUNT(DISTINCT cs.user_id) AS unique_users
FROM chat_sessions cs
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND cs.created_at >= NOW() - INTERVAL '30 days'
LIMIT 2000;
```

## 按日趋势

```sql
SELECT
  cs.created_at::date AS day,
  COUNT(*) AS proposals
FROM chat_sessions cs
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND cs.created_at >= NOW() - INTERVAL '90 days'
GROUP BY cs.created_at::date
ORDER BY day
LIMIT 2000;
```

## 消息深度（Top 会话）

```sql
SELECT
  cm.session_id,
  COUNT(*) AS message_count,
  COUNT(*) FILTER (WHERE cm.role = 'user') AS user_messages
FROM chat_messages cm
JOIN chat_sessions cs ON cs.id = cm.session_id
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND cs.created_at >= NOW() - INTERVAL '30 days'
GROUP BY cm.session_id
ORDER BY message_count DESC
LIMIT 50;
```

## 已生成 Proposal 的会话数

```sql
SELECT COUNT(DISTINCT ssv.session_id) AS generated_count
FROM session_state_version ssv
JOIN chat_sessions cs ON cs.id = ssv.session_id
WHERE NOT cs.is_template
  AND ssv.is_proposal_generated IS TRUE
  AND ssv.created_at >= NOW() - INTERVAL '30 days'
LIMIT 2000;
```

## 阶段分布（最新态）

```sql
SELECT
  st.state::jsonb->>'stage' AS stage,
  COUNT(*) AS cnt
FROM chat_states st
JOIN chat_sessions cs ON cs.id = st.session_id
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND cs.created_at >= NOW() - INTERVAL '30 days'
GROUP BY st.state::jsonb->>'stage'
ORDER BY cnt DESC
LIMIT 2000;
```

## 创建会话但未生成 Proposal（明细）

> 判断标准：`session_state_version` 中**从未**出现 `is_proposal_generated IS TRUE`。勿用 `users.role`；`chat_states` 须单独 JOIN。

```sql
SELECT
  cs.id AS session_id,
  cs.created_at,
  cs.last_activity_at,
  cs.status,
  cs.user_mail,
  st.state::jsonb->>'stage' AS current_stage,
  (SELECT COUNT(*) FROM chat_messages cm WHERE cm.session_id = cs.id) AS message_count,
  (SELECT COUNT(*) FROM chat_messages cm WHERE cm.session_id = cs.id AND cm.role = 'user') AS user_message_count
FROM chat_sessions cs
LEFT JOIN chat_states st ON st.session_id = cs.id
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND NOT EXISTS (
    SELECT 1
    FROM session_state_version ssv
    WHERE ssv.session_id = cs.id
      AND ssv.is_proposal_generated IS TRUE
  )
ORDER BY cs.created_at DESC
LIMIT 200;
```

## 同一用户多次创建但未完成（聚合）

```sql
SELECT
  cs.user_id,
  cs.user_mail,
  COUNT(*) AS incomplete_sessions,
  MIN(cs.created_at) AS first_created_at,
  MAX(cs.last_activity_at) AS last_activity_at
FROM chat_sessions cs
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND NOT EXISTS (
    SELECT 1
    FROM session_state_version ssv
    WHERE ssv.session_id = cs.id
      AND ssv.is_proposal_generated IS TRUE
  )
GROUP BY cs.user_id, cs.user_mail
HAVING COUNT(*) >= 2
ORDER BY incomplete_sessions DESC, last_activity_at DESC
LIMIT 100;
```

## 注意

- 用户去重优先 `user_id`；为空时用 `user_mail`
- 报告用「报价会话」「活跃同事」「完成生成」等业务词，不写表名
