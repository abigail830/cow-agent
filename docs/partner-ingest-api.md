# OpenKMS 知识入库对接文档（对方 Vercel 服务）

面向外部系统：创建频道与 RAG 知识库，异步上传文件并自动 parse / ASR / 索引，失败重试，读取原件与 `markdown.md`。

**本侧 API 也跑在 Vercel。** 对接时把「小 JSON 走 API、大文件直传 OSS」当成硬约束，不要把文件字节再绕一层 serverless。

Base URL：本平台 **backend** 主机（不是前端 SPA）。

---

## 0. 鉴权（Bearer）

本文列出的 **本平台 HTTP API 全部使用同一个 header**：

```http
Authorization: Bearer <token>
```

`<token>` 二选一：

| Token | 形态 | 给谁用 |
|-------|------|--------|
| **User API Key（对接推荐）** | `okf_` 开头 | 对方服务端长期调用 |
| 登录 JWT | 普通 JWT | 人在浏览器里操作本平台时 |

本侧 `requireAuth` 看到 `okf_` 就按 API Key 解析成 **签发该 Key 的用户**；其余当 JWT。Key 与用户同权限（RBAC + 资源 ACL），不是另套 Basic Auth / 签名 query。

**对接这条入库链路，Key 需要对以下资源有对应级别：**

| 能力 | RBAC 资源 | 级别 |
|------|-----------|------|
| 列/建/改频道、workflow、读文档/capture | `documents` | 读或写（写接口要 write） |
| 列/建知识库、绑 RAG、workflow | `knowledge-bases` | 读或写 |

另外还有 **对象级 ACL**：频道 / 知识库的创建者自动有权限；别人分享的也能出现在 list 里。对某个 `channel_id` / `knowledge_base_id` 没有权限会 **403 Forbidden**（已登录但未授权），没带 Token 是 **401 Unauthorized**。

签发 Key：本平台用户 **登录 JWT**（不能用 `okf_`）调用 `POST /api/user/api-keys`，明文只返回一次。对方把 `okf_...` 放服务端环境变量，不要进前端。

**不用 Bearer 的例外（不是本 API）：**

| 调用 | 鉴权 |
|------|------|
| `PUT` / `GET` OSS presigned URL | URL 自带签名，**不要**再加 `Authorization` |
| 本平台打到对方的 webhook | 对方验 `X-OpenKMS-Signature`（HMAC），不是 Bearer |

OpenAPI：`GET /api/openapi.json`（同样要 Bearer，除登录/health 外）。

---

## 0.1 Vercel 对接必须遵守的规则

| 规则 | 原因 |
|------|------|
| **API 请求体只传 JSON 元数据**，不要把文件 POST 到本 API | Vercel 请求体上限约 **4.5 MB**，超出会 `413` |
| **上传：本 API 只签发 presigned URL → 调用方对 OSS 做 HTTP PUT** | 签名是本地 HMAC，不连 OSS。若把文件经本 API 或对方 Vercel 中转去阿里云华南，跨境 TCP 容易 `ETIMEDOUT` / `fetch failed` |
| **下载：本 API 只返回短时 presigned GET → 调用方对 OSS 做 GET** | 同上，禁止让本 API 把 `markdown.md` / 原件流式转发出去 |
| **Presigned URL 当场用、不要缓存** | 上传约 1h、文档读约 15min；过期是 OSS **403**，不是超时。过期后重新调创建（可用同一 `Idempotency-Key`）拿新 URL |
| **PUT 的 `Content-Type` 必须与签发时完全一致** | 否则 OSS 立即 403 |
| **Webhook handler 必须在约 10s 内 2xx** | 本侧同步 POST、超时 10s、不重试。对方 handler 里不要做 parse / 写库长事务 |
| **终态以 GET workflow 为准** | Webhook 是加速通知；漏事件、对端超时都以 GET 对账 |
| **对方 webhook URL 必须公网 https** | 创建时拒绝 http / localhost / 内网 / 云 metadata |
| **本 Workflow 只支持 RAG 知识库** | `page_index` / `faq` 不要绑到这条链路 |

推荐调用形态：对方 Vercel 函数只调本 API 的小 JSON；文件 PUT/GET 尽量从 **能访问阿里云 OSS 的环境**（用户浏览器、国内 worker、或已验证可达的运行时）发出，不要默认从 Vercel HK 直连 OSS。

---

## 1. 列出当前用户可见的频道（可选）

```http
GET /api/knowledge/document-channels
Authorization: Bearer okf_...
```

返回该用户 **有读权限** 的频道树（自己创建的 + 被分享的），含 `id`、`name`、pipeline 字段。不必每次新建频道。

---

## 1.1 创建 Document Channel

频道决定文件落在哪、以及 document parse / 音频转写 / capture 后处理用哪套 pipeline。创建时会继承系统默认 pipeline；建议创建后再核对三个 pipeline id。

### 1.2 可选：列出可用 pipeline

```http
GET /api/knowledge/document-channels/processing-options
```

响应：

```json
{
  "document_pipelines": [{ "id": "uuid", "name": "...", "pipelineName": "..." }],
  "transcription_pipelines": [{ "id": "uuid", "name": "...", "pipelineName": "..." }],
  "post_process_pipelines": [{ "id": "uuid", "name": "...", "pipelineName": "..." }]
}
```

### 1.3 创建频道

```http
POST /api/knowledge/document-channels
Content-Type: application/json
```

```json
{
  "name": "外部接入-客户A",
  "description": "可选",
  "parent_id": null
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 1–256 字符 |
| `description` | 否 | |
| `parent_id` | 否 | 挂到已有频道下时，调用方需对该父频道有 **manage** 权限 |

**201** 响应（节选）：

```json
{
  "id": "uuid",
  "name": "外部接入-客户A",
  "pipeline_id": "uuid | null",
  "transcription_pipeline_id": "uuid | null",
  "post_process_pipeline_id": "uuid | null",
  "auto_start_pipeline": false
}
```

记下 `id`，后面 workflow 的 `channel_id` 用它。

### 1.4 如需指定 pipeline

```http
PUT /api/knowledge/document-channels/:id
```

```json
{
  "pipeline_id": "<document parse pipeline uuid>",
  "transcription_pipeline_id": "<audio ASR pipeline uuid>",
  "post_process_pipeline_id": "<capture post-process pipeline uuid>",
  "auto_start_pipeline": true
}
```

`auto_start_pipeline` 建议为 `true`，否则 attach 后可能不自动开 parse/ASR。需要对该频道 **manage**。

---

## 2. 知识库

本条入库链路 **只支持 `type: "rag"`**。先 list 复用已有库，没有再创建。

### 2.1 列出当前用户可见的知识库

```http
GET /api/knowledge/knowledge-bases
Authorization: Bearer okf_...
```

需要 `knowledge-bases` **read**。返回该用户能读的全部知识库（自己创建的 + ACL 分享的；平台 admin 可见全部）。

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "客户A-RAG",
      "description": "...",
      "type": "rag",
      "pipeline_id": "uuid",
      "pipeline_name": null,
      "embedding_model_config_id": "uuid",
      "embedding_dimensions": 1024,
      "is_configured": true,
      "item_count": 12,
      "created_by": "uuid",
      "created_at": "2026-09-15T10:00:00.000Z",
      "updated_at": "2026-09-15T12:00:00.000Z",
      "capabilities": {}
    }
  ]
}
```

对接入库时用 `type === "rag"` 的项，取其 `id` 作为 `knowledge_base_id`。`item_count`：RAG 为已索引文档数。

### 2.2 创建知识库

```http
POST /api/knowledge/knowledge-bases
Content-Type: application/json
```

```json
{
  "name": "客户A-RAG",
  "description": "可选",
  "type": "rag"
}
```

`type` 只允许 `rag`（平台另有 `page_index` / `faq`，**不要**用在下面的 Workflow）。

**201** 记下 `id`，即 `knowledge_base_id`。创建时会绑默认 RAG index pipeline 与 embedding 配置。

---

## 3. 异步上传并自动导入（Ingest Workflow）

一条 workflow 可带最多 **100** 个文件。约定：**1 文件 = 1 capture = 1 条库文档 = 1 次 RAG index**。不要传 `capture_group` / `groups`（传了 400）。

```
对方 Vercel                         本 API                         OSS（阿里云）
    │ POST /workflows（JSON） ──►  202 + upload_url
    │ PUT 文件字节 ──────────────────────────────────────────────►
    │ POST /upload-complete ──►   attach + await 启动 worker
    │                             parse / ASR / post-process / index（GHA worker）
    │ ◄── webhook（可选，10s 内 2xx）
    │ GET /workflows/:id ──────►  终态 / 对账
```

### 3.1 创建 workflow

```http
POST /api/knowledge/workflows
Authorization: Bearer okf_...
Idempotency-Key: <可选，同一调用方用户 24h 内幂等>
Content-Type: application/json
```

```json
{
  "channel_id": "uuid",
  "knowledge_base_id": "uuid",
  "knowledge_base_type": "rag",
  "files": [
    {
      "client_ref": "ext-doc-001",
      "filename": "report.pdf",
      "file_hash": "<64 位小写 sha256 hex，必须等于即将 PUT 的字节>",
      "size_bytes": 12345,
      "content_type": "application/pdf"
    },
    {
      "client_ref": "ext-aud-001",
      "filename": "meeting.m4a",
      "file_hash": "<sha256 hex>",
      "size_bytes": 67890,
      "content_type": "audio/mp4"
    },
    {
      "client_ref": "ext-tr-001",
      "filename": "notes.md",
      "file_hash": "<sha256 hex>",
      "size_bytes": 2000,
      "content_type": "text/markdown; charset=utf-8",
      "type": "transcript"
    }
  ],
  "steps": ["upload", "process", "index"],
  "index_content": { "audio": "combined" },
  "index_mode": "batch",
  "retry": { "max_attempts": 2, "auto_retry": true },
  "webhook_url": "https://your-app.vercel.app/api/openkms/webhook",
  "signature_mode": "hmac_sha256"
}
```

| 字段 | 说明 |
|------|------|
| `files[].client_ref` | 调用方文件 ID，workflow 内唯一 |
| `files[].file_hash` | **64 位小写 SHA-256**，与 PUT 字节一致，否则 complete 失败 |
| `files[].type` | 可省略。音频扩展名 → `audio`；其余白名单 → `document`。**转写稿必须显式 `"type": "transcript"`**，且只能是 `.md` / `.markdown`（未标的 `.md` 当文档 parse） |
| `index_content.audio` | `combined`（默认：摘要+转写拼进 markdown）或 `summary`（只索引摘要）。仅 audio/transcript |
| `index_mode` | `batch`：全部 item process 完再一次 RAG import；`per_item`：单个 capture 完成即 index |
| `retry.auto_retry` | 默认 `true`；失败 job 从失败子步骤自动续跑，次数受 `max_attempts`（默认 2） |
| `webhook_url` | 可选。仅 https 公网。`webhook_secret` 可自带，否则本侧生成并 **只在本响应出现一次** |

**不要**把文件内容放进这个 JSON。

**202** 响应（节选）：

```json
{
  "workflow_id": "uuid",
  "status": "pending_upload",
  "webhook_secret": "whsec_...",
  "upload_deadline_at": "2026-09-16T06:00:00.000Z",
  "items": [
    {
      "item_id": "uuid",
      "client_ref": "ext-doc-001",
      "detected_type": "document",
      "status": "pending_upload",
      "step": "upload",
      "files": [
        {
          "client_ref": "ext-doc-001",
          "status": "awaiting_put",
          "upload": {
            "upload_url": "https://<bucket>.oss-.../...",
            "s3_key": "documents/<hash>/original.pdf",
            "method": "PUT",
            "headers": { "Content-Type": "application/pdf" }
          }
        }
      ],
      "platform_refs": { "capture_id": "uuid", "document_id": null }
    }
  ]
}
```

保存 `workflow_id`、`item_id`、`capture_id`、`webhook_secret`。

### 3.2 直传 OSS

对每个 `upload.upload_url`：

```http
PUT <upload_url>
Content-Type: <与 headers['Content-Type'] 完全相同>
<原始文件字节>
```

- **不要**经本 API 中转
- **不要**改 Content-Type、不要带额外签名头
- 浏览器侧若 `Failed to fetch`，多半是 OSS CORS，不是签名算法

### 3.3 确认上传（可分批）

文件 PUT 成功后立刻调，不必等全部文件。每个已 confirm 的文件会马上进入 process。

```http
POST /api/knowledge/workflows/:workflow_id/upload-complete
```

```json
{
  "items": [
    {
      "client_ref": "ext-doc-001",
      "s3_key": "documents/<hash>/original.pdf",
      "file_hash": "<与创建时相同的 sha256>",
      "size_bytes": 12345
    }
  ]
}
```

也可用 `item_id` 代替 `client_ref`。同一 `s3_key` + `file_hash` 重复 confirm 幂等。

本请求仍是小 JSON。服务端会 **await** 启动 parse/ASR worker（serverless 上不能 fire-and-forget）。

之后内部自动：

| `detected_type` | process | 进 RAG 的文档 |
|-----------------|---------|----------------|
| `document` | 文档 parse | parse 产物（`documents/{hash}/markdown.md`） |
| `audio` | ASR → capture post-process | `captures/{id}/markdown.md` |
| `transcript` | 跳过 ASR → post-process | 同上 |

### 3.4 查询状态（源真相）

```http
GET /api/knowledge/workflows/:workflow_id
```

GET 会核对 in-flight job（含超时失败），不依赖 webhook 是否到达。

`workflow.status`：`pending_upload` → `running` → `completed` | `partially_completed` | `failed` | `cancelled`。

每个 `items[]`：

- `status` / `step`（`upload` | `process` | `index`）/ `substage`（底层 job 阶段）
- `platform_refs.capture_id`：创建时就有
- `platform_refs.document_id`：process 完成后才有，用它读 markdown / 原件
- `error_code` / `error_message`：失败时

建议轮询：上传完成后 2–5s 一次，直到终态；或 webhook 推送后再 GET 一次确认。

### 3.5 Webhook（可选）

本侧对 `webhook_url` **同步 POST JSON**，超时 **10s**。

请求头：

| Header | 含义 |
|--------|------|
| `Content-Type` | `application/json` |
| `X-OpenKMS-Webhook-Id` | 投递 id，幂等键 |
| `X-OpenKMS-Timestamp` | unix 秒 |
| `X-OpenKMS-Sequence` | 递增序号，按此排序 |
| `X-OpenKMS-Signature` | `v1=<hex>`（`hmac_sha256` 时） |

验签：`HMAC-SHA256(secret, "{timestamp}.{rawBody}")`，与 `v1=` 后 hex 比较。必须用 **原始 body 字节**，不要先 JSON.parse 再 stringify。

对方 Vercel 路由建议：验签 → 写入队列/DB → **立刻 200**。不要在这个函数里调 OpenKMS 再做一轮长处理。

常见 `event`：`workflow.item.uploaded`、`workflow.item.progress`、`workflow.item.completed`、`workflow.item.failed`、`workflow.item.retrying`、`workflow.completed`、`workflow.partially_completed`、`workflow.failed`、`workflow.cancelled`。

---

## 4. 重试

失败后 **从失败的那条 job 子步骤续跑**，不是整条 workflow 重传文件。

### 4.1 自动

创建时 `retry.auto_retry: true`（默认）。parse / ASR / post-process / RAG import PATCH 为 `failed` 时自动 `retryFailedJob`，次数 ≤ `max_attempts`。

### 4.2 手动

item 已是 `failed` 时：

```http
POST /api/knowledge/workflows/:workflow_id/items/:item_id/retry
```

**202** 例：`{ "retried": true, "domain": "audio_pipeline" }`。

`domain` 可能是 `document_pipeline` | `audio_pipeline` | `capture_pipeline` | `kb_import`。

次数用尽后手动也会失败。上传阶段失败（没 PUT / 没 complete）请重新 PUT + `upload-complete`，不要走 retry。

取消未处理完的上传项：`POST /api/knowledge/workflows/:workflow_id/cancel`（已在跑的 worker 不会被这条接口杀掉）。

---

## 5. 读取原件与 markdown.md

先 `GET /api/knowledge/workflows/:id`，用 item 上的 `platform_refs`。所有读接口只返回 **presigned URL**，调用方再 **直接 GET OSS**。URL 短时有效，每次要读都重新调本 API，不要存 URL。

OSS 上对象尚未生成时，阿里云常返回 **403 而不是 404**。应等 item `process`/`index` 完成后再读；把 403 当「还没有」而不是签名错误。

### 5.1 进 RAG 的那份 markdown（推荐）

process 完成后有 `document_id`：

```http
GET /api/knowledge/documents/:document_id/content
```

```json
{
  "id": "uuid",
  "name": "...",
  "file_type": "MD | PDF | ...",
  "status": "done",
  "sources": {
    "markdown_url": "https://...presigned GET...",
    "page_index_url": "https://..."
  }
}
```

然后 `GET sources.markdown_url` 取正文。

| 来源类型 | 这份 markdown 实际是 |
|----------|----------------------|
| document | parse 产物 `documents/{hash}/markdown.md` |
| audio / transcript | post-process 产物 `captures/{capture_id}/markdown.md` |

### 5.2 原件

**文档（PDF/Office/图/当文档的 md 等）**

```http
GET /api/knowledge/documents/:document_id/download
```

```json
{ "url": "https://...presigned GET...", "filename": "report.pdf" }
```

对 `url` 再 GET，即 OSS 上的 `original.<ext>`。

注意：audio/transcript 的 `document_id` 指向的是 **拼合后的 markdown 库文档**，这条 download 拿到的是 `markdown.md`，**不是** 音频原件。

**音频原件 / transcript 原件**

1. `GET /api/knowledge/captures/:capture_id`（`segments[].id`）
2. `GET /api/knowledge/captures/:capture_id/segments/:segment_id/preview`

```json
{
  "playback_url": "https://... 音频原件 presigned GET，transcript 模式为 null",
  "transcript_url": "https://... 转写 md presigned GET",
  "filename": "meeting.m4a"
}
```

音频用 `playback_url`；显式 transcript 上传的那份 md 用 `playback_url` 为空时的 `transcript_url` / segment 原件。

**Audio/transcript 的 capture markdown**（与 5.1 通常同一份）也可：

```http
GET /api/knowledge/captures/:capture_id/artifacts 相关
POST /api/knowledge/captures/:capture_id/post-process-artifacts-presign
```

```json
{ "artifacts": ["markdown"] }
```

响应 `files` 里带 `markdown` 的 presigned GET。同样不要经 API 拉字节。

### 5.3 小结

| 想要的文件 | 何时可读 | 调用 |
|------------|----------|------|
| 文档原件 | document item 已 attach（有 `document_id`） | `GET /documents/:id/download` → GET OSS |
| 文档 parse markdown | document parse `done` | `GET /documents/:id/content` → GET `markdown_url` |
| 音频原件 | audio 已 upload-complete | capture `preview.playback_url` |
| 音视频/转写的入库 markdown | post-process `done` | `GET /documents/:document_id/content` 或 capture `markdown` presign |

索引完成后可用同一 API Key 走 MCP hybrid-search / `POST /api/knowledge/hybrid-search` 检索（不在本文展开）。

---

## 6. 建议对接顺序（对方 Vercel）

1. 向本平台拿 `okf_` Key（documents + knowledge-bases 读写）；之后所有本 API 请求带 `Authorization: Bearer okf_...`
2. `GET /knowledge-bases` 选用已有 RAG 库；没有则 `POST`，`type: "rag"`
3. `GET /document-channels` 选用已有频道；没有则 `POST`，必要时 `PUT` pipeline
4. 计算文件 sha256 → `POST /workflows`（小 JSON）
5. **非 Vercel 中转** PUT OSS
6. `POST .../upload-complete`
7. Webhook 只入队；轮询或事后 `GET .../workflows/:id`
8. `completed` 后用 `document_id` / `capture_id` 按 §5 读内容
9. item `failed` 且未达 `max_attempts`：`POST .../items/:item_id/retry`

一次只处理小 JSON 的 Vercel 函数；文件字节不要进该函数的 request/response。
