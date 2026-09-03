# 企业级本体架构设计模式：打破 NL2SQL 的局限性

在构建面向供应链（如奶粉智能补调）的 AI Agent 时，如何设计底层数据抽象层决定了系统的成败。本文梳理了将传统数据库表解耦为“本体语义层”的核心思考，并对比了其相比传统大模型直接写 SQL（NL2SQL）的降维打击优势。

---

## 一、 本体的误区：它不是死板的索引，更不是大宽表

在面对包含产品、仓库、计划、库存、批次、订单等多张物理表时，常有两种错误的设计倾向：

### ❌ 误区 1：把本体做成“被动电话簿（死索引）”
如果本体仅仅是为 6 张独立的物理表建立了 6 个无关联的映射索引，导致 Agent 在查询某个业务指标时需要分别发起 6 次数据库检索，这不仅效率低下，且完全丧失了关联图谱的推理能力。

### ❌ 误区 2：盲目合并为“单一业务大宽表/视图”
在供应链中，不同表的数据物理粒度（Grain）是完全不对等的：
* `InventorySnapshot`（库存快照）：粒度为 `[产品 x 仓库]`。
* `BatchInventory`（批次库存）：粒度为 `[产品 x 仓库 x 批次号]`。
* `OrderDemand`（订单需求）：粒度为 `[产品 x 仓库 x 订单ID]`。

如果强行用 `LEFT JOIN` 将它们拍平成一张大宽表，会导致严重的**“粒度扇出（Fan-out / 笛卡尔积爆炸）”**。例如，局部仓有 5 个批次和 10 个积压订单，关联后的宽表会将该 SKU 的当前库存复制放大 50 次。当大模型执行 `SUM(store_num)` 时，会严重误判库存大盘，导致断货灾难。

---

## 二、 本体的内核：语义编译器（OBDA 模式）

真正的企业级本体架构采用的是 **OBDA（Ontology-Based Data Access，基于本体的数据访问）** 机制。本体层不是被动的索引，而是一个高级的**“语义编译器（Semantic Compiler）”**。

大模型 Agent 活在纯粹的业务概念世界里，不需要了解物理表结构，通过高效的单次交互完成复杂的跨表复合计算。

### 📊 深度对比：NL2SQL  vs 本体语义编译

以计算北京销售仓（XS-BJ）的 **“发货缺口（order_gap）”** 为例（公式：`现有库存 + 在途库存 - 未发订单`）：

#### 1. 传统 NL2SQL 模式（让大模型裸写 SQL）
* **心智负担**：大模型必须在 Prompt 中死记硬背 6 张表的物理表名、几十个字段名、主外键关联关系，还要强记业务口径。
* **执行缺陷**：大模型极容易漏掉关键业务口径（例如：*在途库存一旦上车发货即算在途，且必须计入收货仓的库存中统计*），写错关联逻辑，或因笛卡尔积导致数据失真。

#### 2. 本体语义编译模式
* **心智负担**：Agent 只需要像调用标准 Python SDK 一样，发出高阶语义指令：
  ```python
  Warehouse("XS-BJ").get_metric("order_gap")
  ```
* **工作原理**：本体引擎（如 Palantir Foundry 语义层）收到指令后，查阅 T-Box 映射规则，发现 `order_gap` 由三个跨表指标组合而成，且均通过 `site_code` 关联。
* **自动编译**：本体引擎自动在底层将该语义指令编译、重写为一段**经过性能优化、预先处理好物理粒度聚合**的标准物理 SQL，一次性发给数据库执行：
  ```sql
  SELECT (i.store_num + t.store_transit - o.unshipped_orders) as order_gap
  FROM t_warehouse w
  LEFT JOIN (SELECT site_code, SUM(store_num) FROM t_inventory GROUP BY site_code) i 
    ON w.site_code = i.site_code
  LEFT JOIN (SELECT site_code, SUM(store_transit) FROM t_transit GROUP BY site_code) t 
    ON w.site_code = t.site_code
  LEFT JOIN (SELECT site_code, SUM(available_quantity) FROM t_orders GROUP BY site_code) o 
    ON w.site_code = o.site_code
  WHERE w.site_code = 'XS-BJ';
  ```
  数据库将干净的单行结果（如 `-2700`）返回给引擎，喂给 Agent。**全程只有一次高性能的物理交互。**

---

## 三、 本体系相比 NL2SQL 的降维打击优势

| 维度 | 传统 NL2SQL 模式 | 本体语义层模式 |
| :--- | :--- | :--- |
| **口径一致性** | 极易发生“口径幻觉”，不同 Prompt 算出的备货率和缺口可能不一致。 | **单一事实来源（SSOT）**。业务规则（如 $\pm 5\%$ 充足度阈值）在本体中全局配置，改动一处，所有 Agent 自动同步。 |
| **系统安全性** | 大模型直接接触 Raw SQL，面临 SQL 注入风险，或可能写出弄垮物理 DB 的死循环语句。 | **天然的安全沙箱**。Agent 接触不到物理表结构，只能在人类定义的语义对象（Objects & Links）作用域内活动。 |
| **异构数据粘合** | 无法处理跨系统查询。无法写出一段同时跨 SAP（库存）、TMS（在途）和 Kafka（突发事件）的 SQL。 | **多模态天然粘合**。本体负责将 `Warehouse` 对象的不同属性路由映射到不同的异构存储，上层 Agent 毫无感知。 |
| **规则例外处理** | 面对复杂的节庆靠经验动态重载、品类隔离（如试饮装 100% 封顶）等硬编码逻辑时彻底失效。 | 规则本身即是实体。Agent 可以柔性地将 `TemporalOverrideRule`（节庆重载）作为图谱上下文拉取并动态改写控制参数。 |

---

## 四、 本地原型（MVP）落地指南：Python 语义函数化

在本地开发验证阶段，不需要部署极其复杂的工业级图数据库系统，可以直接采用 **“Python 语义函数化”** 的方式，将物理库表的正确 JOIN 逻辑封装为对象方法（Tools）喂给 Agent。

```python
from pydantic import BaseModel
from typing import Dict, Any

class SupplyChainOntologyEngine:
    """本地微型本体语义编译器"""
    def __init__(self, db_connection):
        self.db = db_connection

    def get_sku_site_cube(self, site_code: str, product_code: str) -> Dict[str, Any]:
        """
        统一语义视图层：在内部完成单次高效的预聚合与JOIN，
        屏蔽Raw SQL，防止粒度扇出污染数据。
        """
        sql = """
            SELECT 
                w.site_code, p.product_code,
                COALESCE(i.store_num, 0) as store_num,
                COALESCE(t.store_transit, 0) as store_transit,
                COALESCE(o.unshipped_orders, 0) as unshipped_orders,
                COALESCE(pl.plan_num, 0) as plan_num
            FROM t_warehouse w
            CROSS JOIN t_product p
            LEFT JOIN (
                SELECT site_code, product_code, SUM(store_num) as store_num 
                FROM t_inventory GROUP BY site_code, product_code
            ) i ON w.site_code = i.site_code AND p.product_code = i.product_code
            LEFT JOIN (
                SELECT site_code, product_code, SUM(store_transit) as store_transit 
                FROM t_transit GROUP BY site_code, product_code
            ) t ON w.site_code = t.site_code AND p.product_code = t.product_code
            LEFT JOIN (
                SELECT site_code, product_code, SUM(available_quantity) as unshipped_orders 
                FROM t_orders GROUP BY site_code, product_code
            ) o ON w.site_code = o.site_code AND p.product_code = o.product_code
            LEFT JOIN t_sales_plan pl 
                ON w.site_code = pl.site_code AND p.product_code = pl.product_code
            WHERE w.site_code = :site_code AND p.product_code = :product_code
        """
        return self.db.query_single(sql, site_code=site_code, product_code=product_code)

class WarehouseObject:
    """本体实体层（Objects）的逻辑封装"""
    def __init__(self, site_code: str, engine: SupplyChainOntologyEngine):
        self.site_code = site_code
        self.engine = engine

    def get_runtime_metrics(self, product_code: str) -> Dict[str, Any]:
        """
        核心业务计算层（Logic）：由语义层控制公式口径，杜绝 LLM 算错数
        """
        # 从编译视图层获取干净的数据
        cube = self.engine.get_sku_site_cube(self.site_code, product_code)
        
        store_num = cube["store_num"]
        store_transit = cube["store_transit"]
        unshipped_orders = cube["unshipped_orders"]
        plan_num = cube["plan_num"]

        # 严格执行业务定义的公式
        order_gap = store_num + store_transit - unshipped_orders
        current_stock_rate = store_num / (plan_num + (unshipped_orders)) if plan_num > 0 else 0.0
        
        return {
            "site_code": self.site_code,
            "product_code": product_code,
            "order_gap": order_gap,
            "current_stock_rate": round(current_stock_rate, 4),
            "is_anomaly": order_gap < 0 or current_stock_rate < 0.50
        }

# =================================================================
# Agent 调用示例 (Agent 活在绝对干净的语义世界中)
# =================================================================
# ontology_engine = SupplyChainOntologyEngine(db_conn)
# bj_warehouse = WarehouseObject("XS-BJ", ontology_engine)
# metrics = bj_warehouse.get_runtime_metrics("NF-JGZ-3-900")
# print(metrics) 
# 输出: {'site_code': 'XS-BJ', 'product_code': 'NF-JGZ-3-900', 'order_gap': -2700, ...}
```