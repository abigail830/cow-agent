"""Visualization stream events."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from app.agent_specific.viz.context import get_run_viz_state
from app.agent_specific.viz.spec import VizSpec
from app.platform.runtime.stream_emitter import StreamEmitter

if TYPE_CHECKING:
    from app.platform.chat.run_service import StreamTurnAccumulator


def viz_spec_payload(spec: VizSpec) -> dict[str, Any]:
    return spec.model_dump(mode="json", exclude_none=True)


class VizStreamEmitter(StreamEmitter):
    def drain_pending(
        self,
        chat_id: uuid.UUID,
        accumulator: StreamTurnAccumulator,
    ) -> list[dict[str, Any]]:
        state = get_run_viz_state()
        if state is None:
            return []

        events: list[dict[str, Any]] = []
        for spec in state.drain_pending():
            accumulator.record_viz(spec)
            events.append(
                {
                    "event": "viz",
                    "data": {
                        "chat_id": str(chat_id),
                        "spec": viz_spec_payload(spec),
                    },
                }
            )
        return events
