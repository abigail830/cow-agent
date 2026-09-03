# Preview vs Draft

## 本质关系

```
proposal_draft  +  template.yaml (fee_layout, placeholders, section kinds)
        ↓
   render (platform)
        ↓
   Proposal Preview（右侧面板）
```

- **Draft**：可编辑、可持久化的结构化文档。
- **Preview**：只读视图；含 **render 层** 才出现的排版、编号、分组、占位符展开、footnote 聚合等。

**原则**：用户指向 panel 上的任何内容，你要改的是 draft 里 **生成该内容** 的字段，不是 panel 上的 HTML 或装饰性前缀。

## Fee row：Preview 读什么

每行是 **`source`（不可 patch）+ `display`（Preview 真相）**：

| 部分 | Patch？ | Preview / 指称 |
|------|--------|----------------|
| `source` | **否** | 仅定位：`source.sku`、`source.type` |
| `display` | **是** | 服务名、金额、SOW、脚注等用户看到的一切 |

`display` 字段因 `fee_layout.table_style` 而异：

| `table_style` | 主要 display 字段 |
|---------------|-------------------|
| `simple` | `preview_primary`, `amount_display`, `footnotes_display?` |
| `frequency_columns` | `preview_primary`, `scope_of_work_display?`, `frequency_columns_display`, `total_display`, `footnotes_display?` |
| `one_off_recurring` | `preview_primary`, `scope_of_work_display?`, `once_off_display`, `recurring_display`, `footnotes_display?` |

Materialize 时 platform 写入 **layout-agnostic canonical display**（含 `once_off_display`、`recurring_display`、`frequency_columns_display` 等）；切换 `table_style` 只换 renderer。

**实例级 layout**：`fee_section.fee_layout` 的 `table_style`、`service_columns` 等 **draft 实例字段优先于 template**；历史 session load 用存盘 draft，不会被 template yaml 覆盖。

MDM 入库字段（`price_amount`、`department_team` 等）在 **`source`**；改 panel 上的价/名 **只 patch `display.*`**，不要 patch `source.*`。

## Render 层常见现象（不是 draft 字段）

| Preview 里可能有 | Draft 里实际存什么 |
|------------------|-------------------|
| 表序号 `### 2. Title`、行前缀 `2.2 …` | `tables[].title`；行展示名在 **`display.preview_primary`**（**无** 编号前缀） |
| 按 department 拆成多张表 | 同一张 logical table 的 rows；分组键在 **`source.department_team`** |
| `{{client.*}}`、package bullet list | `facts.client`、`fee tables` / placeholders 规则 |
| 脚注 `[1]` 与文末汇总 | **`display.footnotes_display`**（MDM 行 resolve 时也可来自 `source.footnotes`）；聚合编号由 `fee_layout.footnotes` 决定 |
| SOW 渲染成 HTML 列表 | **`display.scope_of_work_display`** 纯文本（frequency layout） |

具体规则因 template 的 `fee_layout.table_style`、`group_by`、`service_columns` 而异 — 必要时读 `template.yaml`，不要假设所有 template 同一套编号。

## 解析用户指称

用户可能用：panel 编号、表名、服务名、SKU、SOW 片段、「那一行」等。通用思路：

1. **读 draft**（`get_proposal_draft`），找到 `fee_section` 或相关 section。
2. **若指称含 render 序号**（如「2.2」「第二张表第三行」）：
   - 序号是 **有内容的表/行** 在 preview 中的 **1-based 显示序**，不是 JSON 的 0-based 下标。
   - 空表在 draft 数组里可能占位，但 preview 计数时常 **跳过空表**。
   - 结合 template 的 `fee_layout` 判断是否在行上显示 `{table}.{row}` 前缀（frequency layout 常见；simple 可能只有标题）。
3. **优先用稳定 key 定位**：
   - **`rows[].source.sku`** > `rows[].id` > **`display.preview_primary`** + `tables[].title`
   - 用户说服务名 → 在 draft 里匹配 **`display.preview_primary`**；删行 / 工具参数仍用 **`source.sku`**。
4. **定位到唯一 row 后**，patch 该 row 的 **`display.*`**（见上表）。
5. **仍歧义** → 用 **一个问题** 确认（SKU 或 `preview_primary` 即可），不要报 JSON 路径给用户。

## 常见思维错误

| 错误假设 | 为何错 |
|----------|--------|
| Panel「2.2」= `rows[2]` | 显示序 1-based；前缀里的 2 是 **表** 序号不是 row 下标 |
| 「2.2」= 全 proposal 第 2 行 | 通常是 **第 2 张（非空）fee 表** 的第 2 行 |
| `display.preview_primary` 里含「2.2」 | 编号是 render 时加的 |
| Catalog / MDM 顺序 = draft row 顺序 | Draft 顺序 = materialize / add 顺序 |
| 改 preview 里看到的 HTML | 应改 **`display`** 源字段（如 `scope_of_work_display` 文本） |
| 改价 = patch `source.price_amount` | **`source` 不可 patch**；改 **`display.amount_display`** 或 frequency 列 |
| 还有 `service_name` / `price.amount` flat 字段 | 已移除；一律 **`source` + `display`** |

## 与 patch 的关系

JSON Pointer 用的是 draft 数组的 **物理下标**（0-based）。从用户指称到 pointer 的映射是 **推理问题**，不是固定公式。

常见 patch 路径（`{i}`=section 下标，`{t}`=table，`{r}`=row）：

| 意图 | 路径示例 |
|------|----------|
| 改展示名 | `.../rows/{r}/display/preview_primary` |
| 改价（simple） | `.../rows/{r}/display/amount_display` |
| 改价（frequency） | `.../rows/{r}/display/frequency_columns_display/once_off` 等 |
| 改价（one_off_recurring） | `.../rows/{r}/display/once_off_display` / `recurring_display` |
| 切换展示模式 | `.../fee_layout/table_style`（实例级，不改 template） |
| 改 SOW（frequency） | `.../rows/{r}/display/scope_of_work_display` |
| 改脚注 | `.../rows/{r}/display/footnotes_display` |

Patch 成功后 platform 会 **refresh 该行 display**（MDM 行在保留你已 patch 的 display 字段前提下 normalize；custom 行 normalize display 必填字段）。

**删行**不用 patch：用 **`remove_fee_rows_from_proposal_draft(skus=[...])`**。

## Required documents（knowledge category）

Template `sections[].knowledge` 指向 **category catalog**（skill reference）+ **`body_root`**（`read_knowledge` 正文）。

| 存什么 | 路径 / 说明 |
|--------|-------------|
| 客户可见清单 | `required_documents.content`（agent compose 后 patch） |
| 选型快照 | `required_documents.composition`（可选：`category`, `status`, `block_ids`, `source_snapshot`） |
| 触发规则 | **不在 draft** — skill `references/required-docs-{category}-catalog.md` |
| 泛化流程 | skill `references/required-docs-compose.md` |

`enable` 只切 `enabled`；**enable ≠ 清单已写入**。fee tables 为空时 content 应为 placeholder（`composition.status: pending_packages`）。

## Appendices（collection.blocks）

| 存什么 | 路径 / 说明 |
|--------|-------------|
| 附录区开关 | `appendices.enabled` |
| 每个附录 | `appendices.blocks[]` — 每项 `kind: markdown_block`，**必须有 `title`** |
| 正文 | `blocks/{b}/content` |
| 顺序 | `blocks` 数组顺序 = preview / 导出顺序 |

动态新增：`patch add` → `/document/sections/{i}/blocks/-`。无预置数量上限。

## Custom 行（非 MDM）

**不必单独 tool**：新增 custom 行 = **`patch_proposal_draft` 的 `add` op** 往 `tables/{t}/rows/-` 追加一行。

```json
{
  "op": "add",
  "path": "/document/sections/{i}/tables/{t}/rows/-",
  "value": {
    "id": "fee_CUSTOM_1",
    "kind": "fee_row",
    "source": { "type": "custom_service", "sku": "CUSTOM_1" },
    "display": {
      "preview_primary": "Ad-hoc advisory fee",
      "amount_display": "USD $500.00"
    }
  }
}
```

约定：

- **`source`** 仅 `{ "type": "custom_service", "sku": "CUSTOM_n" }`；sku 在 draft 内唯一（add 前 `get_proposal_draft` 扫已有 `source.sku`）。
- **`display`** 由 agent 写全（无 MDM resolve）；`preview_primary` 必填；金额字段按 template 的 `table_style` 选 simple 或 frequency 列（与 MDM 行相同）。
- 不要用 `add_services_to_proposal_draft`（那是 MDM catalog 行）。

若日后 LLM 频繁写错 row 形状，再考虑薄封装 tool；当前 **patch add 即可**。
