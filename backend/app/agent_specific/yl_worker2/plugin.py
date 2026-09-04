"""YL Worker 2 runtime plugin."""

from __future__ import annotations

from app.agent_specific.yl_worker2.fulfillment.context import (
    init_run_fulfillment_forms_state,
    reset_run_fulfillment_forms_state,
)
from app.agent_specific.yl_worker2.fulfillment.store import (
    load_fulfillment_forms_from_payload,
    persist_fulfillment_forms_if_dirty,
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

    async def on_finalize_success(self, ctx: RunContext, *, accumulator=None) -> None:
        await persist_fulfillment_forms_if_dirty(ctx.session_store, ctx.chat_id)

    async def on_finalize_failure(self, ctx: RunContext, *, accumulator=None) -> None:
        await persist_fulfillment_forms_if_dirty(ctx.session_store, ctx.chat_id)
