# au-advisory Word export placeholders

Word 模版使用 [docxtpl](https://docxtpl.readthedocs.io/)（Jinja2 语法）。占位符须写在**同一个 Word run** 内，避免 Word 自动拆分。

> **启用导出**：在 `template.yaml` 增加 `document_export.word`，并将 branded `.docx` 保存为 `export/proposal.docx`（可参考 sg-incorp）。

## 封面 / 元信息

```
For {{ cover_for }}
{{ meta.title }}
{{ meta.date }}
{{ meta.template_display_name }}
```

| 字段 | 说明 |
|------|------|
| `cover_for` | `company_name` 优先，否则 `contract_name` |
| `client.company_name` | 公司名 |
| `client.contract_name` | 联系人 |

## 章节正文

```
{{ sections.introduction }}
{{ sections.solution_and_fees.intro }}
{{ sections.payment_options }}
{{ sections.terms }}
```

| 占位符 | 说明 |
|--------|------|
| `sections.introduction` | About Incorp 静态正文 |
| `sections.solution_and_fees.intro` | Solution and fees 简介 |
| `sections.payment_options` | Fee summary 章节 intro（`sections.payment_options.intro`）；汇总表见下方 **Payment options** |
| `sections.terms` | Terms 静态正文 |
| `sections.credentials` | Credentials collection（若有启用 blocks） |
| `sections.appendices` | 同 sg-incorp 附录写法 |

条件判断示例：

```
{% if sections.solution_and_fees.intro.has_content %}
{{ sections.solution_and_fees.intro }}
{% endif %}
```

## 费用表（frequency_columns，6 列）

AU advisory 的 `table_style` 为 **`frequency_columns`**：Service + Monthly / Quarterly / Annual / Once-off + Total。

在 Word 里新建 **6 列 × 4 行** 表格，逐格复制粘贴。

### 表头（第 1 行）

| 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 | 第 5 列 | 第 6 列 |
|---------|---------|---------|---------|---------|---------|
| `Service` | `Monthly` | `Quarterly` | `Annual` | `Once-off` | `Total` |

### 第 2 行（loop 开始，只填第 1 列）

```
{%tr for row in group.rows %}
```

### 第 3 行（数据行）

| 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 | 第 5 列 | 第 6 列 |
|---------|---------|---------|---------|---------|---------|
| 见下方 Service 列 | `{{ row.frequency_columns_display.monthly }}` | `{{ row.frequency_columns_display.quarterly }}` | `{{ row.frequency_columns_display.annual }}` | `{{ row.frequency_columns_display.once_off }}` | `{{ row.display.total_display }}` |

**Service 列（服务名 + SOW）** — 同一单元格内分两行粘贴：

```
{{ row.preview_primary }}
{% if row.scope_of_work_display %}
{{ row.scope_of_work_display }}
{% endif %}
```

| 字段 | 说明 |
|------|------|
| `row.preview_primary` | 服务名（`service_columns.service_name: true`） |
| `row.scope_of_work_display` | SOW；catalog 有 SOW 时 materialize 自动写入 display，否则为空 |
| `row.frequency_columns_display.*` | 各频率列展示价（已含 `AUD $` 格式） |
| `row.display.total_display` | 年化合计 |

### 第 4 行（loop 结束，只填第 1 列）

```
{%tr endfor %}
```

### 表格外段落（包住标题 + 表格）

```
{% if fee_tables.has_groups %}
{% for group in fee_tables.groups %}
{{ group.display_name }}

（此处放上面 6 列 × 4 行表格）

{% endfor %}
{% endif %}
```

### 粘贴注意

- 使用 `{%tr for %}` / `{%tr endfor %}`，**不要**在表格外写 `{% for row in group.rows %}`。
- 每个标签 **一次性粘贴进单元格**，不要被 Word 拆 run。
- 字段名是 `once_off`（下划线），不是 `one_off`。

## Payment options（Fee summary，6 列）

章节需在 draft 中 **启用** `payment_options`。数据来自 `payment_options` context（与 HTML preview 同源，由 fee table 各 group 汇总）。

### 表格外段落（intro + 多 option 循环）

```
{% if sections.payment_options.enabled and payment_options.has_options %}
{% if sections.payment_options.intro.has_content %}
{{ sections.payment_options.intro }}

{% endif %}
{% for option in payment_options.options %}
{{ option.label }}

（此处放下面 6 列 × 4 行表格）

Once-Off Fees: {{ option.summary.once_off_total_display }}
Annualised Total Fees: {{ option.summary.recurring_annualized_total_display }}

{% endfor %}
{% endif %}
```

### 表头（第 1 行）

| 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 | 第 5 列 | 第 6 列 |
|---------|---------|---------|---------|---------|---------|
| `Option` | `Monthly Fees` | `Quarterly Fees` | `Annual Fees` | `Once-Off Fees` | `Total Fees (Annualised)` |

### 第 2 行（loop 开始，只填第 1 列）

```
{%tr for row in option.rows %}
```

### 第 3 行（数据行）

| 第 1 列 | 第 2 列 | 第 3 列 | 第 4 列 | 第 5 列 | 第 6 列 |
|---------|---------|---------|---------|---------|---------|
| `{{ row.label }}` | `{{ row.monthly_display }}` | `{{ row.quarterly_display }}` | `{{ row.annual_display }}` | `{{ row.once_off_display }}` | `{{ row.total_display }}` |

| 字段 | 说明 |
|------|------|
| `row.label` | fee table group 标题（如 `Setup of Xero`） |
| `row.*_display` | 各列金额，已含 `AUD $` 格式；无值时为空 |
| `option.summary.once_off_total_display` | 汇总行：一次性费用合计 |
| `option.summary.recurring_annualized_total_display` | 汇总行：年化 recurring 合计 |

### 第 4 行（loop 结束，只填第 1 列）

```
{%tr endfor %}
```

### 粘贴注意

- 外层用 `{% for option in payment_options.options %}`；表格行内用 `{%tr for row in option.rows %}`。
- 每个 option 可单独放一张表 + 两行汇总（Once-Off / Annualised Total）。
- 与 fee table 相同：标签须在同一 run 内一次性粘贴。

## 附录（collection）

与 sg-incorp 相同：

```
{% if sections.appendices.enabled and sections.appendices.items %}
{{ sections.appendices.title }}

{% for item in sections.appendices.items %}
{{ item.title }}
{{ item.plain }}

{% endfor %}
{% endif %}
```

## 当前限制

| 功能 | Word 导出状态 |
|------|----------------|
| Fee table（frequency_columns） | ✅ `fee_tables.groups` |
| Payment options 汇总表 | ✅ `payment_options.options` |
| Credentials collection | ⚠️ 仅 `sections.credentials` 正文，无专用表格 context |

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
