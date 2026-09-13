# 聊天附件 Context 管理方案

> 解决多轮对话中「同一文件/图片被反复 @」导致的 **重复注入 context** 问题，以及长对话下 **heavy payload 占满窗口** 的问题。  
> 范围：Native（mode1）与 Unify-lite（mode2）；**不含**聊天附件向量检索（超大文件走 **hybrid-search 知识库 MCP**）。

**相关代码**

| 区域 | 路径 |
|------|------|
| 上传 / 解析 | `backend/app/platform/attachments/` |
| Materialization | `backend/app/platform/attachments/materialization/` |
| 发消息组装 | `backend/app/platform/chat/run_service.py` |
| Lite builder（→ materialization） | `backend/app/platform/attachments/unify_lite/message_builder.py` |
| 历史 replay | `backend/app/platform/memory/maf_mapping.py` → `to_maf_messages` |
| Working set | `backend/app/platform/session/session_store.py` |
| 运行时 slim | `backend/app/platform/memory/slimmer.py`、`compaction.py` |
| 前端 @ 引用 | `frontend/src/lib/attachmentMentions.ts` |
| 体积限制 | `backend/app/config.py` → `ATTACHMENT_MAX_*` |

**历史文档**：`docs/UNIFY_LITE.md` 为 v0 调研稿；**实现状态以本文为准**。

---

## 1. 现状摘要

### 1.1 已实现（P0–P2 + 热修）

| 能力 | 状态 |
|------|------|
| 材料库上传，不自动进 LLM | ✅ |
| 发送时仅 `@` 解析出的 attachment 进入本轮 | ✅ |
| Lite 文档 `extracted_snapshot` 落库 + replay 读文本 | ✅ P0 |
| Lite 同 chat `content_hash` 去重；Native 不去重 | ✅ P0′ |
| `build_user_run_input_lite` → 统一 materialization 路径 | ✅ |
| Send + replay 共用 registry dedupe（full / stub） | ✅ P1 |
| working set 含 user 行（`WORKING_SET_VERSION=2`） | ✅ 热修 |
| stub 规范 + 关键词 force re-read | ✅ P2（**临时方案**，见 §6） |
| 测试 | `tests/test_attachment_*.py`、`test_maf_mapping_lite_docs.py` 等 |

### 1.2 已知缺口 / 风险（实施 P1 补丁 & 文档修订前）

| 问题 | 风险 |
|------|------|
| **visibility 多轨**：registry 按 working set 判断，slim 另改 in-flight history | **高** — stub 指向已不可见 full → 假记忆 |
| P3 slim 对**全部** user attachment 行 strip（非「即将滑出」） | **高** — 与 P0 多轮追问冲突 |
| stub 锚点用 `first_inject_turn`，force re-read 后未改指向 | **中** — 悬空引用 |
| 同 chat **中途换 model/mode** 未定义 | **中** |
| P5 Pull / catalog 未做 | 长对话终态未达成 |
| 本地 `.env` 可能与 `.env.example` 5MB 不一致 | **运维** |

---

## 2. 设计原则

### 2.1 图片 vs 文档分开

| 维度 | 文档（Lite extract） | 图片（全 mode Native vision） |
|------|----------------------|-------------------------------|
| mode 分叉 | file API / extract | 主模型 Vision |
| 重复 @ 判定 | `content_hash` + **visibility window** | 同左 |
| 去重后（Push 时代） | 文本 stub 锚点 | 文本 stub |
| 窗口外 / 不可见 | full re-materialize 或 **Pull tool** | 整图 re-inline 或 `analyze_image` |
| 大内容 | cap + char 截断 | cap；整图 atomic |
| 长对话降压（P3→P5） | 摘要 / catalog gist | 占位 / catalog + tool |

### 2.2 传输去重 ≠ 推理去重

- 同 blob / `file_id` 只传一次 → 省存储与上传。
- context 里仍 inline 整图或整篇 extract → **vision / 文本 token 仍占用**。
- registry 解决 history **replay 重复 inline**；**不**等于 provider 免 token。

### 2.3 索引 vs 内容（长期心法）

> **不要让「内容」承担「记忆」；让足够小的「索引」常驻，内容按需 page-in。**

| 层 | 职责 | 是否随 sliding window 消失 |
|----|------|---------------------------|
| **索引（catalog）** | id + filename + 一句话 gist | **否** — 每轮平台注入 |
| **内容（payload）** | snapshot 全文 / vision 整图 | **是** — 仅按需进入 context |

P5 Pull 是终态；P0–P2 是 Push 过渡；P3 仅为 Pull 未开时的 **兜底减压**（见 §8）。

### 2.4 范围外（明确不做）

- 聊天附件向量检索 / RAG 分块（大文件 → **hybrid-search 知识库**）。
- Native 上传 **content_hash 去重**（换 provider 可能需重传）。
- 上传路径默认跑 VLM caption（P3 可选一次性占位、P5 gist 复用主模型副产品除外）。

---

## 3. 核心不变量（P1 前置 — 阻塞项）

### 3.1 Visibility window：单一真相来源

**定义：** 模型在本轮 `agent.run` 中**实际可见**的 history 内容，由以下管道**顺序**决定：

```text
visibility_rows
  := SessionStore.get_working_set_rows(working_set_turns)   // Layer1：按 user turn 截断
  → to_maf_messages + materialization registry              // full / stub 组装
  → PlatformSlimCompaction / attachment_compaction (若启用)  // Layer2：运行时投影
  → sanitize_rows_for_provider (若换 provider)              // Layer3：工具行等
```

**规则（写死）：**

1. `working_set_turns` = **按轮数滑窗**，**不是** token 预算；token 压力由 Layer2 / Pull 分担。
2. registry 的「窗内是否已有 full inject」必须对 **visibility 求值后的 effective payload** 判断，**不能**只对 `working_set_rows` 原始 metadata 判断。
3. 若 stub 锚点 turn 在 visibility 中**不存在可恢复的 full payload** → **禁止 stub**；改为 full inject 或（P5）`read_attachment`。

**实现目标：** 抽出统一的 `compute_materialization_plan(rows, visibility_policy)`，send 与 replay **共用**（当前 send / replay 已共用 registry 类，但未与 slim 对齐 — 待 P1.1 补丁）。

### 3.2 Registry：derive-on-read，禁止跨请求缓存

**写死实现模型：**

```text
Registry = 纯函数(visibility_rows, current_user_message)
         → 每条 attachment_id: FULL | STUB | ABSENT
```

- **禁止** Redis / DB / 进程内 per-chat 可变 registry 缓存。
- 每次 send：`seed_from_prior_rows(prior visibility rows)` + 当前 turn。
- 每次 replay：`to_maf_messages` 内按 sequence 顺序扫描重建。
- 多副本、重启 **无一致性风险**（已实现方向正确；文档此前表述易误导为「有状态实体」）。

### 3.3 Materialization 状态机（`first` / `last` / stub 锚点）

**字段语义：**

| 字段 | 含义 | 用途 |
|------|------|------|
| `first_materialized_turn` | 历史上第一次 full inject 的 turn sequence | 审计 / 调试 |
| `last_full_inject_turn` | **最近一次** full inject 的 turn sequence | **stub 锚点**（待代码修正：当前 stub 误用 first） |
| `content_hash` | 最近一次 full 对应的内容 hash | 变更检测 |

**状态转移：**

```text
[无记录]
  │ 首次 @ / 窗外 re-@ / visibility 无 full
  ▼
[FULL @ turn T]  first=T, last=T
  │
  ├─ 再次 @，hash 不变，visibility 中 turn T 仍有 full → STUB（锚点 last）
  │
  ├─ hash 变更 → FULL @ turn T2；last=T2；metadata 标记 content_version（待实现）
  │
  ├─ force re-read（P2 临时）→ FULL @ turn T3；last=T3；stub 锚点改为 T3
  │
  └─ turn last 滑出 visibility / 被 compact 到不可读
        → registry 无有效锚点 → 下次 @ 必须 FULL 或 read_attachment
```

**禁止：** stub 文本指向 visibility 中找不到 full payload 的 turn（悬空引用）。

### 3.4 Mode / Provider 切换（P0 验收扩展）

同 chat 中途换主模型或 attachment mode 时：

| 场景 | 行为 |
|------|------|
| Native `hosted_file` history → Lite replay | 有 `extracted_snapshot` 用文本；否则 lazy extract blob |
| Lite snapshot history → Native replay | **优先**继续用 snapshot 文本（不强制 re-upload） |
| attachment `provider` 与当前 run model provider 不匹配 | 现有 `resolve_for_message` 报错；产品层提示 **re-upload** 或切回原模型 |
| 跨 provider tool call id | `sanitize_rows_for_provider` 丢弃不兼容 tool 行（**不含** attachment，需单独测） |

**验收：** 换模型后继续 `@` 同一文件，不 raw bytes、不 silent 失败。

---

## 4. 阶段总览

| 阶段 | 名称 | 目标 | 状态 |
|------|------|------|------|
| **P0** | 文档 snapshot 持久化 | replay 正确性 | ✅ |
| **P0′** | Lite hash + 体积 cap | 材料库卫生 | ✅（cap 可分型，见 §5） |
| **P1** | Materialization registry | 重复 @ dedupe | ✅ 核心；**P1.1** visibility 对齐待做 |
| **P2** | stub + force re-read | 体验 | ✅ 临时；P5 后废弃关键词 |
| **P3** | 长对话降压（Push 兜底） | 减 token | ⚠️ 部分；需 P3-a 止血 + 收窄范围 |
| **P4** | Prompt caching | 降本 | ❌ |
| **P5a** | Attachment catalog | 索引常驻 | ❌ |
| **P5b** | Pull tools | 按需 page-in | ❌ |
| **P5c** | Thin send | 首 turn 可配置 inline | ❌ |

---

## 5. P0 — 文档 extract 持久化 ✅

### 5.1 做什么

1. `@` 文档且发送时，extract 写入 `message.metadata.attachments[].extracted_snapshot`（含 `content_hash`、`text`、`extracted_at`）。
2. Send：live extract → 写 metadata → `build_materialized_user_message` 读 snapshot。
3. Replay：只用 `extracted_snapshot.text`；**禁止** docx raw `Content.from_data`。

### 5.2 Legacy

无 snapshot 的旧消息：replay 应 lazy extract 或 stub「需重新 @」，**禁止** silent raw bytes（待补）。

### 5.3 测试

见 `tests/test_attachment_materialization.py`、`tests/test_maf_mapping_lite_docs.py`。

---

## 6. P0′ — Lite hash 去重 + 体积上限 ✅

### 6.1 已实现

- DB `chat_attachments.content_hash`；Lite 同 chat 同 hash 返回已有行；Native 不去重。
- 默认单文件 cap：`ATTACHMENT_MAX_BYTES_PER_FILE=5242880`（`.env.example`）；**部署须同步本地 `.env`**。

### 6.2 分型 cap（建议后续）

| 类型 | 建议 cap | 说明 |
|------|----------|------|
| 文本 / docx（Lite） | 5MB | 聊天 quick Q&A |
| 图片 | 5MB | 与 vision inline 一致 |
| 更大文档 | — | 引导 **hybrid-search 知识库**，非仅 HTTP 400 |

超限 UX：API + 前端明确文案 + 知识库入口（待产品补）。

---

## 7. P1 — Materialization registry

### 7.1 前置条件

**必须先满足 §3（visibility SSOT、registry 纯函数、stub 锚点 = last_full_inject）。**  
未完成 P1.1 前，不得将 P1 标为生产就绪。

### 7.2 决策表（对 visibility 有效 payload 求值）

| 条件 | 行为 |
|------|------|
| visibility 内无该 id 的 full payload | **FULL** inject |
| 再次 @，hash 不变，锚点 turn 的 full **仍在 visibility** | **STUB** |
| hash 变更 | **FULL** + 版本提示 |
| 同轮 metadata 含重复 attachment id | 只 **FULL 一次**（按 id 去重） |
| stub 锚点 full 已不可见 | **禁止 STUB** → FULL 或 P5 tool |

### 7.3 Stub 模板

```text
[Attachment reference]
用户再次引用「{filename}」(id={attachment_id})。
完整内容已在第 {stub_anchor_turn} 轮 user 消息中提供。
如需重新查看原文，请说明「重新读取/再看一遍」或使用 read_attachment（P5）。
```

### 7.4 测试（已有 + 待补）

| 测试 | 断言 |
|------|------|
| `test_registry_*` | 见 `tests/test_attachment_registry.py` |
| `test_attachment_working_set` | working set 含 user snapshot |
| **待补** `test_same_turn_duplicate_attachment_id` | 单 message 双份同 id 仅 1× full |
| **待补** `test_stub_forbidden_when_anchor_not_visible` | slim 后锚点 turn 无 full → 不得 stub |
| **待补** `test_out_of_window_refull_with_working_set_trim` | 缩小 `working_set_turns` 后 re-@ full |

---

## 8. P2 — Force re-read（临时方案）

### 8.1 当前

- 固定短语表触发 full re-inline；更新 `last_full_inject_turn`。
- stub 含 filename、attachment_id、hash 前缀。

### 8.2 局限（已知）

- 口语化说法无法覆盖 → **脆弱**。
- 本质是 P5 Pull 的降级预览。

### 8.3 演进

- **P5 上线后废弃短语表**；改为模型调 `read_attachment` / `analyze_image`。
- 或 send 层对显式 `@` 直接 full，不依赖用户措辞。

---

## 9. P3 — 长对话降压（Push 时代兜底）

### 9.1 Goal（修订）

**不是**终态方案；**不**与 P5 catalog 重复造轮子。

目标：在 **Pull 未启用** 时，降低 **仍在 working set 内但较老** turn 的 heavy payload；**不**误伤最近 N turn 的可追问性。

### 9.2 与 working set / slim 的关系

| 机制 | 触发 | 作用 |
|------|------|------|
| **Layer1** `working_set_turns` | 每轮 `finalize_turn` | 整 turn 移出 session working set |
| **Layer2** `memory.slim` + attachment compaction | 每轮 `before_run` | 运行时压缩 **可见** history |
| **Layer3（P5）** catalog | 每轮注入 | 索引不随 window 消失 |

**优先级：** Layer3 启用后，Layer2 对 attachment 仅作可选兜底；Layer1 窗外 → P1 full re-@ 或 Pull tool。

**无 slim 时：** 仅 Layer1；长 doc/大图靠 turn 截断 + re-@ / Pull，可能撞 token 上限 — 文档化此限制。

### 9.3 做什么（细化）

1. **P3-a（紧急）：** 移除「对所有 user attachment 行 unconditional strip」；改为 `keep_full_attachment_turns`（默认 3）内 **不 strip**。
2. **P3-b：** `finalize_turn` 截断 **前**，对即将滑出 turn 写 compact metadata（可选持久化 DB）。
3. **P3-c：** 文档 snapshot → 截断摘要（N chars）；图片 → 静态 placeholder 或 **一次性** utility caption（非 upload 路径）。

**不做：** 用 P3 strip 替代 P5 catalog；registry `still_in_window` 字段（用 visibility 计算代替）。

### 9.4 测试

见 `tests/test_attachment_compaction.py`；待补「最近 3 turn 不 strip + Turn2 无 @ 仍可答」。

---

## 10. P4 — Prompt caching（平台层）

**不做 provider 特判。** DeepSeek / Qwen / MiniMax / GPT 等默认均为厂商侧**全自动隐式前缀缓存**；Claude 若需显式断点，应单独 opt-in 设计，不混进全局开关。

平台侧唯一值得治理的：

1. **稳定前缀**：tools → system → 稳定知识 → 历史 → 本轮动态输入；序列化逐字节一致（catalog 已按 `attachment_id` 排序）。
2. **别破坏前缀**：catalog gist enrich、LTM 注入等可变内容会拉低 Auto 命中率——见 §11 与 catalog 设计权衡。
3. **（可选，未做）** usage 归一化，用于成本看板，不影响 cache 是否生效。

---

## 11. P5 — Pull + Catalog（架构终态）

### 11.1 与 P1 的关系（叠加，非替换）

| 机制 | 职责 |
|------|------|
| **P1 registry** | Push 模式下 history 内是否重复 inline |
| **P5 catalog** | 附件「存在性 + gist」**不随 window 消失** |
| **P5 tools** | 按需 page-in full payload |
| **P1 + P5** | tool 调用后本轮 context 有 full；registry 可扩展为「本轮已 page-in 集合」防重复 tool |

P5 后「同文件第二次是否调 tool」仍依赖 **本轮 context 是否已有内容**，与 P1 同类判断。

### 11.2 P5a — Attachment catalog（索引常驻）

**注入点：** `AttachmentCatalogContextProvider`（与 `LongTermMemoryProvider` 同级）或 platform instructions 动态尾部。

**每轮重建，不进 sliding window：**

```text
[Chat attachments — index only; use read_attachment / analyze_image for full content]
- id=… filename=report_q3.docx gist="Q3 财报，含营收与风险提示" kind=doc
- id=… filename=arch.png gist="系统架构图，网关+三微服务" kind=image
```

**Gist 来源（不新增 upload VLM）：**

| 类型 | Bootstrap | Enriched |
|------|-----------|----------|
| doc | extract 前 120 字 | 首轮 QA 后 utility/规则抽一句 → `chat_attachments.gist` |
| 图片 | filename | 首轮 Q+A 拼接 gist |

**热/冷分层（二期）：** 最近引用 + 本轮 `@` 全列；更老仅 `search_attachments(query)`（平台内置 ILike/gist，**不走 KB RAG**）。

### 11.3 P5b — Pull tools

| Tool | 用途 |
|------|------|
| `read_attachment(id, query?)` | Lite extract / Native 文本；服务端校验 `chat_id` |
| `analyze_image(id, question?)` | Vision；**前置验证**各 provider tool_result 是否支持 image block |
| `search_attachments(query)` | 冷层索引（二期） |

**Run 级缓存：** `(attachment_id, query_hash)` 本轮不重复读。

**用户可见：** tool 调用时模型可简述「重新查看了《xxx》」。

**与 `@`：** catalog 列 **本 chat 全部上传**；tool 仅读本 chat；`@` = 显式聚焦 / 可选 send 预读。

### 11.4 P5c — Thin send

- `@` 时 user message 仅「附件已就绪：{filename} (id=…)」+ catalog 索引。
- 可配置 **首 turn 仍 inline**（降 latency），后续 Pull。

### 11.5 Provider 兼容性（P5 前置验证）

实施前矩阵摸底：`analyze_image` 的 tool_result 在各 provider 是否可携带 vision content。

### 11.6 测试

| 测试 | 断言 |
|------|------|
| catalog 注入 | 每轮 prompt 含 index；working set 截断后仍在 |
| `read_attachment` | 返回 snapshot；跨 chat 拒绝 |
| P1+ P5 | 已 page-in 本轮不重复 inline + 不重复 tool（可配置） |

---

## 12. 配置与迁移

| 项 | 说明 |
|----|------|
| Alembic `026` | `chat_attachments.content_hash` ✅ |
| Alembic（P5a） | `chat_attachments.gist` TEXT NULL |
| `.env.example` | `ATTACHMENT_MAX_BYTES_PER_FILE=5242880` |
| Agent `memory.working_set_turns` | Layer1 turn 窗口（**非 token**） |
| Agent `memory.slim.enabled` | Layer2 默认 true；与 attachment compaction 将解耦 |
| Agent `memory.attachment_compaction`（待增） | `keep_full_turns`、`doc_summary_chars` |

---

## 13. 推荐实施顺序

```text
已完成：P0, P0′, P1 核心, P2, working set user 行热修

下一步（按优先级）：
  P1.1  visibility SSOT + stub_anchor=last + slim 止血（P3-a）  ← 阻塞生产正确性
  P5a   catalog + gist 持久化                                  ← 长对话终态地基
  P5b   read_attachment / analyze_image + run 缓存
  P5c   thin send（可配置首 turn inline）
  P3-b  finalize_turn 滑出前 compact（可选兜底）
  P4    caching
  废弃  P2 关键词表（P5 后）
```

每个阶段 **独立 PR** + 自动测试 + 手工 checklist。

---

## 14. 附录：行为对照

| 场景 | Push（P1，visibility 正确时） | P5 Pull 后 |
|------|-------------------------------|------------|
| 首轮 `@` doc | full snapshot inline | 可 thin + tool |
| 再次 `@` 同 doc | stub | catalog + 按需 read |
| 不 `@` 问「刚才文档」 | 靠 history full | catalog + model 调 tool |
| 长对话 30 turn | Layer1 截断 + P3 摘要 | catalog 仍在 |
| 图片 3× `@` | 1× vision + 2× stub | catalog + analyze_image |
| Lite 同文件连传 | 1 blob（hash） | 同左 |

---

## 15. 附录：request 管道（单页参考）

```text
User send
  → commit user row (metadata + snapshot)
  → prior_rows = working_set \ current turn
  → materialization plan (registry on visibility)  ← P1.1 须含 slim 后 effective view
  → current run_input
  → HistoryProvider.get_messages → to_maf_messages(prior)
  → PlatformSlimCompaction.before_run (Layer2)
  → AttachmentCatalogProvider (P5, 每轮注入)
  → agent.run (+ read_attachment tools, P5)
  → finalize_turn → merge user+assistant → take_last_turns (Layer1)
```
