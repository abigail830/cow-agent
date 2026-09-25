"""Audio capture persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudioCapture, ChatAttachment


class AudioCaptureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, capture_id: uuid.UUID) -> AudioCapture | None:
        return await self._session.get(AudioCapture, capture_id)

    async def get_for_chat(self, chat_id: uuid.UUID, capture_id: uuid.UUID) -> AudioCapture | None:
        row = await self.get(capture_id)
        if row is None or row.chat_id != chat_id:
            return None
        return row

    async def get_by_host_attachment(self, attachment_id: uuid.UUID) -> AudioCapture | None:
        result = await self._session.execute(
            select(AudioCapture).where(AudioCapture.host_attachment_id == attachment_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def insert(
        self,
        *,
        chat_id: uuid.UUID,
        host_attachment_id: uuid.UUID,
        title: str | None,
        context_snapshot: dict[str, Any],
        status: str = "pending",
    ) -> AudioCapture:
        row = AudioCapture(
            chat_id=chat_id,
            host_attachment_id=host_attachment_id,
            title=title,
            context_snapshot=context_snapshot,
            status=status,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update_status(
        self,
        capture_id: uuid.UUID,
        *,
        status: str,
        parse_job_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        input_message_id: uuid.UUID | None = None,
        output_annotation_id: uuid.UUID | None = None,
    ) -> AudioCapture | None:
        row = await self.get(capture_id)
        if row is None:
            return None
        row.status = status
        if parse_job_id is not None:
            row.parse_job_id = parse_job_id
        if error_code is not None:
            row.error_code = error_code
        if error_message is not None:
            row.error_message = error_message
        if input_message_id is not None:
            row.input_message_id = input_message_id
        if output_annotation_id is not None:
            row.output_annotation_id = output_annotation_id
        await self._session.flush()
        return row

    async def list_parts(self, capture_id: uuid.UUID) -> list[ChatAttachment]:
        capture = await self.get(capture_id)
        result = await self._session.execute(
            select(ChatAttachment).where(
                ChatAttachment.capture_id == capture_id,
                ChatAttachment.attachment_role == "audio_part",
            )
        )
        rows = list(result.scalars().all())
        order_map: dict[str, int] = {}
        if capture is not None:
            for item in (capture.context_snapshot or {}).get("parts") or []:
                if isinstance(item, dict) and item.get("attachment_id") is not None:
                    order_map[str(item["attachment_id"])] = int(item.get("sort_order") or 0)
        rows.sort(key=lambda row: order_map.get(str(row.id), 0))
        return rows
