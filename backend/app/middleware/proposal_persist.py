"""Persist proposal_draft after write tools complete (same request transaction)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.session_store import SessionStore
from app.proposal.context import get_run_proposal_state
from app.proposal.store import persist_proposal_draft_if_dirty

logger = logging.getLogger(__name__)

_WRITE_TOOLS = frozenset(
    {
        "initialize_proposal_draft",
        "patch_proposal_draft",
        "add_package_to_proposal_draft",
        "add_services_to_proposal_draft",
        "remove_fee_rows_from_proposal_draft",
        "enable_proposal_draft_section",
        "render_preview",
        "generate_document",
    }
)


class ProposalPersistMiddleware(FunctionMiddleware):
    """Flush proposal_draft to chat.session_state after each successful write tool."""

    def __init__(
        self,
        db: AsyncSession,
        session_store: SessionStore,
        *,
        chat_id: uuid.UUID | None,
    ) -> None:
        self._db = db
        self._store = session_store
        self._chat_id = chat_id

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        await call_next()
        if self._chat_id is None or context.function.name not in _WRITE_TOOLS:
            return

        ctx = get_run_proposal_state()
        if ctx is None:
            logger.warning(
                "proposal persist skipped after %s: no run context (chat=%s)",
                context.function.name,
                self._chat_id,
            )
            return
        if not ctx.draft_dirty:
            return

        try:
            await persist_proposal_draft_if_dirty(self._store, self._chat_id)
            await self._db.commit()
        except Exception:
            logger.exception(
                "Failed to persist proposal draft after %s for chat %s",
                context.function.name,
                self._chat_id,
            )
            await self._db.rollback()
