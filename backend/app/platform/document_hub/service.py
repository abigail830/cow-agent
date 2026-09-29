"""Document Hub domain service — upload, delete, move, folders."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HubAudioCapture, HubFolder, HubItem
from app.db.repositories.hub_folders import HubFolderRepository
from app.db.repositories.hub_items import HubItemRepository
from app.platform.attachments.convert.pdf_pages import count_pdf_pages
from app.platform.attachments.hash import sha256_hex
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.attachments.parse_ingest import finalize_hub_item_parse
from app.platform.attachments.validation import validate_attachment_file
from app.platform.blob.client import blob_exists_async, blob_storage_enabled
from app.platform.document_hub.blob_upload import hub_upload_mode
from app.platform.document_hub.metadata import hub_item_metadata
from app.platform.document_hub.storage import (
    delete_hub_item_storage,
    format_hub_inline_provider_file_id,
    hub_original_blob_path,
    save_hub_original,
)
from app.platform.docstore.models import ParseStatus


class DocumentHubService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._folders = HubFolderRepository(db)
        self._items = HubItemRepository(db)

    async def prepare_client_upload(
        self,
        user_id: uuid.UUID,
        folder_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        size_bytes: int,
    ) -> dict:
        if hub_upload_mode() != "blob":
            raise ValueError("Client blob upload is not enabled in this environment")
        folder = await self._folders.get_owned(user_id, folder_id)
        if folder is None:
            raise ValueError("Folder not found")
        validate_attachment_file(filename=filename, mime_type=mime_type, size_bytes=size_bytes)

        item_id = uuid.uuid4()
        row = await self._items.insert(
            item_id=item_id,
            user_id=user_id,
            folder_id=folder_id,
            item_kind="file",
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_hash=None,
            provider="inline",
            provider_file_id=format_hub_inline_provider_file_id(item_id),
            parse_status=ParseStatus.UPLOADING.value,
        )
        await self._db.flush()
        return {
            "item_id": str(row.id),
            "user_id": str(user_id),
            "pathname": hub_original_blob_path(user_id, item_id),
            "upload_mode": "blob",
        }

    async def complete_client_upload(
        self,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        size_bytes: int,
    ) -> dict:
        if not blob_storage_enabled():
            raise ValueError("Blob storage is required for client upload")
        row = await self._items.get_owned(user_id, item_id)
        if row is None:
            raise ValueError("Item not found")
        if row.parse_status != ParseStatus.UPLOADING.value:
            raise ValueError("Item is not awaiting upload completion")

        pathname = hub_original_blob_path(user_id, item_id)
        if not await blob_exists_async(pathname):
            raise ValueError("Uploaded file not found in blob storage")

        validate_attachment_file(
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=size_bytes,
        )
        row.size_bytes = size_bytes
        kind = classify_attachment(filename=row.filename, mime_type=row.mime_type)
        row = await finalize_hub_item_parse(self._db, row, kind=kind)
        await self._db.commit()
        await self._db.refresh(row)
        return hub_item_metadata(row)

    async def upload_file(
        self,
        user_id: uuid.UUID,
        folder_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
    ) -> dict:
        folder = await self._folders.get_owned(user_id, folder_id)
        if folder is None:
            raise ValueError("Folder not found")

        kind = classify_attachment(filename=filename, mime_type=mime_type)
        page_count: int | None = None
        if kind == AttachmentKind.PDF:
            page_count = count_pdf_pages(data)
        validate_attachment_file(
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            page_count=page_count,
        )

        content_hash = sha256_hex(data)
        duplicate = await self._items.find_by_content_hash(user_id, content_hash)
        if duplicate is not None:
            await self._db.refresh(duplicate)
            return {
                **hub_item_metadata(duplicate),
                "duplicate_of_existing": True,
            }

        item_id = uuid.uuid4()
        save_hub_original(user_id, item_id, data)
        row = await self._items.insert(
            item_id=item_id,
            user_id=user_id,
            folder_id=folder_id,
            item_kind="file",
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            content_hash=content_hash,
            provider="inline",
            provider_file_id=format_hub_inline_provider_file_id(item_id),
        )
        row = await finalize_hub_item_parse(self._db, row, kind=kind)
        await self._db.commit()
        await self._db.refresh(row)
        return hub_item_metadata(row)

    async def move_item(
        self,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        folder_id: uuid.UUID,
    ) -> HubItem:
        row = await self._items.get_owned(user_id, item_id)
        if row is None or row.attachment_role == "audio_part":
            raise ValueError("Item not found")
        folder = await self._folders.get_owned(user_id, folder_id)
        if folder is None:
            raise ValueError("Folder not found")
        return await self._items.move_to_folder(row, folder_id)

    async def delete_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
        row = await self._items.get_owned(user_id, item_id)
        if row is None or row.attachment_role == "audio_part":
            raise ValueError("Item not found")
        await self._delete_item_tree(row)

    async def delete_folder_cascade(self, user_id: uuid.UUID, folder_id: uuid.UUID) -> None:
        root = await self._folders.get_owned(user_id, folder_id)
        if root is None:
            raise ValueError("Folder not found")
        folder_ids = self._collect_folder_subtree(await self._folders.list_for_user(user_id), folder_id)
        for fid in reversed(folder_ids):
            for item in await self._items.list_folder_items(user_id, fid):
                await self._delete_item_tree(item)
            folder = await self._folders.get_owned(user_id, fid)
            if folder is not None:
                await self._folders.delete(folder)

    async def _delete_item_tree(self, row: HubItem) -> None:
        if row.item_kind == "audio_capture" and row.capture_id:
            parts = await self._items.list_parts(row.capture_id)
            for part in parts:
                delete_hub_item_storage(part)
                await self._items.delete(part)
            capture = await self._db.get(HubAudioCapture, row.capture_id)
            if capture is not None:
                await self._db.delete(capture)
                await self._db.flush()
        delete_hub_item_storage(row)
        await self._items.delete(row)

    @staticmethod
    def _collect_folder_subtree(all_folders: list[HubFolder], root_id: uuid.UUID) -> list[uuid.UUID]:
        children_by_parent: dict[uuid.UUID | None, list[HubFolder]] = defaultdict(list)
        for folder in all_folders:
            children_by_parent[folder.parent_id].append(folder)
        ordered: list[uuid.UUID] = []
        stack = [root_id]
        while stack:
            fid = stack.pop()
            ordered.append(fid)
            for child in children_by_parent.get(fid, []):
                stack.append(child.id)
        return ordered

    async def retry_parse(self, user_id: uuid.UUID, item_id: uuid.UUID) -> dict:
        row = await self._items.get_owned(user_id, item_id)
        if row is None:
            raise ValueError("Item not found")
        kind = classify_attachment(filename=row.filename, mime_type=row.mime_type)
        row = await finalize_hub_item_parse(self._db, row, kind=kind)
        await self._db.commit()
        await self._db.refresh(row)
        return hub_item_metadata(row)
