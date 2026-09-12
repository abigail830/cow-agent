import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.modes import AttachmentProcessingMode, DEFAULT_ATTACHMENT_MODE, parse_attachment_mode
from app.platform.attachments.attachment_storage import (
    delete_inline_attachment,
    is_inline_provider_file_id,
    parse_inline_attachment_id,
)
from app.platform.attachments.native.maf_content import attachment_metadata
from app.platform.attachments.native.upload import NativeAttachmentUploader
from app.platform.attachments.unify_lite.handler import UnifyLiteAttachmentHandler

class AttachmentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._attachments = AttachmentRepository(db)
        self._native = NativeAttachmentUploader(db, self._attachments)
        self._unify_lite = UnifyLiteAttachmentHandler(db, self._attachments)

    async def upload(
        self,
        chat_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
        processing_mode: str | AttachmentProcessingMode | None = None,
    ) -> dict:
        mode = (
            processing_mode
            if isinstance(processing_mode, AttachmentProcessingMode)
            else parse_attachment_mode(processing_mode)
        )
        if mode == AttachmentProcessingMode.UNIFY_LITE:
            return await self._unify_lite.upload(
                chat_id,
                filename=filename,
                mime_type=mime_type,
                data=data,
            )
        return await self._native.upload(
            chat_id,
            filename=filename,
            mime_type=mime_type,
            data=data,
        )

    async def resolve_for_message(
        self,
        chat_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
        *,
        expected_provider: str,
        processing_mode: str | AttachmentProcessingMode | None = None,
    ) -> list:
        mode = (
            processing_mode
            if isinstance(processing_mode, AttachmentProcessingMode)
            else parse_attachment_mode(processing_mode)
        )
        if mode == AttachmentProcessingMode.UNIFY_LITE:
            rows = await self._unify_lite.resolve_for_message(chat_id, attachment_ids)
            self._unify_lite.ensure_run_input_supported()
            return rows

        return await self._native.resolve_for_message(
            chat_id,
            attachment_ids,
            expected_provider=expected_provider,
        )

    async def delete(self, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
        row = await self._attachments.delete(chat_id, attachment_id)
        if row is None:
            raise ValueError("Attachment not found for this chat")
        if is_inline_provider_file_id(row.provider_file_id):
            try:
                delete_inline_attachment(chat_id, parse_inline_attachment_id(row.provider_file_id))
            except OSError:
                pass
        await self._db.commit()

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[dict]:
        rows = await self._attachments.list_for_chat(chat_id)
        result: list[dict] = []
        for row in rows:
            mode = (
                AttachmentProcessingMode.UNIFY_LITE.value
                if row.provider == AttachmentProcessingMode.UNIFY_LITE.value
                else AttachmentProcessingMode.NATIVE.value
            )
            payload = attachment_metadata(row, processing_mode=mode)
            if row.created_at is not None:
                payload["created_at"] = row.created_at.isoformat()
            result.append(payload)
        return result

    @staticmethod
    def default_processing_mode() -> AttachmentProcessingMode:
        return DEFAULT_ATTACHMENT_MODE
