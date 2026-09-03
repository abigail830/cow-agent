---
name: yl-supply-chain-analytics
description: 伊利奶粉分仓补货供应链只读分析：全国/分仓供需缺口、库存天数、计划达成、大日期与在途、仓间均衡、调拨追溯。用户问缺货、压仓、补货、分货、库存监控、DOS、发货缺口、全国货源、基地仓可分配量、横向调拨时使用。只读 YL 库；回复语言跟随用户。
---

# 伊利奶粉供应链分析

## 写 SQL 的默认策略

1. **先对路由表选数据源**，再 **复制对应 Few-shot**，只改 `product_code`、仓名、`adjust_date`——不从零拼表名/列名。
2. **默认表**：全国 → `yl_national_sales_warehouse_inventory_report`；基地 → `yl_base_warehouse_inventory_report`；分仓 → `yl_sales_warehouse_inventory_report`。
3. **下钻再用**：`yl_spot_inventory`、`yl_transit_inventory`、`yl_forward_transfer`、`yl_lateral_transfer`、`yl_sales_plan`、`yl_actual_sales`。
4. **最新快照**：`adjust_date = (SELECT MAX(adjust_date) FROM …)`；跨表 JOIN 对齐同一业务日。
5. **结构不明时**：用 `list_tables` / `describe_table` / `get_schema` 核实；**表名只取自下文「表清单」或 MCP 返回值**。
6. **`query_data` 只提交一条只读查询**：以 `SELECT` 或 `WITH` 开头、无第二条语句、无分号串联；探库不走 `query_data`。
7. **失败即改、不得停轮**：工具报错后在本轮继续——对照报错修正 SQL 形态并重试，或向用户说明；不因单次 `query_data` 失败结束回合。

### 业务问题 → 数据源（先选表，再写 SQL）

| 用户关心 | 用这张表 | 直接可用的字段 / 算法 |
|----------|----------|------------------------|
| 分仓缺口、库存天数、预警分级 | `yl_sales_warehouse_inventory_report` | `ship_gap`, `order_gap`, `dos_days`（见指标词典公式） |
| 全国货源、总缺口 | `yl_national_sales_warehouse_inventory_report` | 同上（汇总口径） |
| **计划达成 / 销售完成率 / 订单完成率** | **`yl_sales_warehouse_inventory_report` 或 `yl_national_*`** | **`plan_num`, `sell_num`, `out_put_num`, `sell_completion_rate`, `order_completion_rate`** |
| 跨月计划输入、计划调整 | `yl_sales_plan` | `plan_year`, `plan_month`, `plan_num`, `avg_plan_num` |
| 月度实销归档、渠道实绩 | `yl_actual_sales` | `sell_num`, `out_put_num`, `unshipped_orders`, `sell_year`, `sell_month` |
| 基地可发、正向补货 | `yl_base_warehouse_inventory_report` + `yl_forward_transfer` | `from_store_num_h`, `from_available` |
| 横向 / 正向调拨追溯 | `yl_lateral_transfer`, `yl_forward_transfer` | `trans_num`, `reason`, `adjust_date` |
| 批次库龄、大日期 | `yl_spot_inventory`, `yl_big_date_inventory` | `produce_date`, `big_date_num` |

**计划达成没有单独汇总表**——完成率在监控报表里已算好；跨月对比用 `yl_sales_plan` + 报表或 `yl_actual_sales` JOIN，见 [demand-fulfillment.md](references/demand-fulfillment.md)。

### `query_data` 提交形态（每次调用前对照）

| 步骤 | 做法 |
|------|------|
| 探有哪些表 / 列 | `list_tables` → `describe_table` / `get_schema` |
| 取数 | `query_data` 传入 **一条** 以 `SELECT` 或 `WITH` 开头的 SQL |
| 复杂分析 | 用 `WITH … AS (SELECT …)` 包在同一个 `SELECT` 里，不要拆成多条语句 |
| 需要 LIMIT | 可写 `LIMIT n`；平台也会自动封顶 |

### 工具形态（易错点 · 原则）

- **参数是裸 SQL 字符串**，不是 markdown；不要把代码围栏（```sql）或说明文字传给 `query` 参数。
- **每个 Few-shot / reference 代码块 = 一次 `query_data`**；文档里连续多个块时，分次调用，禁止一次粘贴多段。
- **首 token 必须是 `SELECT` 或 `WITH`**；探 schema 用 MCP 元数据工具，不用 `query_data` 试探。
- **报错「Only SELECT…」** → 检查是否多语句、空 query、非 SELECT 开头或把注释/说明当成了 query；回到 Skill 复制单条 Few-shot 再试。

## 指标词典

| 业务名 | 来源 | 口径说明 |
|--------|------|----------|
| 合格现货 / 可发量 | 列 `from_store_num_h` | 销售仓/基地报表；明细表用 `store_num`（`status='合格'`）或 `invetory_deduct_sum`（抵扣后） |
| 待检现货 | 列 `from_store_num_d` | 不可计入可发 |
| 在途 | 列 `from_store_transit`（报表）或 `store_transit`（`yl_transit_inventory`） | 含待检+合格在途 |
| 未发订单 | 列 `total_unship`（报表）或 `unshipped_orders`（`yl_actual_sales`） | 同一概念，**表不同、列名不同** |
| 发货缺口 | 列 `ship_gap` | 报表已算：现货 − 未发 |
| 订单缺口 | 列 `order_gap` | 报表已算：现货 + 在途 − 未发 |
| 日均计划 | 列 `avg_plan_num`、`next_avg_plan_num` | 件/天 |
| 月计划 / 销量 / 出库 | 列 `plan_num`、`sell_num`、`out_put_num` | 当月累计 |
| 近 14 日需求 | **计算** `avg_plan_num * 14` | `AS demand_14d` |
| 近 7 日需求 | **计算** `avg_plan_num * 7` | 紧急窗口 |
| **库存天数 DOS** | **计算**，表内无列 | `(COALESCE(from_store_num_h,0)+COALESCE(from_store_transit,0))/NULLIF(avg_plan_num,0) AS dos_days`；对用户称「库存天数」 |
| 可调拨量 | **计算** | `from_store_num_h - COALESCE(total_unship, 0)` |
| 基地可分配量 | 列 `from_available`（`yl_forward_transfer`） | 正向调拨上限参考 |
| 销售/订单完成率 | 列 `sell_completion_rate`、`order_completion_rate` | 字符串 `'88.5%'`；排序用 `REPLACE(col,'%','')::numeric` |
| 大日期数量 | 列见 Schema 附录「大日期按表」 | 全国表用 `xs_big_date_num` / `jd_big_date_num`，不是 `big_date_num` |
| 区域/电商出货 | 列 `out_put_area`、`out_put_ec` | 渠道结构 |
| 库龄（批次） | **计算** | `ds::date - produce_date`（`yl_spot_inventory`） |

**缺口分级（默认阈值）**：

| 级别 | 条件 |
|------|------|
| 红 / 紧急 | 现货+在途 < 7 日需求 **且** `dos_days` < 7 |
| 黄 / 偏低-常规补货 | `dos_days` 7–14 |
| 蓝 / 压仓 | `dos_days` > 60 |

## Few-shot

### 1. 各销售分仓最新快照（最常用）

```sql
SELECT
  s.adjust_date,
  s.from_site_name,
  s.product_code,
  s.product_name,
  s.from_store_num_h,
  s.from_store_transit,
  s.total_unship,
  s.ship_gap,
  s.order_gap,
  s.avg_plan_num,
  s.plan_num,
  s.sell_num,
  s.out_put_num,
  s.sell_completion_rate,
  s.big_date_num,
  CASE WHEN s.avg_plan_num > 0
       THEN (COALESCE(s.from_store_num_h, 0) + COALESCE(s.from_store_transit, 0)) / s.avg_plan_num
       END AS dos_days
FROM yl_sales_warehouse_inventory_report s
WHERE s.adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND s.product_code = 'MOCK_YLP001'
ORDER BY dos_days ASC NULLS FIRST;
```

### 2. 计划 vs 实销 / 完成率（用户问「达成」「完成率」时用）

```sql
SELECT
  s.adjust_date,
  s.from_site_name,
  s.plan_num,
  s.sell_num,
  s.out_put_num,
  s.total_unship,
  s.sell_completion_rate,
  s.order_completion_rate,
  s.out_put_area,
  s.out_put_ec
FROM yl_sales_warehouse_inventory_report s
WHERE s.adjust_date = (SELECT MAX(adjust_date) FROM yl_sales_warehouse_inventory_report)
  AND s.product_code = 'MOCK_YLP001'
  AND s.from_site_code = 'MOCK_WH_S03'   -- 按用户指定仓替换；全国则改查 yl_national_* 并去掉 site 条件
ORDER BY s.from_site_name;
```

### 3. 全国大盘

```sql
SELECT
  n.adjust_date,
  n.product_name,
  n.from_store_num_h,
  n.from_store_transit,
  n.total_unship,
  n.ship_gap,
  n.order_gap,
  n.avg_plan_num,
  n.avg_plan_num * 14 AS demand_14d,
  CASE WHEN n.avg_plan_num > 0
       THEN (COALESCE(n.from_store_num_h, 0) + COALESCE(n.from_store_transit, 0)) / n.avg_plan_num
       END AS dos_days,
  n.xs_big_date_num,
  n.jd_big_date_num
FROM yl_national_sales_warehouse_inventory_report n
WHERE n.adjust_date = (SELECT MAX(adjust_date) FROM yl_national_sales_warehouse_inventory_report)
  AND n.product_code = 'MOCK_YLP001';
```

### 4. 更多场景（整段复制，勿改列名）

| 意图 | 文件 |
|------|------|
| 缺口分级、全国供需 | [supply-demand-gaps.md](references/supply-demand-gaps.md) |
| 计划达成、未发、推式/拉式 | [demand-fulfillment.md](references/demand-fulfillment.md) |
| 大日期、库龄、待检结构 | [inventory-freshness.md](references/inventory-freshness.md) |
| 仓间对比、调拨配对 | [cross-warehouse-balance.md](references/cross-warehouse-balance.md) |
| JOIN、快照对齐、系列聚合 | [drilldown-joins.md](references/drilldown-joins.md) |
| **调拨 / 分货多方案** | Skill **`yl-transfer-planning`**（本 Skill 只做缺口识别） |

## 分析原则

1. **供需先于库存**：先看需求窗口内缺口，再看绝对库存。
2. **分层**：全国 → 基地 → 分仓 → 批次。
3. **动静态结合**：现货 + 在途 + 计划/销量 → 库存天数与缺口。
4. **新鲜度同等重要**：大日期、待检与缺货并列关注。

## 执行与输出

1. 理解范围 → **业务路由表选表** → 复制 Few-shot 或 `read_skill_resource` → **`query_data` 单条 SELECT**
2. 对用户：业务语言，**不出现**表名/列名/SQL（见 `system_prompt.md`）
3. 可视化默认不出图；分仓排名 ≥5 行且含 `dos_days` 时用 `intent=ranking`

---

## 附录：Schema 与表结构

### 表清单（`yl_` 前缀）

| 表 | 用途 | 时间键 |
|----|------|--------|
| `yl_sales_warehouse_inventory_report` | **分仓监控（默认）** | `adjust_date` |
| `yl_national_sales_warehouse_inventory_report` | **全国监控** | `adjust_date` |
| `yl_base_warehouse_inventory_report` | 基地监控 | `adjust_date` |
| `yl_sales_plan` | 月计划 | `ds`, `plan_year`, `plan_month` |
| `yl_actual_sales` | 月实绩 | `ds`, `sell_year`, `sell_month` |
| `yl_spot_inventory` | 批次现货 | `ds`, `produce_date` |
| `yl_transit_inventory` | 在途流向 | `ds` |
| `yl_big_date_inventory` | 大日期清单 | — |
| `yl_forward_transfer` / `yl_lateral_transfer` | 正向 / 横向调拨 | `adjust_date` |
| `yl_product` / `yl_warehouse` | 主数据 | — |
| `yl_wms_waybill` / `yl_tms_gps` | 物流辅助 | — |

### JOIN 与对齐

- 键：`product_code`；仓 `from_site_code`（报表）或 `site_code`（计划/现货/warehouse）
- `yl_warehouse.site_type`：`0` 基地仓，`1` 销售分仓
- 报表 `adjust_date` ≈ 明细 `ds`（同一业务日再 JOIN）

### 销售分仓报表常用列

`yl_sales_warehouse_inventory_report`：`adjust_date`, `from_site_code`, `from_site_name`, `product_code`, `product_name`, `pro_series`, `from_store_num_h`, `from_store_num_d`, `from_store_transit`, `total_unship`, `ship_gap`, `order_gap`, `avg_plan_num`, `next_avg_plan_num`, `plan_num`, `sell_num`, `out_put_num`, `sell_completion_rate`, `order_completion_rate`, `big_date`, `big_date_num`, `out_put_area`, `out_put_ec`

### 全国报表差异

`yl_national_sales_warehouse_inventory_report`：汇总列名同分仓表，但**无** `from_site_name`；大日期用 `xs_big_date_num`、`jd_big_date_num`（**无** `big_date_num`）

### 基地 / 明细 / 实绩

| 表 | 常用列 |
|----|--------|
| `yl_base_warehouse_inventory_report` | `from_site_code`, `from_store_num_h/d`, `from_store_transit`, `month_store_in`, `now_store_in` |
| `yl_spot_inventory` | `site_code`, `ds`, `produce_date`, `status`, `store_num`, `invetory_deduct_sum` |
| `yl_transit_inventory` | `from_site_code`, `to_site_code`, `ds`, `store_transit`, `remark` |
| `yl_actual_sales` | `sell_num`, `out_put_num`, `unshipped_orders`, `sell_year`, `sell_month` |

### 大日期字段按表

| 表 | 列 |
|----|-----|
| `yl_sales_warehouse_inventory_report` | `big_date`, `big_date_num` |
| `yl_national_sales_warehouse_inventory_report` | `xs_big_date`, `xs_big_date_num`, `jd_big_date`, `jd_big_date_num` |
| `yl_base_warehouse_inventory_report` | `big_date`, `big_date_num` |
| `yl_big_date_inventory` | `big_date_num` |

### 分析维度

地理（全国/分仓/基地/流向）· 品项（`product_code`, `pro_series`, `brand`）· 时间（快照日/计划月/批次生产日期）· 供需（缺口、完成率、14/7 日窗口）· 结构（合格/待检/大日期/渠道出货）· 执行（调拨单）

### 惯例

- 常规分析忽略礼盒列 `*_lh_*`
- Mock 品编码 `MOCK_YLP*`
- 最新快照：`SELECT MAX(adjust_date) FROM yl_national_sales_warehouse_inventory_report`
