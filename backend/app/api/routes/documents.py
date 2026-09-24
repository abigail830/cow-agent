import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DocumentListOut, DocumentOut
from app.db.repositories.attachments import AttachmentRepository
from app.db.repositories.chat_ui_annotations import ChatUiAnnotationRepository
from app.platform.auth.current_user import get_current_user_id
from app.platform.documents.list_helpers import merge_document_pages
from app.platform.documents.out import artifact_document_out, attachment_document_out
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


async def _list_attachment_documents(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    q: str | None,
    parse_status: str | None,
    mime_type: str | None,
    agent_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[DocumentOut], int]:
    repo = AttachmentRepository(db)
    rows, total = await repo.list_for_user(
        user_id,
        q=q,
        parse_status=parse_status,
        mime_type=mime_type,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )
    items = [attachment_document_out(attachment, chat, agent) for attachment, chat, agent in rows]
    return items, total


async def _list_artifact_documents(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    q: str | None,
    agent_id: uuid.UUID | None,
    artifact_kind: str | None,
    limit: int,
    offset: int,
) -> tuple[list[DocumentOut], int]:
    repo = ChatUiAnnotationRepository(db)
    total = await repo.count_artifacts_for_user(
        user_id,
        q=q,
        agent_id=agent_id,
        artifact_kind=artifact_kind,
    )
    rows = await repo.list_artifacts_for_user(
        user_id,
        q=q,
        agent_id=agent_id,
        artifact_kind=artifact_kind,
        limit=limit,
        offset=offset,
    )
    items: list[DocumentOut] = []
    for row in rows:
        doc = artifact_document_out(row)
        if doc is not None:
            items.append(doc)
    return items, total


@router.get("", response_model=DocumentListOut)
async def list_documents(
    q: str | None = Query(default=None, max_length=200),
    parse_status: str | None = Query(default=None, max_length=32),
    mime_type: str | None = Query(default=None, max_length=128),
    agent_id: uuid.UUID | None = Query(default=None),
    source: Literal["all", "attachment", "artifact"] = Query(default="all"),
    artifact_kind: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentListOut:
    if source == "attachment":
        items, total = await _list_attachment_documents(
            db,
            user_id,
            q=q,
            parse_status=parse_status,
            mime_type=mime_type,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )
        return DocumentListOut(items=items, total=total)

    if source == "artifact":
        items, total = await _list_artifact_documents(
            db,
            user_id,
            q=q,
            agent_id=agent_id,
            artifact_kind=artifact_kind,
            limit=limit,
            offset=offset,
        )
        return DocumentListOut(items=items, total=total)

    fetch_n = limit + offset
    attachment_items, attachment_total = await _list_attachment_documents(
        db,
        user_id,
        q=q,
        parse_status=parse_status,
        mime_type=mime_type,
        agent_id=agent_id,
        limit=fetch_n,
        offset=0,
    )
    artifact_items, artifact_total = await _list_artifact_documents(
        db,
        user_id,
        q=q,
        agent_id=agent_id,
        artifact_kind=artifact_kind,
        limit=fetch_n,
        offset=0,
    )
    items = merge_document_pages(
        attachment_items,
        artifact_items,
        offset=offset,
        limit=limit,
    )
    return DocumentListOut(items=items, total=attachment_total + artifact_total)
