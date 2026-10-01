# 国产模型专用部署说明

平台已移除 **Azure OpenAI (GPT)** 与 **Azure Anthropic (Claude)** 的一等公民支持。聊天与 agent 仅通过 `backend/config/models.yaml` 中的 **dashscope / deepseek / siliconflow** 配置。

## 已删除的配置

| 区域 | 内容 |
|------|------|
| `backend/config/models.yaml` | `gpt-5.4`、`claude-sonnet-4-6` 及 `azure_*` provider |
| `backend/.env` | `AZURE_*`、`CLAUDE_AZURE_*`（见 `.env.example`） |
| `ModelProvider` | `azure_openai`、`azure_anthropic` |
| `model_registry.py` | `OpenAIChatClient`（Azure Responses）、`PlatformAnthropicClient` |
| `anthropic_client.py` | Claude Files API beta 客户端（整文件可删） |

## 原 Claude/GPT 专用附件逻辑（已移除或不再触发）

| 能力 | 原行为 | 现行为 |
|------|--------|--------|
| **OpenAI Files API** | Azure GPT：PDF 走 `file_id`，图片 inline | 已删除 `OpenAIAttachmentAdapter` |
| **Anthropic Files API** | Claude：PDF/图片均 `file_id` | 已删除 `AnthropicAttachmentAdapter` |
| **Azure MIME 校验** | docx/xlsx 上传拦截 | 已删除 `validate_azure_openai_attachment_mime` |
| **capabilities** | `gpt-*` / `claude-*` → `pdf_via=file_id` | Qwen → `file_data`；MiniMax/DeepSeek/SiliconFlow → `raster` + parse hydrate |
| **upload.py** | `caps.pdf_file_id` 时调 provider adapter | 仅 **DeepSeek** 仍可选 Files API（`deepseek_files.py`） |

国产模型附件路径见 `app/platform/attachments/capabilities.py` 与 parse pipeline hydrate（Document Hub `@` 引用）。

## Agent 默认模型

所有 `backend/agents/*/profile.yaml` 默认 `model_provider: dashscope`、`default_model: qwen3.7-plus`。数据库里旧的 `azure_*` 需在部署后执行 `python scripts/sync_agent_profiles.py` 覆盖。

## Utility / 健康检查

- 标题、压缩：`UTILITY_MODEL_*` 未设时回退 **DashScope**（`DASHSCOPE_API_KEY` + `qwen3.7-flash`）。
- `/health/models`：smoke **dashscope** + utility，不再测 Claude。

## 仍保留的「OpenAI 兼容」命名

`OpenAICompatibleReasoningClient`、Chat Completions 协议用于 **Qwen / DeepSeek / SiliconFlow**，与 Azure GPT 无关。
