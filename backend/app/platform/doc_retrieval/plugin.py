"""Initialize doc retrieval context for chat runs."""

from __future__ import annotations

from app.platform.doc_retrieval.context import init_doc_retrieval_context, reset_doc_retrieval_context
from app.platform.doc_retrieval.store import build_chat_library
from app.platform.doc_retrieval.tools import DOC_RETRIEVAL_TOOL_NAMES
from app.platform.runtime.plugin import AgentPlugin, RunContext


class DocRetrievalPlugin(AgentPlugin):
    """Platform-wide: every chat agent can grep/read parsed attachments."""

    tool_names = DOC_RETRIEVAL_TOOL_NAMES

    def matches(self, agent_slug: str | None) -> bool:
        return True

    async def on_run_start(self, ctx: RunContext) -> None:
        library = await build_chat_library(ctx.db, ctx.chat_id)
        init_doc_retrieval_context(
            chat_id=ctx.chat_id,
            library=library,
            turn_attachment_ids=ctx.turn_attachment_ids,
        )

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_doc_retrieval_context()
