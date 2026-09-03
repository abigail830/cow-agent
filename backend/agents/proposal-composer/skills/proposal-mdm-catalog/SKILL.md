---
name: proposal-mdm-catalog
description: >-
  Read-only MDM catalog lookup for Proposal Composer via list_mdm_packages,
  get_mdm_package_services, search_mdm_services, and list_mdm_packages_for_services.
  Use when package_id or SKU is unknown, when exploring catalog in scope, comparing
  bundles, or resolving which packages contain given SKUs — not when patching an
  existing draft or editing client facts. Do not write SQL for MDM tables.
---

# Proposal MDM Catalog

## 与 System Prompt 的分工

| 层 | 内容 |
|----|------|
| **System prompt** | 角色、tool 并行/顺序、对外话术 |
| **本 Skill** | Catalog 概念、四个 MDM tool 的语义、与 add tools 的衔接 |
| **proposal-composer skill** | Draft 编辑、Reply gate、section 种类 |

触发后 catalog 查数以 **MDM tools** 为准；**禁止**对 `mdm_*` 表写 SQL 或调用 postgres MCP。

## 核心原则

1. **Catalog 回答「能卖什么、标价多少」；draft 回答「这份 proposal 里有什么」** — 已写入 draft 的改单、调价、改 SOW **不再查 catalog**。
2. **Service 与 package 同等** — package 只是「常一起卖的服务集合 / shortcut」，**不是** proposal 的前置条件。可以只加 services，也可以加 package；必要时向销售 **建议** 整包，但 **不得** 因「必须先选 package」而 block 编写。
3. **查与写分离** — 四个 MDM tools **只读**；确认选型后，用 `add_package_to_proposal_draft` 或 `add_services_to_proposal_draft` **单独**写入（顺序、不并行）。
4. **Scope 自动** — `jurisdiction` + `bu` 来自 `template_id` 或已 initialize 的 draft；勿手填错 jurisdiction。
5. **完整 row** — `get_mdm_package_services` 返回完整 `services[]` 供预览/确认；写入 draft 时 **`add_package_to_proposal_draft` 只需 `package_id`**，由 tool 服务端加载全部 ACTIVE 服务，勿手传截断的 services 列表。

## 四个 Tool（按问题选，无固定顺序）

| 销售 / 任务问题 | Tool | 得到什么 |
|-----------------|------|----------|
| 这个 jurisdiction 有哪些 package？/ 搜 AML package | `list_mdm_packages` | `packages[]`（可选 `skus` / `sku_count`） |
| 这个 package 里有哪些服务、什么价？ | `get_mdm_package_services` | `package` + `services[]` + `warnings` |
| 按 SKU / 关键词 / 部门找服务 | `search_mdm_services` | `services[]` + `not_found_skus` + `warnings` |
| 这些 SKU 属于哪些 package？（bundle 建议用） | `list_mdm_packages_for_services` | `items[].packages[]` |

**写入 draft（本 skill 不覆盖细节，但需衔接）：**

| 选型结果 | Add tool |
|----------|----------|
| 确认整包 | `add_package_to_proposal_draft(package_id=...)` — tool 服务端从 MDM 加载全部 ACTIVE 服务 |
| 确认若干服务（含单 SKU、跨 package 拼单） | `add_services_to_proposal_draft(services)` — `services` 来自 `search_mdm_services` |

`services[]` 在 MDM search tool 里可直接传给 `add_services_to_proposal_draft`；整包 add 只需 `package_id`。

## `warnings` 与定价

Tool 可能在 `warnings` 里提示 catalog 行缺少展示所需定价（如 FIXED 无 `price_amount`、UNIT_RATE 无 `fee_raw`）。含义：

- **可以**先把 row 加入 draft，preview 可能显示 `missing_facts`
- **应**向销售确认数量/规则后再 patch `price.amount` 或补事实 — 不是 catalog tool 的错误

`pricing_type` 行为见 proposal-composer skill 的 row 语义；catalog 只提供源数据。

## Scope 与 template

| Template | `jurisdiction` | `bu` |
|----------|----------------|------|
| `harneys-bvi` | `BVI` | `Harneys` |
| `au-advisory` | `AU` | `Incorp AU` |
| `sg-incorp` | `SG` | `Incorp SG` |

无 draft 时传 `template_id`；有 draft 时可省略（从 `meta.template_id` 推断）。

## 反模式

- 写 `SELECT … FROM mdm_services`（用 MDM tools）
- 只把 `sku, price_amount` 传给 add tool（BVI 等会丢 `description` / `department_team`）
- 手传 `services[]` 给 `add_package_to_proposal_draft`（应只传 `package_id`；tool 服务端加载 catalog）
- 因 SKU 在某个 package 里就 **强制** 整包 add（应听销售要整包还是散加）
- 查 catalog 代替 patch 已有 draft row

## 何时 **不需要** 本 skill

- 用户只改 draft 里已有服务名、价格、optional 章节
- 纯客户 facts / 文档 generate（无 catalog 选型）
