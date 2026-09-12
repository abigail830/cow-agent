# Agent definitions (file-based)

Each subdirectory under `backend/agents/` is one deployable agent. The platform loads these on startup — no UI configuration.

## Layout

```
agents/
  <slug>/
    profile.yaml
    system_prompt.md
    mcp_servers.yaml      # optional
    skills/<name>/SKILL.md
    knowledge/            # optional — runtime data (see proposal-composer)
```

`profile.yaml` 的 `id` 必须与目录名一致。

## profile.yaml

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Slug，与目录名一致 |
| `name` | yes | 显示名 |
| `model_provider` | yes | `azure_openai` / `azure_anthropic` / `siliconflow` / `dashscope` / `deepseek` |
| `default_model` | recommended | Catalog id in `backend/config/models.yaml`（如 `claude-sonnet-4-6`、`minimax-m3`） |
| `model` | no | 可选 override；deployment 字符串，支持 `${ENV_VAR}`。未写时从 `default_model` 查 catalog |
| `mcp_servers` | no | 引用 `mcp_servers.yaml` 中的 key；可在 profile 内联 `env`（见下） |
| `allowed_tools` | no | MAF 工具名，如 `postgres_query_data`（对应 mcp-postgres 的 `query_data`） |
| `hooks` | no | 平台 hook 及参数（见下） |

### hooks（平台可复用）

Hook 实现注册在 `app/platform/hooks/hook_catalog.py`，任意 agent 按名称启用并覆盖参数。Middleware 分层见 `app/platform/ARCHITECTURE.md`。

```yaml
hooks:
  sql_validator:
    max_rows: 2000
  result_truncator:
    max_observation_bytes: 50000
```

仅用默认值时可写 `sql_validator: {}` 或列表形式 `- sql_validator`。

平台还会自动挂载（无需在 profile 声明）：

- `ChatPiiRedactionMiddleware` — Chat 层密钥/PII 脱敏
- `AuditMiddleware` — 结构化 tool 调用审计（有 chat 上下文时）

| Hook | 参数 | 默认 |
|------|------|------|
| `sql_validator` | `max_rows` | `2000` |
| `result_truncator` | `max_observation_bytes` | `50000` |
| `sql_viz` | `auto`, `min_rows` | `false`, `3`（应排在其他 SQL hook 之后；平台会自动排序） |
| `proposal_persist` | — | 无参数；需 `allowed_tools` 含 proposal builtin tools |

新增平台 hook：在 `hook_catalog.py` 注册 `HookSpec`，并在 `hook_config._HOOK_ORDER` 中指定顺序（如需要）。

### 完整示例

```yaml
id: yl-worker1
name: "YL-Worker-001"
model_provider: azure_anthropic
default_model: claude-sonnet-4-6

# 推荐：在 profile 配置各 agent 的 MCP 环境变量（支持 ${ENV_VAR}）
mcp_servers:
  postgres:
    env:
      DATABASE_URL: ${YL_DATABASE_URL}
      DB_READ_ONLY: "true"

# mcp_servers.yaml 示例:
# servers:
#   postgres:
#     command: ${NPX_PATH:-npx}
#     args: [-y, mcp-postgres@latest]

# 仍支持列表形式（env 留在 mcp_servers.yaml 或通过 mcp_env 覆盖）：
# mcp_servers: [postgres]

allowed_tools:
  - postgres_list_tables
  - postgres_describe_table
  - postgres_get_schema
  - postgres_query_data

hooks:
  sql_validator:
    max_rows: 2000
  result_truncator:
    max_observation_bytes: 50000
```

### 模型目录（`backend/config/models.yaml`）

所有可选模型的 **deployment 名称** 统一维护在 `config/models.yaml`（如 `gpt-5.4`、`claude-sonnet-4-6`、`MiniMax/MiniMax-M3`）。`.env` 只放 **API Key 和 base URL**，不再用 `*_DEFAULT_MODEL` 指定聊天模型。

Agent profile 写 `default_model: <catalog-id>` 即可；若某环境的 Azure deployment 名与 catalog 不同，可在 profile 加 `model: your-custom-deployment` 覆盖。

### DashScope（阿里云百炼）

OpenAI **Chat Completions** 兼容模式（Qwen、MiniMax M3 等；thinking 可通过 OpenAI 兼容 `extra_body` 传递，无需单独 SDK）：

```yaml
model_provider: dashscope
default_model: minimax-m3
```

后端 / Vercel 环境变量：

```bash
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

可选模型见 `backend/config/models.yaml`（如 `qwen3.7-plus`、`qwen3.8-max`、`minimax-m3`）。

**Unify-lite 附件**：txt/md/docx 抽取为文本；图片上传至 blob，仅在消息中 `@filename` 引用时以 Native 多模态发送。

**Native 附件**：PDF（Azure）/ 图片 inline 多模态。

### DeepSeek

OpenAI **Chat Completions** 兼容接口：

```yaml
model_provider: deepseek
default_model: deepseek-flash
```

后端 / Vercel 环境变量：

```bash
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

附件：Native 模式下图片 inline 多模态；Unify-lite 下 `@` 引用图片时同样走 Native 多模态。

### mcp_servers.yaml vs profile

- `mcp_servers.yaml`：进程定义（`command` / `args`），可复用
- `profile.yaml`：本 agent 的 `env`、凭证占位符（`${MY_AGENT_DB_URL}`），不同 agent 可用不同变量名连不同库

## Adding an agent

1. `backend/agents/<slug>/` + `profile.yaml` + `system_prompt.md`
2. 按需添加 `mcp_servers.yaml`、`skills/`；在 profile 的 `mcp_servers.<key>.env` 写连接信息
3. 重启后端
