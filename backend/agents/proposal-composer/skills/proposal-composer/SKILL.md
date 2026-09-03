---
name: proposal-composer
description: >-
  Editable proposal_draft semantics: document meta-model (facts, sections by kind),
  preview-vs-draft, patch vs materialize, and template as render contract. Use when
  initializing or editing a proposal draft—not for MDM catalog lookup (see proposal-mdm-catalog skill).
---

# Proposal Composer — Draft Skill

## 与 System Prompt 的分工

| 层 | 内容 |
|----|------|
| **System prompt** | 角色、销售语言、任务驱动 |
| **Tool descriptions** | 各 tool 的调用时机与参数 |
| **本 Skill** | draft **元模型**与编辑原则 |
| **`references/`** | 补充说明（preview 差异、template 字段）；**非**完整 schema 镜像 |

## 编辑原则

1. **Draft 是编辑真相，Preview 是渲染结果** — 改用户指的内容 = 改产生该内容的 draft 字段，不是 panel 上的装饰（编号、分组、脚注序号等）。

2. **先定位，再修改** — `get_proposal_draft` → 按 section `kind` / `id` 找到 node → 用稳定 key（`source.sku`、`package_id`、服务名）定位 → patch。详见 [preview-vs-draft.md](references/preview-vs-draft.md)。

3. **新增 vs 编辑** — catalog 新增用 materializer；可见内容编辑用 patch。勿 patch 手写整行来「加服务」。

4. **Template 是契约** — section 有哪些 slot、render 怎么画，以 `templates/{id}/template.yaml` 为准（`read_knowledge("templates/{template_id}/template.yaml")`，`template_id` 来自 `/meta/template_id`）。结构不清楚时查契约，不要凭 skill 记路径。常用字段：

   | 字段 | 含义 |
   |------|------|
   | `sections[].id` / `kind` | 稳定 id；kind 决定 node 形状（见上表） |
   | `sections[].default_enabled` / `required` | 初始可见性 / 能否关闭 |
   | `sections[].editable` | 是否允许 patch 可见内容 |
   | `sections[].fee_layout` | 表样式、列、分组、脚注、列宽等 render 规则 |
   | `sections[].package_briefs.index` | package_id → brief 模板路径 |
   | `sections[].derivation` | `derived_section` 专用：`type`、`source_section`；决定推导与配置语义 |
   | `sections[].agent_guidance` | 该 section 的 agent 操作说明（materialize 后出现在 draft 同名字段） |
   | `sections[].knowledge` | Required documents 等：`category`、`body_root`、`source_section`、skill resource 路径 |
   | `placeholders` | introduction 等处的占位符解析规则 |

   静态正文在 `blocks/*.md`；结构规则在 `template.yaml`。Catalog 价格与 SKU 不在 template 里。

5. **Platform 会重算的不要重复做** — `edit_state: source` 的块、add_package 触发的 brief/占位符；只为销售明确要的差异 patch，必要时锁定 edit_state。patch 销售定制文案后，若不应再被 placeholder 覆盖，确认该 node 的 edit_state 语义再决定是否一并调整。

6. **Readiness 只约束导出** — live preview / 改单无步骤锁。

## Reply gate（回复前强制检视）

**何时必须做**：本轮调用了 **任何会改 draft 的 tool**，或你准备在回复里 **声称** 某内容「已加入 / 已改 / 已启用 / 已完成」时。纯 catalog 问答、用户尚未确认写 draft 时可跳过。

**目的**：避免「tool 调了 ≠ 用户意图已满足 ≠ 回复里说的属实」——例如只 `enable` 推导型 section 却对用户说两套方案都已写好。

**做法（泛化，非场景 checklist）**：

1. **收束用户意图** — 本句 + 仍有效的先前要求：要哪些 section / package / 服务 / 变体 / 客户字段 / 价格？
2. **读 draft 真相** — 优先用 **最后一笔写 draft tool 返回的 `draft`**；不够再 `get_proposal_draft`（或 `path` 查相关 subtree）。**不要**仅凭 tool 成功或自己的计划下结论。
3. **三维对照**（逐条问，不限于 fee / payment）：
   - **Scope**：用户要的每一块在 draft 里是否 **存在且 enabled**（含 derived 的配置是否够，不是只有 default）？
   - **Fidelity**：名称、SKU、金额、optional 内容是否与用户指定一致（报价看 fee row **`display.*`**，MDM 原价在 **`source.*`**）？
   - **Honesty**：准备写的回复，是否 **每一条完成态表述** 都能在上一步 draft 里找到依据？说不清就改 draft 或改口（部分完成 / 还差什么）。
4. **推导 / 聚合 render** — 若意图涉及 `derived_section`、footnote 聚合、分组表等，draft 字段对了仍可能和 panel 不一致时，再 `render_preview` 或让用户看 panel；**panel 与 draft 冲突以 draft 为准去 patch**。
5. **Fail closed** — 对不上：**继续 patch / enable / materialize**，或 **明确告知未完成项**；禁止「Done + 右侧面板将会显示…」式空头承诺。

与 **generate 门禁** 无关：Reply gate 约束 **你对销售的每一句完成态表述**；`ready_to_generate` 仍只约束导出。

## Document 元模型

```
proposal_draft
├── meta          … template_id, title
├── facts         … client（跨 section 的客户事实）
└── document
    └── sections[]   … 每个 node 有 kind，kind 决定「里面有什么」
```

**不要**把 skill 当成 JSON Schema 镜像。对象演进时：**以 `get_proposal_draft` 返回为准**；本 skill 只描述稳定 **概念层**。

### Section 由 `kind` 决定形状

| kind | 概念 | 典型可编辑内容 |
|------|------|----------------|
| `markdown_block` / `static_block` | 单块文案 | `content`（视 editable） |
| **`fee_section`** | **定价区 composite**（见下） | intro、package 叙事、fee rows |
| `derived_section` | 从其他 draft 节点 **render 时推导** | 见下 **推导型 section** |
| `collection` | 条目列表 | `items[]`（legacy，如 credentials）或 **`blocks[]`**（`collection.child_kind: markdown_block`，如 appendices） |

其他 kind 出现时：读 template + 当前 draft，按 node 上实际字段编辑。

### `fee_section`：一个 section，多个内容槽

Template 里通常一个 id（如 `solution_and_fees`）对应 **一个** `fee_section` node，**不是**两个并列 template section。

Draft 内按 **语义槽** 组织（非独立 sub-section id）：

| 槽 | 存什么 | Preview 里大致对应 |
|----|--------|-------------------|
| `intro` | 定价区引导文案（`kind: markdown_block`） | Solution 开头段落 |
| `tables[].brief` | 每个 package 的 solution 说明（`kind: markdown_block`；à-la-carte 表无 brief） | package 说明段落（在 fee 表 **之前**，按 `tables[]` 顺序拼接） |
| `tables[].rows[]` | 计费行（`source` 快照 + `display` 渲染字段） | Fee tables（在 brief **之后**） |

**Preview 顺序**（intro → 各 table 的 brief 拼接 → fee 表标题 → tables → 可选脚注区）由 platform render + `fee_layout` 决定，不是 draft 里再嵌一层 section tree。

`add_package` 在 `tables[]` 写入带 `brief` 的 fee_table；改 package 说明 patch `tables/{t}/brief/content`；改展示 patch 对应 row 的 **`display.*`**；删行用 **`remove_fee_rows_from_proposal_draft(skus=[...])`**（用户说服务名，draft 里用 `display.preview_primary` 定位，tool 传 `source.sku`）。

### Fee row：`source` + `display`

每行 **固定形状**：

| 部分 | 可 patch？ | 含义 |
|------|----------|------|
| **`source`** | **否** | MDM 入库快照（`type: mdm_service` + sku、price_amount、department_team、footnotes 等 catalog 字段） |
| **`display`** | **是** | Preview / 销售指称的展示真相；render **只贴 display** |

**`display` 字段（按 `fee_layout.table_style`）**：

| `table_style` | display 字段 |
|---------------|----------------|
| `simple` | `preview_primary`, `amount_display`, `footnotes_display?` |
| `frequency_columns` | `preview_primary`, `scope_of_work_display?`, `frequency_columns_display`, `total_display`, `footnotes_display?` |
| `one_off_recurring` | `preview_primary`, `scope_of_work_display?`, `once_off_display`, `recurring_display`, `footnotes_display?` |

Materialize 时 platform 会写 **canonical display**（含上述全部金额字段）；换 `table_style` 只换 renderer，不必重跑 MDM。

- 改价：**simple** patch `display.amount_display`；**frequency** patch 对应 `display.frequency_columns_display.{monthly|quarterly|annual|once_off}` 与/或 `display.total_display`；**one_off_recurring** patch `display.once_off_display` / `display.recurring_display`。
- **Display 文案**：`source` 不可改；`display.*` 可 patch。纯改价（如 `USD $750.00`）会 normalize；**同金额加说明**（如 `USD $703.00 (Refer appendix)`）按字面保留，refresh 不会 strip。
- 改标题/服务名展示：patch `display.preview_primary`（勿 patch `source.service_name`）。
- 脚注正文：patch `display.footnotes_display`（聚合编号仍由 render 处理）。
- **`department_team` 只在 `source`**，供 `group_by: department`；不进 display。

JSON Pointer 示例：`/document/sections/{i}/tables/{t}/rows/{r}/display/preview_primary`。

### Custom 行（非 catalog）

**不需要单独 add tool** — 与改价一样走 **`patch_proposal_draft`**，对 `tables/{t}/rows/-` 做 **`add`**，append 完整 `fee_row` node：

- `source`: `{ "type": "custom_service", "sku": "CUSTOM_n" }`（sku 唯一，add 前读 draft 分配 `CUSTOM_1`、`CUSTOM_2`…）
- `display`: agent 直接写 `preview_primary` + 按 `table_style` 写金额字段（无 MDM resolve）

详见 [preview-vs-draft.md](references/preview-vs-draft.md#custom-行非-mdm)。**勿**用 `add_services_to_proposal_draft`（仅 MDM）。

### `fee_layout`：只改显示，不改存储路径

`fee_layout`（在 fee_section 或 template 上）控制 **怎么画**，不改变 footnote/price 存在哪：

| layout 开关 | 存储 | Preview |
|-------------|------|---------|
| `footnotes: aggregate` | 仍在 **每行** `source.footnotes` / `display.footnotes_display` | 全文去重、统一编号、section 末一次渲染 |
| `group_by: department` | `department_team` 在 **source** | render 时按 department 拆多张表 |
| `service_columns` | resolve 时决定 `display.preview_primary` / `scope_of_work_display` | 决定 Service 单元格展示哪些列 |
| `show_billing_frequency` | resolve 时写入 **`display.amount_display`**（仅 `table_style: simple`） | simple 价列追加 `Monthly` / `Quarterly` / `Annual`（ONE_TIME 不加；未知 enum 保留 DB 原值） |
| `table_style` | — | `simple` / `frequency_columns` / `one_off_recurring`（Section View 同样三种 layout） |

**实例级展示**：`fee_section.fee_layout.table_style` 等 presentation 字段在 **新建 draft 时从 template 复制**，之后 **draft 实例优先于 template**（历史 load 用 session 里存的 layout + display，不会被 template 覆盖）。切换展示：patch `fee_section.fee_layout.table_style`，无需改 template yaml。

未来非 aggregate 脚注模式：row 路径仍相同，仅 render 不同。

### `derived_section`：推导型 section

**概念**：Preview 里该 section 的正文 **由 platform 按 `derivation` 规则从其他 draft 节点渲染时计算**，agent 不写也不应 replace 其 markdown 内容。Draft 上存的是 **开关 + 推导所需配置**，不是最终渲染结果。

**核心认知**：`enable_proposal_draft_section` 只切换可见性；**enable ≠ 用户意图已满足**。platform 在配置缺失时只应用该 `derivation.type` 的内置 default，default 往往是最简结果（例如单套汇总）。用户要的变体、多套方案、alternate 配置——这些需要在 enable 之后 **额外 patch 该 section 的配置字段**。

**workflow（适用所有 `derived_section`，无论 template）**：

1. **发现** — `get_proposal_draft` 定位该 node（或读 template）；看 `kind`、`derivation.type`、`derivation.source_section`、`default_enabled`，以及 `agent_guidance`（若存在：default 行为、配置 slot 格式与示例）。**不要凭 skill 记哪个 template 有哪些 derived_section**——template 会增加，skill 不跟实例走。
2. **读配置现状** — `get_proposal_draft` 定位该 node；看 **该 node 上实际有哪些配置字段**（以返回 JSON 为准，不猜 schema）。
3. **Enable** — 若 `default_enabled: false`，先 `enable_proposal_draft_section`。停在这里，**不要向用户宣称已完成**。
4. **判断 default 是否够用** — 对照用户意图与 default 推导结果：够用则止，不够则继续。
5. **Patch 配置** — 用户要超出 default 的变体/配置时，`patch_proposal_draft` 写入该 section 的配置 slot。**配置格式以 draft 上该 section 的 `agent_guidance` 为准（若有）**（platform 读 `derivation.type`/`source_section`，`agent_guidance` 只给 agent 看）。**不要发明字段**——只用 guidance 里出现的 key 和结构。
6. **Reply gate** — 在回复之前，Scope 维逐条确认用户指名的每个变体在 draft 配置里都存在（见 Reply gate）。

**勿 patch 生成结果** — `policy.editable: false` 时不要 replace 渲染出的 markdown；改 **配置 slot** 或 `intro.content`（若 template 标记 editable）。

**与普通 optional section 的本质区别**：普通 optional（`markdown_block`、`collection` 等）enable 之后即显示已有内容，用户要改就改内容字段；`derived_section` enable 后内容来自推导，用户要「第二套方案」类需求时 **enable 不够，必须 patch 推导配置**。同一个 tool `enable_proposal_draft_section`，两类语义不同——遇到 `derived_section` 必须额外问：**default 推导是否已覆盖用户的全部意图？**

*例*：au-advisory `payment_options`（`payment_options_from_fee_tables`）默认推导单套汇总方案；用户要月付 Option B 时 enable 不够，需 patch 该 node 的配置字段（字段名从 `get_proposal_draft` 读，不从 skill 查表）。

*例*：sg-incorp `first_invoice`（`first_invoice_from_fee_tables`）enable 即可；platform 从 fee rows 推导首票表（排除 adhoc、用 display 价、template `derivation.tax` 算 GST），fee 变更后自动重算，**勿 patch 表格**。

### Required documents（knowledge category + compose）

**概念**：`required_documents` 等章节的正文由 **category catalog 选型 + body 文件拼接** 组成；catalog 规则在 skill reference，客户在 proposal 里只看到 patch 后的 `content`。

**与 `derived_section` 的区别**：platform **不**自动 compose；agent 读 compose reference + category catalog 并 patch。`enable_proposal_draft_section` 只切可见性 — **enable ≠ 清单已写好**。

**Template 契约**（`sections[].knowledge`，以 yaml 为准）：

| 字段 | 含义 |
|------|------|
| `category` | catalog 名，如 `harneys` → `references/required-docs-{category}-catalog.md` |
| `body_root` | `read_knowledge` 前缀，如 `peripheral/required-docs/harneys` |
| `source_section` | 选型来源 fee_section id，通常 `solution_and_fees` |
| `compose_skill_resource` | 泛化流程，默认 `references/required-docs-compose.md` |

**Routing**

| template / category | Catalog resource |
|---------------------|------------------|
| `harneys-bvi` → `harneys` | [required-docs-harneys-catalog.md](references/required-docs-harneys-catalog.md) |

**Compose 行为**：读 compose reference（`references/required-docs-compose.md`）了解不变量与选型逻辑；读 category catalog 获取具体规则；按 fee tables 选 block，只读选中 body 文件。fee tables 为空时 patch 占位文案，不读 body。

**Refresh**：fee tables 变化后若 section enabled，对照 `composition.source_snapshot` 判断是否需要 recompose；用户手改过（`edit_state.content === "user"`）时先确认再覆盖。

**Reply gate**：对用户说 required documents 已齐之前，确认 draft 里 `content` 非空且 `composition.status` 为 `ready`，或如实说明 `pending_packages` / `pending_structure`。

### Appendices（collection + markdown_block blocks）

**概念**：`appendices` 是 `kind: collection`，子块在 **`blocks[]`**，每项为标准 **`markdown_block`**（必须有 **`title`** + `content`）。数量不限，按需 `add` / 调序 / 删除，无需 template 预置多个 appendix slot。

**Template 契约**：`collection.child_kind: markdown_block`；`render.block_as_chapter: true` → preview 每项独立 `# Title`，无外层 `# Appendices` 包裹。

**Workflow**：`enable_proposal_draft_section("appendices")` → `patch_proposal_draft` **`add`** 到 `.../appendices/blocks/-`，value 用 `new_collection_markdown_block` 形状（`id`, `kind: markdown_block`, `title`, `content`, `edit_state`, `policy`）。改文案 patch `blocks/{b}/content`；调序 replace/move `blocks` 数组；删块 remove 或 filter。

**勿**与 legacy `collection.items[]`（credentials）混淆——appendices 只用 **`blocks[]`**。

### Facts 与 placeholders

`facts.client` 是跨 section 输入；template `placeholders` 在 render 时注入 markdown 块。Patch client facts 即可；勿为 `{{client.*}}` 去 patch introduction 全文（除非销售要 override 且 edit_state 允许）。

## 用户指称 → 思考方式

- **某行 / 某价 / SOW / 脚注** → 在 `fee_section` 的 `tables[].rows[]` 里按 sku/名称定位 → patch 对应 **语义字段**。
- **某 package 方案说明** → `tables[]` 里按 `source.package_id` 定位 → patch `brief/content`。
- **客户 / 公司** → `facts.client.*`。
- **`derived_section`**（需要 enable 的推导型章节）→ 先读 template 确认 `derivation.type`；enable ≠ 全部变体；读 draft 发现配置字段 → patch。
- **其他 optional 章节**（`markdown_block`、`static_block`、`collection` 等）→ enable 后 patch 该 kind 的内容字段（`content`、`items[]`…）。
- **Required documents（knowledge category）** → template `sections[].knowledge` 声明 category；读 compose reference + category catalog，按 fee tables 选型 → 只读选中 body → patch `content` + `composition`（见下）。
- **Appendices** → `appendices` collection → enable → patch `blocks/-` 追加 `markdown_block`（必须有 title）；见 **Appendices** 节。
- **加/换 catalog 项** → catalog 查询 → materialize；只改已有 draft → patch。

Path 不确定：**读 draft**，不要猜数组下标。

## References

| 主题 | Resource |
|------|----------|
| Preview vs draft、指称解析 | [preview-vs-draft.md](references/preview-vs-draft.md) |
| Required documents compose（泛化） | [required-docs-compose.md](references/required-docs-compose.md) |
| Required documents catalog（Harneys） | [required-docs-harneys-catalog.md](references/required-docs-harneys-catalog.md) |
