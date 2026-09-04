"""Orchestrate plugin stream emitters during chat runs."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.agent_specific.viz.stream_emitter import VizStreamEmitter
from app.platform.agent.plugin_registry import iter_plugins_for_slug
from app.platform.runtime.stream_emitter import StreamEmitter
from app.shared.artifacts.stream_emitter import ArtifactStreamEmitter

if TYPE_CHECKING:
    from app.platform.chat.run_service import StreamTurnAccumulator

_GLOBAL_EMITTERS: tuple[StreamEmitter, ...] = (
    VizStreamEmitter(),
    ArtifactStreamEmitter(),
)


def collect_stream_emitters(agent_slug: str | None) -> list[StreamEmitter]:
    emitters: list[StreamEmitter] = list(_GLOBAL_EMITTERS)
    for plugin in iter_plugins_for_slug(agent_slug):
        for emitter in plugin.stream_emitters():
            if emitter.matches_slug(agent_slug):
                emitters.append(emitter)
    return emitters


def drain_stream_events(
    emitters: list[StreamEmitter],
    chat_id: uuid.UUID,
    accumulator: StreamTurnAccumulator,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for emitter in emitters:
        events.extend(emitter.drain_pending(chat_id, accumulator))
    return events


async def drain_remaining_stream_events(
    emitters: list[StreamEmitter],
    chat_id: uuid.UUID,
    accumulator: StreamTurnAccumulator,
) -> AsyncIterator[dict[str, Any]]:
    for emitter in emitters:
        async for event in emitter.drain_remaining(chat_id, accumulator):
            yield event


def tool_result_stream_events(
    emitters: list[StreamEmitter],
    chat_id: uuid.UUID,
    tool_name: str,
    accumulator: StreamTurnAccumulator,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for emitter in emitters:
        events.extend(emitter.events_for_tool_result(chat_id, tool_name, accumulator))
    return events
