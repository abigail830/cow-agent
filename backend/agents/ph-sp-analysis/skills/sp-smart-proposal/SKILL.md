---
name: sp-smart-proposal
description: >-
  Analyzes Smart Proposal PostgreSQL data and proposalState JSON: session usage, funnel,
  SKU/package mix, pricing bands, cross-sell patterns, and deal/CRM attribution.
  For product teams and management. Use when users ask about Smart Proposal usage,
  active users, services in proposals, package combinations, pricing ranges, HubSpot deals,
  pipeline sources, diff proposals type and conversation details. Read-only PostgreSQL; reply language
  follows the user's question language.
---

# Smart Proposal 分析

## 与 Agent 系统 Prompt 的分工

| 层 | 位置 | 内容 |
|----|------|------|
| **角色与对外表述** | `agents/ph-sp-analysis/system_prompt.md` | 读者画像、业务语言、PII、禁止泄露实现细节 |
| **运行时** | `agents/ph-sp-analysis/profile.yaml` | 只读 MCP、**必须加载本 Skill** |
| **数据内核（对内）** | 本文 §数据模型 + §proposalState | 表 JOIN、JSON 路径、选用规则——**仅供查数** |
| **专题 SQL（对内）** | `references/*.md` | PostgreSQL 语法模板；按意图按需 `read_skill_resource` |

触发本 Skill 后，查数步骤以本文与 references 为准；**回复正文遵守 system prompt 的「对外沟通铁律」**。

## 数据模型（PostgreSQL 表关系）

```
users ──< chat_sessions ──┬── chat_states (1:1 最新 state JSON)
                          ├── chat_messages
                          ├── session_state_version (每动作快照)
                          └── deal_info (0:1 CRM / 本地 pipeline)

service_and_fee_ph_incorp ── catalog（SKU / 标准定价，对照 state 与 deal）
```

| 表 | 粒度 | 分析用途 |
|----|------|----------|
| **users** | 用户 | `id`, `email`, `name`；去重活跃用户数 |
| **chat_sessions** | 一次 Proposal 流程 | `id`(UUID), `proposal_type`, `status`, `is_template`, `created_at`, `last_activity_at`, `user_id`, `user_mail` |
| **chat_messages** | 对话消息 | `session_id`, `role`, `content`, `created_at`, `feedback`, `rate`；互动深度 |
| **chat_states** | 会话最新报价态 | `session_id`, `proposal_type`, **`state`** JSON = proposalState |
| **session_state_version** | 状态快照 | `session_id`, **`state_data`** JSON, `revision_no`, `is_proposal_generated`, `created_at`；漏斗/里程碑 |
| **deal_info** | Deal / Pipeline | `proposal_id`, `session_id`, `deal_id`, `deal_name`, `amount`, `pipeline_name`, `deal_source_layer_*`, `line_items` JSON |
| **service_and_fee_ph_incorp** | 产品目录 | `sku`, `service_name`, `is_package`, `hubspot_price`, `standard_pricing`, `is_active`, `proposal_types` |

### 主键与 JOIN

| 关联 | ON 条件 |
|------|---------|
| session → 用户 | `chat_sessions.user_id = users.id`（或 `user_mail` 与 `users.email`） |
| session → 最新 state | `chat_states.session_id = chat_sessions.id` |
| session → 消息 | `chat_messages.session_id = chat_sessions.id` |
| session → 快照 | `session_state_version.session_id = chat_sessions.id` |
| session → deal | `deal_info.session_id = chat_sessions.id` |
| SKU 对照目录 | `JSON` 中 `sku` ↔ `service_and_fee_ph_incorp.sku` |

### 何时用哪张态表

| 问题类型 | 数据源 |
|----------|--------|
| 当前选了哪些服务/价格、客户档案、阶段 | **`chat_states.state`**（最新） |
| 何时生成 Proposal、阶段变化、历史 revision | **`session_state_version`**（按 `created_at` / `revision_no`） |
| 有无 HubSpot deal、pipeline、来源层级 | **`deal_info`** |
| 标准价 / 套餐定义 | **`service_and_fee_ph_incorp`** |

**时间轴默认**：`chat_sessions.created_at`（新建趋势）或 `last_activity_at`（活跃）；快照事件用 `session_state_version.created_at`。

## proposalState 要点（`chat_states.state` / `session_state_version.state_data`）

分析常用字段：

| 路径 | 含义 |
|------|------|
| `proposal_type` | 报价类型；PH 常为 'incorp_ph_general', 'incorp_ph_recruitment' |
| `stage` | 当前流程阶段（字符串，可空） |
| `stage_history` | 阶段变更历史（数组） |
| `client_profile` | 客户档案：`company_name`, `contact_name`, `contact_email`, `company_location` 等 |
| `business_case_services` | **核心服务表**：`currency`, `business_cases[]` |
| `business_case_services.business_cases[].name` | 业务方案/套餐名 |
| `business_case_services.business_cases[].services[]` | 行项目：`sku`, `service_name`, `amount`, `one_off_fee`, `recurring_fee`, `annual_fee`, … |
| `pricing_overrides` | 相对默认定价的覆盖 |
| `pricing_defaults` | 默认定价引用 |
| `first_total_invoice[]` | 首单发票行：`service_name`, `price`, `total`, `currency` |
| `deal_name` | 报价内 deal 名称（可能与 `deal_info` 交叉验证） |
| `missing_required` / `missing_optional` | 完整性信号 |

### PostgreSQL JSON 展开范式（SKU 列表）

先用 **`postgres_describe_table` / `postgres_get_schema`** 确认列名与 JSON 类型，再复用 `references/*.md` 中模板（均为 PostgreSQL 语法）。典型：从最新态展开所有 SKU：

```sql
SELECT
  cs.id AS session_id,
  svc_elem->>'sku' AS sku,
  svc_elem->>'service_name' AS service_name
FROM chat_sessions cs
JOIN chat_states st ON st.session_id = cs.id
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(st.state::jsonb->'business_case_services'->'business_cases', '[]'::jsonb)
) AS bc(bc_elem)
CROSS JOIN LATERAL jsonb_array_elements(
  COALESCE(bc_elem->'services', '[]'::jsonb)
) AS svc(svc_elem)
WHERE NOT cs.is_template
  AND cs.proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')
  AND LOWER(cs.user_mail) NOT IN (
    'huiman.cao@incorp.asia', 'wei.wang@incorp.asia', 'ping.qian@incorp.asia',
    'zhenxuan.wang@incorp.asia', 'ge.zeng@incorp.asia', 'ken.yu@ascentium.com',
    'wangsha.tse@ascentium.com', 'maggie.luo@ascentium.com',
    'william.cheung@ascentium.com', 'william.cheung@incorp.asia',
    'dl-fabric@incorp.asia'
  )
  AND cs.created_at >= NOW() - INTERVAL '30 days'
LIMIT 2000;
```

阶段/是否已生成：优先 `session_state_version.is_proposal_generated` 与 `state_data` 内 `stage`。

## 可视化（按需 suggest_visualization）

SQL 成功后平台**只缓存**，不自动出图。总结或解读时若图表能显著帮助理解，再调用 `suggest_visualization`（`intent`：`auto` / `trend` / `matrix` / `ranking` / `detail` / `none`）。顺序跟随 ReAct 流（说明 → 查数 → 解读 → 按需出图），勿暴露 tool 名或 JSON。

- 多步：说明 → `postgres_query_data` → 文字解读 →（需要时）`suggest_visualization` → 下一查询 → 总结
- 同轮多查询：先 `list_sql_results`，用 `source_call_id` 指定要可视化的那次结果
- 矩阵三列 + `matrix`；热力图橙色系；多系列用平台配色

## 执行顺序

1. **确定回复语言**（与 system prompt 一致）
2. **postgres MCP**：用 **`postgres_list_tables` / `postgres_describe_table` / `postgres_get_schema`** 确认结构，再用 **`postgres_query_data`** 执行业务 SELECT
3. **`postgres_query_data` 必须带非空 `sql`**；平台会注入/校验 `LIMIT`（`hooks.sql_validator`）
4. 按 §意图路由 用 `read_skill_resource` 加载对应 reference 中的 **PostgreSQL** SQL 模板
5. **禁止**使用 MySQL 语法（`JSON_TABLE`、`REGEXP`、`JSON_KEYS`、`SUM(布尔)`）
6. **禁止 `run_skill_script`**

## 意图路由

| 用户意图 | read_skill_resource |
|----------|---------------------|
| 活跃、新建、留存、消息深度、漏斗 | [usage-analytics.md](references/usage-analytics.md) |
| SKU、套餐、服务组合、cross-sell 共现 | [product-analytics.md](references/product-analytics.md) |
| 价格带、override、首单金额、目录对比 | [pricing-analytics.md](references/pricing-analytics.md) |
| HubSpot deal、pipeline、来源层级 | [deal-analytics.md](references/deal-analytics.md) |
| 综合周报 | 按需组合上表 2～3 份 |
| 仅解释 state 某字段 | 本文 §proposalState，无需 reference |

## 过滤惯例

- NOT chat_sessions.is_template
- `proposal_type IN ('incorp_ph_general', 'incorp_ph_recruitment')` 除非用户指定其他类型
- **内部用户（默认必排）**：除非用户明确要求包含内部账号，**所有**活跃、漏斗、SKU、定价、deal 等分析 SQL 都必须排除下列邮箱（`users.email` 或 `chat_sessions.user_mail`，用 `LOWER()` 做大小写不敏感匹配）：

  | 邮箱 |
  |------|
  | huiman.cao@incorp.asia |
  | wei.wang@incorp.asia |
  | ping.qian@incorp.asia |
  | zhenxuan.wang@incorp.asia |
  | ge.zeng@incorp.asia |
  | ken.yu@ascentium.com |
  | wangsha.tse@ascentium.com |
  | maggie.luo@ascentium.com |
  | william.cheung@ascentium.com |
  | william.cheung@incorp.asia |
  | dl-fabric@incorp.asia |

  典型写法（JOIN `users u` 后）：

  ```sql
  AND LOWER(COALESCE(u.email, cs.user_mail)) NOT IN (
    'huiman.cao@incorp.asia',
    'wei.wang@incorp.asia',
    'ping.qian@incorp.asia',
    'zhenxuan.wang@incorp.asia',
    'ge.zeng@incorp.asia',
    'ken.yu@ascentium.com',
    'wangsha.tse@ascentium.com',
    'maggie.luo@ascentium.com',
    'william.cheung@ascentium.com',
    'william.cheung@incorp.asia',
    'dl-fabric@incorp.asia'
  )
  ```

  无 `users` JOIN 时，对 `cs.user_mail` 单独应用同一 `NOT IN`。报告「分析口径」中默认写一句「已排除内部用户」；若用户要求含内部数据，须在口径中显式说明。
- 目录对照：`service_and_fee_ph_incorp.is_active IS TRUE`
- 所有分析 SQL 带 `LIMIT`（平台上限 2000 行）

## 易错写法

- 空参数调用 `postgres_query_data`
- 未用 `postgres_describe_table` 就猜列名（如 `user_email` vs `user_mail`）
- 直接复制 MySQL 写法（`JSON_TABLE`、`REGEXP`、`DATE_SUB`、`is_template = 0` 等）
- 把 `users.role` 当成用户身份列（**`users` 无 `role`**；角色在 `chat_messages.role`）
- 把 `chat_states` 写成 `cs.chat_states`（须 `JOIN chat_states st ON st.session_id = cs.id`）
- 在 `session_state_version` 上读 `state`（应为 **`state_data`**）
- 用 `session_state_version` 做「当前服务清单」截面（应使用 `chat_states`）
- 在正文向用户展示 `client_profile.contact_email` 等 PII

## 输出格式（用户可见）

结构对齐 system prompt；下列为内容要点，**标题与正文均勿使用表名/列名/SQL/MCP/Skill**。

### 摘要（30 秒版）
- 时间范围、Proposal 量级、2～3 条最重要结论

### 使用情况 / 产品与组合 / 定价 / 商机
- 各块用业务语言 + 关键数字；cross-sell 与定价建议标明推断依据

### 分析口径（可选，1–3 句白话）
- 例：「统计过去 30 天recruitment模板的报价会话」「已排除内部用户」「按最新报价内容统计服务出现次数」

### 建议的下一步
- 产品、培训、定价复盘、销售跟进等可执行动作

### 对内 ↔ 对外 用语对照

| 对内（仅思考/查数） | 对用户说 |
|---------------------|----------|
| `chat_sessions` | 报价会话 / Proposal 流程 |
| `chat_states.state` | 当前报价内容 / 最新方案状态 |
| `business_case_services` | 方案中的服务与套餐 |
| `session_state_version` | 报价过程中的历史节点 |
| `service_and_fee_ph_incorp` | 标准服务目录与标价 |
| `deal_info` | CRM 商机或 pipeline 登记信息 |
| `jsonb_array_elements` 展开 SKU | 统计各服务在报价中的出现情况 |

## 禁止

- 不要 `UPDATE`/`INSERT`/`DELETE` 业务表
- 不要批量粘贴 `chat_messages.content` 或客户 PII
- 不要在无 Skill reference 时臆造复杂 JSON 路径（先对照本文与 `docs/schema.py` 思路）
