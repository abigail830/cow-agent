import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DocumentListOut, DocumentOut, ParsedArtifactsOut
from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.api_out import attachment_out
from app.platform.attachments.metadata import attachment_metadata
from app.platform.auth.current_user import get_current_user_id
from app.platform.docstore.availability import parsed_artifacts_availability
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListOut)
async def list_documents(
    q: str | None = Query(default=None, max_length=200),
    parse_status: str | None = Query(default=None, max_length=32),
    mime_type: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentListOut:
    repo = AttachmentRepository(db)
    rows, total = await repo.list_for_user(
        user_id,
        q=q,
        parse_status=parse_status,
        mime_type=mime_type,
        limit=limit,
        offset=offset,
    )
    items: list[DocumentOut] = []
    for attachment, chat in rows:
        payload = attachment_metadata(attachment)
        if attachment.created_at is not None:
            payload["created_at"] = attachment.created_at.isoformat()
        base = attachment_out(attachment.chat_id, payload)
        artifacts = ParsedArtifactsOut()
        if base.parse_status == "ready":
            flags = parsed_artifacts_availability(attachment.chat_id, attachment.id)
            artifacts = ParsedArtifactsOut(**flags)
        items.append(
            DocumentOut(
                **base.model_dump(),
                chat_title=chat.title,
                has_parsed_content=artifacts.content_md,
                parsed_artifacts=artifacts,
            )
        )
    return DocumentListOut(items=items, total=total)
