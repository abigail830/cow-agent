# Agent Platform

文件配置 Agent + 单页 Chat 前端。Agent 定义在 `backend/agents/<slug>/`。

## 环境准备

```bash
# 后端
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # 填写 DATABASE_URL、模型密钥、YL_DATABASE_URL 等

# 前端
cd frontend
npm install
```

## 启动方式

### 方式一：一键后台启动（无终端日志）

进程在后台运行，日志写入文件（见下文「查看后台日志」）。

```bash
# 项目根目录
./scripts/start.sh

# 停止
./scripts/stop.sh
```

启动后：

| 服务 | 地址 |
|------|------|
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |

### 方式二：前后端分开前台启动（推荐调试）

先停掉后台进程，避免端口占用：

```bash
./scripts/stop.sh
```

开 **两个终端**，日志直接打在各自窗口：

**终端 A — 后端**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**终端 B — 前端**

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

调试聊天、MCP、工具调用时，优先看 **终端 A** 的后端输出。

### 查看后台日志

使用 `./scripts/start.sh` 时，日志不在当前终端，需 `tail -f`：

```bash
# 后端
tail -f backend/.run/uvicorn.log

# 前端（另开终端）
tail -f frontend/.run/vite.log
```

### 健康检查

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/agents
```

### 登录与用户

平台使用 **邮箱 + 密码** 登录，会话为 **HttpOnly Cookie + 服务端 session**（无自助注册）。

1. 执行数据库迁移：

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

2. 预置用户密码（bcrypt 哈希写入 DB）：

```bash
python scripts/set_user_password.py --email you@example.com --name "Your Name"
```

3. 启动前后端后访问 http://127.0.0.1:5173 ，未登录会跳转 `/login`。

本地调试可设 `AUTH_DISABLED=true` 跳过密码校验（仍使用 seed 开发用户）。

| 变量 | 说明 |
|------|------|
| `AUTH_DISABLED` | `true` 时免登录（仅开发） |
| `AUTH_COOKIE_NAME` | Session cookie 名，默认 `ap_session` |
| `AUTH_SESSION_TTL_HOURS` | 会话有效期（小时），默认 168 |
| `AUTH_COOKIE_SECURE` | 生产 HTTPS 下设 `true` |

## 冒烟测试

```bash
cd backend
source .venv/bin/activate

# 验证 yl-worker1 agent 的 postgres MCP 工具已挂载（需 npx 可用）
python scripts/smoke_mcp_agent.py

# 单元测试
pytest tests/ -q

# yl-worker2 本体 Tool 集成测试（需 YL PG mock 数据）
# 1. 在 .env 配置 YL_DATABASE_URL
# 2. 加载 mock：bash scripts/load_yl_mock_ylp001.sh
pytest tests/yl_worker2/ -v
```

### YL-Worker-002（本体驱动补调）

| 项 | 说明 |
|----|------|
| Agent 配置 | `backend/agents/yl-worker2/`（`yl-oip-ontology-core` + `system_prompt`） |
| 实现代码 | `backend/app/yl_worker2/`（19 个 Tool + Webhook） |
| Mock 数据 | `bash backend/scripts/load_yl_mock_ylp001.sh` |
| 人触发 Script1 | UI 选 YL-Worker-002，发送「开始今日巡检」 |
| 外系统 Script2 | `POST /api/v1/agents/yl-worker2/triggers`（默认自动 `run_message`） |
| 方案文档 | `docs/yl-worker2-ontology-plan.md` |
| 实体访问层规划 | `docs/yl-worker2-entity-access-layer.md` |

## 常见日志说明

| 日志 | 是否阻塞聊天 | 处理 |
|------|-------------|------|
| `Redis connection failed — session cache will use DB only` | 否 | 本地可改 `REDIS_URL=redis://127.0.0.1:6379` 或忽略 |
| `Failed to start MCP server 'npx'` / MCP connection errors | **是** | 确认 Node.js / `npx` 可用；`./scripts/start.sh` 会自动加载 nvm 并设置 `NPX_PATH` |
| `anthropic.AuthenticationError: 401 Unauthorized` | **是** | 修正 `CLAUDE_AZURE_API_KEY` / `CLAUDE_AZURE_FOUNDRY_ENDPOINT` |

**YL-Worker-001** 与 SP 分析师通过 stdio MCP 启动成熟 MCP 包，由 MCP server 直接连接远程数据库。本地启动时需 Node.js / `npx`；Vercel Python serverless 无法可靠 spawn `npx`，生产若继续部署在 Vercel，需要改用这些 MCP 包自带的 remote HTTP 模式或换成长驻后端。

MCP agent 使用 `azure_anthropic`，必须在 `backend/.env` 配置：

```bash
CLAUDE_AZURE_API_KEY=<Azure AI Foundry 资源的 API Key>
CLAUDE_AZURE_FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/anthropic
CLAUDE_AZURE_FOUNDRY_MODEL=claude-sonnet-4-6
```

Key 与 Endpoint 必须来自**同一 Azure 资源、同一区域**（例如都是 China East / Southeast Asia 等）。

## Vercel 环境变量（首次部署）

后端变量较多，可用脚本批量上传**非敏感**配置；API Key、数据库 URL 等请在 Vercel Dashboard 手动填写。

```bash
# 1. 安装最新 Vercel CLI
npm i -g vercel@latest

# 2. 切换 Vercel 账号（与 git 邮箱无关）
#
# 若 `vercel login` 浏览器跳回旧账号 / 无法完成授权，改用 Token（推荐）：
#   1) 浏览器无痕窗口登录 abigail830 的 Vercel → Settings → Tokens → Create
#   2) export VERCEL_TOKEN="vercel_xxx"   # 仅当前终端有效
#   3) vercel whoami
#
# 或尝试 Device Flow（先 logout，无痕窗口打开终端给的链接）：
#   vercel logout
#   vercel login
#   vercel whoami

# 3. 在后端目录关联 Vercel 项目
cd backend
vercel link

# 4. 预览 / 上传（可在 backend/scripts/vercel-env.expected-user 写入期望的 Vercel 用户名）
python scripts/sync_vercel_env.py --dry-run
python scripts/sync_vercel_env.py --expected-vercel-user YOUR_VERCEL_USERNAME

# 可选：从本地 .env 上传非敏感项（已有值的 URL 等）
python scripts/sync_vercel_env.py --from .env

# 可选：连敏感项一起上传（Vercel 标记为 sensitive）
python scripts/sync_vercel_env.py --from .env --include-sensitive --mark-sensitive --force
```

敏感项列表见 `backend/scripts/vercel-env.sensitive-keys.txt`，可自行增删。

生产环境还需在 Vercel 手动设置例如：

| 变量 | 建议值 |
|------|--------|
| `DATABASE_URL` | Neon / Supabase 等 |
| `AZURE_API_KEY` | Azure 密钥 |
| `CORS_ORIGINS` | 前端 Vercel 域名，如 `https://xxx.vercel.app` |
| `AUTH_COOKIE_SECURE` | `true` |

## 前后端如何连接（Vercel 单仓库）

源码在 **单一 monorepo**（`cow-agent`）。Vercel 上创建两个项目，分别设置 Root Directory 为 `backend` / `frontend`，即可从同一仓库独立部署。

本地：前端请求 `/api/v1`，Vite proxy 转到 `127.0.0.1:8000`。

生产二选一：

### 方式 A — 前端 Rewrite 代理（推荐）

1. 编辑 `frontend/vercel.json`，将 `YOUR-BACKEND.vercel.app` 换成后端域名。
2. 不设置 `VITE_API_BASE_URL`。
3. 浏览器只访问前端域名，`/api/*` 由 Vercel 转发 → Cookie 同源，`AUTH_COOKIE_SAMESITE=lax` 即可。
4. 后端：`AUTH_COOKIE_SECURE=true`，`CORS_ORIGINS` 包含前端 URL。

### 方式 B — 跨域直连

1. 前端 Vercel：`VITE_API_BASE_URL=https://你的后端.vercel.app`（build 时注入，改后需 redeploy）。
2. 后端：`CORS_ORIGINS=https://你的前端.vercel.app`，`AUTH_COOKIE_SECURE=true`，`AUTH_COOKIE_SAMESITE=none`。

| | 方式 A | 方式 B |
|--|--------|--------|
| 前端 env | 无 | `VITE_API_BASE_URL` |
| 后端 CORS | 建议 | **必须** |
| Cookie | `SameSite=lax` | `SameSite=none` + Secure |

## 相关文档

- Agent 配置：`backend/agents/README.md`
- 环境变量模板：`backend/.env.example`
