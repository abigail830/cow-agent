"""Agent runtime plugin protocol — per-slug run hooks and tool declarations."""

from __future__ import annotations

import uuid
from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import Chat
    from app.platform.session.session_store import SessionStore


@dataclass
class RunContext:
    db: AsyncSession
    chat: Chat
    chat_id: uuid.UUID
    session_store: SessionStore
    agent_slug: str | None
    run_id: uuid.UUID | None = None


class AgentPlugin(ABC):
    """Optional runtime behavior for an agent (context init, persist, stream extras)."""

    slug: str = ""
    slugs: frozenset[str] = frozenset()
    tool_names: frozenset[str] = frozenset()

    def matches(self, agent_slug: str | None) -> bool:
        if self.slugs:
            return agent_slug in self.slugs
        return bool(self.slug) and agent_slug == self.slug

    async def on_run_start(self, ctx: RunContext) -> None:
        return None

    async def on_run_end(self, ctx: RunContext) -> None:
        return None

    async def on_finalize_success(
        self, ctx: RunContext, *, accumulator: Any | None = None
    ) -> dict[str, Any] | None:
        return None

    def stream_emitters(self) -> list:
        return []

    async def on_finalize_failure(
        self, ctx: RunContext, *, accumulator: Any | None = None
    ) -> dict[str, Any] | None:
        return None

