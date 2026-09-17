"""Per-user per-agent hybrid-search KB enable/disable preferences."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.kb_preferences import KbPreferenceRepository
from app.platform.integrations.kb_client import HybridSearchKbClientError, list_visible_knowledge_bases

# Short TTL cache so chat turns don't pay OpenKMS RTT on every AgentFactory.build.
_VISIBLE_IDS_CACHE: dict[uuid.UUID, tuple[float, list[str]]] = {}
_VISIBLE_IDS_TTL_SECONDS = 60.0


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
    cleaned = await KbPreferenceRepository(db).upsert_disabled_ids(user_id, agent_id, disabled_kb_ids)
    # Preference change may alter which ids are enabled — drop cache so next scoped run refreshes.
    _VISIBLE_IDS_CACHE.pop(user_id, None)
    return cleaned


def enabled_kb_ids(*, visible_ids: list[str], disabled_ids: list[str]) -> list[str]:
    disabled = {str(item).strip() for item in disabled_ids if str(item).strip()}
    return [kb_id for kb_id in visible_ids if kb_id not in disabled]


def invalidate_visible_kb_cache(user_id: uuid.UUID | None = None) -> None:
    if user_id is None:
        _VISIBLE_IDS_CACHE.clear()
        return
    _VISIBLE_IDS_CACHE.pop(user_id, None)


async def resolve_enabled_kb_ids_for_run(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    api_key: str | None,
) -> list[str] | None:
    """Return enabled KB ids for middleware, or None when no scoping is needed.

    Fast path: empty disabled preference → None (skip OpenKMS list; no middleware).
    Slow path: user disabled some KBs → list visible ids (cached ~60s) and subtract.
    """
    disabled = await get_disabled_kb_ids(db, user_id, agent_id)
    if not disabled:
        return None
    if not api_key:
        return None

    now = time.monotonic()
    cached = _VISIBLE_IDS_CACHE.get(user_id)
    if cached is not None and (now - cached[0]) < _VISIBLE_IDS_TTL_SECONDS:
        visible = cached[1]
    else:
        try:
            items: list[dict[str, Any]] = await list_visible_knowledge_bases(api_key=api_key)
        except HybridSearchKbClientError:
            return None
        visible = [str(item.get("id") or "").strip() for item in items if item.get("id")]
        _VISIBLE_IDS_CACHE[user_id] = (now, visible)

    return enabled_kb_ids(visible_ids=visible, disabled_ids=disabled)
