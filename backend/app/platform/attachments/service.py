import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.cleanup import delete_attachment_storage
from app.platform.attachments.metadata import attachment_metadata
from app.platform.attachments.parse_ingest import retry_attachment_parse
from app.platform.attachments.upload import AttachmentUploader
from app.platform.parse_pipeline.repository import ParseJobRepository


class AttachmentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._attachments = AttachmentRepository(db)
        self._uploader = AttachmentUploader(db, self._attachments)

    async def upload(
        self,
        chat_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
    ) -> dict:
        return await self._uploader.upload(
            chat_id,
            filename=filename,
            mime_type=mime_type,
            data=data,
        )

    async def resolve_for_message(
        self,
        chat_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
    ) -> list:
        return await self._uploader.resolve_for_message(chat_id, attachment_ids)

    async def delete(self, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
        row = await self._attachments.get(attachment_id)
        if row is None or row.chat_id != chat_id:
            raise ValueError("Attachment not found for this chat")

        delete_attachment_storage(row)
        await ParseJobRepository(self._db).delete_for_attachment(attachment_id)
        await self._attachments.delete(chat_id, attachment_id)
        await self._db.commit()

    async def retry_parse(self, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> dict:
        row = await self._attachments.get(attachment_id)
        if row is None or row.chat_id != chat_id:
            raise ValueError("Attachment not found for this chat")
        updated = await retry_attachment_parse(self._db, row)
        await self._db.commit()
        payload = attachment_metadata(updated)
        if updated.created_at is not None:
            payload["created_at"] = updated.created_at.isoformat()
        return payload

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[dict]:
        rows = await self._attachments.list_for_chat(chat_id)
        result: list[dict] = []
        for row in rows:
            payload = attachment_metadata(row)
            if row.created_at is not None:
                payload["created_at"] = row.created_at.isoformat()
            result.append(payload)
        return result
