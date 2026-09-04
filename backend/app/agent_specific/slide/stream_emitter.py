"""Slide async build completion stream events."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.shared.artifacts.context import get_run_artifact_state
from app.shared.artifacts.stream_emitter import ArtifactStreamEmitter
from app.platform.runtime.stream_emitter import StreamEmitter

if TYPE_CHECKING:
    from app.platform.chat.run_service import StreamTurnAccumulator


class SlideBuildStreamEmitter(StreamEmitter):
    slug = "slide-studio"

    def matches_slug(self, agent_slug: str | None) -> bool:
        return agent_slug == self.slug

    def drain_pending(
        self,
        chat_id: uuid.UUID,
        accumulator: StreamTurnAccumulator,
    ) -> list[dict[str, Any]]:
        from app.agent_specific.slide.build_jobs import drain_completed_slide_build_jobs

        specs = drain_completed_slide_build_jobs(chat_id)
        if not specs:
            return []

        slide_ctx = get_run_artifact_state()
        if slide_ctx is not None:
            for spec in specs:
                slide_ctx.queue_artifact(spec)
        return ArtifactStreamEmitter().drain_pending(chat_id, accumulator)

    async def drain_remaining(
        self,
        chat_id: uuid.UUID,
        accumulator: StreamTurnAccumulator,
    ) -> AsyncIterator[dict[str, Any]]:
        from app.config import get_settings
        from app.agent_specific.slide.build_jobs import has_pending_slide_build_jobs

        settings = get_settings()
        if not settings.sandbox_async_build:
            return

        deadline = asyncio.get_event_loop().time() + max(60.0, settings.sandbox_timeout_seconds + 30.0)
        while asyncio.get_event_loop().time() < deadline:
            for event in self.drain_pending(chat_id, accumulator):
                yield event
            if not has_pending_slide_build_jobs(chat_id):
                return
            await asyncio.sleep(0.5)


def flush_completed_slide_build_artifacts(chat_id: uuid.UUID) -> None:
    from app.agent_specific.slide.build_jobs import drain_completed_slide_build_jobs

    specs = drain_completed_slide_build_jobs(chat_id)
    slide_ctx = get_run_artifact_state()
    if slide_ctx is None:
        return
    for spec in specs:
        slide_ctx.queue_artifact(spec)
