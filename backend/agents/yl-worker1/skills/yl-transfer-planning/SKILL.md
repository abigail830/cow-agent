---
name: yl-transfer-planning
description: 伊利奶粉分仓补货调拨方案设计：基于缺口与备货率生成横向/正向调拨建议，支持时效优先、成本最优、新鲜度对冲、全网均衡等多策略对比。用户问调拨方案、补货分配、分货计划、备货率排序、多方案对比、横向调拨建议、基地直发建议时使用。只读 YL 库；回复语言跟随用户。
---

# 调拨 / 分货方案设计

## 与分析 Skill 的分工

| Skill | 何时用 |
|-------|--------|
| `yl-supply-chain-analytics` | 先看**够不够、谁缺谁压、缺口分级**（步骤 1 全景识别） |
| **本 Skill** | 在缺口清楚后，产出**可执行的调拨 / 正向补货方案**（步骤 2 优先级与分配量），支持**多策略并列对比** |

用户只问「全国够吗 / 哪些仓红灯」→ 用 analytics；用户问「怎么调 / 给几个方案 / 分多少」→ **load 本 Skill**（必要时两个 Skill 都用）。

## 触发与策略选择

**用户指定了侧重点**（如「时效优先」「成本最低」「把大日期洗掉」）→ 只出 **1 个主方案 + 可选 1 个对照**。

**用户未指定** → 默认出 **2–4 个命名方案**供对比，至少覆盖：

1. **时效与服务率优先**
2. **全网备货率均衡**（截图步骤 2 默认逻辑）
3. **新鲜度对冲**
4. **成本优化**（若路线/运费数据可查）

每个方案须说明：**优化目标、主要路径（基地→销仓 / 销仓→销仓）、取舍、不适用条件**。

策略维度全集与扩展脑暴见 [strategy-dimensions.md](references/strategy-dimensions.md)。

## 共享指标（算方案前统一口径）

| 指标 | 公式（SQL 侧） | 业务白话 |
|------|----------------|----------|
| **生产备货率** | `(from_store_num_h + from_store_transit + out_put_num) / NULLIF(plan_num,0)` | 本月进销存覆盖度；**均衡方案的核心** |
| **简化备货率**（均衡近似） | `(from_store_num_h + from_store_transit) / NULLIF(plan_num,0)` | 用户口语「库存+在途 / 月计划」 |
| **库存天数 DOS** | `(from_store_num_h + from_store_transit) / NULLIF(avg_plan_num,0)` | 还能卖几天 |
| **可调拨盈余** | `from_store_num_h - COALESCE(total_unship,0)` | 横向调出上限（未扣安全水位） |
| **安全水位** | `avg_plan_num * {7\|14}`（默认 **14 日**） | 调出仓必须保留的底仓 |
| **可转出量** | `GREATEST(0, from_store_num_h + from_store_transit - safety_stock - total_unship)` | 均衡方案只用富余量 |
| **调入需求缺口** | `GREATEST(0, -order_gap)` 或 `total_unship` 超可发部分 | 时效方案优先满足 |
| **运输时效** | 从 `yl_transit_inventory.remark` 解析「预计 N 天」；无则查历史 `yl_lateral_transfer` / `yl_forward_transfer` | 天数越短越优先 |
| **运费档** | remark 中 `运费档:低/中/高` | 成本方案排序用 |
| **大日期压力** | `big_date_num / NULLIF(from_store_num_h,0)` | 新鲜度方案排序用 |
| **库龄** | `yl_spot_inventory`: `ds::date - produce_date` | 批次级新鲜度下钻 |

详细推导与各策略专用算法见 [allocation-calcs.md](references/allocation-calcs.md)。

## 工作流程

```
- [ ] 1. 澄清：品项(product_code)、范围(全国/区域/单仓对)、策略(指定 or 多方案)
- [ ] 2. 拉快照：复制 [data-queries.md](references/data-queries.md) 中「方案输入包」SQL
- [ ] 3. 识别调入池 / 调出池（红黄牌调入；蓝牌或高备货率调出，受安全水位约束）
- [ ] 4. 按策略分别算：路径 → 优先级 → 建议件数 → 调拨后备货率/DOS
- [ ] 5. 校验：调出后调出仓 DOS≥安全天数；调入后 order_gap 改善；总量守恒
- [ ] 6. 输出：多方案对比表 + 每方案明细 + 需业务确认项
```

**查数规范**（与 analytics Skill 一致）：表名取自 Skill 附录或 `list_tables`；`query_data` **仅一条** `SELECT`/`WITH`；探结构用 `describe_table`。

**工具形态（原则）**：

- [data-queries.md](references/data-queries.md) 中**每个** SQL 代码块 = **一次** `query_data`（如「方案输入包」「基地可分配」「在途路线」分三次），禁止合并。
- 传给工具的 `query` 是裸 SQL，不含 markdown 围栏；失败则读报错改形态重试，**本轮必须**继续查数或向用户说明，不得静默结束。
- 大日期调拨：先用 analytics / `inventory-freshness` 看清源仓压力与全网缺口，再跑本 Skill 的「方案输入包」做分配。

## 调拨类型决策

| 情况 | 优先动作 |
|------|----------|
| 销仓 🔴 且基地有 `from_available` / 基地现货 | **正向** 基地 → 销仓 |
| 全国够、结构失衡（一仓压一仓缺） | **横向** 盈余销仓 → 缺口销仓 |
| 大日期在低速仓、缺口在高速仓 | **横向** 旧货出、**正向** 新货进（新鲜度方案） |
| 调出仓调后 DOS < 7 天 | **禁止调出** 或减量 |

路径与运费见 [data-queries.md](references/data-queries.md) 在途 remark；历史单见 `yl_lateral_transfer` / `yl_forward_transfer`。

## 方案输出模板（用户可见 · 业务语言）

```markdown
## 摘要
- 快照日：… · 品项：… · 共 N 套方案供对比

## 方案 A：<策略名，如「时效与服务率优先」>
**目标**：…
**适用**：…

| 序号 | 调出 | 调入 | 建议量(件) | 预计到达 | 调出后备货率→ | 调入后备货率→ | 说明 |
|-----|------|------|-----------|---------|--------------|--------------|------|
| 1 | … | … | … | …天 | …%→…% | …%→…% | … |

**方案要点**（2–3 条）· **风险/取舍**：…

## 方案 B：…
（同上）

## 方案对比（决策用）
| 维度 | 方案 A | 方案 B | … |
|------|--------|--------|---|
| 覆盖紧急缺口仓数 | | | |
| 总调拨件数 | | | |
| 预估总运费档 | | | |
| 大日期消化贡献 | | | |
| 备货率离散度(标准差) | | | |

## 建议首选
…（说明在什么业务偏好下选哪套）

## 需业务确认
- [ ] …
```

正文**禁止**表名/SQL；数字与百分比可展示。

## 默认多方案算法速查

| 方案 | 排序键 | 分配量启发式 |
|------|--------|--------------|
| **时效优先** | 调入仓 `order_gap` 升序 × 路线 lead_days 升序 | `MIN(缺口, 调出可转, 在途可衔接)` |
| **均衡优先** | 调入仓备货率升序；调出仓备货率降序 | 迭代：把调出 **可转出量** 分配给最缺仓，使各仓备货率向 **全网加权平均** 靠拢 |
| **新鲜度** | 调出：`big_date_num` 降序；调入：`sell_num/plan_num` 降序 | 优先移出大日期；调入侧用基地正向补 **低库龄**（`spot_inventory` 最新批次） |
| **成本优先** | 运费档 低→高；同档按距离 remark km | 同均衡但限制 **仅低/中档** 路线，不足再升档 |

完整伪代码与边界见 [allocation-calcs.md](references/allocation-calcs.md)。

## Reference 索引

| 文件 | 内容 |
|------|------|
| [strategy-dimensions.md](references/strategy-dimensions.md) | 策略维度脑暴、指标、适用场景 |
| [allocation-calcs.md](references/allocation-calcs.md) | 各策略计算步骤与校验 |
| [data-queries.md](references/data-queries.md) | 方案输入 SQL、路线、历史调拨 |
