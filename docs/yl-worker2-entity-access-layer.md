# yl-worker2 实体访问层：发现 / 解析 / 点查 能力规划

> 版本：**v0.2** | 日期：2026-07-08  
> 状态：**P0 已实施；P1 别名 + L0 自省已实施**（26 Tool，暂缓 `resolve_snapshot_date`）  
> 关联：[yl-worker2-ontology-plan.md](./yl-worker2-ontology-plan.md)（v0.5 本体 Tool 总方案）、[opt.md](./opt.md)（OBDA 架构模式）

---

## 0. 文档目的

本文汇总 **yl-worker2 自然语言与发现能力缺口** 的调研结论，提出在现有「本体语义 Tool + OBDA」架构之上、**不退回 NL2SQL** 的前提下，应补足的 **Entity Access Layer（实体访问层）** 能力清单与实施优先级。

**不在本文重复**：Metric 公式、StandardPolicyMatrix 条文、Mock 契约数字——那些仍是各 Tool `description` 的 SSOT（见 v0.5 方案 §6）。

---

## 1. 问题陈述

### 1.1 用户反馈的两个核心痛点

| # | 痛点 | 表现 |
|---|------|------|
| 1 | **泛化 Discovery 不足** | 「现在有什么产品？」「有哪些仓库？」「有哪些快照日？」答不了或要求用户已知 ID |
| 2 | **强迫人记 ID** | Agent 反复索要 `product_code` / `site_code`；用户说「郑州仓」「金领冠」无法直接检索 |

### 1.2 为何 Worker2 体验反而差于 Worker1

| 维度 | Worker1（postgres MCP + NL2SQL） | Worker2（本体 Tool + OBDA） |
|------|----------------------------------|-------------------------------|
| 用户说「郑州仓」 | SQL `WHERE site_name LIKE '%郑州%'` | 所有业务 Tool 入参为 `site_code` |
| 用户说「有哪些产品」 | `SELECT DISTINCT product_code …` | 无 list/search Tool |
| 探索 / 消歧 | 查询多行 → Agent 展示让用户选 | 无 `candidates[]` 协议 → 失败即「请提供 ID」 |
| 口径一致性 | 易漂移（模型拼 SQL） | 强（Tool + `applied_rule`） |

**结论**：Worker2 用 OBDA 藏掉了 SQL，但**未把「主数据浏览 + 自然语言实体解析」提升为语义 Tool 层**，导致入口体验倒退。这不是本体路线错误，而是 **缺少 Entity Access Layer**。

---

## 2. 参考模型：四层实体访问（L0–L4）

业界（Palantir Ontology、Microsoft Fabric IQ、Databricks Genie、OBDA 文献）共识：**Agent 不应直接碰物理表，而应在本体对象上完成分层访问**。

```text
用户自然语言
    │
    ▼
┌──────────────────────────────────────────┐
│ L2 实体解析 Entity Resolution             │
│     search_* / resolve_entity            │
│     「郑州仓」→ site_code                │
│     「金领冠」→ product_code             │
└──────────────────────────────────────────┘
    │ canonical ID
    ▼
┌──────────────────────────────────────────┐
│ L1 发现 Discovery / Catalog               │
│     list_* / query_snapshot_catalog      │
│     有哪些 SKU？某日哪些仓有快照？         │
└──────────────────────────────────────────┘
    │ product + site + adjust_date
    ▼
┌──────────────────────────────────────────┐
│ L3 语义点查 Semantic Point Query          │
│     query_* / get_* / eval_* / calc_*    │  ← yl-worker2 已实现
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ L4 交易动作 Transactions                  │
│     save_* / update_* / activate_*       │  ← yl-worker2 已实现
└──────────────────────────────────────────┘

（可选）L0 模式自省 Schema Introspection
         describe_entity_type / list_entity_types
```

### 2.1 三类问题模式对照

| 模式 | 用户意图 | 典型说法 | 系统职责 | yl-worker2 现状 |
|------|----------|----------|----------|-----------------|
| **Discovery** | 不知道 ID，先摸清「有什么」 | 「有哪些产品？」「6/30 哪些仓有数据？」 | 枚举目录、默认推荐、分页 | 部分：`query_snapshot_catalog` **强制** `product_code` |
| **Resolution** | 知道业务名，不知 canonical ID | 「郑州仓」「天津基地」「金领冠」 | NL/别名 → ID；多候选消歧 | **缺失** |
| **Point Query** | ID 已确定，查指标或写单 | 「该仓备货率多少？」 | 确定性 Tool 求值 | **已实现**（18+1 个 Tool） |

### 2.2 推荐 Agent 调用顺序

```text
1. load_skill(yl-oip-ontology-core)     # 理解实体/关系/推理规约
2. resolve_entity / search_*            # 用户给了业务名、没给 ID
3. list_* / query_snapshot_catalog      # 用户问「有什么」或日期/覆盖不明
4. resolve_snapshot_date（可选）        # 「今天」「最新」「6月30」
5. query_* / eval_* / calc_*            # 点查与规则求值
6. save_* / activate_*                  # 经理确认后写回
```

---

## 3. 当前实现缺口（基于代码与 DB）

### 3.1 已有 Tool 与断点

| Tool | 层级 | 断点 |
|------|------|------|
| `query_snapshot_catalog` | L1 | 入参 **必填** `product_code`；无法单独回答「有哪些产品」 |
| `query_inventory_snapshot` 等 | L3 | 需要完整三元组 `product_code + site_code + adjust_date` |
| （无） | L2 | 无法从 `site_name` / `product_name` 反查 ID |
| （无） | L1 | 无 `list_products` / `list_warehouses` |

`fetch_snapshot_catalog` 虽返回 `warehouse_master`（`site_code`, `site_name`, `site_type`），但：

- 嵌在「已知 SKU」的 catalog 调用里，Agent 不会为「有哪些仓」单独使用；
- 不按 `mention` 搜索，无法解析「郑州仓」。

### 3.2 DB 中已有、未暴露给 Agent 的主数据

| 表 | 关键字段 | 应支撑的语义能力 |
|----|----------|------------------|
| `yl_product` | `product_code`, `product_name`, `brand`, `pro_series`, `business`, `is_delete` | 枚举 SKU、按品牌/品名/系列搜索 |
| `yl_warehouse` | `site_code`, `site_name`, `site_desc`, `site_type`（0=基地，1=销售） | 枚举仓网、按城市/简称/类型搜索 |
| `yl_sales_warehouse_inventory_report` | `product_code`, `from_site_code`, `adjust_date` | 反查「某日有快照的 SKU×仓」 |
| `yl_national_sales_warehouse_inventory_report` | `product_code`, `adjust_date` | 反查「某日有全国汇总的品项」 |

Mock 环境示例规模（`yl_warehouse_product.sql`）：8 个 `MOCK_YLP*` 产品、4 基地仓 + 9 销售仓——**数据在库，语义 API 未建**。

---

## 4. 业界最佳实践摘要

### 4.1 Palantir Ontology

- **架构**：异构源统一为 Object / Property / Link；Agent 通过 **Object Query Tool** 在授权内 filter/aggregate/traverse，**不直接写 SQL**。
- **发现**：[Object Explorer](https://www.palantir.com/docs/foundry/object-explorer/search-syntax/) 全局关键词、属性过滤、关系过滤、模糊匹配；[Objects Search API](https://www.palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/search-objects/) 结构化 `containsAllTerms` / `eq` 等。
- **实体解析**：多在 **Pipeline 入库阶段**（Levenshtein join、LLM 最近邻）合并多源为 canonical Object；查询阶段做 **mention linking**。
- **启示**：**Search API（发现/解析）与 Metric/Action Tool（点查/写回）分离**；property description 是 Agent 路由 SSOT。

### 4.2 Microsoft Fabric IQ Ontology

- **架构**：Entity Types、Properties、Relationships；**NL2Ontology** 将自然语言转为结构化本体查询（非裸 SQL）。
- **Agent MCP**：[Fabric IQ Ontology MCP](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-fabric-iq-ontology-work-iq) 暴露：
  - `list_ontology_entity_types` — schema/目录发现
  - `search_ontology` — NL 问答 → JSON + 可选摘要
- **启示**：Agent 标配 **list schema + search** 双 Tool；浏览与点查分层。

### 4.3 Databricks Unity Catalog / Genie

- **架构**：[Business Semantics](https://www.databricks.com/product/unity-catalog/business-semantics) / Metric Views 集中指标、维度、**synonyms**。
- **实体解析**：[Genie tune quality](https://docs.databricks.com/aws/en/genie/tune-quality) — **Entity matching**：为列预存 distinct 值（≤1024/列），将用户说法映射到存储值；配合 Knowledge Store 的 column synonyms。
- **启示**：为 `product_name`、`site_name` 维护 **curated 值字典 + 别名**；值解析从 SQL 生成中**拆出独立层**（Genie 仍生成 SQL，但 matching 先行）。

### 4.4 OBDA 学术范式

- **核心**：[Calvanese et al., OBDA Survey (IJCAI 2018)](https://www.ijcai.org/Proceedings/2018/2018/0777.pdf) — Mapping + 本体概念层；领域词汇 → OMQ → SQL 重写（Ontop、Stardog 等）。
- **Entity linking**：[Springer 2025, adaptive entity linking](https://link.springer.com/article/10.1007/s11280-025-01355-x) — **标准 OBDA 不提供 entity linking**；需独立 middleware；联邦场景 per-source adaptive linker。
- **启示**：`resolve_entity` 应是 **OBDA 之上的独立 Tool**，不塞进 `eval_target_stock_rate` 或单次 SQL。

### 4.5 Knowledge Graph / ER Agent

- **ERKG**：[Modern Data 101 — ER meets KG](https://www.moderndata101.com/blogs/ai-for-entity-resolution-er-meets-knowledge-graphs-downstream-ai-apps) — 入库 blocking → matching → clustering，下游 Agent 在已解析图上推理。
- **消歧**：[Enterprise KG 架构](https://agility-at-scale.com/ai/architecture/enterprise-knowledge-graph/) — **关系上下文**消歧（场景下的「Mercury」≠ 化学元素）。
- **开源**：[SERF](https://github.com/Graphlet-AI/serf) — DSPy 编排 blocking、LLM matching。
- **启示**：补调场景用 `WarehouseType`（Base/Sales）+ 对话意图（正向 vs 横调）作消歧 context。

---

## 5. 与 NL2SQL 的差异及 UX 对齐方式

| 维度 | Raw NL2SQL（Worker1 / Genie） | 本体 Agent（Worker2 目标） |
|------|-------------------------------|----------------------------|
| 用户入口 | 自然语言 | 同样自然语言 |
| 系统内部 | 选表 → 生成 SQL → 执行 | 解析实体 → 语义 Tool → OBDA |
| ID 来源 | Entity matching 隐式写入 WHERE | 显式 `resolve_entity` / `search_*` |
| 指标口径 | 易漂移 | Tool description + `applied_rule` |
| 消歧 | 多行结果展示 | `status: ambiguous` + `candidates[]`，Agent 追问 |
| 写回 | 通常只读 | `activate_allocation_and_push` 等闭环 |

**UX 对齐关键**：用户界面只出现业务名（「郑州销售仓」「金领冠 1 段」）；`product_code` / `site_code` 仅在 Tool 链内部传递。

---

## 6. 能力清单（规划 Tool 全集）

### 6.1 分层总览

```text
【L0 自省】  describe_entity_type          （P1，可选）

【L1 发现】  list_products
             list_warehouses
             query_snapshot_catalog          （已有，需增强）
             list_snapshot_coverage          （P0，或与 catalog 合并）
             resolve_snapshot_date           （P1）

【L2 解析】  search_products
             search_warehouses
             resolve_entity                  （P0 统一入口）

【L3 点查】  现有 Metrics / Assets Tool      （已实现，不变）

【L4 动作】  现有 Allocation Tool            （已实现，不变）
```

### 6.2 L1 — Discovery / Catalog

| 规划 Tool | 本体实体 | 输入 | 输出（摘要） | 优先级 |
|-----------|----------|------|--------------|--------|
| `list_products` | ProductSKU | `active_only?`, `business?`, `limit?` | `products[]`: code, name, brand, series | **P0** |
| `list_warehouses` | Warehouse | `site_type?`（base/sales）, `limit?` | `warehouses[]`: code, name, type | **P0** |
| `query_snapshot_catalog`（增强） | InventorySnapshot | `product_code?`, `adjust_date?` | 支持**无 product_code**：仅日期 → 覆盖矩阵；无参 → 最新快照日 + 概览 | **P0** |
| `list_snapshot_coverage` | InventorySnapshot | `adjust_date?`, `product_code?` | 某日（某 SKU）有报表的 `sku×site` 列表 | P0 或与上合并 |
| `resolve_snapshot_date` | （时间语义） | `mention`（今天/最新/6月30） | `adjust_date`, `match_method` | P1 |

**`query_snapshot_catalog` 增强要点**：

- `product_code` 改为可选；
- 仅 `adjust_date` → 从 `yl_sales_warehouse_inventory_report` DISTINCT 返回当日有数据的 SKU 与仓；
- 无参 → 返回 `latest_adjust_date` + 可选默认推荐（由 DB 推导，不 hardcode 在 Skill）。

### 6.3 L2 — Entity Resolution

| 规划 Tool | 本体实体 | 输入 | 输出（摘要） | 优先级 |
|-----------|----------|------|--------------|--------|
| `search_products` | ProductSKU | `mention`, `brand?`, `limit?` | `candidates[]`: code, name, confidence, match_method | **P0** |
| `search_warehouses` | Warehouse | `mention`, `site_type?`, `limit?` | `candidates[]`: code, name, type, confidence | **P0** |
| `resolve_entity` | 跨实体 | `entity_type`, `mention`, `context?` | 见 §6.5 统一契约 | **P0** |

**解析实现选项（可组合，OBDA 内部）**：

| 方法 | 适用 | 参考 |
|------|------|------|
| 精确 / 包含匹配 | 仓名、品名 | Fabric display name |
| 别名表 | 简称、城市名 | Genie synonyms |
| Trigram / fuzzy | 拼写近似 | Palantir Levenshtein join |
| 关系上下文 | 基地 vs 销售、调入/调出 | Enterprise KG 消歧 |
| Embedding + ANN | 大规模 SKU 描述 | Palantir / SERF（P2） |

### 6.4 L0 — Schema Introspection（可选）

| 规划 Tool | 作用 | 优先级 |
|-----------|------|--------|
| `describe_entity_type` | 返回某实体类型的主键、可搜属性、关联实体 | P1 |
| `list_entity_types` | 返回 ProductSKU、Warehouse、InventorySnapshot 等摘要 | P1 |

可与 `yl-oip-ontology-core` Skill 互补：Skill 讲概念，Tool 讲运行时 schema。

### 6.5 `resolve_entity` 统一返回契约（建议）

```json
{
  "entity_type": "Warehouse",
  "mention": "郑州仓",
  "status": "resolved",
  "resolved_id": "MOCK_WH_S04",
  "display_name": "郑州销售仓",
  "confidence": 0.92,
  "candidates": [
    {
      "id": "MOCK_WH_S04",
      "display_name": "郑州销售仓",
      "confidence": 0.92,
      "match_method": "site_name_contains"
    }
  ],
  "context_used": { "site_type_hint": "sales" },
  "applied_rule": "resolve.warehouse.site_name_contains"
}
```

| `status` | Agent 行为 |
|----------|------------|
| `resolved` | 用 `resolved_id` 调 L3 Tool |
| `ambiguous` | **禁止**调需 ID 的 Metric Tool；向经理展示 `candidates` 请确认 |
| `not_found` | 说明未匹配；建议 `list_*` 或换说法 |

### 6.6 P2 — 体验增强（后续）

| 能力 | 说明 |
|------|------|
| `browse_inventory_anomalies` | 封装多仓快照 + 规则阈值，返回异常仓列表（对应 Palantir「先搜后滤」） |
| 别名表 `yl_entity_alias` | FDE 可维护；版本化 |
| 值字典预计算 Job | 定期刷新 Genie 式 entity matching 索引 |
| Embedding 检索 | SKU 描述多、别名杂时 |

---

## 7. Agent / Skill / Prompt / Tool 分工（实施时遵守）

| 层 | 职责 | 禁止 |
|----|------|------|
| **`yl-oip-ontology-core` Skill** | 实体/关系/规则角色；**先 resolve 再 point query** 推理顺序 | Mock 数字、阈值条文、仓码表、逐步剧本 |
| **Tool description** | 每个 search/resolve/list Tool 的匹配规则、返回字段、`applied_rule` | — |
| **system_prompt** | 角色、人在环、Script1/2 **触发语境**；**禁止向经理索要 ID** | 逐步 Tool 清单、主数据枚举 |
| **OBDA 实现** | SQL、模糊匹配、别名查找 | 暴露给 Agent |

**Skill 需增补的一条规约（实施后）**：

> 用户给业务名、未给 ID → 必须先调 L1/L2 Tool；`status=ambiguous` 时必须追问；禁止要求经理提供 `product_code` / `site_code`。

---

## 8. 实施优先级路线图

### P0 — 解锁自然语言入口 ✅ 已实施

1. ✅ `list_products` / `list_warehouses`
2. ✅ `search_products` / `search_warehouses`
3. ✅ `resolve_entity`（统一入口 + ambiguous 协议）
4. ✅ 增强 `query_snapshot_catalog`（`product_code` 可选、支持按日反查覆盖）
5. ✅ 更新 `profile.yaml` 白名单、`yl-oip-ontology-core` 推理规约、契约测试

**实现路径**：`runtime/entity_resolver.py`、`obda/entity_queries.py`、`tools/discovery.py`

**验收场景**（待 UI 手测）：

- 「有哪些产品？」→ `list_products`
- 「有哪些销售仓？」→ `list_warehouses(site_type=sales)`
- 「郑州仓金领冠今天缺口多少？」→ `resolve_entity` ×2 → `resolve_snapshot_date` 或 catalog → `get_order_gap`
- 「郑州」匹配多仓 → `ambiguous` → Agent 追问，不猜 ID

### P1 — 可治理 🚧 部分已实施

- ✅ `entity_aliases.yaml` 配置化别名（FDE 可维护，集成 resolve/search）
- ⏸ `resolve_snapshot_date`（暂缓）
- ✅ `describe_entity_type` / `list_entity_types`
- ⏸ `pg_trgm` 或等价 fuzzy 索引（暂缓，当前用规则匹配 + 别名）

### P2 — 规模与巡检体验

- `browse_inventory_anomalies`
- Embedding + ANN（SKU 规模大时）
- 关系感知消歧 `context` 扩展

### 明确不做

- ❌ Worker2 退回 NL2SQL / postgres MCP 查 `yl_*`
- ❌ 在 Skill / prompt 硬编码主数据表
- ❌ 解析失败时臆造 `site_code`（如 `BEIJING`、`BJ`）

---

## 9. 与 v0.5 本体方案的关系

```
v0.5 已交付：L3 语义点查 + L4 交易动作（18+1 Tool）
本文规划补全：L1 发现 + L2 解析（+ 可选 L0 自省）

合并后架构：

  Agent
    → ontology-core Skill（模型理解）
    → L2 resolve / L1 list / catalog
    → L3 Metrics & Assets（Tool description = 规则 SSOT）
    → L4 Transactions
    → OBDA → yl_* / mock_branch_replenishment_order
```

v0.5 方案 **§11 实施阶段** 可增 **P1.5：Entity Access Layer（本文）**，不改动既有 Metric/Allocation Tool 契约。

---

## 10. 参考资料

| 来源 | 链接 | 相关点 |
|------|------|--------|
| Palantir Ontology | https://www.palantir.com/docs/foundry/architecture-center/ontology-system/ | Object、Link、Agent Object Query |
| Palantir Object Search | https://www.palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-objects/search-objects/ | 结构化发现 API |
| Microsoft Fabric IQ | https://learn.microsoft.com/en-us/fabric/iq/ontology/overview | NL2Ontology、实体类型 |
| Fabric Ontology MCP | https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-fabric-iq-ontology-work-iq | list + search 双 Tool |
| Databricks Business Semantics | https://www.databricks.com/product/unity-catalog/business-semantics | 语义层 + synonyms |
| Genie Entity Matching | https://docs.databricks.com/aws/en/genie/tune-quality | 值字典映射 |
| OBDA Survey (IJCAI 2018) | https://www.ijcai.org/Proceedings/2018/0777.pdf | OMQ 与 linking 分离 |
| Adaptive Entity Linking (2025) | https://link.springer.com/article/10.1007/s11280-025-01355-x | OBDA 需独立 linker |
| 本项目 opt.md | [opt.md](./opt.md) | OBDA vs NL2SQL、语义编译器 |
| 本项目 ontology-plan | [yl-worker2-ontology-plan.md](./yl-worker2-ontology-plan.md) | Tool SSOT、Skill 分工 |

---

## 11. 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-07-08 | 初稿：调研摘要 + 能力清单 + P0/P1/P2 路线图 |
| v0.2 | 2026-07-08 | P0 实施：`list_*` / `search_*` / `resolve_entity` + 增强 `query_snapshot_catalog` |
| v0.3 | 2026-07-08 | P1 部分：`entity_aliases.yaml`、`list_entity_types` / `describe_entity_type`（26 Tool） |
