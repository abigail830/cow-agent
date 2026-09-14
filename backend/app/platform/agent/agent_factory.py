import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel
from app.config import get_settings
from app.platform.memory.compaction import build_platform_compaction
from app.platform.memory.long_term.context_provider import LongTermMemoryProvider
from app.platform.memory.memory_config import parse_memory_config
from app.platform.memory.postgres_history import PostgresHistoryProvider
from app.platform.attachments.catalog.context_provider import AttachmentCatalogContextProvider
from app.platform.agent.agent_bundle import AgentBundle
from app.platform.mcp.mcp_pool import McpPoolHandle
from app.platform.hooks.hook_config import normalize_hooks
from app.platform.hooks.hook_registry import resolve_middleware
from app.platform.mcp.mcp_registry import McpRegistry
from app.platform.llm.model_catalog import resolve_agent_model
from app.platform.llm.model_registry import ModelProvider, ModelProviderRegistry
from app.platform.agent.platform_instructions import append_platform_instructions
from app.platform.session.session_store import SessionStore
from app.platform.agent.skill_registry import SkillRegistry
from app.platform.agent.tool_registry import ToolRegistry
from app.platform.agent.plugin_registry import tool_names_for_slug, viz_tool_names
from app.platform.agent.builtin_registry import BUILTIN_TOOLS
from app.platform.attachments.modes import AttachmentProcessingMode, parse_attachment_mode
from app.platform.agent.platform_time import PLATFORM_ALWAYS_BUILTIN_TOOL_NAMES, PLATFORM_TIME_TOOL_NAME
from app.platform.agent.tool_groups import resolve_builtin_tools


class AgentFactory:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._registry = ModelProviderRegistry()
        self._tools = ToolRegistry(db)
        self._mcp = McpRegistry(db)
        self._skills = SkillRegistry(db)

    async def get_agent_row(self, agent_id: uuid.UUID) -> AgentModel:
        result = await self._db.execute(select(AgentModel).where(AgentModel.id == agent_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Agent not found: {agent_id}")
        return row

    async def build(
        self,
        agent_id: uuid.UUID,
        *,
        chat_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        model_id: str | None = None,
        stop_event: asyncio.Event | None = None,
        turn_start_sequence: int | None = None,
        session_store: SessionStore | None = None,
        mcp_tools: list | None = None,
        mcp_pool_handle: McpPoolHandle | None = None,
        attachment_mode: str | None = None,
    ) -> AgentBundle:
        row = await self.get_agent_row(agent_id)
        model_entry = resolve_agent_model(row, model_id)
        provider = ModelProvider(model_entry.provider)
        model_name = model_entry.deployment

        enable_attachment_pull = (
            get_settings().attachment_pull_enabled
            and parse_attachment_mode(attachment_mode) == AttachmentProcessingMode.UNIFY_LITE
        )
        memory_config = parse_memory_config(row.config)
        if not enable_attachment_pull:
            from dataclasses import replace

            memory_config = replace(
                memory_config,
                attachment_pull=replace(memory_config.attachment_pull, enabled=False),
            )
        store = session_store or SessionStore(self._db)
        history = PostgresHistoryProvider(
            self._db,
            session_store=store,
            memory_config=memory_config,
            pending_turn_start_sequence=turn_start_sequence,
            model_provider=provider.value,
        )
        _, compaction_provider = build_platform_compaction(memory_config)
        context_providers: list = [history]
        if memory_config.long_term.enabled and user_id is not None:
            context_providers.append(
                LongTermMemoryProvider(
                    self._db,
                    user_id=user_id,
                    agent_id=agent_id,
                    agent_slug=row.slug or row.name,
                    memory_config=memory_config,
                )
            )
        if memory_config.attachment_pull.enabled and chat_id is not None:
            context_providers.append(
                AttachmentCatalogContextProvider(
                    self._db,
                    chat_id=chat_id,
                    pull_config=memory_config.attachment_pull,
                )
            )
        if compaction_provider is not None:
            context_providers.append(compaction_provider)
        skills_provider = await self._skills.resolve_provider_for_agent(agent_id)
        skill_tools: set[str] = set()
        if skills_provider is not None:
            context_providers.append(skills_provider)
            skill_tools.update({"load_skill", "read_skill_resource"})

        always_builtin_names = frozenset({PLATFORM_TIME_TOOL_NAME})
        if enable_attachment_pull:
            always_builtin_names = PLATFORM_ALWAYS_BUILTIN_TOOL_NAMES
        extra_allowed_tools = set(always_builtin_names) | skill_tools

        middleware = resolve_middleware(
            row.config,
            self._db,
            chat_id=chat_id,
            session_store=store,
            extra_allowed_tools=extra_allowed_tools or None,
            stop_event=stop_event,
            enable_attachment_pull=enable_attachment_pull,
        )

        function_tools = await self._tools.resolve_for_agent(agent_id)
        if mcp_tools is None:
            mcp_tools = await self._mcp.resolve_for_agent(
                agent_id,
                agent_config=row.config,
                user_id=user_id,
            )
        allowed = list((row.config or {}).get("allowed_tools") or [])

        has_sql_viz_hook = any(
            name == "sql_viz" for name, _ in normalize_hooks(row.config.get("hooks"))
        )
        slug_tools = tool_names_for_slug(row.slug)
        builtin_tools = resolve_builtin_tools(allowed, slug_tools)
        if has_sql_viz_hook:
            builtin_tools.extend(resolve_builtin_tools(allowed, viz_tool_names()))

        always_builtin = [
            BUILTIN_TOOLS[name]
            for name in always_builtin_names
            if name in BUILTIN_TOOLS
        ]
        combined_tools = [
            *always_builtin,
            *builtin_tools,
            *list(function_tools or []),
            *mcp_tools,
        ]

        instructions = append_platform_instructions(
            row.instructions,
            include_attachment_pull=enable_attachment_pull,
        )

        agent = self._registry.create_agent(
            name=row.name,
            instructions=instructions,
            model_provider=provider,
            model_name=model_name,
            context_providers=context_providers,
            middleware=middleware,
            tools=combined_tools or None,
            require_per_service_call_history_persistence=False,
        )
        return AgentBundle(agent=agent, mcp_pool_handle=mcp_pool_handle)
