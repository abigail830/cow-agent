# 附件 Materialization 策略重构 — 现状 / 问题 / 优化方案

> **专题文档**，与 [`ATTACHMENT_CONTEXT.md`](ATTACHMENT_CONTEXT.md)（P0–P5 能力总览）、[`MULTI_ATTACHMENT_CONTEXT.md`](MULTI_ATTACHMENT_CONTEXT.md)（多附件爆炸与 Map-Reduce）互补。  
> **本文聚焦**：`FULL / THIN / STUB` 决策逻辑如何从「平台 hardcode 规则」演进为「预算护栏 + 模型策略」。

**前置产品要求（本文假设）**

- 所有 **chat 模型**（含 DeepSeek Flash 等）均为 **多模态（VL）**，可直接通过 user message 中的 image content block 看像素。
- `vision_worker` 模型（如 catalog 中的 `qwen-vl-max`）是 **可选 delegate**，不是 chat 模型的强制替代路径。

**相关代码**

| 区域 | 路径 |
|------|------|
| FULL/THIN/STUB 决策 | `backend/app/platform/attachments/materialization/plan.py` |
| Preflight 预算 | `backend/app/platform/attachments/services/preflight.py` |
| Send / replay 组装 | `backend/app/platform/attachments/materialization/replay.py` |
| Replay dedup registry | `backend/app/platform/attachments/materialization/registry.py` |
| Pull tools | `backend/app/platform/attachments/tools/pull_tools.py` |
| Catalog 注入 | `backend/app/platform/attachments/catalog/formatter.py` |
| 平台 instructions | `backend/app/platform/agent/platform_instructions.py` |
| 模型 catalog | `backend/config/models.yaml` |

---

## 1. 现状

### 1.1 架构概览

当前附件进入主模型 context 的路径分为三层：

```text
Send / Replay 组装（materialization/plan.py）
  → FULL：文档全文 / 图片 vision block inline 进 user message
  → THIN：仅「附件已就绪」文字 + catalog 索引
  → STUB：指向历史某轮已有 full payload 的引用文字

Agent loop（pull tools）
  → read_attachment / analyze_image / map_attachment
  → worker 返回 text summary（persist 瘦身，tool_result 不含图片 bytes）

Replay dedup（registry + visibility）
  → 避免历史 turn 重复 replay 同一大 payload
```

P5 Pull 模式（`AttachmentPullConfig.enabled=true`，默认开启）下，catalog 常驻；按需通过 tool 拉取内容。

### 1.2 当前决策规则（pull 模式）

`compute_attachment_plan()` 在 `pull.enabled=True` 时的核心逻辑：

| 条件 | 行为 |
|------|------|
| 附件数 `≥ 3`（preflight） | **强制 THIN**，与单文件大小无关 |
| 估算 inline 字符超 budget | **强制 THIN** |
| registry **无** entry，且未 force_thin | 首 send 可 FULL（`first_turn_inline=true` 时） |
| registry **已有** entry | **永远 THIN**（再次 `@` 无例外） |
| hash 变更 | FULL |
| `user_requests_force_reread()` 短语匹配 | **仅在 `pull.enabled=False` 时生效**；pull 模式下被关闭 |

关键代码位置：

- `backend/app/platform/attachments/materialization/plan.py` — `compute_attachment_plan()`
- `backend/app/platform/attachments/services/preflight.py` — `preflight_should_force_thin()`（含 `len(unique) >= 3`）
- `backend/tests/test_attachment_visibility.py` — `test_pull_mode_second_at_is_thin_not_full` 将「再次 `@` 必 THIN」固化为预期行为

### 1.3 当前 platform instructions

平台尾部 instructions（`platform_instructions.py`）对模型的指引是 **prescriptive（规定性）** 的：

- 图片 → 必须用 `analyze_image`（返 text summary）
- 多文件概括 → `map_attachment`
- 文档精读 → `read_attachment`

未注入每轮 **预算 envelope**，也未提供「主模型自行 inline 看图」的 tool 路径。

### 1.4 当前 tool 与 worker 关系

| Tool | 行为 | 返 orchestrator |
|------|------|-----------------|
| `analyze_image` | 调 `AttachmentVisionService` → ephemeral vision mini-run | JSON summary，无 base64 |
| `map_attachment` | 图片走 VisionService；文档走 text worker | JSON summary |
| `read_attachment` | 提取全文（有 char 上限） | 文本 content |

`vision_worker` 角色模型用于 isolated mini-request，**实现上**与 chat 模型并行存在；**产品上** chat 模型本身具备 VL 能力，user message inline 与 worker delegate 应是并列选项，而非二选一 hardcode。

### 1.5 文档与实现的分歧

[`ATTACHMENT_CONTEXT.md`](ATTACHMENT_CONTEXT.md) §8.3 曾写：

> P5 上线后……或 **send 层对显式 `@` 直接 full，不依赖用户措辞**。

[`MULTI_ATTACHMENT_CONTEXT.md`](MULTI_ATTACHMENT_CONTEXT.md) §0.3 强调国内 provider **tool_result 不能含 image block**——这是 **tool 返回路径** 的协议约束，**不是** user message 不能 inline 图片。

实现侧走了相反方向：pull 模式关闭 force re-read，且 registry 有 entry 则永久 THIN。

---

## 2. 问题

### 2.1 核心缺陷：两个维度被耦合到同一状态机

平台把两件独立的事绑在同一个开关上：

| 维度 | 应管什么 | 当前错误做法 |
|------|----------|--------------|
| **Replay dedup** | 历史 turn 是否重复 replay 大 payload | registry 有 entry → **当前 turn 也永久 THIN** |
| **Current-turn 展开粒度** | 本轮用户/模型需要 summary 还是 pixels | 被 `≥3` 硬规则 + registry 一票否决 |

后果：

- 用户 `@` 单张图并说「仔细看一下」→ 若该 id 曾在多文件 turn 出现过，**永远无法 FULL inline**。
- 主模型（含 DeepSeek Flash VL）**有能力直接看像素**，但平台不给出 inline 路径，只能反复走 worker summary。
- 模型能力升级（更强 VL、更大 context）**无法自动受益**——规则写死在 `plan.py`，与模型无关。

### 2.2 Preflight 的「数量阈值」过于粗暴

```python
# preflight.py
if len(unique) >= 3:
    return True  # force THIN
```

4 张小图与 4 张 10MB 图被同等对待；与真实 token 预算脱钩。防爆炸的意图正确，但应用层替模型做了战略决策（「多文件 = 永远摘要」），而非只提供预算信息。

### 2.3 Instructions 与能力模型不匹配

Instructions 规定「图片用 `analyze_image`」，等价于平台 prescriptive 地选择 worker 路径。在「所有 chat 模型均为 VL」的前提下，应改为 **budget-driven 决策框架**，由模型在 direct inline vs delegate 之间选择。

### 2.4 需区分的两类约束（避免混淆）

| 约束类型 | 内容 | 谁负责 |
|----------|------|--------|
| **协议约束** | tool_result 不能带 image block（DeepSeek/Qwen/MiniMax 等） | 平台保证 worker / inline tool 不返 bytes |
| **产品策略** | 本轮看 summary 还是 pixels | **模型**根据 budget + 意图决定 |
| **安全护栏** | 绝不超 context 导致 400 | **平台** hardcode 仅在此处 |

此前方案误将「tool_result 限制」等同于「chat 模型不能 FULL」——这是错误的。FULL inline 走 **user message image block**，与 tool_result 无关，对所有 VL chat 模型（含 DeepSeek Flash）成立。

---

## 3. 优化方案

### 3.1 设计原则

```text
平台 = 预算计算 + 安全门控 + replay dedup + 决策上下文
模型 = 策略（direct inline vs worker delegate）
```

**平台允许 hardcode 的唯一策略**：超预算 → 拒绝并明确提示，绝不 silent 400。

**平台不应 hardcode 的策略**：

- 「≥ N 个附件 → 永远 THIN」
- 「registry 已见过 → 永远不能 FULL」
- 「某 provider / 某模型 → 必须走 vision_worker」
- 「图片 → 必须 analyze_image」

### 3.2 目标架构

```text
用户 send（@ 附件 + 问题）
  │
  ▼
平台组装
  ├─ catalog（索引，已有）
  ├─ [Attachment Budget] 块（新增，每轮注入）
  │     inline_budget_remaining_est
  │     @mentioned_this_turn: [{ id, filename, kind, inline_cost_est, status }]
  │     cached_summaries: (若有)
  │     available_tools: inline_attachment | read_attachment | analyze_image | map_attachment
  └─ Send 默认：@ 附件 **不自动 inline**（保守起始状态 = THIN）
        ※ 非永久降级；模型可在同轮 tool 请求展开

  ▼
主模型（任意 VL chat 模型）
  读 budget + 用户意图 → 选择工具

  ├─ inline_attachment(id)      直接看图（FULL，user message inject）
  ├─ read_attachment(id)        文档精读
  ├─ analyze_image(id, q?)      可选 delegate：worker 摘要
  └─ map_attachment(id, focus?) 多文件 map

  ▼
平台执行 + 预算校验
  通过 → 注入 / 返 summary
  拒绝 → tool error + 建议（改用 worker 或压缩历史）

  ▼
主模型综合回答
```

### 3.3 新增核心能力：`inline_attachment` tool

模型请求 **direct vision** 的入口；兼容所有 VL chat 模型（含 DeepSeek Flash）。

**行为：**

1. 校验 inline 预算（preflight 纯数字门控，无数量 hardcode）。
2. **不**在 tool_result 中返回图片 bytes（遵守 provider 协议）。
3. 写入 `run_state.pending_inline`（**按 attachment_id 去重的 set / dict**，见 §3.3.1）。
4. 在 agent loop **下一次 orchestrator 调用前**，将该图作为 **user message supplement**（image content block）注入；注入成功后标记 `injected_inline_ids`。
5. 返回 `{"status": "ok", "message": "Image is now visible in your context"}`。

像素走 user message，不走 tool_result——与国内 provider 兼容，也与 GPT/Claude 路径统一。

#### 3.3.1 幂等性：同轮重复 `inline_attachment(id)`

模型可能在同一 turn 内重复调用（遗忘、重试、多 step 幻觉等）。`pending_inline` **必须按 id 防重**：

| 状态 | 再次调用同一 id 时的行为 |
|------|--------------------------|
| 尚未注入（已在 `pending_inline`） | 返 `{"status": "ok", "cached": true, "message": "Already scheduled for injection"}`，**不**重复计入 budget |
| 已注入（在 `injected_inline_ids`） | 返 `{"status": "ok", "cached": true, "message": "Already visible in your context this turn"}` |
| 首次 | 正常 schedule + 扣 budget |

实现建议：`run_state.pending_inline: dict[str, Literal["scheduled", "injected"]]`，或 `pending_inline: set[str]` + `injected_inline_ids: set[str]`。注入阶段对 `injected_inline_ids` 做 union，保证 user message **至多 1 份**同 id 的 vision block。

**测试**：`test_inline_attachment_idempotent_same_turn` — 同轮调两次，messages 里仅 1 个 vision block，第二次 tool_result 含 `cached: true`。

**文档类附件：** 可对称提供 `inline_attachment` 的 doc 变体，或复用 `read_attachment` 并在 budget 块中标注「精读成本」；首版可仅覆盖 image，doc 仍走 `read_attachment`。

### 3.4 `[Attachment Budget]` 上下文块（每轮注入）

扩展 catalog ContextProvider 或 formatter，示例：

```text
[Attachment budget]
inline_budget_remaining_est: 72000 chars
context_remaining_est: (optional, 若可估)

@mentioned_this_turn:
  - id=aaa  filename=page2.jpg  kind=image  inline_cost_est=8200  status=not_inlined
  - id=bbb  filename=page3.jpg  kind=image  inline_cost_est=8100  status=not_inlined

cached_summaries: 2 available
Tools:
  inline_attachment — direct vision (costs inline_budget)
  analyze_image       — worker summary (cheaper, no pixels in your context)
  map_attachment      — batch summarize per id
  read_attachment     — verbatim document text
```

模型读成本与选项，自行决策；模型升级后同一 budget 下可自然选择更多 direct inline，**无需改平台规则**。

### 3.5 改写 `plan.py`：拆维度

#### Replay dedup（保留，语义不变）

- `registry` + `visibility`：仅决定 **历史 replay** 是否重复 inline 旧 turn 的大 payload。
- **不参与**当前 turn 模型能否调用 `inline_attachment`。

#### Current-turn send 默认（简化）

| 场景 | 新行为 |
|------|--------|
| 用户 `@` N 个附件 | Send 默认 **THIN**（不自动塞 payload） |
| 用户未 `@` | 仅 catalog |
| hash 变更 | 标记 `content_updated`，budget 块提示 |
| force re-read 短语 / 模型已 schedule inline | 走 `inline_attachment` 或 send 时 inline，**不受 registry 阻挡** |

#### 删除的规则

- `preflight_should_force_thin` 中的 `len(unique) >= 3`
- `pull.enabled` 下 `entry is not None → THIN`
- `force_reread = ... if not pull.enabled else False`

#### Preflight 新职责

仅输出：

- `inline_budget_remaining_est`
- 各 attachment 的 `inline_cost_est`
- `allow_inline(ids)` / `deny_inline(reason)` — **安全门控**，非策略选择

### 3.6 改写 platform instructions

**从 prescriptive：**

```text
Images: analyze_image(attachment_id) (returns a text summary).
```

**改为 decision framework：**

```text
## Platform: attachment strategy (budget-driven)

Each turn includes an attachment budget block. Choose per task:
- Pixel-level inspection (charts, handwriting, layout): inline_attachment(id)
- Batch summarize many files / save context: map_attachment(id) or analyze_image(id)
- Verbatim document text: read_attachment(id)

Attachments are NOT inlined unless you called inline_attachment this turn
or they appear as image blocks in the current user message.
Respect budget errors; do not retry inline if over budget.
```

同步更新 `pull_tools.py` 中各 tool 的 description，明确互斥与选用场景，但 **不强制**图片必须 analyze。

### 3.7 `vision_worker` 的新定位

| 角色 | 说明 |
|------|------|
| **保留** | `analyze_image` / `map_attachment` 的 backend delegate |
| **不再作为** | chat 模型看图的前置必要条件 |
| **收益** | 模型可主动选择 cheaper worker path；map-reduce 批量场景仍可用 |

catalog 中 `roles: [vision_worker]` 与 `roles: [chat]` 并存；chat 模型默认 multimodal，worker 为可选加速/省 context 路径。

### 3.8 Pin / 持续聚焦（二期）

| 粒度 | 触发 | 行为 |
|------|------|------|
| **单轮** | 模型调 `inline_attachment(id)` | 本轮可见，下轮自动回落 |
| **持续 pin** | 模型调 `pin_attachment(id)`（可选新 tool） | 连续多轮该 id 优先出现在 budget 推荐中；用户换题或 `unpin_attachment` 解除 |

#### 3.8.1 状态存放（与 registry 分离）

| 存储 | 内容 | 生命周期 |
|------|------|----------|
| `registry` | replay dedup：某 id 曾在哪轮 FULL inject | chat 历史 seed，纯 dedup 元数据 |
| `session.pinned_attachment_ids`（或 chat-scoped store） | 用户/模型显式 pin 的 id 集合 | 跨 turn 持久，直到 unpin |
| `run_state.pending_inline` / `injected_inline_ids` | 单 run 内 schedule / 注入状态 | 单次 agent run |

Pin **不写入 registry**——registry 仍只记录「发生过 FULL inject」，不表达「用户希望持续聚焦」。

#### 3.8.2 Pin 与 replay dedup 的交互（设计期必定，避免二期踩坑）

**问题**：若只把 pin 放在 run_state，下一轮 replay 历史时仍按旧规则对同一 id 做 STUB/THIN 降级，pin 等于失效——模型每轮都要重新 `inline_attachment`，体验差且浪费 tool 轮次。

**规则（pin 有效期内 replay dedup 对该 id 暂时豁免）**：

```text
组装 orchestrator messages（replay + 当前 turn）时：

若 attachment_id ∈ pinned_attachment_ids：
  1. replay 阶段：该 id 在历史 user 行中 **不得** 被 STUB/THIN 替换为纯文字摘要；
     保留最近一次 FULL inject 的 recoverable payload，或在 replay 末尾补一条 synthetic FULL supplement。
  2. 当前 turn send：若本轮 user 未 @ 该 id，仍在 turn 开头 **自动 schedule** pending_inline（等同 eager inline），
     仍过 budget 门控；超 budget 则 pin 不自动 inline，budget 块标注 pinned_but_over_budget。
  3. registry 仍记录 dedup 元数据，但 compute_replay_plan 对 pinned id 跳过「anchor 可见 → STUB」分支。

若 attachment_id ∉ pinned：
  走常规则 replay dedup（STUB / THIN / 按需 re-inline）。
```

**与 visibility / compaction 的关系**：P3 scoped compaction 若会把旧 turn 的 full payload strip 掉，pinned id 的 anchor turn **不参与 compaction**，或 compaction 后立即登记「需 re-inject」并在下轮 send 补 inline。实现二选一，但语义一致：**pin 期间 pixels 对主模型持续可达**。

**测试（二期 PR5，规则 PR1 文档锁定）**：

- `test_pin_exempts_replay_stub` — pin id 后新 turn replay，历史 full 不被 STUB。
- `test_pin_auto_schedules_inline_next_turn` — 未 @ 的 pinned id 在新 turn 仍进入 pending_inline（budget 允许时）。
- `test_unpin_restores_normal_dedup` — unpin 后下一轮恢复 STUB/THIN 常规则。

### 3.9 Send 默认 THIN 是否算 hardcode？

| 层 | 行为 | 判定 |
|----|------|------|
| Send 默认 | `@` 附件 send 时不自动 inline | ✅ 保守默认，防首包 4 图爆炸 |
| 永久降级 | registry 记过 → 永远不能 inline | ❌ 删除 |
| 数量阈值 | `≥3` 永远 THIN | ❌ 删除，改纯预算 |

Send 默认 THIN = 本轮 **起始状态未展开**，不是 **永远不能 FULL**。模型同轮即可 `inline_attachment` 全部 @ 附件，只要预算允许。

可选优化（非阻塞）：轻量 pre-router 让模型在 send 前建议 inline 列表——增加 latency，首版可不做了。

### 3.10 哲学对齐审查（针对「已 inline 仍调 analyze_image」等场景）

> **核心哲学**：平台管 **预算 + 安全 + 事实（facts）**；模型管 **策略（strategy）**。  
> 类比：平台暴露 `context_used / budget_remaining`，由模型决定是否 compact history——而不是平台 hardcode「超过 N 轮必 compact」。

#### 3.10.1 新方案已对齐的部分

| 项 | 说明 |
|----|------|
| 删除 `≥3` / registry 永久 THIN | 平台不再替模型做「多文件 = 永远摘要」策略 |
| `[Attachment Budget]` 块 | 类似 token 用量面板，提供成本数字供模型决策 |
| `inline_attachment` 作为 opt-in | 模型主动请求展开，平台只做 budget 门控 |
| worker tools 降级为 optional delegate | 不再 prescriptive「图片必 analyze_image」 |
| replay dedup 与 current-turn 解耦 | registry 只管 history 安全，不锁死本轮能力 |

#### 3.10.2 仍与哲学有张力、需补强的点

**A. Catalog / instructions 仍在「替模型做策略」（当前 prod 根因）**

即使 send 已 FULL inline，catalog 仍写 `index only; use analyze_image for full content`，instructions 写 `Images → analyze_image`——这是 **prescriptive 策略**，不是 **事实陈述**。新方案 §3.6 已改 instructions，但须同步：

- catalog header 改为 **事实型**：`[Chat attachments — availability index]`，**禁止**「use analyze_image for full content」类动宾指引；
- 每个 id 带 **`visibility` 字段**（见下），而非统一叫「index only」。

**B. Budget 块须升级为「Facts + Budget」——关键补强**

仅有 `inline_cost_est` 不够；必须让模型知道 **当前轮像素是否已在 context 里**，否则仍会误调 tool。建议每 id 必有：

```text
- id=aaa  filename=page.jpg  kind=image
  visibility: inlined_this_turn | not_inlined | summary_only_in_history
  inline_cost_est: 8200
  inline_allowed: true
```

| visibility | 模型策略含义（由模型自己决定，平台只陈述事实） |
|--------------|-----------------------------------------------|
| `inlined_this_turn` | 像素已在当前 user message；**不应**再调 `inline_attachment` / `analyze_image` |
| `not_inlined` | 仅 catalog/metadata；要像素 → `inline_attachment`；要廉价摘要 → worker |
| `summary_only_in_history` | 有 cached summary，无 pixels；是否 re-inline 由模型按 budget 判断 |

**这直接覆盖「单图首 @ + 已 FULL inline 仍 analyze_image」**：平台陈述 `inlined_this_turn`，tool description 加 guard「Do NOT call when visibility=inlined_this_turn」——策略权仍在模型，但 **不再被错误事实误导**。

**C. Send 默认 THIN：是安全默认，不是策略——但需说清与 `@` 的关系**

§3.9 的「Send 默认 THIN」符合哲学（零 payload 起始态，防 4 图首包爆炸），但与用户 `@` 显式引用之间存在产品语义张力：

| 立场 | 行为 | 哲学归类 |
|------|------|----------|
| **严格模型策略** | 凡 @ 都 THIN，模型第一动作自选 inline/worker | ✅ 策略全归模型；❌ 单图多一轮 tool latency |
| **@ = 用户意图信号** | 平台对 **@mentioned** 且 **budget.allow** 的 id **自动 inline**（执行用户附件意图，非替模型选题） | ⚠️ 边界：算「帮用户贴附件」还是「替模型决定看像素」？ |

**已定产品立场（2026-03）** — 保留 `first_turn_inline` auto FULL，但 **钉死边界、显式定性**：

| 定性 | 说明 |
|------|------|
| **层级** | **I/O 便利层**（平台代为执行用户明确的单一 `@` 意图），**不是** materialization 策略层 |
| **触发条件（全部满足）** | `first_turn_inline=true` + pull enabled + **唯一附件** + registry **无** entry + preflight **未** over budget |
| **禁止扩散** | 多附件、registry 已有 entry、budget 临界/超限 → **必须** THIN/STUB，无条件转交模型（`inline_attachment` / worker） |

```text
Send 组装（plan.py auto_full_on_send）：
  1. 默认 THIN（安全）
  2. 仅当 unique_attachment_count == 1 且 registry 无 entry 且 budget 允许 → auto FULL（I/O 捷径）
  3. 多附件或 registry 有 entry 或超 budget → THIN；facts visibility=not_inlined；模型自选策略

Facts 块如实写 visibility=inlined_this_turn | not_inlined
```

**为何保留单图捷径**：该场景无策略分歧（理性模型必选 FULL），多一轮 tool round-trip 只增延迟与误调风险；此前「@ 图只能拿摘要」根因是 **registry 永久 THIN**，不是 auto FULL 本身。

**治理**：`visibility_constants.py` 为 visibility 词汇 SSOT；instructions / tool descriptions / guard 文案均从此渲染；`test_attachment_prompt_governance.py` 断言对齐；`test_auto_full_only_single_attachment_*` 钉死 auto FULL 边界。

**D. §3.8.2 Pin 的「自动 schedule inline」违反哲学——应改**

原文「pin 期间 turn 开头自动 schedule pending_inline」是 **平台替模型决定看像素**，与核心哲学冲突。

改为：

- pin 仅影响 budget 块：`pinned: true, visibility: …, recommendation_note: "user focus"`
- **不**自动 inline；由模型调 `inline_attachment` 或依赖 replay 豁免保留的历史 pixels
- replay 豁免（pin 期间不对该 id STUB）属于 **replay 安全/dedup 例外**，不是策略

**E. Tool description 是「互斥事实」，不是「路由规则」**

各 tool 应写 **when NOT to call**（基于 visibility / budget error），而非 **when MUST call**：

```text
analyze_image: Do NOT call if visibility=inlined_this_turn for this id.
inline_attachment: Do NOT call if visibility=inlined_this_turn or inline_allowed=false.
```

#### 3.10.3 场景走查：单图「分析一下内容是啥」

**当前 prod（未改）**

```text
send: FULL inline（单图 first_turn_inline）
catalog: "index only → use analyze_image"     ← 错误事实 + 错误策略
instructions: "Images → analyze_image"       ← prescriptive
→ 模型调 analyze_image（被诱导），worker 404，再 fallback 自己看
```

**新方案（补强后）**

```text
send: @ 1 图 + budget 允许 → auto inline（§3.10.2 C 折中）
facts: visibility=inlined_this_turn
instructions: 已 inline → 直接回答，勿调 analyze_image
→ 模型直接 vision 回答（零 tool）；符合哲学

或（严格 THIN 路径）：
send: THIN
facts: visibility=not_inlined, inline_cost=8k, inline_allowed=true
→ 模型自选 inline_attachment（direct）或 analyze_image（省 context）
→ 两种均合法；策略归模型，平台不 prescriptive
```

#### 3.10.4 实施顺序调整（哲学优先）

| 阶段 | 内容 | 理由 |
|------|------|------|
| **PR0** | catalog 事实化 + instructions/tool guards + `visibility` 字段（即使尚未有 inline_attachment） | **立刻**修复「已 inline 仍 analyze_image」，不改 plan 大逻辑 |
| PR1–PR5 | 按 §5 原排期 | 结构性 refactor |

#### 3.10.5 验收补充

| 场景 | 期望 |
|------|------|
| 单图 @ + budget 内 auto inline | **0 次** analyze_image；facts=`inlined_this_turn` |
| 单图 @ + budget 内 THIN 模式 | 模型自选；若选 inline_attachment 则 1 次 tool，若直接… 不可能（无 pixels）→ 必择一 tool 或需 auto inline |
| 4 图 @ + over budget | facts 列 4 id + over_budget；模型策略性选 1–2 inline + 其余 map |
| worker 404 | 不 prescriptive 必须 worker；inlined 时本不应调 worker |

---

## 4. 与现有文档 / 测试的关系

### 4.1 需更新的文档

| 文档 | 变更 |
|------|------|
| [`ATTACHMENT_CONTEXT.md`](ATTACHMENT_CONTEXT.md) §1.3 Truth 表 | 增加「model-driven materialization」行；修订 P5c 描述 |
| [`MULTI_ATTACHMENT_CONTEXT.md`](MULTI_ATTACHMENT_CONTEXT.md) §0.3 | 澄清：tool_result 限制 ≠ chat 不能 FULL inline |
| 本文 | 实施完成后标记各 Phase 状态 |

### 4.2 需新增 / 修订的测试

| 测试 | 断言 |
|------|------|
| `test_preflight_no_count_threshold` | 3 张小图估算未超 budget → 不 force thin |
| `test_inline_attachment_injects_image_block` | 调 tool 后 orchestrator 下一 step 含 vision block |
| `test_registry_does_not_block_inline_tool` | registry 有 entry + `inline_attachment` → 仍可见像素 |
| `test_budget_denial_returns_actionable_error` | 超 budget → tool error + 文案 |
| `test_inline_attachment_idempotent_same_turn` | 同轮重复调同一 id → 仅 1 vision block，`cached: true` |
| `test_pin_exempts_replay_stub` | pin 有效期内 replay 不对该 id STUB（PR5） |
| `test_unpin_restores_normal_dedup` | unpin 后恢复常规则 replay dedup（PR5） |
| 修订 `test_pull_mode_second_at_is_thin_not_full` | send 默认 THIN 仍成立，但 inline tool 可 override |
| `test_attachment_prompt_governance.py` | visibility SSOT 与 instructions/tools/guard 文案一致；guard 含 `recovery=answer_from_context` |
| `test_auto_full_only_single_attachment_*` | 多附件 / registry entry / over budget 时 auto FULL **不**生效 |

### 4.3 验收场景（对齐 MULTI §11）

| 场景 | 期望 |
|------|------|
| TC-C2：`@` 单文件精读（catalog 内另有 4 个） | 模型 `inline_attachment` 或 `read_attachment` 仅 1 个大 payload |
| TC-E1：DeepSeek 主模型 + 看图 | 可走 `inline_attachment`；orchestrator user message 含 image block |
| TC-G2：stub 不挡精读 | 模型调 inline / read，不被 STUB 文案误导停止 |
| 4 图概括 | 模型自选 4×map 或 4×inline（视 budget） |
| 单图 @ 已 inline | **0 次** analyze_image（PR0/§3.10.3） |

---

## 5. 实施排期

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **PR0** | catalog/instructions/tool **事实化 + visibility guards**（§3.10.2 A/B/E）；修复已 inline 仍 analyze_image | — |
| **PR1** | 删 `≥3 force_thin`、`entry→永久 THIN`、恢复 pull 下 force_reread；preflight 改纯预算 | PR0 |
| **PR2** | `[Attachment Facts + Budget]` 块注入（含 per-id visibility） | PR1 |
| **PR3** | `inline_attachment` tool + mid-run inject + **同轮幂等防重**（§3.3.1） | PR1, PR2 |
| **PR4** | 改写 `platform_instructions.py` + tool descriptions | PR3 |
| **PR5**（可选） | `pin_attachment` / `unpin_attachment` + **replay dedup 豁免**（§3.8.2）、budget 超限 UX | PR4 |

---

## 6. 一句话总结

**现状**：平台用 `plan.py` hardcode（`≥3`、registry 已见）把「历史 dedup」与「本轮展开粒度」绑死，并 prescriptive 规定图片走 worker summary。

**问题**：VL chat 模型（含 DeepSeek Flash）无法按需 FULL inline；模型能力升级无法水涨船高。

**方案**：平台只负责 **预算计算、超预算拒绝、replay dedup、每轮 budget 上下文**；由主模型通过 **`inline_attachment`（direct）vs worker tools（delegate）** 自行决策。Send 默认 THIN 仅是保守起始状态，不是永久降级。
