"""Inject attachment catalog index before each agent run (P5a)."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import ContextProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.catalog.facts import format_facts_and_budget_block
from app.platform.attachments.catalog.gist import bootstrap_gist
from app.platform.attachments.run_state import AttachmentRecord, attachment_records_from_rows
from app.platform.memory.memory_config import AttachmentPullConfig

SOURCE_ID = "attachment-catalog"


class AttachmentCatalogContextProvider(ContextProvider):
    def __init__(
        self,
        db: AsyncSession,
        *,
        chat_id: uuid.UUID,
        pull_config: AttachmentPullConfig,
    ) -> None:
        super().__init__(SOURCE_ID)
        self._db = db
        self._chat_id = chat_id
        self._pull_config = pull_config

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        if not self._pull_config.enabled:
            return

        repo = AttachmentRepository(self._db)
        rows = await repo.list_for_chat(self._chat_id)
        records: list[AttachmentRecord] = []
        for row in rows:
            gist = bootstrap_gist(
                filename=row.filename,
                mime_type=row.mime_type,
                existing_gist=row.gist,
            )
            records.append(
                AttachmentRecord(
                    attachment_id=row.id,
                    chat_id=row.chat_id,
                    filename=row.filename,
                    mime_type=row.mime_type,
                    provider=row.provider,
                    provider_file_id=row.provider_file_id,
                    size_bytes=row.size_bytes,
                    gist=gist,
                    content_hash=row.content_hash,
                )
            )
        block = format_facts_and_budget_block(records)
        if block:
            context.extend_instructions(self.source_id, block)
