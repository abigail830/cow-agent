import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel
from app.platform.memory.compaction import build_platform_compaction
from app.platform.memory.long_term.context_provider import LongTermMemoryProvider
from app.platform.memory.memory_config import apply_model_compaction_defaults, parse_memory_config
from app.platform.memory.postgres_history import create_postgres_history_provider
from app.platform.agent.agent_bundle import AgentBundle
from app.platform.mcp.mcp_pool import McpPoolHandle
from app.platform.hooks.hook_config import normalize_hooks
from app.platform.hooks.hook_registry import resolve_middleware
from app.platform.mcp.mcp_registry import McpRegistry
from app.platform.llm.model_catalog import resolve_agent_model
from app.platform.llm.model_registry import ModelProvider, ModelProviderRegistry
from app.platform.integrations.kb_client import HybridSearchKbClientError, list_visible_knowledge_bases
from app.platform.integrations.kb_preference import (
    agent_supports_kb_scope,
    resolve_enabled_kb_ids_for_run,
)
from app.platform.integrations.providers.hybrid_search import HYBRID_SEARCH_PROVIDER_ID
from app.platform.integrations.token_service import IntegrationTokenService
from app.platform.agent.platform_instructions import append_platform_instructions
from app.platform.session.session_store import SessionStore
from app.platform.agent.skill_registry import SkillRegistry
from app.platform.agent.tool_registry import ToolRegistry
from app.platform.agent.plugin_registry import tool_names_for_slug, viz_tool_names
from app.platform.agent.builtin_registry import BUILTIN_TOOLS
from app.platform.agent.platform_time import PLATFORM_TIME_TOOL_NAME
from app.platform.agent.tool_groups import resolve_builtin_tools
from app.platform.llm.utility_models import UtilityModelRegistry, UtilityPurpose


class AgentFactory:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._registry = ModelProviderRegistry()
        self._tools = ToolRegistry(db)
        self._mcp = McpRegistry(db)
        self._skills = SkillRegistry(db)
        self._utility = UtilityModelRegistry()

    async def get_agent_row(self, agent_id: uuid.UUID) -> AgentModel:
        result = await self._db.execute(select(AgentModel).where(AgentModel.id == agent_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Agent not found: {agent_id}")
        return row

    async def _resolve_enabled_kb_ids(
        self,
        *,
        agent_row: AgentModel,
        user_id: uuid.UUID | None,
        agent_id: uuid.UUID,
    ) -> list[str] | None:
        if user_id is None:
            return None
        if not agent_supports_kb_scope(agent_row.config if isinstance(agent_row.config, dict) else {}):
            return None
        api_key = await IntegrationTokenService(self._db).get_api_key(
            user_id=user_id,
            provider=HYBRID_SEARCH_PROVIDER_ID,
        )
        return await resolve_enabled_kb_ids_for_run(
            self._db,
            user_id=user_id,
            agent_id=agent_id,
            api_key=api_key,
        )

    async def build(
        self,
        agent_id: uuid.UUID,
        *,
        chat_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        model_id: str | None = None,
        turn_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        stop_event: asyncio.Event | None = None,
        session_store: SessionStore | None = None,
        mcp_tools: list | None = None,
        mcp_pool_handle: McpPoolHandle | None = None,
    ) -> AgentBundle:
        if chat_id is None:
            raise ValueError("chat_id is required for PostgresHistoryProvider")

        row = await self.get_agent_row(agent_id)
        model_entry = resolve_agent_model(row, model_id)
        provider = ModelProvider(model_entry.provider)
        model_name = model_entry.deployment

        memory_config = apply_model_compaction_defaults(parse_memory_config(row.config), model_entry)
        store = session_store or SessionStore(self._db)
        history = create_postgres_history_provider(
            self._db,
            chat_id=chat_id,
            turn_id=turn_id,
            run_id=run_id,
            memory_config=memory_config,
            model_provider=provider.value,
            model_id=model_entry.id,
        )

        summarization_client = None
        if memory_config.compaction.enabled and memory_config.compaction.summarization.enabled:
            summarization_client = self._utility.get_client(UtilityPurpose.HISTORY_COMPACTION)

        in_run_compaction, compaction_provider = build_platform_compaction(
            memory_config,
            chat_id=chat_id,
            model_id=model_entry.id,
            model_provider=provider.value,
            summarization_client=summarization_client,
        )

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
        if compaction_provider is not None:
            context_providers.append(compaction_provider)
        skills_provider = await self._skills.resolve_provider_for_agent(agent_id)
        skill_tools: set[str] = set()
        if skills_provider is not None:
            context_providers.append(skills_provider)
            skill_tools.update({"load_skill", "read_skill_resource"})

        always_builtin_names = frozenset({PLATFORM_TIME_TOOL_NAME})
        extra_allowed_tools = set(always_builtin_names) | skill_tools

        scoped_kb_ids = await self._resolve_enabled_kb_ids(
            agent_row=row,
            user_id=user_id,
            agent_id=agent_id,
        )

        middleware = resolve_middleware(
            row.config,
            self._db,
            chat_id=chat_id,
            session_store=store,
            extra_allowed_tools=extra_allowed_tools or None,
            stop_event=stop_event,
            user_id=user_id,
            agent_id=agent_id,
            enabled_kb_ids=scoped_kb_ids,
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

        instructions = append_platform_instructions(row.instructions)

        agent = self._registry.create_agent(
            name=row.name,
            instructions=instructions,
            model_provider=provider,
            model_name=model_name,
            context_providers=context_providers,
            middleware=middleware,
            tools=combined_tools or None,
            compaction_strategy=in_run_compaction,
        )
        return AgentBundle(agent=agent, mcp_pool_handle=mcp_pool_handle)
