# yl-worker2 本体驱动智能补调 · 建设方案

> 版本：**v0.5** | 日期：2026-07-07  
> 范围：仅规划 yl-worker2，**不改动 yl-worker1**，不实施代码  
> 依据：`t-box-core.png`、OIP 业务纪要、mock case 脚本、`opt.md`、YL PG schema

---

## 0. 版本修订记录

| 版本 | 核心变化 |
|------|----------|
| v0.1–v0.3 | 见历史（Neo4j、多表、场景 Skill 等，已废弃） |
| v0.4 | 代码迁 `app/yl_worker2/`；Webhook + 新 Session；废弃 replenishment_plan/item |
| v0.3.1 | 确认下发同步写 `mock_branch_replenishment_order` |
| **v0.5** | **本体 = Tool + description（无独立 rules MD/YAML）**；**Tool 命名对齐 T-Box 语义**；**agents/ 仅配置文件** |

---

## 1. 定位与架构

yl-worker2 是补调经理的**决策副驾**：通过**本体 Tool** 读写在 PG 里的业务状态 → Agent 推理编排 → 对话确认 → 写入调拨底表。

```
┌─────────────────────────────────────────────────────────────┐
│  T-Box（对外契约）                                            │
│  system_prompt.md + 各 Tool 的 name / description            │
│  （给人看、给 AI 路由；规则写在 description 里）               │
├─────────────────────────────────────────────────────────────┤
│  A-Box（实例层）                                              │
│  yl_* 原表 + mock_branch_replenishment_order                 │
├─────────────────────────────────────────────────────────────┤
│  语义运行时（内部实现，可随时重构）                              │
│  app/yl_worker2/：OBDA、规则求值、写库逻辑                     │
├─────────────────────────────────────────────────────────────┤
│  Agent（推理层）                                              │
│  读 Tool description → 选 Tool → 组合结果 → 与人对话          │
└─────────────────────────────────────────────────────────────┘
```

**与 yl-worker1**：完全独立，零耦合。

**核心设计决策（v0.5）**：

- **不另建 rules 的 MD / YAML**——业务看不懂 YAML，MD 又与代码易漂移；**Tool 的 description 即规则说明书**，给人也给 AI。
- **单一本体 Skill**——`yl-oip-ontology-core` 教实体/关系/规则在模型中的位置/推理规约；规则条文在 Tool description。
- **Tool 内部实现可换**（硬编码、查表、DMN…）不影响对外契约，只要行为与 description 一致。

---

## 2. 调拨单底表

（§2.1–2.4 与 v0.4 相同，略述要点）

| 层 | 表 | 谁写 |
|----|-----|------|
| OIP | `yl_forward_transfer` / `yl_lateral_transfer` | worker2 |
| 履约 UI | `mock_branch_replenishment_order` | worker2 **同步写**（Dashboard 唯一数据源） |

| 本体动作 | OIP | 履约 |
|----------|-----|------|
| `save_as_draft` | INSERT，`push_num=NULL` | 可选 `status=草稿` |
| `activate_and_push` | UPDATE `push_num/...` | INSERT/UPDATE `status=生效` |
| `update_qty` | UPDATE `trans_num` | UPDATE `transfer_qty` |
| `cancel_order` | 作废标记 | `status=作废` |

不使用 `yl2_allocation_order`、`replenishment_plan`、`replenishment_item`。

---

## 3. 数据与审计

**最小数据**：`yl_*` 只读为主 + 调拨双写；`mock_branch_replenishment_order`；可选 VIEW `v_sku_site_inventory_cube`。

**不建**：event 表、impact 表、审计表、rule_override（MVP）。审计靠 `chats` / `messages`。

**影响分析**：规则 + 最新 A-Box + 查待确认调拨行 → Agent 现场推理，不预存 impact。

---

## 4. 触发方式

### 4.1 人触发（Script 1）

经理：「开始今日巡检」「帮看今天 Dashboard 异常」→ Agent 按 Tool description 自主选 Tool 推理。

### 4.2 外系统触发（Script 2，方式 B）

```
外系统 UPDATE yl_* → POST /api/v1/agents/yl-worker2/triggers
  → 新 Chat Session → 渲染首条消息 → run_message → Agent 调 Tool
```

业界参考：Event-driven agents、Google ADK Ambient Agents（每事件一新 Session）、本仓库 `scheduled-agent-tasks-design.md`。

Webhook payload 约定写在 `app/yl_worker2/triggers/schemas.py` 的 docstring / OpenAPI，**不放 agents 下 MD 文件**。

---

## 5. 目录结构

```
backend/agents/yl-worker2/          # ★ 配置 + 单一本体 Skill
├── profile.yaml
├── system_prompt.md                # 角色、人在环、Script 触发语境
├── mcp_servers.yaml
└── skills/yl-oip-ontology-core/SKILL.md   # 实体/关系/规则角色/推理规约

backend/app/yl_worker2/             # ★ 全部代码
├── obda/                           # 语义 → yl_* 列（内部）
├── runtime/                        # 引擎、规则求值（内部，不暴露给 Agent）
├── tools/
│   ├── metrics.py                  # SupplyChainMetrics 类 Tool
│   ├── allocation.py               # AllocationOrder 类 Tool
│   └── inventory.py                # InventorySnapshot 查询 Tool
└── triggers/
    ├── schemas.py
    └── handler.py

backend/app/api/routes/
└── yl_worker2_triggers.py
```

**注册**：`tool_registry.py` 从 `app.yl_worker2.tools` 导入；仅 yl-worker2 的 `profile.yaml` 启用这些 Tool。

---

## 6. 规则与本体：Tool 即契约

### 6.1 为什么不搞 MD / YAML

| 方案 | 问题 |
|------|------|
| MD + Python 双维护 | 易漂移 |
| YAML 决策表 | 业务同样难改难懂 |
| **Tool + description** | 业务/FDE 改规则 = 改 Tool 实现 + 同步改 description；**对外只有一个入口**，AI 和人看同一份说明 |

### 6.2 分工

| 角色 | 职责 |
|------|------|
| **Tool description** | 规则语义、适用条件、输入输出、业务口径（**SSOT for 可执行契约**） |
| **Tool 实现** | 确定性求值 + OBDA 读写在 PG；**内部可重构** |
| **Skill `yl-oip-ontology-core`** | 实体/关系/规则角色/推理规约；**不含**阈值与 Mock |
| **system_prompt** | 角色、人在环、Script1/2 **触发语境**（非逐步 Tool 清单） |
| **Agent** | load Skill 理解模型 → 读 Tool description 选 Tool → 组合返回 → 对话确认 |

### 6.3 description 写法要求（示例见 §8）

每个 Tool 的 `description` 须包含：

1. **本体归属**（对应 t-box-core 哪个类/动作）
2. **业务含义**（白话）
3. **规则摘要**（判定条件、公式、阈值——写清，供 AI 解释时引用）
4. **何时调用**（Agent 路由提示）
5. **返回字段说明**（含 `applied_rule` 等，便于 Agent 引用）

规则变更流程：业务确认 → FDE 改 Tool 实现 + 更新 description → PR → Mock case 契约测试通过。

---

## 7. YL PG 映射（简）

| 本体对象 | 物理表 |
|----------|--------|
| `ProductSKU` | `yl_product` |
| `Warehouse` | `yl_warehouse` |
| `InventorySnapshot` | `yl_sales_warehouse_inventory_report` 等 |
| `AllocationOrder`（正向/横向） | `yl_forward_transfer` / `yl_lateral_transfer` |
| `ReplenishmentOrder` | `mock_branch_replenishment_order` |

可选 VIEW：`v_sku_site_inventory_cube`（SKU×仓预聚合）。

---

## 8. 本体 Tool 清单（命名对齐 T-Box）

命名原则：

- **对齐 t-box-core 类名与方法名**，不用 `yl2_` 前缀
- **动词开头**，一眼看懂干什么
- 按四类模块分组，与图中 **Objective Assets / SupplyChainMetrics / Rules（内嵌于 Metric Tool）/ Transactions** 一致

### 8.1 SupplyChainMetrics（指标与规则求值）

规则类计算放在 Metric Tool 内；description 写清 StandardPolicyMatrix 等规则。

| Tool 名 | 本体映射 | 作用 |
|---------|----------|------|
| `get_order_gap` | `SupplyChainMetrics.get_order_gap(Warehouse, ProductSKU)` | 发货缺口 = 现货 + 在途 − 未发订单 |
| `get_ship_gap` | `SupplyChainMetrics.get_ship_gap(...)` | 发货缺口（仅现货 − 未发） |
| `get_order_progress` | `SupplyChainMetrics.get_order_progress(...)` | 订单完成率 |
| `get_current_stock_rate` | `SupplyChainMetrics.get_current_stock_rate(...)` | 当前生产备货率 |
| `eval_national_supply_status` | `SupplyChainMetrics.eval_national_supply_status(ProductSKU)` | 全国充足/持平/不足（±5% 规则写在 description） |
| `eval_target_stock_rate` | `StandardPolicyMatrix` + 上项结果 | 目标备货率（旬度×三态×订单进度规则写在 description） |
| `calc_replenishment_quantity` | 派生计算 | 建议补货量 = 目标口径库存 − 当前口径库存 |

**`eval_target_stock_rate` description 示例片段**（完整版实施时写入代码）：

```text
按 StandardPolicyMatrix 计算目标生产备货率。
输入：product_code, site_code, period（early_month|mid_month|late_month）。
先调 eval_national_supply_status 得 PLENTIFUL|BALANCED|DEFICIT。
充足态+中旬：订单进度>标准进度时，目标=min(订单进度+20%, 100%)；否则见规则矩阵…
返回：target_rate, applied_rule（如 plentiful.mid_month.order_above_standard）, inputs_used。
```

### 8.2 Objective Assets（资产查询）

| Tool 名 | 本体映射 | 作用 |
|---------|----------|------|
| `query_inventory_snapshot` | `InventorySnapshot` @ Warehouse×SKU | 读分仓库存快照（计划、现货、在途、未发、备货率、大日期等） |
| `query_batch_big_date_inventory` | `BatchInventory` | 大日期批次库存 |
| `query_base_warehouse_availability` | 基地仓 `from_available` | 各基地仓可发量、时效 |
| `query_national_inventory_summary` | 全国报表聚合 | 全国供应/需求用于 eval_national_supply_status |

### 8.3 Transactions（调拨与履约）

| Tool 名 | 本体映射 | 作用 |
|---------|----------|------|
| `list_pending_allocation_orders` | `AllocationOrder` 草案 | 查 `push_num IS NULL` 的正向/横向待确认行 |
| `simulate_allocation_effect` | 仿真 | 给定调拨方案，算各仓调后备货率 |
| `save_forward_allocation_draft` | `AllocationOrder.save_as_draft`（正向） | INSERT `yl_forward_transfer` |
| `save_lateral_allocation_draft` | `AllocationOrder.save_as_draft`（横向） | INSERT `yl_lateral_transfer` |
| `update_allocation_quantity` | 经理改量 | UPDATE OIP `trans_num` + 同步履约 `transfer_qty` |
| `activate_allocation_and_push` | `AllocationOrder.activate_and_push` | UPDATE OIP 下发字段 + **同步写 `mock_branch_replenishment_order`** |
| `cancel_allocation_order` | `AllocationOrder.cancel_order` | OIP 作废 + 履约 `status=作废` |

### 8.4 不提供

- `get_event_impacts`——影响靠 Agent 读新 A-Box + `list_pending_allocation_orders` + `eval_*` 推理
- 带 `yl2_` 前缀的临时名——全部使用上表命名

### 8.5 profile.yaml 白名单（规划）

```yaml
allowed_tools:
  - get_order_gap
  - get_ship_gap
  - get_order_progress
  - get_current_stock_rate
  - eval_national_supply_status
  - eval_target_stock_rate
  - calc_replenishment_quantity
  - query_inventory_snapshot
  - query_batch_big_date_inventory
  - query_base_warehouse_availability
  - query_national_inventory_summary
  - list_pending_allocation_orders
  - simulate_allocation_effect
  - save_forward_allocation_draft
  - save_lateral_allocation_draft
  - update_allocation_quantity
  - activate_allocation_and_push
  - cancel_allocation_order
```

---

## 9. Agent 推理 vs Tool 执行

```
Agent：
  · 读 system_prompt + Tool descriptions（加载时 MAF 注入 tool 定义）
  · 决定分析哪些 SKU/仓、先横调还是正向
  · 调用 eval_target_stock_rate 等拿确定性数字
  · 用 applied_rule + 数字向经理解释
  · 人确认后调 activate_allocation_and_push

Tool：
  · OBDA 读 PG；内部 rules 怎么实现外界不关心
  · 返回结构化结果（值 + applied_rule + inputs_used）
```

**Agent 不算数**；**Agent 不读独立 rules 文件**；**Agent 不写 SQL**。

---

## 10. Mock Case 验收

### Script 1（人：「开始今日巡检」）

| 步骤 | Tool |
|------|------|
| 读郑州仓异常 | `query_inventory_snapshot` → `get_order_gap` |
| 全国状态 | `eval_national_supply_status` |
| 目标备货率 92% | `eval_target_stock_rate` |
| 补货量 4700 | `calc_replenishment_quantity` |
| 选天津基地 | `query_base_warehouse_availability` + Agent 按 description 中时效优先推理 |
| 写草案 | `save_forward_allocation_draft` |
| 横调+正向组合 | `save_lateral_allocation_draft` + `save_forward_allocation_draft` |
| 经理改 1600 | `update_allocation_quantity` |
| 下发 | `activate_allocation_and_push` → Dashboard 可见 |

### Script 2（Webhook + 新 Session）

| 事件 | 外系统改表 | Agent |
|------|-----------|-------|
| 基地延期 | `from_available=3200` | `list_pending_allocation_orders` → 对比可发量 → 重算 → `update_*` / `activate_*` |
| 大订单 | `total_unship+=2800` | `query_inventory_snapshot` → `eval_target_stock_rate` → 追加草案 |

契约测试：`tests/yl_worker2/test_mock_case_metrics.py` 断言 Tool 输出与 mock case 数字一致。

---

## 11. 实施阶段

| 阶段 | 交付 | 状态（2026-07） |
|------|------|----------------|
| **P0** | `app/yl_worker2/` + 本体 Tool（§8）+ description 写全 + 契约测试 + `v_sku_site_inventory_cube` | ✅ 已完成 |
| **P1** | Script 1 端到端（人触发 → 双表写入） | ✅ 已完成（Tool 链 + 双写集成测） |
| **P2** | Webhook trigger API + 新 Session + Script 2 | ✅ 已完成（默认 `auto_run` + 事件契约测） |
| **P1.5** | Entity Access Layer（发现 / 解析 / 自然语言入口） | 🚧 P0 已实施，见 [yl-worker2-entity-access-layer.md](./yl-worker2-entity-access-layer.md) |
| **P3+** | memory / 队列削峰 / 履约真实 API | 未做 |

**测试**：`cd backend && .venv/bin/python -m pytest tests/yl_worker2/ -v`（需 `YL_DATABASE_URL` + `scripts/load_yl_mock_ylp001.sh`）。

**注册说明**：Tool 通过 `app/tools/__init__.py` 合并 `YL_WORKER2_TOOLS` 进入 `BUILTIN_TOOLS`（非独立 `tool_registry.py`）。

---

## 12. 一句话总结

yl-worker2 = **本体语义 Tool（名对齐 T-Box，description 承载规则）+ 内部 OBDA 实现可换 + Agent 读 Tool 推理**；配置只在 `agents/yl-worker2/`；无 rules MD/YAML；调拨写 OIP 表并同步 `mock_branch_replenishment_order`；外系统走 Webhook + 新 Session。
