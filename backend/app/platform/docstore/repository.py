from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment
from app.platform.docstore.manifest import merge_parsed_artifact_record
from app.platform.docstore.models import ParseStatus


class DocstoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_parse_ready(
        self,
        attachment_id: uuid.UUID,
        *,
        pipeline_id: str | None = None,
        skipped: bool = False,
    ) -> ChatAttachment | None:
        row = await self._session.get(ChatAttachment, attachment_id)
        if row is None:
            return None
        row.parse_status = ParseStatus.SKIPPED.value if skipped else ParseStatus.READY.value
        row.parse_pipeline_id = pipeline_id
        row.parse_job_id = None
        row.parse_error_code = None
        row.parse_error_message = None
        row.parse_stage_snapshot = None
        row.parsed_artifact_manifest = None
        await self._session.flush()
        return row

    async def mark_parse_pending(
        self,
        attachment_id: uuid.UUID,
        *,
        pipeline_id: str,
        job_id: str,
    ) -> ChatAttachment | None:
        row = await self._session.get(ChatAttachment, attachment_id)
        if row is None:
            return None
        row.parse_status = ParseStatus.PENDING.value
        row.parse_pipeline_id = pipeline_id
        row.parse_job_id = job_id
        row.parse_error_code = None
        row.parse_error_message = None
        row.parse_stage_snapshot = None
        row.parsed_artifact_manifest = None
        await self._session.flush()
        return row

    async def record_parsed_artifact(
        self,
        attachment_id: uuid.UUID,
        *,
        chat_id: uuid.UUID,
        artifact_key: str,
        size_bytes: int,
        content_type: str,
    ) -> ChatAttachment | None:
        row = await self._session.get(ChatAttachment, attachment_id)
        if row is None or row.chat_id != chat_id:
            return None
        row.parsed_artifact_manifest = merge_parsed_artifact_record(
            row.parsed_artifact_manifest,
            chat_id=chat_id,
            attachment_id=attachment_id,
            artifact_key=artifact_key,
            size_bytes=size_bytes,
            content_type=content_type,
        )
        await self._session.flush()
        return row

    async def apply_parse_webhook(
        self,
        attachment_id: uuid.UUID,
        *,
        status: str,
        stage_snapshot: dict[str, Any] | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ChatAttachment | None:
        row = await self._session.get(ChatAttachment, attachment_id)
        if row is None:
            return None
        row.parse_status = status
        if stage_snapshot is not None:
            row.parse_stage_snapshot = stage_snapshot
        if error_code is not None:
            row.parse_error_code = error_code
        if error_message is not None:
            row.parse_error_message = error_message
        await self._session.flush()
        return row
