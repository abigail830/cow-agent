"""Per-user per-agent hybrid-search KB enable/disable preferences."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.kb_preferences import KbPreferenceRepository
from app.platform.integrations.kb_client import HybridSearchKbClientError, list_visible_knowledge_bases
from app.platform.memory.long_term.formatter import bullets_to_lines, parse_bullets, validate_line
from app.platform.memory.long_term.repository import MemoryRepository, MemoryScope

logger = logging.getLogger(__name__)

# Short TTL cache so UI + chat turns don't pay OpenKMS RTT on every list/toggle.
_VISIBLE_ITEMS_CACHE: dict[uuid.UUID, tuple[float, list[dict[str, Any]]]] = {}
_VISIBLE_ITEMS_TTL_SECONDS = 60.0

# Stable marker for the platform-managed agent-memory bullet (upsert by this substring).
KB_SCOPE_MEMORY_MARKER = "Enabled hybrid-search knowledge bases (platform-managed)"


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
    return cleaned


def enabled_kb_ids(*, visible_ids: list[str], disabled_ids: list[str]) -> list[str]:
    disabled = {str(item).strip() for item in disabled_ids if str(item).strip()}
    return [kb_id for kb_id in visible_ids if kb_id not in disabled]


def invalidate_visible_kb_cache(user_id: uuid.UUID | None = None) -> None:
    if user_id is None:
        _VISIBLE_ITEMS_CACHE.clear()
        return
    _VISIBLE_ITEMS_CACHE.pop(user_id, None)


async def fetch_visible_knowledge_bases_cached(
    *,
    user_id: uuid.UUID,
    api_key: str,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """List visible KBs from OpenKMS with a per-user TTL cache."""
    now = time.monotonic()
    if not force_refresh:
        cached = _VISIBLE_ITEMS_CACHE.get(user_id)
        if cached is not None and (now - cached[0]) < _VISIBLE_ITEMS_TTL_SECONDS:
            return list(cached[1])

    items = await list_visible_knowledge_bases(api_key=api_key)
    _VISIBLE_ITEMS_CACHE[user_id] = (now, items)
    return items


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

    try:
        items = await fetch_visible_knowledge_bases_cached(user_id=user_id, api_key=api_key)
    except HybridSearchKbClientError:
        return None
    visible = [str(item.get("id") or "").strip() for item in items if item.get("id")]
    return enabled_kb_ids(visible_ids=visible, disabled_ids=disabled)


def format_kb_scope_memory_line(*, enabled_items: list[dict[str, Any]]) -> str:
    """Build the [!] agent-memory bullet describing currently enabled KBs."""
    if not enabled_items:
        return (
            f"[!] {KB_SCOPE_MEMORY_MARKER}: none enabled — do not call hybrid_search."
        )
    parts: list[str] = []
    for item in enabled_items:
        kb_id = str(item.get("id") or "").strip()
        if not kb_id:
            continue
        name = str(item.get("name") or kb_id).strip() or kb_id
        parts.append(f"{name} ({kb_id})")
    if not parts:
        return (
            f"[!] {KB_SCOPE_MEMORY_MARKER}: none enabled — do not call hybrid_search."
        )
    return (
        f"[!] {KB_SCOPE_MEMORY_MARKER}: only use these kb_ids — {'; '.join(parts)}. "
        "Pass only these ids to hybrid_search; do not search other knowledge bases."
    )


def upsert_kb_scope_memory_content(content: str, *, line: str | None) -> str:
    """Remove any managed KB-scope bullet; optionally append a fresh one."""
    kept: list[tuple[str, str]] = []
    for prefix, text in parse_bullets(content):
        if KB_SCOPE_MEMORY_MARKER in text:
            continue
        kept.append((prefix, text))
    if line is not None:
        validated = validate_line(line)
        if validated.startswith("[!]"):
            kept.append(("[!]", validated[3:].strip()))
        else:
            body = validated[1:].strip() if validated.startswith("-") else validated
            kept.append(("-", body))
    if not kept:
        return ""
    return "\n".join(bullets_to_lines(kept))


async def sync_enabled_kbs_to_agent_memory(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    disabled_kb_ids: list[str],
    api_key: str | None,
) -> None:
    """Upsert/clear a platform-managed [!] bullet in agent-scoped long-term memory.

    - No disabled preferences → clear the managed line (all visible KBs allowed).
    - Some disabled → write enabled id+name list (requires api_key to list visible KBs).
    - Missing api_key / list failure while some KBs are disabled → leave memory unchanged.
    """
    scope = MemoryScope("agent", agent_id=agent_id)
    repo = MemoryRepository(db)

    if not disabled_kb_ids:
        await repo.remove_lines(user_id, scope, match=KB_SCOPE_MEMORY_MARKER)
        return

    if not api_key:
        logger.info(
            "Skipping KB-scope memory sync for user=%s agent=%s: no hybrid-search API key",
            user_id,
            agent_id,
        )
        return

    try:
        items = await fetch_visible_knowledge_bases_cached(user_id=user_id, api_key=api_key)
    except HybridSearchKbClientError as exc:
        logger.warning(
            "Skipping KB-scope memory sync for user=%s agent=%s: %s",
            user_id,
            agent_id,
            exc,
        )
        return

    disabled = {str(item).strip() for item in disabled_kb_ids if str(item).strip()}
    enabled_items = [
        item
        for item in items
        if str(item.get("id") or "").strip()
        and str(item.get("id") or "").strip() not in disabled
    ]
    line = format_kb_scope_memory_line(enabled_items=enabled_items)
    await repo.remove_lines(user_id, scope, match=KB_SCOPE_MEMORY_MARKER)
    await repo.append_lines(user_id, scope, [line], source="kb-preferences")
