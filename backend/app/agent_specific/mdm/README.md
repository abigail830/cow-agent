# MDM Catalog（PostgreSQL 模拟）

> **产品目录**在 `mdm_services` / `mdm_packages`。  
> Proposal template 通过 `templates/{id}/template.yaml` 的 `catalog_filter` 选择可用 MDM 范围。

## 表

| 表 | 说明 |
|----|------|
| `mdm_services` | SKU、`pricing_type`、`price_amount`（汇总）、`fee_raw`（非 FIXED 展示）、`service_name` / `department_team` |
| `mdm_packages` | Solution Package（AU：`package_name` = `内部名*外部名`） |
| `mdm_package_services` | package ↔ SKU |

## 初始化 / 迁移

```bash
cd backend
alembic upgrade head
```

Runtime source of truth: PostgreSQL `mdm_*` tables.  
Migration snapshot fixture retained for revision 008: `app/mdm/data/bvi_catalog.json`.

Runtime proposal flows query MDM through **catalog builtin tools**
(`list_mdm_packages`, `get_mdm_package_services`, `search_mdm_services`,
`list_mdm_packages_for_services`). See `proposal-mdm-catalog` skill.

## Agent 如何读

| 需求 | 来源 |
|------|------|
| 列 template、默认 catalog filter | `templates/{id}/template.yaml` |
| 搜 SKU、列 package | `mdm_*` 产品表（MCP postgres） |
| 模版章节、placeholder | `templates/{id}/template.yaml` |
