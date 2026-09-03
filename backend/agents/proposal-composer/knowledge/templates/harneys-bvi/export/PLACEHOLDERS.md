# harneys-bvi Word export placeholders

Word 模版使用 [docxtpl](https://docxtpl.readthedocs.io/)（Jinja2 语法）。占位符须写在**同一个 Word run** 内，避免 Word 自动拆分。

> **启用导出**：在 `template.yaml` 增加 `document_export.word`，并将 branded `.docx` 保存为 `export/proposal.docx`（可参考 sg-incorp）。

## 封面 / 元信息

```
For {{ cover_for }}
{{ meta.title }}
{{ meta.date }}
```

| 字段 | 说明 |
|------|------|
| `cover_for` | `company_name` 优先，否则 `contract_name` |
| `client.company_name` | 公司名 |
| `client.contract_name` | 联系人（Introduction 里也会用到） |

## Introduction 中的占位符

Introduction 章节正文在导出前已由 platform 展开 `template.yaml` → `placeholders.introduction` 规则；Word 里直接写：

```
{{ sections.introduction }}
```

等价 token（已在 markdown 源里使用，供对照）：

| token | 来源 |
|-------|------|
| `{{client.contract_name}}` | `/facts/client/contract_name` |
| `{{selected_packages_bullet_list}}` | 已选 package  bullet 列表 |

也可在 Word 模版其他位置直接使用 context 字段：

```
{{ client.contract_name }}
{{ derived.selected_packages_bullet_list }}
```

## 章节正文

```
{{ sections.introduction }}
{{ sections.additional_info }}
```

| 占位符 | 说明 |
|--------|------|
| `sections.introduction` | Introduction（含联系人、package 列表等已展开占位符） |
| `sections.additional_info` | Additional information 静态块（`default_enabled: false`，建议加 `{% if %}`） |
| `sections.appendices` | 附录 collection（同 sg-incorp） |

> **Package solution  prose**（`blocks/solutions/PKG*.md`）在 HTML Preview 里会注入到 fee section 前；**Word 导出目前不包含** package brief 正文，需在 Word 模版中静态排版或后续扩展 context。

## Required documents（非空才展示）

`required_documents` 由 agent compose 后写入 draft；fee tables 为空时可能只有 placeholder，**应同时判断 `enabled` 和 `has_content`**。

**直接复制粘贴：**

```
{% if sections.required_documents.enabled and sections.required_documents.has_content %}
{{ sections.required_documents.title }}
{% if sections.required_documents.subdoc %}{{ sections.required_documents.subdoc }}{% else %}{{ sections.required_documents.plain }}{% endif %}
{% endif %}
```

| 占位符 | 说明 |
|--------|------|
| `sections.required_documents.enabled` | 章节是否启用（draft 里 `enabled !== false`） |
| `sections.required_documents.has_content` | 正文非空（compose 完成后为 `true`） |
| `sections.required_documents.title` | 章节标题（template.yaml：`Required documents`） |
| `sections.required_documents.subdoc` | compose 后的 markdown（GFM 表格 → Word 原生 table） |
| `sections.required_documents.plain` | 纯文本 fallback（无表格时用） |

> 不要裸写 `{{ sections.required_documents }}` —— 未 compose 或章节关闭时会出现空白块。含 `\|...\|` 表格时必须用 `subdoc`。

## 费用表（simple，2 列）

Harneys BVI 的 `table_style` 为 **`simple`**，`service_columns` 使用 **description**（不是 service_name），SOW 列关闭。

`preview_primary` = 行的 **description**（如 "Formation fee"），不是 SKU 名。

在 Word 里新建 **2 列 × 4 行** 表格。

### 表头（第 1 行）

| 第 1 列 | 第 2 列 |
|---------|---------|
| `Scope` | `Fees (US$)` |

（列标题可与 `fee_layout.amount_column_label` 保持一致。）

### 第 2 行（loop 开始，只填第 1 列）

```
{%tr for row in group.rows %}
```

### 第 3 行（数据行）

| 第 1 列 | 第 2 列 |
|---------|---------|
| `{{ row.preview_primary }}` | `{{ row.amount_display }}` |

| 字段 | 说明 |
|------|------|
| `row.preview_primary` | 服务描述（来自 `source.description` → `display.preview_primary`） |
| `row.amount_display` | 费用展示文本（如 `USD $100.00` 或 `USD $200.00 Annual`） |
| `row.once_off_display` | 也可用，simple 布局下与 amount 一致（ONE_TIME 时） |

Harneys **不展示 SOW 列**（`scope_of_work: false`），第一列只放 `preview_primary` 即可。

### 第 4 行（loop 结束，只填第 1 列）

```
{%tr endfor %}
```

### 表格外段落

Harneys 按 **department** 分组，同一 logical table 可能拆成多个 `group`（如 `Fees — Corporate`）。

```
{% if fee_tables.has_groups %}
{% for group in fee_tables.groups %}
{{ group.display_name }}

（此处放上面 2 列 × 4 行表格）

{% endfor %}
{% endif %}
```

## 脚注（aggregate）

Harneys 启用 `fee_layout.footnotes: aggregate`。表格行上的 `[1]` 由 preview 渲染；Word 模版可在所有 fee 表后追加：

```
{% if fee_tables.footnotes %}
{% for note in fee_tables.footnotes %}
[{{ note.number }}] {{ note.text }}
{% endfor %}
{% endif %}
```

## 附录（collection）

含 GFM markdown 表格时用 `{{ item.subdoc }}`：

```
{% if sections.appendices.enabled and sections.appendices.items %}
{{ sections.appendices.title }}

{% for item in sections.appendices.items %}
{{ item.title }}
{% if item.subdoc %}{{ item.subdoc }}{% else %}{{ item.plain }}{% endif %}

{% endfor %}
{% endif %}
```

## 当前限制

| 功能 | Word 导出状态 |
|------|----------------|
| Fee table（simple） | ✅ `fee_tables.groups` |
| Package solution briefs | ❌ 尚未注入 Word context |
| Required documents | ✅ `sections.required_documents.subdoc`（需 `enabled` + `has_content`） |
| Markdown GFM 表格 | ✅ appendix / required_documents 通过 `subdoc` 渲染 |
| 行内 footnote 上标 | ⚠️ Word 模版需自行排版；文末汇总可用 `fee_tables.footnotes` |

## 模版文件位置

```
export/proposal.docx
```

并在 `template.yaml` 中配置：

```yaml
document_export:
  word:
    enabled: true
    template_file: export/proposal.docx
```
