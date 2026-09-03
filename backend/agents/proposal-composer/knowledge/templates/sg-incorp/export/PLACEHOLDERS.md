# sg-incorp Word export placeholders

Word 模版使用 [docxtpl](https://docxtpl.readthedocs.io/)（Jinja2 语法）。占位符须写在**同一个 Word run** 内，避免 Word 自动拆分。

## 封面

**「For …」行（公司名优先，无公司名再用联系人）：**

```
For {{ cover_for }}
```

等价写法：

```
For {{ client.company_name or client.contract_name }}
```

| 字段 | draft 路径 | 说明 |
|------|------------|------|
| `cover_for` | 派生 | `company_name` 非空则用公司名，否则用 `contract_name`（联系人） |
| `client.company_name` | `/facts/client/company_name` | 公司名 |
| `client.contract_name` | `/facts/client/contract_name` | 联系人姓名 |

## 文档元信息

```
{{ meta.title }}
{{ meta.date }}
{{ meta.template_display_name }}
```

## 章节正文

所有 section 直接用 `{{ }}` 普通替换，Word 模版段落的样式完全由模版控制：

```
{{ sections.executive_summary }}
{{ sections.scope_of_service }}
{{ sections.solution_and_fees.intro }}
```

可以加条件判断（内容为空时跳过整段）：

```
{% if sections.scope_of_service.has_content %}
{{ sections.scope_of_service }}
{% endif %}

{% if sections.solution_and_fees.intro.has_content %}
{{ sections.solution_and_fees.intro }}
{% endif %}
```

| 占位符 | 说明 |
|--------|------|
| `{{ sections.executive_summary }}` | Executive Summary 正文（纯文本） |
| `{{ sections.scope_of_service }}` | Scope of Service 正文 |
| `{{ sections.solution_and_fees.intro }}` | Solution and Fees 简介段落 |
| `{{ sections.about_incorp }}` | About InCorp 静态正文 |
| `{{ sections.terms }}` | Terms 静态正文 |
| `{{ sections.xxx.title }}` | 任意章节标题（来自 template.yaml） |
| `{{ sections.xxx.has_content }}` | 是否有内容（用于 `{% if %}` 判断） |

## 费用表（Word 表格内 loop）

在 Word 里新建 **3 列 × 4 行** 的表格，然后 **逐格复制粘贴** 下面内容（整格选中 → 粘贴，不要手动敲标签）。

### 第 1 步：表格 4 行（每格复制一行）

**第 1 行（表头，普通文字）**

| 第 1 列 | 第 2 列 | 第 3 列 |
|---------|---------|---------|
| `Service` | `One-off` | `Recurring` |

**第 2 行（loop 开始，只填第 1 列，其余两格留空）**

第 1 列整格粘贴：

```
{%tr for row in group.rows %}
```

第 2 列、第 3 列：留空。

**第 3 行（数据行，三列各粘贴一行）**

| 第 1 列 | 第 2 列 | 第 3 列 |
|---------|---------|---------|
| 见下方「Service 列」 | `{{ row.once_off_display }}` | `{{ row.recurring_display }}` |

**Service 列（第 1 列，服务名 + SOW）**

在同一个单元格里 **分两行粘贴**（第一行服务名，第二行起是 SOW，有内容才显示）：

```
{{ row.preview_primary }}
{% if row.scope_of_work_display %}
{{ row.scope_of_work_display }}
{% endif %}
```

| 字段 | 说明 |
|------|------|
| `row.preview_primary` | 服务名（来自 `display.preview_primary`，materialize 时从 `source.service_name` 生成） |
| `row.scope_of_work_display` | SOW 正文；**仅当 MDM 有 SOW 或用户在 draft 里改过 SOW 时才有值**（见下文逻辑说明） |

> **SOW 数据逻辑（与 Preview 一致）**
>
> - `source.scope_of_work`：MDM 目录原始值，**不可 patch**。
> - `display.scope_of_work_display`：Preview / Word **实际读取**的 SOW。
> - 添加服务行时，platform 会把 `source.scope_of_work` **自动复制**到 `display.scope_of_work_display`（若 catalog 有 SOW）。
> - 若 catalog 里 SOW 为空（如 Transfer in 截图里 `scope_of_work: null`），则 `display` 里也没有 `scope_of_work_display`，Word 只显示服务名。
> - 用户改 SOW 时 patch 的是 `display/scope_of_work_display`，不是 `source`。

**第 4 行（loop 结束，只填第 1 列，其余两格留空）**

第 1 列整格粘贴：

```
{%tr endfor %}
```

第 2 列、第 3 列：留空。

### 第 2 步：表格外段落（包住「标题 + 上面那张表」）

在表格**上方**新建 3 个段落，在表格**下方**新建 1 个段落，按顺序粘贴：

**段落 1（有费用才显示整段）**

```
{% if fee_tables.has_groups %}
```

**段落 2（每个 package 循环开始）**

```
{% for group in fee_tables.groups %}
```

**段落 3（package 标题，如 ACCOUNTING AND FINANCE）**

```
{{ group.display_name }}
```

**→ 紧接着放第 1 步那张 4 行表格 ←**

**段落 4（每个 package 循环结束）**

```
{% endfor %}
```

**段落 5（有费用才显示整段 — 结束）**

```
{% endif %}
```

### 完整结构一览（对照检查用）

```
{% if fee_tables.has_groups %}
{% for group in fee_tables.groups %}
{{ group.display_name }}

┌─────────────────┬─────────┬───────────┐
│ Service         │ One-off │ Recurring │  ← 第 1 行表头
├─────────────────┼─────────┼───────────┤
│ {%tr for ... %} │         │           │  ← 第 2 行，仅第 1 格有字
├─────────────────┼─────────┼───────────┤
│ {{ row.... }}   │ {{ ... }}│ {{ ... }}│  ← 第 3 行数据
├─────────────────┼─────────┼───────────┤
│ {%tr endfor %}  │         │           │  ← 第 4 行，仅第 1 格有字
└─────────────────┴─────────┴───────────┘

{% endfor %}
{% endif %}
```

### 粘贴时注意

- 每个 `{%tr ... %}`、`{{ ... }}` 必须 **一次性粘贴进单元格**，不要被 Word 拆成多段（可先关拼写检查，或用「粘贴为纯文本」）。
- **禁止**把 `{%tr for %}` 和 `{%tr endfor %}` 写在第 3 行数据行的同一行里。
- **禁止**在表格外写 `{% for row in group.rows %}`（那样不会复制表格行）。

### 首票表（4 列，同样 4 行结构）

新建 **4 列 × 4 行** 表格，表格外段落：

**段落（在表格上方，按顺序）**

```
{% if sections.first_invoice.enabled and first_invoice.has_rows %}
{{ sections.first_invoice.title }}
```

**表格 4 行**

| 行 | 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 |
|----|---------|---------|---------|---------|
| 表头 | `Description` | `Price` | `Tax` | `Total` |
| loop 开始 | `{%tr for row in first_invoice.rows %}` | （空） | （空） | （空） |
| 数据 | `{{ row.description }}` | `{{ row.price_display }}` | `{{ row.tax_display }}` | `{{ row.total_display }}` |
| loop 结束 | `{%tr endfor %}` | （空） | （空） | （空） |

**段落（在表格下方）**

```
Subtotal: {{ first_invoice.subtotal_display }}
{{ first_invoice.tax_label }}: {{ first_invoice.tax_display }}
Total: {{ first_invoice.total_display }}
{% endif %}
```

## 附录（可选）

`appendices` 是 **collection**：父级一个总标题，每个子块有自己的标题和正文。

**标准配置（总标题 + 逐条 appendix）**

正文含 **GFM markdown 表格** 时用 `{{ item.subdoc }}`（渲染为 Word 原生表格）；纯文本也可用 `{{ item.plain }}`。

```
{% if sections.appendices.enabled and sections.appendices.items %}
{{ sections.appendices.title }}

{% for item in sections.appendices.items %}
{{ item.title }}
{% if item.subdoc %}{{ item.subdoc }}{% else %}{{ item.plain }}{% endif %}

{% endfor %}
{% endif %}
```

分页用 Word 模版里的物理分页符（在循环体末尾手动 Ctrl+Enter 插入分页段落），或：

```
{% for item in sections.appendices.items %}
{{ item.title }}
{% if item.subdoc %}{{ item.subdoc }}{% else %}{{ item.plain }}{% endif %}
{% if not loop.last %}
（此处在 Word 里插入分页符段落）
{% endif %}
{% endfor %}
```

| 占位符 | 说明 |
|--------|------|
| `sections.appendices.enabled` | 整个 Appendices 是否启用 |
| `sections.appendices.items` | 已启用且有内容的子块列表 |
| `item.title` | 子块标题（如 `"Appendix A — Required documents"`） |
| `item.subdoc` | 子块正文（GFM 表格 → Word 原生 table；段落仍为纯文本） |
| `item.plain` | 子块正文纯文本 fallback（无 markdown 表格时用） |
| `item.page_break_after` | 是否在该块后分页（最后一个为 `false`） |

## 模版文件位置

将 branded `.docx` 保存为：

`export/proposal.docx`

（与 `template.yaml` 中 `document_export.word.template_file` 一致。）
