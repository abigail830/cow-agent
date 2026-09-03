"""Inject long-term memory documents before each agent run."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import ContextProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.long_term.formatter import format_for_injection
from app.memory.long_term.repository import MemoryRepository, MemoryScope
from app.memory.memory_config import MemoryConfig

SOURCE_ID = "long-term-memory"


class LongTermMemoryProvider(ContextProvider):
    def __init__(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        agent_slug: str,
        memory_config: MemoryConfig,
    ) -> None:
        super().__init__(SOURCE_ID)
        self._db = db
        self._user_id = user_id
        self._agent_id = agent_id
        self._agent_slug = agent_slug
        self._memory_config = memory_config

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        if not self._memory_config.long_term.enabled:
            return

        repo = MemoryRepository(self._db)
        user_snapshot = await repo.get_snapshot(self._user_id, MemoryScope("user"))
        agent_snapshot = await repo.get_snapshot(
            self._user_id,
            MemoryScope("agent", agent_id=self._agent_id),
        )
        user_content = user_snapshot.content if user_snapshot else ""
        agent_content = agent_snapshot.content if agent_snapshot else ""
        block = format_for_injection(
            user_content,
            agent_content,
            agent_slug=self._agent_slug,
            max_tokens=self._memory_config.long_term.inject_max_tokens,
        )
        if block:
            context.extend_instructions(self.source_id, block)
