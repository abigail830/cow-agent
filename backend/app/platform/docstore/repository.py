from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment, HubItem
from app.platform.docstore.manifest import merge_hub_parsed_artifact_record, merge_parsed_artifact_record
from app.platform.docstore.models import ParseStatus

ParsedArtifactRecord = tuple[str, int, str]  # artifact_key, size_bytes, content_type

ParseDocumentRow = ChatAttachment | HubItem


class DocstoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_parse_row(self, document_id: uuid.UUID) -> ParseDocumentRow | None:
        row = await self._session.get(ChatAttachment, document_id)
        if row is not None:
            return row
        return await self._session.get(HubItem, document_id)

    async def mark_parse_ready(
        self,
        attachment_id: uuid.UUID,
        *,
        pipeline_id: str | None = None,
        skipped: bool = False,
    ) -> ParseDocumentRow | None:
        row = await self._get_parse_row(attachment_id)
        if row is None:
            return None
        row.parse_status = ParseStatus.SKIPPED.value if skipped else ParseStatus.READY.value
        row.parse_pipeline_id = pipeline_id
        row.parse_job_id = None
        row.parse_error_code = None
        row.parse_error_message = None
        row.parse_stage_snapshot = None
        row.parsed_artifact_manifest = None
        row.gist = None
        row.gist_content_sha256 = None
        row.gist_generated_at = None
        await self._session.flush()
        return row

    async def mark_parse_pending(
        self,
        attachment_id: uuid.UUID,
        *,
        pipeline_id: str,
        job_id: str,
    ) -> ParseDocumentRow | None:
        row = await self._get_parse_row(attachment_id)
        if row is None:
            return None
        row.parse_status = ParseStatus.PENDING.value
        row.parse_pipeline_id = pipeline_id
        row.parse_job_id = job_id
        row.parse_error_code = None
        row.parse_error_message = None
        row.parse_stage_snapshot = None
        row.parsed_artifact_manifest = None
        row.gist = None
        row.gist_content_sha256 = None
        row.gist_generated_at = None
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
        result = await self._session.execute(
            select(ChatAttachment)
            .where(ChatAttachment.id == attachment_id)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
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

    async def record_parsed_artifacts_batch(
        self,
        attachment_id: uuid.UUID,
        *,
        chat_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        artifacts: list[ParsedArtifactRecord],
    ) -> ParseDocumentRow | None:
        """Merge all parsed artifact keys in one locked transaction (no lost updates)."""
        if not artifacts:
            return None
        if user_id is not None:
            result = await self._session.execute(
                select(HubItem).where(HubItem.id == attachment_id).with_for_update()
            )
            row = result.scalar_one_or_none()
            if row is None or row.user_id != user_id:
                return None
            manifest = row.parsed_artifact_manifest
            for artifact_key, size_bytes, content_type in artifacts:
                manifest = merge_hub_parsed_artifact_record(
                    manifest,
                    user_id=user_id,
                    item_id=attachment_id,
                    artifact_key=artifact_key,
                    size_bytes=size_bytes,
                    content_type=content_type,
                )
            row.parsed_artifact_manifest = manifest
            await self._session.flush()
            return row

        if chat_id is None:
            return None
        result = await self._session.execute(
            select(ChatAttachment)
            .where(ChatAttachment.id == attachment_id)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.chat_id != chat_id:
            return None
        manifest = row.parsed_artifact_manifest
        for artifact_key, size_bytes, content_type in artifacts:
            manifest = merge_parsed_artifact_record(
                manifest,
                chat_id=chat_id,
                attachment_id=attachment_id,
                artifact_key=artifact_key,
                size_bytes=size_bytes,
                content_type=content_type,
            )
        row.parsed_artifact_manifest = manifest
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
    ) -> ParseDocumentRow | None:
        row = await self._get_parse_row(attachment_id)
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
