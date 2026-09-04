"""Stream SSE side-channel emitters (viz, artifacts, proposal preview, slide builds)."""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.platform.chat.run_service import StreamTurnAccumulator


class StreamEmitter(ABC):
    """Drain domain-specific pending events during an agent stream."""

    def matches_slug(self, agent_slug: str | None) -> bool:
        return True

    def drain_pending(
        self,
        chat_id: uuid.UUID,
        accumulator: StreamTurnAccumulator,
    ) -> list[dict[str, Any]]:
        return []

    async def drain_remaining(
        self,
        chat_id: uuid.UUID,
        accumulator: StreamTurnAccumulator,
    ) -> AsyncIterator[dict[str, Any]]:
        return
        yield  # pragma: no cover — makes this an async generator

    def events_for_tool_result(
        self,
        chat_id: uuid.UUID,
        tool_name: str,
        accumulator: StreamTurnAccumulator,
    ) -> list[dict[str, Any]]:
        return []
