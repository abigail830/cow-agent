import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AgentModel
from app.platform.memory.compaction import build_platform_compaction
from app.platform.memory.long_term.context_provider import LongTermMemoryProvider
from app.platform.memory.memory_config import parse_memory_config
from app.platform.memory.postgres_history import PostgresHistoryProvider
from app.platform.agent.agent_bundle import AgentBundle
from app.platform.hooks.hook_config import normalize_hooks
from app.platform.hooks.hook_registry import resolve_middleware
from app.platform.mcp.mcp_registry import McpRegistry
from app.platform.llm.model_registry import ModelProvider, ModelProviderRegistry
from app.platform.agent.platform_instructions import append_platform_instructions
from app.platform.session.session_store import SessionStore
from app.platform.agent.skill_registry import SkillRegistry
from app.platform.agent.tool_registry import ToolRegistry
from app.platform.agent.plugin_registry import tool_names_for_slug, viz_tool_names
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
        stop_event: asyncio.Event | None = None,
        turn_start_sequence: int | None = None,
        session_store: SessionStore | None = None,
    ) -> AgentBundle:
        row = await self.get_agent_row(agent_id)
        provider = ModelProvider(row.model_provider)
        settings = get_settings()
        if provider == ModelProvider.AZURE_OPENAI:
            model_name = row.model_name or settings.azure_openai_deployment
        elif provider == ModelProvider.SILICONFLOW:
            model_name = row.model_name or settings.siliconflow_default_model or ""
        else:
            model_name = row.model_name or settings.claude_azure_foundry_model or ""

        memory_config = parse_memory_config(row.config)
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
        if compaction_provider is not None:
            context_providers.append(compaction_provider)
        skills_provider = await self._skills.resolve_provider_for_agent(agent_id)
        skill_tools: set[str] = set()
        if skills_provider is not None:
            context_providers.append(skills_provider)
            skill_tools.update({"load_skill", "read_skill_resource"})

        middleware = resolve_middleware(
            row.config,
            self._db,
            chat_id=chat_id,
            session_store=store,
            extra_allowed_tools=skill_tools or None,
            stop_event=stop_event,
        )

        function_tools = await self._tools.resolve_for_agent(agent_id)
        mcp_tools = await self._mcp.resolve_for_agent(agent_id, agent_config=row.config)
        allowed = list((row.config or {}).get("allowed_tools") or [])

        has_sql_viz_hook = any(
            name == "sql_viz" for name, _ in normalize_hooks(row.config.get("hooks"))
        )
        slug_tools = tool_names_for_slug(row.slug)
        builtin_tools = resolve_builtin_tools(allowed, slug_tools)
        if has_sql_viz_hook:
            builtin_tools.extend(resolve_builtin_tools(allowed, viz_tool_names()))

        combined_tools = [
            *builtin_tools,
            *list(function_tools or []),
            *mcp_tools,
        ]

        agent = self._registry.create_agent(
            name=row.name,
            instructions=append_platform_instructions(row.instructions),
            model_provider=provider,
            model_name=model_name,
            context_providers=context_providers,
            middleware=middleware,
            tools=combined_tools or None,
            require_per_service_call_history_persistence=False,
        )
        return AgentBundle(agent=agent)
