"""YL Worker 2 runtime plugin."""

from __future__ import annotations

from app.agent_specific.yl_worker2.fulfillment.context import (
    get_run_fulfillment_forms_state,
    init_run_fulfillment_forms_state,
    reset_run_fulfillment_forms_state,
)
from app.agent_specific.yl_worker2.fulfillment.store import (
    FULFILLMENT_FORMS_KEY,
    load_fulfillment_forms_from_payload,
    wrap_forms_document,
)
from app.agent_specific.yl_worker2.tools import YL_WORKER2_TOOL_NAMES
from app.platform.runtime.plugin import AgentPlugin, RunContext


class YlWorker2Plugin(AgentPlugin):
    slug = "yl-worker2"
    tool_names = YL_WORKER2_TOOL_NAMES

    async def on_run_start(self, ctx: RunContext) -> None:
        payload = await ctx.session_store.get_payload(ctx.chat_id)
        initial = load_fulfillment_forms_from_payload(payload)
        init_run_fulfillment_forms_state(chat_id=ctx.chat_id, initial_forms=initial)

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_run_fulfillment_forms_state()

    async def on_finalize_success(self, ctx: RunContext, *, accumulator=None) -> dict[str, object] | None:
        state = get_run_fulfillment_forms_state()
        if state is None or not state.dirty:
            return None
        state.dirty = False
        return {FULFILLMENT_FORMS_KEY: wrap_forms_document(state.forms)}

    async def on_finalize_failure(self, ctx: RunContext, *, accumulator=None) -> dict[str, object] | None:
        state = get_run_fulfillment_forms_state()
        if state is None or not state.dirty:
            return None
        state.dirty = False
        return {FULFILLMENT_FORMS_KEY: wrap_forms_document(state.forms)}
