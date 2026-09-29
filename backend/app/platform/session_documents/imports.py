"""Session document import list (chat-scoped @ and doc_retrieval boundary)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, ChatAttachment, HubItem
from app.db.repositories.chat_document_imports import ChatDocumentImportRepository
from app.db.repositories.hub_items import HubItemRepository
from app.platform.docstore.manifest import parsed_artifact_in_manifest


async def auto_import_chat_attachment(
    session: AsyncSession,
    *,
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    repo = ChatDocumentImportRepository(session)
    await repo.upsert(
        chat_id=chat_id,
        source="chat_attachment",
        ref_id=attachment_id,
        imported_by_user_id=user_id,
    )


async def import_hub_items(
    session: AsyncSession,
    *,
    chat: Chat,
    hub_item_ids: list[uuid.UUID],
) -> list[dict]:
    hub_repo = HubItemRepository(session)
    import_repo = ChatDocumentImportRepository(session)
    out: list[dict] = []
    for item_id in hub_item_ids:
        item = await hub_repo.get_owned(chat.user_id, item_id)
        if item is None:
            raise ValueError(f"Hub item not found: {item_id}")
        if item.attachment_role == "audio_part":
            continue
        imp = await import_repo.upsert(
            chat_id=chat.id,
            source="hub_item",
            ref_id=item.id,
            imported_by_user_id=chat.user_id,
        )
        out.append(
            {
                "import_id": str(imp.id),
                "source": imp.source,
                "ref_id": str(imp.ref_id),
                "filename": item.filename,
                "parse_status": item.parse_status,
            }
        )
    return out


async def lazy_backfill_chat_imports(session: AsyncSession, chat: Chat) -> None:
    """One-time: import attachments already linked to messages in this chat."""
    from sqlalchemy import select

    from app.db.models import ChatAttachment

    import_repo = ChatDocumentImportRepository(session)
    existing = await import_repo.list_for_chat(chat.id)
    if existing:
        return
    result = await session.execute(
        select(ChatAttachment.id).where(
            ChatAttachment.chat_id == chat.id,
            ChatAttachment.message_id.isnot(None),
        )
    )
    for att_id in result.scalars():
        await import_repo.upsert(
            chat_id=chat.id,
            source="chat_attachment",
            ref_id=att_id,
            imported_by_user_id=chat.user_id,
        )


def hub_item_importable(item: HubItem) -> bool:
    if item.attachment_role == "audio_part":
        return False
    if item.attachment_role == "transcript_host":
        return parsed_artifact_in_manifest(item.parsed_artifact_manifest, "content_md")
    return True
