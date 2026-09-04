"""Proposal Composer runtime plugin."""

from __future__ import annotations

from app.agent_specific.proposal.context import init_run_proposal_state, reset_run_proposal_state
from app.agent_specific.proposal.store import (
    load_proposal_draft_from_payload,
    persist_proposal_draft_if_dirty,
)
from app.agent_specific.proposal.stream_emitter import ProposalStreamEmitter
from app.platform.runtime.plugin import AgentPlugin, RunContext

PROPOSAL_TOOL_NAMES = frozenset(
    {
        "list_templates",
        "read_knowledge",
        "list_mdm_packages",
        "get_mdm_package_services",
        "search_mdm_services",
        "list_mdm_packages_for_services",
        "initialize_proposal_draft",
        "get_proposal_draft",
        "patch_proposal_draft",
        "add_package_to_proposal_draft",
        "add_services_to_proposal_draft",
        "remove_fee_rows_from_proposal_draft",
        "enable_proposal_draft_section",
        "render_preview",
        "generate_document",
        "generate_word_document",
    }
)


class ProposalPlugin(AgentPlugin):
    slug = "proposal-composer"
    tool_names = PROPOSAL_TOOL_NAMES

    async def on_run_start(self, ctx: RunContext) -> None:
        payload = await ctx.session_store.get_payload(ctx.chat_id)
        initial_draft = load_proposal_draft_from_payload(payload)
        init_run_proposal_state(chat_id=ctx.chat_id, initial_draft=initial_draft)

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_run_proposal_state()

    async def on_finalize_success(self, ctx: RunContext, *, accumulator=None) -> None:
        await persist_proposal_draft_if_dirty(ctx.session_store, ctx.chat_id)

    async def on_finalize_failure(self, ctx: RunContext, *, accumulator=None) -> None:
        await persist_proposal_draft_if_dirty(ctx.session_store, ctx.chat_id)

    def stream_emitters(self) -> list:
        return [ProposalStreamEmitter()]
