"""Initialize doc retrieval context for chat runs."""

from __future__ import annotations

from app.db.models import AgentModel
from app.platform.doc_retrieval.context import init_doc_retrieval_context, reset_doc_retrieval_context
from app.platform.doc_retrieval.store import build_chat_library
from app.platform.doc_retrieval.tools import DOC_RETRIEVAL_TOOL_NAMES
from app.platform.runtime.plugin import AgentPlugin, RunContext


class DocRetrievalPlugin(AgentPlugin):
    tool_names = DOC_RETRIEVAL_TOOL_NAMES

    def matches(self, agent_slug: str | None) -> bool:
        return True

    async def _agent_has_doc_tools(self, ctx: RunContext) -> bool:
        agent = await ctx.db.get(AgentModel, ctx.chat.agent_id)
        if agent is None:
            return False
        allowed = set((agent.config or {}).get("allowed_tools") or [])
        return bool(allowed & DOC_RETRIEVAL_TOOL_NAMES)

    async def on_run_start(self, ctx: RunContext) -> None:
        if not await self._agent_has_doc_tools(ctx):
            return
        library = await build_chat_library(ctx.db, ctx.chat_id)
        init_doc_retrieval_context(
            chat_id=ctx.chat_id,
            library=library,
            turn_attachment_ids=ctx.turn_attachment_ids,
        )

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_doc_retrieval_context()
