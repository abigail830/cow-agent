# 各策略分配计算

## 0. 公共输入（每仓一行）

从 `yl_sales_warehouse_inventory_report` 最新快照取：

```
plan_num, avg_plan_num, from_store_num_h, from_store_transit, out_put_num,
total_unship, ship_gap, order_gap, big_date_num, sell_completion_rate
```

派生列（可在 SQL 或解读中算）：

```sql
stock_prep_rate_full AS (from_store_num_h + from_store_transit + out_put_num) / NULLIF(plan_num, 0),
stock_prep_rate_simple AS (from_store_num_h + from_store_transit) / NULLIF(plan_num, 0),
dos_days AS (from_store_num_h + from_store_transit) / NULLIF(avg_plan_num, 0),
available_lateral AS GREATEST(0, from_store_num_h - COALESCE(total_unship, 0)),
safety_stock AS avg_plan_num * 14,  -- 可调
transferable_surplus AS GREATEST(
  0,
  from_store_num_h + from_store_transit - (avg_plan_num * 14) - COALESCE(total_unship, 0)
),
inbound_need AS GREATEST(0, -order_gap),
urgency AS COALESCE(total_unship, 0) + GREATEST(0, -order_gap)
```

**调入池**：`order_gap < 0` OR `dos_days < 7` OR `ship_gap < 0`（🔴/🟡）

**调出池**：`transferable_surplus > 0` OR (`dos_days > 45` AND `order_gap > 0`)（盈余/🔵）

---

## 1. 时效与服务率优先

**排序**

1. 调入仓：`urgency DESC`, `dos_days ASC NULLS FIRST`
2. 对每个调入仓，候选调出/基地：`lead_days ASC`（见 data-queries 路线表）
3. 同 lead_days：`transferable_surplus DESC`

**分配量**（单条建议）

```
qty = MIN(
  inbound_need,           -- 或 total_unship 若更紧
  transferable_surplus,   -- 横向
  from_available          -- 正向，基地
)
```

**调拨后备货率**（展示用）

```
to_rate_after = (to_h + to_t + to_out + qty) / to_plan
from_rate_after = (from_h + from_t + from_out - qty) / from_plan
```

优先输出 **3–5 条** 能解 🔴 的最短路径；不解 🟡 也可接受若用户要「极快」。

---

## 2. 全网备货率均衡

**目标备货率**（默认）

```
target_rate = SUM(from_store_num_h + from_store_transit) / SUM(plan_num)
```

**迭代分配**（贪心，可在回复中描述为「向 target 靠拢」）

1. 找备货率最低调入仓 `to`（且低于 target − 2pp）
2. 找备货率最高调出仓 `from`（高于 target + 2pp）且 `transferable_surplus > 0`
3. `qty = MIN(transferable_surplus, (target - to_rate) * to_plan)`，上限 `(from_rate - target) * from_plan` 对应件数
4. 更新虚拟库存，重复直到无 🔴 或无可转出量

**展示**：各仓 **调拨前/后备货率**、与 target 偏差。

---

## 3. 新鲜度对冲

**阶段 A — 横向洗大日期**

- 调出：`big_date_num DESC`, `sell_num/plan_num ASC`
- 调入：`sell_num/plan_num DESC`, `dos_days ASC`（有消化能力）
- `qty = MIN(from.big_date_num, to.inbound_need * 0.5, transferable_surplus)` — 大日期货优先，不超过缺口一半防二次压仓

**阶段 B — 正向补新货**

- 查 `yl_spot_inventory` 最新 `produce_date` 批次在基地的可发量
- 偏远/低 DOS 仓：`qty = MIN(base_available, inbound_need - 阶段A已分配)`

**对比指标**：调拨前后全网 `SUM(big_date_num)`、高流速仓大日期下降量。

---

## 4. 成本最优化

在 **均衡算法** 或 **时效算法** 基础上加硬约束：

1. 仅允许 `运费档 IN ('低','中')` 的路径
2. 若无解，才引入「高」档，并在方案中标注成本上升
3. 方案总评：`SUM(qty * distance_km * tier_weight)`，`tier_weight: 低=1, 中=1.5, 高=2.5`

---

## 5. 最小干预（可选对照方案）

1. 仅针对 🔴 仓
2. 每条路径 `qty = MIN(inbound_need, surplus)` 一次解完
3. 目标：调拨单数 ≤ 3，总件数最小

---

## 校验清单（出稿前）

- [ ] 每条建议：调出仓调后 DOS ≥ 7
- [ ] 横向：qty ≤ transferable_surplus
- [ ] 正向：qty ≤ from_available（若可查）
- [ ] 调入仓：调后 order_gap 改善或备货率上升
- [ ] 方案对比表已填：总件数、覆盖 🔴 仓数、备货率标准差、大日期变化
