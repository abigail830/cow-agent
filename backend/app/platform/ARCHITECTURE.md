# Platform architecture (MAF alignment)

This document describes how `backend/app/platform/` maps to [Microsoft Agent Framework (MAF)](https://learn.microsoft.com/en-us/agent-framework/) concepts and where product-specific code lives.

## Layering

```
app/
├── agent_specific/*/         # Per-agent domain: tools, hooks, plugins, stream emitters
├── shared/                   # Cross-agent capabilities
│   ├── artifacts/            # Chat artifact cards: slide/html, diagram (PlantUML), content docs
│   └── sandbox/              # E2B execution for content-studio / slide builds
├── platform/                 # MAF assembly + platform services
│   ├── attachments/          # User message file uploads (all agents)
│   ├── chat/                 # Chat run orchestration (ChatRunService, stream pipeline)
│   ├── agent/                # AgentFactory, registries, profile sync
│   ├── hooks/                # MAF middleware (Agent / Function / Chat)
│   ├── guardrails/           # Pure validation rules (consumed by hooks)
│   ├── mcp/                  # MCP connection, registry, native DB tools
│   ├── memory/               # HistoryProvider, ContextProvider, compaction
│   ├── llm/                  # Model clients
│   ├── session/              # SessionStore, user run input
│   └── runtime/              # AgentPlugin protocol, StreamEmitter protocol
└── api/                      # HTTP routes
```

### agent_specific layout (example: proposal-composer)

```
agent_specific/proposal/
├── mdm/          # MDM catalog (proposal-composer only)
├── draft/        # Draft state machine, fee tables, placeholders
├── export/       # Word export
├── runtime/      # Plugin, tools, hooks, stream emitter
├── storage/      # Proposal artifacts + blob client
├── templates/    # template.yaml loaders
└── *.py          # Back-compat shims → prefer subpackages for new code
```

## MAF middleware (three layers)

MAF routes middleware by **type**, not list position across types:

| Layer | Class | Platform module | Purpose |
|-------|--------|-----------------|--------|
| Agent run | `AgentMiddleware` | `hooks/stop_requested.py` | Cancel run before next model step |
| Function (tool) | `FunctionMiddleware` | `hooks/allowed_tools.py`, `sql_validator.py`, … | Tool allowlist, SQL guardrails, truncation, domain post-hooks |
| Chat (model) | `ChatMiddleware` | `hooks/chat_redaction.py` | Redact secrets in messages before LLM call |

Register middleware in `hooks/hook_registry.resolve_middleware()`. Profile YAML enables **Function** hooks by name:

```yaml
hooks:
  sql_validator:
    max_rows: 2000
  result_truncator:
    max_observation_bytes: 50000
```

Hook order is stabilized in `hooks/hook_config.py` (`sql_viz` always last).

## guardrails vs hooks

- **`platform/guardrails/`** — stateless rules (e.g. `validate_sql`, `redact_sensitive_text`).
- **`platform/hooks/`** — MAF middleware that **enforces** rules at runtime.

Do not add a `guardrails:` section to new profiles; configure `hooks:` only.

## Memory (PG transcript SSOT + Redis session cache)

Agent context and UI reload share one PG transcript (`chat_messages`); rich UI anchors are separate annotations. Redis caches `AgentSession` only (`session:{chat_id}`); DB fallback is `chats.session_state`.

| Layer | Component | Role |
|-------|-----------|------|
| Transcript SSOT | `PostgresHistoryProvider` → `chat_messages.body` | MAF `Message.to_dict()` append-only; agent load applies slim projection in memory |
| Rich UI | `chat_ui_annotations` | viz / artifact timeline anchors; blob side store unchanged |
| Run lifecycle | `chat_runs` | running / completed / cancelled / failed (no fake message rows) |
| In-run compaction | `Agent.compaction_strategy` → `ContextWindowCompactionStrategy` | Token-budget gate before each model call (on-demand) |
| Run compaction | `PlatformCompactionProvider` | `before_run`: slim projectors (memory only); `after_run`: summarization append |
| Session identity | `SessionStore` | `AgentSession.to_dict()` + agent extensions (Redis hot cache + `chats.session_state`) |
| UI reload | `GET /messages` or `GET /timeline` | Full canonical messages + annotations merged by `sequence` |
| Cross-session | `LongTermMemoryProvider` | Inject bullets from `memory_snapshots` |
| Skills | `SkillsProvider` | Skill resources |

**Single writer**: user messages early-commit via platform; assistant/tool rows only via MAF `HistoryProvider.after_run`. Stream accumulator writes `ui_annotations` only (SSE unchanged).

## Tools

| Source | Registration |
|--------|----------------|
| Builtin `@tool` | `agent_specific/*/runtime/tools.py` or `shared/**/tools.py` → `platform/agent/builtin_registry.py` |
| MCP | DB `McpServer` + `platform/mcp/mcp_registry.py` |
| Skills | `platform/agent/skill_registry.py` |

`AgentFactory.build()` merges builtin + MCP + skill tools and attaches middleware.

## MCP lifecycle

Remote MCP tools connect via `AgentBundle` (`async with bundle as agent`). SSE streams use `mcp/mcp_connect.py` keepalive during connect. Secrets come from DB (`MCP_SECRETS_KEY`); do not override MCP config from env in production.

## Agent plugins (product extension)

`platform/runtime/plugin.py` defines `AgentPlugin` — **not** a MAF primitive. Plugins handle run-scoped context init, persistence, and optional `StreamEmitter`s. Register in `agent/plugin_registry.py`.

## Audit logging

- **Chat layer**: `ChatPiiRedactionMiddleware` logs redaction counts.
- **Tool layer**: `AuditMiddleware` logs structured `tool_invocation_start` / `tool_invocation_finish` (tool name, duration, MCP server metadata, argument **keys** only — no values).

For production, point log aggregation at these `audit_event` fields or add OpenTelemetry spans later.

## Adding a platform hook

1. Implement `FunctionMiddleware` or register factory in `hooks/hook_catalog.py`.
2. Add order in `hooks/hook_config._HOOK_ORDER` if sequence matters.
3. Document in `backend/agents/README.md`.
4. Enable in agent `profile.yaml` under `hooks:`.

## Legacy paths (removed)

Pre-reorg duplicates under `app/middleware/`, `app/memory/`, `app/viz/`, `app/services/chat_run.py`, and `app/application/` were deleted. Use `platform/` imports only.
