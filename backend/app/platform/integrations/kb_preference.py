"""Per-user per-agent hybrid-search KB enable/disable preferences."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.kb_preferences import KbPreferenceRepository


def agent_supports_kb_scope(config: dict | None) -> bool:
    """True when the agent profile exposes hybrid-search MCP tools."""
    allowed = list((config or {}).get("allowed_tools") or [])
    for name in allowed:
        text = str(name or "")
        if text.startswith("hybrid-search_") or text in {"hybrid_search", "list_knowledge_bases"}:
            return True
    mcp = (config or {}).get("mcp_servers")
    if isinstance(mcp, list):
        return any(str(item) == "hybrid-search" for item in mcp)
    if isinstance(mcp, dict):
        return "hybrid-search" in mcp
    return False


async def get_disabled_kb_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> list[str]:
    return await KbPreferenceRepository(db).get_disabled_ids(user_id, agent_id)


async def set_disabled_kb_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    disabled_kb_ids: list[str],
) -> list[str]:
    return await KbPreferenceRepository(db).upsert_disabled_ids(user_id, agent_id, disabled_kb_ids)


def enabled_kb_ids(*, visible_ids: list[str], disabled_ids: list[str]) -> list[str]:
    disabled = {str(item).strip() for item in disabled_ids if str(item).strip()}
    return [kb_id for kb_id in visible_ids if kb_id not in disabled]
