---
name: yl-oip-ontology-core
description: 伊利成人营养品事业部调度管理组工作助手（本体驱动）：主数据模糊查询、库存监控解读、分仓补调与调拨。OIP 本体模型、实体关系与推理规约。用户问产品/仓网/指标/巡检/补调/调拨/外系统事件时，会话首轮必须先 load 本 Skill。公式与阈值在各 Tool description。事业部口径为成人营养品事业部（CRYYBU）。
---

# OIP 本体核心（yl-oip-ontology-core）

## 本 Skill 教什么 / 不教什么

| 在本 Skill | 不在本 Skill（去哪找） |
|------------|------------------------|
| 实体、关系、四类模块、**规则在模型中的角色** | 公式、阈值、判定数字 → **各 Tool 的 description** |
| 规则如何经 Tool 暴露（`applied_rule`） | 具体 SKU/仓码/日期 → **`query_snapshot_catalog` 与 Tool 返回** |
| 推理顺序与 Agent 规约 | 场景触发语境 → **system_prompt** |

## 四类模块

```
Objective Assets   — 「现在有什么」：分仓/全国资产、批次、基地可发
SupplyChainMetrics — 「指标是多少」：缺口、进度、备货率、全国三态
Rules              — 「按什么政策判」：见下文专节；可执行条文在 Metric Tool description
Transactions       — 「要做什么单」：草案、改量、下发、作废
```

## 规则（Rules）在本体中的位置

规则**不是**独立 MD/YAML，而是补调判定逻辑在本体里的**第三类模块**，与指标、交易并列：

### 规则管什么

从 Dashboard 异常到可执行补调建议，典型判定链为：

```text
全国供应状态（够/平/不够）
  → 分仓目标备货率（结合旬度、订单进度等政策）
    → 建议补货量（目标口径 − 当前口径）
      → 调拨方案（正向/横向，受基地可发等约束）
```

每一环的**判定语义**由对应 Metric Tool 承载；**判定结果**由 Tool 返回，不靠 Agent 心算。

### 规则如何暴露给 Agent（两处，不重复第三处）

| 暴露方式 | 作用 |
|----------|------|
| **Tool description** | 规则 SSOT：适用条件、公式口径、何时调用、返回字段 |
| **Tool 返回的 `applied_rule`** | 本次命中哪条判定分支（向经理解释「为什么是这个数」） |

本 Skill **不抄写** Tool description 里的条文，只要求：需要规则细节时**去读当次注入的 Tool 定义**，需要解释时**引用返回的 `applied_rule`**。

### 标准政策矩阵（StandardPolicyMatrix）

本体中的**结构化策略对象**：把「全国供应状态 × 旬度 × 订单进度」映射到**目标生产备货率**。它是 Rules 模块的核心概念，**不是**单独配置文件。

- 全国三态判定 → `eval_national_supply_status`
- 目标备货率 → `eval_target_stock_rate`（description 中展开矩阵分支）
- 派生补货量 → `calc_replenishment_quantity`

Agent 按依赖顺序调用，不跳步、不颠倒。

### 使用规则的 Agent 规约

1. **不背诵、不心算**规则条文或阈值。
2. **先 Tool、后解释**：数字与分支名来自 Tool 返回。
3. **向经理汇报**：用业务语言转述 `applied_rule`，不贴 JSON，不报 SQL。
4. **规则变更**：只改 Tool 实现 + Tool description；本 Skill 描述的仍是「规则在模型中的角色」，不是具体条文。

## 事业部（BusinessUnit）口径

| 维度 | 值 |
|------|-----|
| 展示名称 | **成人营养品事业部** |
| 编码 | **CRYYBU** |
| 主数据字段 | `yl_product.business` / `yl_warehouse.business`；报表类表用 `business_code` |
| 履约中心 | `business_unit` 筛选项与补录单字段，与上表一致 |
| 已废弃 | ~~奶粉事业部~~、~~NFBU~~ — 不得出现在 Tool 入参、Agent 输出表格或履约写入 |

Agent 规约：

- 组织边界、用户沟通、数据解读一律用 **成人营养品事业部**。
- `propose_fulfillment_forms` 调用时**传入** `business_unit`；取值与 `yl_product.business` 一致，本环境为 **成人营养品事业部**。
- 用户问「哪个事业部」→ `search_products` / `query_source(yl_product)` 读 `business` 后再填，不凭记忆或旧称谓（奶粉事业部）回答。

## 核心实体

| 实体 | 含义 | 典型标识 |
|------|------|----------|
| **BusinessUnit** | 组织边界（本环境唯一：**成人营养品事业部**） | `business` / `business_code`（`CRYYBU`） |
| **ProductSKU** | 补调最小品项 | `product_code` |
| **Warehouse** | 基地仓或销售仓 | `site_code`；类型 Base / Sales |
| **SalesPlan** | 月度销售计划 | 挂在 SKU×仓 快照上 |
| **InventorySnapshot** | 某日某仓某品的监控状态 | `product_code` + `site_code` + `adjust_date` |
| **BatchInventory** | 批次/大日期明细 | 粒度细于仓级快照 |
| **TransitInventory** | 在途 | 关联发出仓与收货仓 |
| **UnshippedOrder** | 未发订单量 | 快照字段 |
| **AllocationOrder** | 调拨建议（正向/横向） | 草案 / 待确认 / 已下发 |
| **ReplenishmentOrder** | 经理确认后的履约单 | 与 AllocationOrder 双写联动 |

## 对象关系（推理时用）

```text
ProductSKU has SalesPlan
ProductSKU has InventorySnapshot at Warehouse
Warehouse has WarehouseType(Base | Sales)
InventorySnapshot contains BatchInventory
Warehouse has TransitInventory to Warehouse
SalesWarehouse has UnshippedOrder
ReplenishmentDecision recommends TransferAction
TransferAction has SourceWarehouse and TargetWarehouse
TransferAction creates ReplenishmentOrder
ManagerApproval confirms | modifies | rejects ReplenishmentDecision
DecisionReason explains ReplenishmentDecision
```

推理顺序（与规则链一致）：

- **先资产、后指标、后规则求值、后交易**：不跳过 `InventorySnapshot` 直接报补货量；不未调 Metric Tool 就写草案。
- **先全国、后分仓**：全国状态是目标备货率规则的输入（见 `eval_target_stock_rate` description）。
- **事件影响**：外系统改变库存/订单/基地可发 → 重读资产与指标 → 评估既有 `AllocationOrder` → 更新或新建草案。

## Tool 与本体动作（语义层）

具体何时调用、入参、返回以 **MAF 注入的 Tool description** 为准。

| 本体概念 | Tool 族 |
|----------|---------|
| 发现快照目录 / 全局覆盖 | `query_snapshot_catalog` |
| 枚举品项 / 仓网 | `list_products` / `list_warehouses` |
| 自然语言解析 ID | `search_products` / `search_warehouses` / `resolve_entity`（含 `entity_aliases.yaml`） |
| 本体 schema 自省 | `list_entity_types` / `describe_entity_type` |
| 数据源目录 / 表结构 / 单表遍历 / 引用跳转 | `list_sources` / `describe_table` / `query_source` / `follow_ref`（白名单 `ontology_sources.yaml`，引用 `ontology_refs.yaml`） |
| 读资产 | `query_*` |
| 求指标与规则求值 | `get_*`、`eval_*`、`calc_*` |
| 查待确认/仿真 | `list_pending_*`、`simulate_*` |
| 调拨生命周期 | `propose_fulfillment_forms`（会话表单）→ 前端 Confirm → 履约 API；`save_*`/`activate_*` 暂禁用 |

## Agent 推理规约

1. **首轮必载本 Skill**：每个新会话第一条 tool 调用为 `load_skill(yl-oip-ontology-core)`。
2. **主数据必先查 Tool**：问产品/仓网/列举/计数/模糊找品 → `list_*` / `search_*` / `resolve_entity` 或 `query_source`；**禁止**声称无目录查询能力或让用户去 MDM/WMS。
3. **探索链**：不确定表/列 → `list_sources` → `describe_table` → `query_source`；行内编码 → `follow_ref`。
4. **标识符不全先解析**：业务名未给 ID → `resolve_entity` / `search_*`；不确定日期/覆盖 → `query_snapshot_catalog`。
5. **`ambiguous` 必须追问**：不得调需 ID 的 Metric Tool。
6. **数字只信 Tool**；**规则只信 Tool description + `applied_rule`**。
7. **人在环**：`activate_allocation_and_push` 仅在用户明确确认后调用。

## 与 system_prompt 的分工

- **system_prompt**：角色、人在环、Script1/2 触发语境。
- **本 Skill**：本体结构、**规则在模型中的位置**、关系与推理规约。
- **Tool description**：可执行契约（含规则条文）。
