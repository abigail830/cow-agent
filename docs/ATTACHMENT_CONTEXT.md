# 聊天附件 Context 管理方案

> 解决多轮对话中「同一文件/图片被反复 @」导致的 **重复注入 context** 问题。  
> 范围：Native（mode1）与 Unify-lite（mode2）；**不含**大文件向量检索（超大文件走知识库 MCP）。

**相关代码**

| 区域 | 路径 |
|------|------|
| 上传 / 解析 | `backend/app/platform/attachments/` |
| 发消息组装 | `backend/app/platform/chat/run_service.py` → `_build_run_input` |
| Lite 混合 builder | `backend/app/platform/attachments/unify_lite/message_builder.py` |
| 历史 replay | `backend/app/platform/memory/maf_mapping.py` → `to_maf_messages` |
| 前端 @ 引用 | `frontend/src/lib/attachmentMentions.ts` |
| 体积限制 | `backend/app/config.py` → `ATTACHMENT_MAX_*` |

**现状摘要（已实现）**

- 上传进材料库 → 只写 blob，**不**自动进 LLM context。
- 发送时仅 `@filename` 解析出的 attachment 进入本轮（`parseAttachmentMentionIds`）。
- Unify-lite：txt/md/docx 发送时 extract；图片 **全 mode** 走 Native `Content.from_data`。
- **缺口**：history replay 对每条带 attachments 的 user 消息 **全量 replay**；Lite 文档 extract **未持久化**，replay 可能变成 raw bytes。

---

## 1. 设计原则

### 1.1 图片 vs 文档分开

| 维度 | 文档（Lite extract） | 图片（全 mode Native vision） |
|------|----------------------|-------------------------------|
| mode1/mode2 分叉 | **需要**（file API / extract） | **不需要**（主模型必 Vision） |
| 重复 @ 判定 | `content_hash` + 是否在 working set | 同左 |
| 去重后处理 | 文本 **stub 锚点** | 文本 stub（含 filename + attachment_id + 首次 turn） |
| 窗口外再 materialize | 重新 inject **extract 全文**（snapshot） | **整图 re-inline**（无局部重贴） |
| 大内容 | 5MB cap + char 截断 | 5MB cap；整图 atomic |
| 压缩降级（P3） | 摘要 / 截断 | 可选：淘汰前生成短文字占位 |

### 1.2 传输去重 ≠ 推理去重

- `file_id` / 同 blob 只传一次 → 省存储与上传。
- 只要该轮 **context 里仍 inline 整图或整篇 extract**，vision / 文本 token **照样占用**。
- **会话 registry** 解决的是 history **replay 重复 inline**，不是 provider 自动免 token。

### 1.3 范围外（明确不做）

- 附件向量检索 / RAG 分块（大文件引导用户走 **hybrid-search 知识库**）。
- Native 模式上传 **content_hash 去重**（换模型 provider 可能需重传）。
- 上传时默认跑 VLM 生成图片描述（理解仍靠 Native vision；P3 压缩占位除外）。

### 1.4 长期方向（P5）

Push（发送时塞全文/全图）→ Pull（`read_attachment` / `analyze_image` 工具按需读取）。  
P0–P2 为 Pull 改造前的 **registry + 持久化** 过渡方案。

---

## 2. 阶段总览

| 阶段 | 名称 | 目标 |
|------|------|------|
| **P0** | 文档 extract 持久化 | replay 与首轮一致，禁止 raw docx bytes |
| **P0′** | Lite 上传 hash 去重 + 5MB cap | 同 chat 不重复 blob；限制单文件体积 |
| **P1** | 会话 materialization registry | working set 内重复 @ → stub，不重复 full inject |
| **P2** | 图片 stub 规范 + force re-read | 指代清晰；用户明确要求时可整图重贴 |
| **P3** | Compaction 剥离 heavy payload | 长对话窗口压力；图片可选文字占位 |
| **P4** | Prompt caching | 降本/延迟，**不**扩 context window |
| **P5** | Pull 工具统一 | `read_attachment` / `analyze_image` |

---

## 3. P0 — 文档 extract 持久化

### 3.1 做什么

1. 用户 `@` 文档且发送时，extract 结果写入 **message metadata**（或 attachment 级 sidecar），例如：

```json
{
  "attachments": [{
    "id": "...",
    "filename": "report.docx",
    "mime_type": "application/...",
    "provider_file_id": "inline:...",
    "extracted_snapshot": {
      "content_hash": "sha256:...",
      "text": "...",
      "truncated": false,
      "char_count": 1234,
      "extracted_at": "ISO8601"
    }
  }],
  "attachment_mode": "unify_lite"
}
```

2. `build_user_run_input_lite` **优先读 snapshot**（send 路径可仍 live extract，但结果必须写回 metadata）。
3. `to_maf_messages` replay 时：
   - 文档：**只用 `extracted_snapshot.text` 拼进 lite 文本块**；
   - **禁止**对 docx/txt 走 `metadata_attachment_to_maf_content` → raw `Content.from_data`。

### 3.2 不应发生

- 第二轮对话 replay 第一轮 user 消息时，模型收到 docx 二进制 Content。
- 同一 attachment 每轮 send 都重新 parse docx（无缓存时可接受 send 时 extract 一次，replay 必须读 snapshot）。

### 3.3 自动测试

| 测试 | 位置建议 | 断言 |
|------|----------|------|
| snapshot 写入 | `tests/test_attachment_materialization.py` | mock send 后 `Message.metadata.attachments[0].extracted_snapshot.text` 非空 |
| replay 无 raw doc | `tests/test_maf_mapping_lite_docs.py` | `to_maf_messages(rows)` 中文档 attachment **无** `type=data` + docx mime |
| replay 文本一致 | 同上 | replay 的 text Content 包含 snapshot 中的关键 substring |
| 回归 extract | 现有 `tests/test_unify_lite_extractors.py` | 仍通过 |

### 3.4 手工验证

1. Unify-lite 模式，上传 `report.docx`，发送：`请总结 @report.docx`。
2. 等 assistant 回复后，再发纯文本：`刚才文档里的结论是什么？`（**不再 @**）。
3. **期望**：模型仍能回答（snapshot 已在 history 文本块中）。
4. 开发者：查 DB `messages.metadata`，确认首轮 user 消息含 `extracted_snapshot`。
5. **失败信号**：第二轮模型称「看不到文档」或 tool/API 日志出现 docx binary content block。

---

## 4. P0′ — Lite 上传 hash 去重 + 5MB 上限

### 4.1 做什么

1. **DB**：`chat_attachments.content_hash`（SHA-256 hex，可 NULL 兼容旧数据）。
2. **Unify-lite upload**：算 hash → 同 `chat_id` 下已存在相同 hash → **返回已有 attachment**（不新写 blob）。
3. **Native upload**：行为不变（不 hash 去重）。
4. **配置**：`ATTACHMENT_MAX_BYTES_PER_FILE=5242880`（5MB），`.env.example` 同步。

### 4.2 不应发生

- 同 chat、同文件内容连传两次，材料库出现两行、两个 blob。
- Native 模式因 hash 合并 attachment（换 provider 场景）。

### 4.3 自动测试

| 测试 | 断言 |
|------|------|
| `test_unify_lite_upload_dedupes_by_hash` | 同 chat 上传两次相同 bytes → 同一 `attachment.id` 或明确 409 + 同一 id |
| `test_native_upload_no_hash_dedup` | 同 bytes 上传两次 Native → 两个 attachment id（或两次 provider 流程） |
| `test_validate_rejects_over_5mb` | `validate_attachment_file` / API 400 |

### 4.4 手工验证

1. Unify-lite，上传 `a.txt`，再上传 **内容完全相同** 的 `b.txt`。
2. **期望**：材料库一条记录（或 UI 提示已存在）；第二次不新增条目。
3. 切换到 Native，同一文件上传两次（或换模型后再传）。
4. **期望**：仍允许两次独立上传（或 provider 绑定行为与现网一致）。
5. 上传 6MB 文件 → **期望**：前端/ API 明确报错，提示 5MB 限制与知识库引导文案。

---

## 5. P1 — 会话 materialization registry

### 5.1 做什么

维护 **per-chat**（或从 message 序列推导）的注入状态：

```text
registry[attachment_id] = {
  content_hash,
  materialized_kind: "extract_text" | "vision",
  first_inject_turn_sequence,
  last_full_inject_turn_sequence,
}
```

**Send 路径（`run_service._build_run_input`）**

| 条件 | 行为 |
|------|------|
| 首次 @ 该 attachment（本 working set 内） | **full inject**（文档 snapshot 文本块 / 图片 `Content.from_data`） |
| 再次 @，hash 不变，首次 inject 仍在 working set | **stub 文本**，不 full inject |
| hash 变（重传同名新内容） | full inject + stub 提示「新版本」 |
| 首次 inject 已滑出 working set | full inject（模型物理上看不到旧内容） |

**Replay 路径（`to_maf_messages`）**

- 与 send **同一规则**：每条历史 user 消息重建时，按 registry + turn 顺序决定 full vs stub。
- working set 内同一 `attachment_id` **最多一条 user 消息** 带 full payload（建议：**保留 first full inject 那条**，后续历史 turn 改为 stub）。

### 5.2 Stub 模板（文档 / 图片）

```text
[Attachment reference]
用户再次引用「{filename}」(id={attachment_id})。
完整内容已在第 {first_turn} 轮 user 消息中提供。
如需重新查看原文，请在消息中说明「重新读取/再看一遍」。
```

图片 stub **必须**含 filename + attachment_id，避免多图指代混淆。

### 5.3 不应发生

- 同 chat、working set 内 3 次 `@chart.png`，API 请求中 history 出现 **3 份** 相同 vision Content。
- 文档第二次 @ 仍贴完整 extract 全文（hash 未变且在 window 内）。

### 5.4 自动测试

| 测试 | 断言 |
|------|------|
| `test_registry_first_at_full_second_stub` | 模拟两轮 send input：第二轮 `Message.contents` 无第二份 `type=data` 图片 |
| `test_registry_replay_dedupes_three_turns` | 3 条 user rows 同 attachment_id → `to_maf_messages` 仅 **1** 个 image data block |
| `test_registry_out_of_window_refull` | 缩小 working_set_turns，最老 full inject 被截断 → 新 @ 触发 full inject |
| `test_registry_hash_change_rematerialize` | 同 filename 新 hash → full inject + metadata 标记 |

可选：**集成测试** 带 mock LLM client，统计每轮 request 中 image block 数量。

### 5.5 手工验证

**图片**

1. 上传 `chart.png`，Turn1：`分析 @chart.png` → 确认回复合理。
2. Turn2：`@chart.png` 里左上角数字是多少？（再次 @）
3. **期望**：Turn2 仍答对；开发者检查 backend 日志 / debug hook：Turn2 的 **request** 中 history 不应含 **两份** 完整 chart 二进制块（若仅有 stub + Turn1 一份 full，为 PASS）。
4. Turn3：不发 @，问「还是刚才那张图」→ 依赖 Turn1 full + stub 指代。

**文档（Lite）**

1. `@report.docx` 总结 → 再 `@report.docx` 问细节。
2. **期望**：第二轮 user Message 文本含 stub，**不含** 第二份完整 doc extract 块。

**窗口外**

1. 连续对话超过 `working_set_turns`（或临时把配置改小为 4），使 Turn1 滑出。
2. 再次 `@` 同一文件。
3. **期望**：重新 full inject；模型仍能读取（文档 snapshot / 图片整图）。

---

## 6. P2 — 图片 stub 规范 + force re-read

### 6.1 做什么

1. 固化 stub 字段：`filename`、`attachment_id`、`first_inject_turn`、`content_hash` 前 8 位。
2. **Force re-read 触发**（任一词出现在 user 文本即 full re-inline）：
   - 「重新读取」「再看一遍」「重新查看原文」「re-read attachment」等（可配置短语表）。
3. force 时 **更新** `last_full_inject_turn_sequence`，后续重复 @ 再回 stub 逻辑。

### 6.2 自动测试

| 测试 | 断言 |
|------|------|
| `test_force_reread_phrase_triggers_full_image` | 第二轮带「再看一遍 @x.png」→ 含 `Content.from_data` |
| `test_stub_contains_attachment_id` | stub 文本含 UUID |

### 6.3 手工验证

1. 同一图 @ 两次（第二次应 stub）。
2. 第三次消息：`请再看一遍 @chart.png 确认颜色`。
3. **期望**：第三轮 request 含 **新的** full image block；模型能回答颜色细节。

---

## 7. P3 — Compaction 剥离 heavy payload

### 7.1 做什么

1. 平台 compaction / working set 截断时，对 **即将滑出** 的 user 消息：
   - 文档：保留 extract 摘要或 stub（可截断至 N chars）。
   - 图片：可选调用 **一次性** 短 caption 占位（**非** upload 路径；仅 compaction 钩子）。
2. registry 标记 `still_in_window=false`，下次 @ 走 P1「窗口外 → full materialize」。

### 7.2 自动测试

| 测试 | 断言 |
|------|------|
| `test_compaction_strips_image_data_from_old_turn` | compaction 后 old row metadata 无 inline payload，有 placeholder |
| `test_after_compaction_re_at_reinlines` | 同 P1 out-of-window |

### 7.3 手工验证

1. 长对话（>20 turn）带大图，触发 memory compaction（若 agent 配置了 compaction）。
2. 确认旧 turn 不再占满 request 体积（日志 / token 估算）。
3. 再次 @ 同一图 → 模型仍能分析（re-inline 或占位 + re-inline 策略按实现为准）。

---

## 8. P4 — Prompt caching（可选）

### 8.1 做什么

- 将 **稳定的** system + 早期 materialized 块置于 prompt 前缀，利用 Anthropic/OpenAI caching。
- **不**作为重复 @ 的主方案；window 占用不变。

### 8.2 验证

| 类型 | 方法 |
|------|------|
| 自动 | 若 provider 返回 `cache_read_input_tokens`，断言第二轮 > 0（集成环境，可 skip CI） |
| 手工 | 对比同一长对话第 2–5 轮 latency / 账单 caching 行 |

---

## 9. P5 — Pull 工具（长期）

### 9.1 做什么

- 平台 builtin：`read_attachment(attachment_id, query?)`、`analyze_image(attachment_id, question?)`。
- `@` 时 user Message 仅：**「附件已就绪：{filename} (id=…)」**，不 inline 全文/全图（或首 turn 仍 inline，可配置）。
- mode1：内部走 Native file_id / vision；mode2：internal extract + 可选片段。

### 9.2 自动测试

| 测试 | 断言 |
|------|------|
| tool 注册 | `platform_time` 同级注入 allowlist |
| `read_attachment` | 返回 extract 文本；未 @ 的不返回 |
| agent 集成 | mock agent 调 tool 后 answer 含文件内容 |

### 9.3 手工验证

1. 上传 doc，发送「根据 @report.docx 回答」**不含**全文 inject（Pull 模式开启时）。
2. 观察 process 步骤：`read_attachment` 被调用 → 再出答案。
3. 同文件第二次提问不重复调 tool（模型判断已读过）或调 tool 带 query（按 prompt 设计）。

---

## 10. 配置与迁移清单

| 项 | 说明 |
|----|------|
| Alembic | `chat_attachments.content_hash`（P0′） |
| `.env.example` | `ATTACHMENT_MAX_BYTES_PER_FILE=5242880` |
| `docs/UNIFY_LITE.md` | 历史规划文档；实现状态以本文为准 |
| Agent profile | `memory.working_set_turns` 影响 P1「窗口外」判定 |

---

## 11. 推荐实施顺序

```text
P0   文档 snapshot（正确性）
P0′  Lite hash 去重 + 5MB（材料库 hygiene）
P1   registry dedupe（核心：重复 @）
P2   图片 stub + force re-read（体验）
P3   compaction 降级（长对话）
P4   caching（成本）
P5   Pull 工具（架构统一）
```

每个阶段 **独立 PR**，附带对应 § 自动测试 + 手工 checklist 勾验后再合并下一阶段。

---

## 12. 附录：当前行为 vs 目标（对照）

| 场景 | 当前 | P0 后 | P1 后 |
|------|------|-------|-------|
| Lite doc 首轮 @ | extract inline | + snapshot 落库 | 同左 |
| Lite doc replay | 可能 raw bytes | snapshot 文本 | stub 去重 |
| 图片 3 轮各 @ 一次 | 3× vision in history | 3×（未变） | **1× full + 2× stub** |
| Lite 同文件连传两次 | 2 blob | 2 blob | **1 blob（P0′）** |
| 未 @ 的文件 | 不进 context | 同左 | 同左 |
