# Chat Attachments

平台级聊天附件能力：用户把文件上传到某个 chat 的附件库，再通过 composer 的 staged chips / `@` mention 随消息发送；后端按当前模型能力把内容注入 LLM（file_id / inline / PDF 栅格化 / 文本抽取）。

与 **知识库（KB / Hybrid Search）** 无关；与 **制品（artifacts）下载** 也无关——附件没有公开 download API，字节只在服务端 materialize 时读取。

对所有 agent 可用，不依赖 `profile.yaml` 的 `allowed_tools`。

---

## 总览数据流

```
用户上传文件
  → POST /chats/{id}/attachments
  → 校验 / 哈希去重 / 落盘（本地或 Blob）
  → 可选：上传到模型 Provider Files API
  → 写入 chat_attachments
  → 前端 chat library + staged / @mention

用户发送消息
  → MessageCreate.attachment_ids
  → AttachmentService.resolve_for_message
  → 写 user message（metadata.attachments）+ link_to_message
  → materialize_attachment(s) → MAF Message contents
  → agent run

历史重放
  → metadata.attachments → build_replay_attachment_contents（first-full + reference）
```

---

## 后端布局

根目录：`backend/app/platform/attachments/`

| 模块 | 职责 |
|------|------|
| `service.py` | `AttachmentService`：upload / resolve / delete / list |
| `upload.py` | `AttachmentUploader`：校验、去重、落盘、可选 provider 上传 |
| `storage.py` | 本地 `data/chat-attachments/` 或 Vercel Blob；`inline:{uuid}` provider id |
| `validation.py` | 单文件 / 单消息 size + PDF page 预算；拒绝 Office |
| `limits.py` | 从 Settings 读限额 |
| `kinds.py` | `AttachmentKind`：`image` / `pdf` / `sheet` / `text` / `office` |
| `capabilities.py` | 按 model/provider 决定 image/pdf 传输方式 |
| `materialize.py` | 注入 LLM：`materialize_attachment(s)`、`build_user_message_with_attachments`、`build_replay_attachment_contents` |
| `metadata.py` | 消息 metadata / API 字典 |
| `pages.py` | 读字节、PDF 页数成本 |
| `hash.py` | content hash 去重 |
| `extract/text.py` | 文本解码 |
| `extract/tables.py` | xlsx / xls / csv → Markdown 表 |
| `extract/truncate.py` | 头尾截断 |
| `convert/pdf_pages.py` | PyMuPDF 页数 / JPEG 栅格化 |
| `image_io.py` | 魔数识别、校验、LLM 用规范化（含超大图自动缩小） |
| `providers/adapters.py` | OpenAI / Anthropic Files 适配 |
| `providers/deepseek_files.py` | DeepSeek Files 上传 |

相关层：

| 路径 | 说明 |
|------|------|
| `api/routes/chats.py` | list / upload / delete |
| `api/routes/config.py` | `GET /config/attachments` |
| `api/schemas.py` | `AttachmentOut`、`MessageCreate.attachment_ids` |
| `db/models.py` | `ChatAttachment` |
| `db/repositories/attachments.py` | `AttachmentRepository` |
| `platform/chat/run_service.py` | `_resolve_attachments` / `_build_run_input` / `_commit_user_turn` |
| `platform/memory/maf_mapping.py` | 历史重放时重建附件 contents |

---

## API

均需登录，且 chat 须属于当前用户（`get_owned_chat`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/config/attachments` | 限额配置（前端初始化用） |
| `GET` | `/api/v1/chats/{chat_id}/attachments` | 该 chat 附件库列表 |
| `POST` | `/api/v1/chats/{chat_id}/attachments` | multipart `file`，返回 `AttachmentOut` |
| `DELETE` | `/api/v1/chats/{chat_id}/attachments/{attachment_id}` | 删除（204） |

发送消息时在 stream / run body 中携带：

```json
{
  "content": "请看这份材料 @notes.md",
  "attachment_ids": ["uuid-1", "uuid-2"]
}
```

**没有**附件下载 / 预览字节的公开端点。

---

## 校验与限额

### 允许的类型

- 图片：png / jpeg / gif / webp
  - 上传与 materialize 时经 `image_io.prepare_image_for_storage` / `normalize_image_for_llm` 重编码
  - **超大画布**（常见于 Figma @2x 导出）：最长边 &gt; 8192px 会自动缩小至 8192 以内再发给模型；DeepSeek 等 OpenAI 兼容 API 超限时往往误报 `unsupported image` 而非尺寸错误
- PDF
- 文本：txt / md / csv / json
- 表格：xls / xlsx

### 拒绝

- Word / PPT（doc / docx / ppt / pptx）——提示另存为 PDF

### 默认限额（均可 env 覆盖）

| Setting | 默认 |
|---------|------|
| `ATTACHMENT_MAX_FILES_PER_MESSAGE` | 5 |
| `ATTACHMENT_MAX_BYTES_PER_FILE` | 20 MB |
| `ATTACHMENT_MAX_TOTAL_BYTES_PER_MESSAGE` | 50 MB |
| `ATTACHMENT_MAX_PAGES_PER_FILE` | 50（单 PDF） |
| `ATTACHMENT_MAX_PAGES_PER_MESSAGE` | 60（消息合计） |
| `ATTACHMENT_EXTRACT_MAX_CHARS_PER_FILE` | 32 000 |
| `ATTACHMENT_EXTRACT_MAX_CHARS_PER_MESSAGE` | 80 000 |
| `ATTACHMENT_TABLE_MAX_ROWS_PER_SHEET` | 2000 |

上传时校验单文件；发送时再跑消息级 size / page 预算。

---

## 存储与数据库

### 平台存储（始终）

`save_inline_attachment`：

- 本地：`backend/data/chat-attachments/{chat_id}/{attachment_id}`
- Blob 开启时：`chat-attachments/{chat_id}/{attachment_id}`（与制品共用 `ARTIFACT_STORAGE` / `BLOB_READ_WRITE_TOKEN`）

若无可用的 Provider Files API，则 `provider_file_id = "inline:{attachment_id}"`。

### Provider 文件（可选）

当当前模型的 `AttachmentCapabilities` 支持 `image_file_id` / `pdf_file_id` 时，上传时额外打到对应 Files API，并写入真实 `provider_file_id`。切换模型后若 provider 不一致，materialize 会回退到 inline 读盘。

### 去重

同一 chat 内相同 `content_hash` 直接返回已有行，不重复落盘。

### 表 `chat_attachments`

| 列 | 说明 |
|----|------|
| `id` | UUID |
| `chat_id` | 所属会话 |
| `message_id` | 发送后 link；未发送前可为 null |
| `provider` | 上传时使用的模型 provider（可空） |
| `provider_file_id` | Provider file id 或 `inline:{id}` |
| `filename` / `mime_type` / `size_bytes` | 元数据 |
| `content_hash` | SHA-256 去重 |
| `gist` | 预留目录索引（当前上传路径未写） |
| `created_at` | 时间戳 |

相关迁移：`021_chat_attachments`、`026_..._content_hash`、`027_..._gist`。

---

## 前端交互

### 关键文件

| 路径 | 作用 |
|------|------|
| `pages/ChatPage.tsx` | 上传、staged、mention、发送编排 |
| `lib/attachments.ts` | 限额类型、accept 列表、粘贴/校验 |
| `lib/attachmentUpload.ts` | pending id、staged + mention 合并 |
| `lib/attachmentMentions.ts` | `@` 解析 / 插入 / 过滤 |
| `lib/attachmentCompat.ts` | 是否可引用（上传完成等） |
| `components/ComposerStagedChips.tsx` | 待发送 chips |
| `components/ComposerMentionInput.tsx` | 带 mention 高亮的输入 |
| `components/AttachmentMentionPopup.tsx` | `@` 弹出选择 |
| `components/MessageBubble.tsx` | 用户消息上的附件 chip（来自 metadata） |
| `api/client.ts` | `getAttachmentConfig` / `list|upload|deleteChatAttachment`；stream 带 `attachment_ids` |

### 状态模型

1. **Chat library**：该 chat 已上传的全部附件（`listChatAttachments`）
2. **Staged chips**：`stagedAttachmentIds`，发送时一并带上
3. **`@` mention**：输入 `@` 从 library 选文件，文本里写 `@filename`；发送时再解析成 id

实际上传入口：文件按钮、拖拽进 composer、粘贴截图（无 `text/plain` 时）。

上传中会用临时 `pending-{uuid}`，成功后替换为真实 id 并保持 staged。

发送合并逻辑（概念上）：

```ts
mergeAttachmentIdsForSend(stagedIds, parseAttachmentMentionIds(text, attachments))
```

### 类型（与后端对齐）

```ts
// ChatAttachment / AttachmentOut
{
  id: string
  chat_id: string
  filename: string
  mime_type: string
  size_bytes: number
  provider: string | null
  provider_file_id: string | null
  created_at: string
}

// 写入 message.metadata.attachments 的项
{
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  provider: string | null
  provider_file_id: string | null
}

// AttachmentLimits（来自 GET /config/attachments）
{
  max_files_per_message: number
  max_bytes_per_file: number
  max_total_bytes_per_message: number
  max_pages_per_file?: number
  max_pages_per_message?: number
}
```

---

## LLM 注入（first-full + reference + re-inline on @）

核心：`materialize.py`。发送与历史重放走同一套路径（重放用 `build_replay_attachment_contents`）。

### 引用策略

| 场景 | 行为 |
|------|------|
| 会话内**首次** `@` 某 attachment | full materialize（文本 / 图片 / PDF 等） |
| 同会话**再次** `@`，且 context 里仍有该文件的 full inline | 只发 **reference stub**（含 `attachment_id=`） |
| slim / compaction 把 full inline stub 化，或 history tail 截断掉 full 版本 | context 中视为**无 full 副本**；**不会**自动 re-inline |
| stub 化之后用户**再次** `@` 同一文件 | 重新 full materialize |

判定「context 里是否还有 full 副本」看 message **contents**（`hosted_file` / `data` / 带 ` ``` ` 的文本块），**不是**只看 `metadata.attachments` 是否出现过。

Slim 往返时在 row metadata 写入 `attachment_inline_modes`（`full` / `reference`），避免 passive replay 把 stub 误重建为 full。

### 按 kind

| Kind | 行为 |
|------|------|
| **IMAGE** | 可用 provider file_id → `Content.from_hosted_file`；否则 inline `Content.from_data` |
| **PDF** | `file_id` → hosted；`file_data` → PDF bytes；`raster` → 每页 JPEG |
| **SHEET** | 抽 Markdown 表 → text block（行数 cap） |
| **TEXT** | 解码 → text block |

文本块形态大致为：标题行 `### filename (mime, size)`，可选 note / truncated 提示，再跟 fenced 正文。

文本 / 表格受 per-file / per-message 字符上限截断。用户原文字与附件文本合并，binary / image / pdf parts 追加到 MAF `Message.contents`。

### Capabilities（`capabilities.py`）

按 **model id 优先，其次 provider**，默认 `image=inline`、`pdf=raster`。

示例：

| 模型 / Provider | Image | PDF |
|-----------------|-------|-----|
| gpt / Azure OpenAI | inline | file_id |
| Claude / Azure Anthropic | file_id | file_id |
| Qwen / DashScope | inline | file_data |
| MiniMax / SiliconFlow / DeepSeek 默认 | inline 或 file_id | raster |

`ModelEntry.supports_attachments`：带 `MODEL_ROLE_CHAT` 的可选模型为 true；worker-only 为 false。

---

## 与其它能力的边界

| 主题 | 行为 |
|------|------|
| **知识库** | KB 走 Hybrid Search / Memory scope；chat attachments 是用户上传到会话的文件库，两条线独立 |
| **制品 artifacts** | 有 download / preview URL；attachments **没有**下载 API |
| **Fork chat** | 当前 fork **不复制** attachments（只复制消息） |
| **PII redaction** | 中间件只 redact **text** Content；image / PDF binary 不扫；抽成文本的 sheet/text 会经过 |
| **Blob delete** | Blob 模式下删附件可能只删 DB（storage delete 为 no-op） |
| **Office** | 前后端均拒绝 Word/PPT |

---

## Phase 2：Parse + Hydrate + doc_retrieval

Parse pipeline 完成后，parsed 产物落在 `chat-attachments/{chat_id}/parsed/{attachment_id}/`（`content.md`、`meta.json`、`pageindex.json`、`figures/`）。国产模型（DeepSeek / Qwen / MiniMax 等）在 parse ready 时走 **双层 Hydrate**，不再 inline 32k 截断或 PDF 栅格化；Claude/GPT 默认仍用 file_id（`DOCUMENT_HYDRATE_UNIFIED=false`）。

### Hydrate 注入

| 块 | 内容 |
|----|------|
| **Turn manifest** | 本 turn `@` 的附件：filename、pages/lines、figure 数、section 摘要、tool 提示 |
| **Chat library index** | 全 chat ready 附件紧凑目录（默认最多 20 条） |

配置：`HYDRATE_PREVIEW_MAX_BYTES`、`HYDRATE_LIBRARY_MAX_ITEMS`、`DOCUMENT_HYDRATE_UNIFIED`。

### doc_retrieval 工具（全 agent 自动注入）

与 `platform_time` 相同，六个 attachment 工具由 `AgentFactory` 自动挂载，**无需**在各 agent `profile.yaml` 的 `allowed_tools` 重复声明：

| Tool | 用途 |
|------|------|
| `attachment_find` | 模糊指代 → top 5 candidates |
| `attachment_list_chat` | 全 chat 附件目录 |
| `attachment_grep` | 搜 `content.md` |
| `attachment_read` | 按行/页/章切片 |
| `attachment_list_sections` | 结构目录 |
| `attachment_read_figure` | 读镜像 figure → vision base64 |

鉴权：**chat_library** — 同 chat 任意 parse ready 附件可读；turn manifest 仅控制 Hydrate 注入范围。

模块：`backend/app/platform/doc_retrieval/`；注册于 `platform/agent/builtin_registry.py`。

---

## 关键代码入口（快速跳转）

```
backend/app/platform/attachments/service.py      # 门面
backend/app/platform/attachments/materialize.py  # LLM 注入
backend/app/platform/attachments/capabilities.py # 模型路由
backend/app/api/routes/chats.py                  # HTTP
backend/app/platform/chat/run_service.py         # 发送编排
backend/app/platform/doc_retrieval/              # grep/read/find + hydrate manifest
parse-pipeline/parse_pipeline/normalize/         # figure 镜像 + meta.pages
backend/app/platform/docstore/                   # parsed artifact 存储
frontend/src/pages/ChatPage.tsx                  # UI 编排
frontend/src/lib/attachmentMentions.ts           # @ mention
frontend/src/lib/attachmentUpload.ts             # staged 合并
```
