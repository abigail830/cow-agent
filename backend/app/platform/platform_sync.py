import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DEV_USER_EMAIL,
    DEV_USER_ID,
    DEV_USER_NAME,
    AgentMcpServer,
    AgentModel,
    AgentSkill,
    AgentTool,
    McpServer,
    Skill,
    Tool,
    User,
)
from app.platform.mcp_config import pack_for_storage
from app.platform.profile_loader import (
    AGENTS_ROOT,
    discover_agent_profiles,
    load_agent_mcp_servers,
    mcp_storage_name,
)
from app.tools import BUILTIN_TOOLS

logger = logging.getLogger(__name__)

_AGENT_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def agent_id_for_slug(slug: str) -> uuid.UUID:
    return uuid.uuid5(_AGENT_NS, f"agent-platform:agent:{slug}")


async def ensure_platform_user(session: AsyncSession) -> None:
    """Ensure the pre-SSO dev user exists (all chats use this identity)."""
    user = await session.get(User, DEV_USER_ID)
    if user is None:
        session.add(
            User(id=DEV_USER_ID, email=DEV_USER_EMAIL, name=DEV_USER_NAME)
        )
        return
    if user.email != DEV_USER_EMAIL or user.name != DEV_USER_NAME:
        user.email = DEV_USER_EMAIL
        user.name = DEV_USER_NAME


async def _sync_agent_mcp_servers(
    session: AsyncSession,
    slug: str,
    agent_dir: Path,
    mcp_overrides: dict[str, dict] | None = None,
) -> dict[str, uuid.UUID]:
    """Sync agents/<slug>/mcp_servers.yaml. Returns local name -> mcp_server id."""
    configs = load_agent_mcp_servers(agent_dir, mcp_overrides)
    local_to_id: dict[str, uuid.UUID] = {}

    for local_name, cfg in configs.items():
        if not cfg.get("url") and not cfg.get("command"):
            logger.warning("Skipping MCP server %s/%s: missing command or url", slug, local_name)
            continue
        try:
            connection = pack_for_storage(cfg)
            connection["tool_name"] = local_name
        except Exception:
            logger.exception("Failed to pack MCP config for %s/%s", slug, local_name)
            continue

        storage_name = mcp_storage_name(slug, local_name)
        row = (
            await session.execute(select(McpServer).where(McpServer.name == storage_name))
        ).scalar_one_or_none()
        if row is None:
            row = McpServer(
                name=storage_name,
                description=f"MCP server for agent {slug} ({local_name})",
                transport=connection["transport"],
                connection=connection,
            )
            session.add(row)
        else:
            row.description = f"MCP server for agent {slug} ({local_name})"
            row.transport = connection["transport"]
            row.connection = connection
        await session.flush()
        local_to_id[local_name] = row.id

    return local_to_id


async def _cleanup_orphan_file_mcp_servers(session: AsyncSession, active_slugs: set[str]) -> None:
    """Remove file-synced MCP rows (slug:local) whose agent no longer exists on disk."""
    result = await session.execute(select(McpServer))
    for row in result.scalars().all():
        if ":" not in row.name:
            continue
        slug, _local = row.name.split(":", 1)
        if slug in active_slugs:
            continue
        link = (
            await session.execute(
                select(AgentMcpServer.agent_id).where(AgentMcpServer.mcp_server_id == row.id).limit(1)
            )
        ).first()
        if link:
            logger.warning("MCP %s kept (still linked to an agent)", row.name)
            continue
        await session.delete(row)
        logger.info("Removed orphan MCP server: %s", row.name)


async def _ensure_builtin_tool(session: AsyncSession, name: str) -> uuid.UUID | None:
    if name not in BUILTIN_TOOLS:
        return None
    row = (await session.execute(select(Tool).where(Tool.name == name))).scalar_one_or_none()
    if row is None:
        row = Tool(
            name=name,
            description=f"Builtin tool: {name}",
            tool_type="builtin",
            definition={"kind": "builtin", "name": name},
        )
        session.add(row)
        await session.flush()
    return row.id


async def _link_allowed_builtin_tools(
    session: AsyncSession,
    agent_id: uuid.UUID,
    allowed_tools: list[str] | None,
) -> None:
    for name in allowed_tools or []:
        tool_id = await _ensure_builtin_tool(session, name)
        if tool_id is not None:
            session.add(AgentTool(agent_id=agent_id, tool_id=tool_id))


async def sync_agents_from_profiles(session: AsyncSession) -> None:
    profiles = discover_agent_profiles()
    if not profiles:
        logger.warning("No agent profiles found under backend/agents/")
        return

    synced_slugs = {p.slug for p in profiles}

    for profile in profiles:
        agent_dir = AGENTS_ROOT / profile.slug
        agent_id = agent_id_for_slug(profile.slug)
        mcp_ids = await _sync_agent_mcp_servers(
            session,
            profile.slug,
            agent_dir,
            profile.mcp_server_overrides,
        )

        row = await session.get(AgentModel, agent_id)
        if row is None:
            row = AgentModel(
                id=agent_id,
                user_id=DEV_USER_ID,
                slug=profile.slug,
                name=profile.name,
                description=profile.description,
                instructions=profile.instructions,
                model_provider=profile.model_provider,
                model_name=profile.model_name,
                config=profile.extra_config,
            )
            session.add(row)
        else:
            row.slug = profile.slug
            row.name = profile.name
            row.description = profile.description
            row.instructions = profile.instructions
            row.model_provider = profile.model_provider
            row.model_name = profile.model_name
            row.config = profile.extra_config

        await session.flush()

        await session.execute(delete(AgentTool).where(AgentTool.agent_id == agent_id))
        await session.execute(delete(AgentMcpServer).where(AgentMcpServer.agent_id == agent_id))
        await session.execute(delete(AgentSkill).where(AgentSkill.agent_id == agent_id))

        for mcp_name in profile.mcp_servers:
            mcp_id = mcp_ids.get(mcp_name)
            if mcp_id is None:
                logger.warning(
                    "Agent %s references unknown MCP server %s (check agents/%s/mcp_servers.yaml)",
                    profile.slug,
                    mcp_name,
                    profile.slug,
                )
                continue
            session.add(AgentMcpServer(agent_id=agent_id, mcp_server_id=mcp_id))

        for skill_path in profile.skill_paths:
            backend_root = AGENTS_ROOT.parent
            rel_str = str(skill_path.relative_to(backend_root)).replace("\\", "/")
            skill_name = skill_path.name
            skill_row = (
                await session.execute(select(Skill).where(Skill.name == skill_name))
            ).scalar_one_or_none()
            if skill_row is None:
                skill_row = Skill(
                    name=skill_name,
                    description=f"Skill from {rel_str}",
                    source_type="file",
                    source_path=rel_str,
                    skill_metadata={},
                )
                session.add(skill_row)
            else:
                skill_row.source_path = rel_str
                skill_row.description = f"Skill from {rel_str}"
            await session.flush()
            session.add(AgentSkill(agent_id=agent_id, skill_id=skill_row.id))

        await _link_allowed_builtin_tools(
            session,
            agent_id,
            list(profile.extra_config.get("allowed_tools") or []),
        )

        logger.info("Synced agent profile: %s", profile.slug)

    from app.db.models import Chat

    result = await session.execute(select(AgentModel).where(AgentModel.slug.isnot(None)))
    for row in result.scalars().all():
        if row.slug and row.slug not in synced_slugs:
            chat_count = (
                await session.execute(select(Chat.id).where(Chat.agent_id == row.id).limit(1))
            ).first()
            if chat_count:
                logger.warning("Agent %s removed from disk but kept (has chats)", row.slug)
                continue
            await session.delete(row)
            logger.info("Removed agent no longer in profiles: %s", row.slug)

    await _cleanup_orphan_file_mcp_servers(session, synced_slugs)


async def sync_platform_config(session: AsyncSession) -> None:
    await ensure_platform_user(session)
    await sync_agents_from_profiles(session)
    await session.commit()
