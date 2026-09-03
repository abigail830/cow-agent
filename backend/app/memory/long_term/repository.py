"""Persistence for scope-level memory documents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEvent, MemorySnapshot
from app.memory.long_term.formatter import bullets_to_lines, parse_bullets, validate_line


@dataclass(frozen=True)
class MemoryScope:
    scope: str  # user | agent
    agent_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if self.scope == "user" and self.agent_id is not None:
            raise ValueError("user scope cannot have agent_id")
        if self.scope == "agent" and self.agent_id is None:
            raise ValueError("agent scope requires agent_id")


class MemoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_snapshot(self, user_id: uuid.UUID, memory_scope: MemoryScope) -> MemorySnapshot | None:
        stmt = select(MemorySnapshot).where(
            MemorySnapshot.user_id == user_id,
            MemorySnapshot.scope == memory_scope.scope,
        )
        if memory_scope.scope == "agent":
            stmt = stmt.where(MemorySnapshot.agent_id == memory_scope.agent_id)
        else:
            stmt = stmt.where(MemorySnapshot.agent_id.is_(None))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_snapshot(self, user_id: uuid.UUID, memory_scope: MemoryScope) -> MemorySnapshot:
        existing = await self.get_snapshot(user_id, memory_scope)
        if existing is not None:
            return existing
        row = MemorySnapshot(
            user_id=user_id,
            scope=memory_scope.scope,
            agent_id=memory_scope.agent_id,
            content="",
            revision=1,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def replace_content(
        self,
        user_id: uuid.UUID,
        memory_scope: MemoryScope,
        content: str,
        *,
        source: str,
    ) -> MemorySnapshot:
        snapshot = await self.get_or_create_snapshot(user_id, memory_scope)
        normalized = _normalize_document(content)
        snapshot.content = normalized
        snapshot.revision += 1
        await self._record_event(snapshot, action="replace", lines=None, source=source)
        await self._db.flush()
        return snapshot

    async def append_lines(
        self,
        user_id: uuid.UUID,
        memory_scope: MemoryScope,
        lines: list[str],
        *,
        source: str,
    ) -> tuple[MemorySnapshot, list[str]]:
        snapshot = await self.get_or_create_snapshot(user_id, memory_scope)
        validated = [validate_line(line) for line in lines if line.strip()]
        if not validated:
            return snapshot, []

        existing_lines = {
            bullets_to_lines([row])[0] for row in parse_bullets(snapshot.content)
        }
        added: list[str] = []
        for line in validated:
            if line in existing_lines:
                continue
            added.append(line)

        if not added:
            return snapshot, []

        base = snapshot.content.rstrip()
        snapshot.content = f"{base}\n{chr(10).join(added)}".strip() if base else "\n".join(added)
        snapshot.revision += 1
        await self._record_event(snapshot, action="append", lines=added, source=source)
        await self._db.flush()
        return snapshot, added

    async def remove_lines(
        self,
        user_id: uuid.UUID,
        memory_scope: MemoryScope,
        *,
        match: str,
        also_search_user_scope: bool = False,
        agent_id_for_user: uuid.UUID | None = None,
    ) -> list[tuple[str, list[str]]]:
        """Remove bullets containing match. Returns list of (scope, removed_lines)."""
        needle = match.strip()
        if not needle:
            return []

        scopes: list[MemoryScope] = [memory_scope]
        if also_search_user_scope and memory_scope.scope == "agent":
            scopes.append(MemoryScope("user"))

        results: list[tuple[str, list[str]]] = []
        for scope in scopes:
            snapshot = await self.get_snapshot(user_id, scope)
            if snapshot is None or not snapshot.content.strip():
                continue
            rows = parse_bullets(snapshot.content)
            kept: list[tuple[str, str]] = []
            removed: list[str] = []
            for prefix, text in rows:
                full = f"[!] {text}" if prefix == "[!]" else f"- {text}"
                if needle in text or needle in full:
                    removed.append(full)
                else:
                    kept.append((prefix, text))
            if not removed:
                continue
            snapshot.content = "\n".join(bullets_to_lines(kept))
            snapshot.revision += 1
            await self._record_event(snapshot, action="remove", lines=removed, source="explicit")
            results.append((scope.scope, removed))
        await self._db.flush()
        return results

    async def _record_event(
        self,
        snapshot: MemorySnapshot,
        *,
        action: str,
        lines: list[str] | None,
        source: str,
    ) -> None:
        self._db.add(
            MemoryEvent(
                snapshot_id=snapshot.id,
                action=action,
                lines=lines,
                source=source,
            )
        )


def _normalize_document(content: str) -> str:
    rows = parse_bullets(content)
    if not rows:
        return ""
    return "\n".join(bullets_to_lines(rows))
