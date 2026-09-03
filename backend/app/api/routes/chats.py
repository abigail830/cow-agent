import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AttachmentOut,
    ChatCreate,
    ChatListOut,
    ChatOut,
    MessageCreate,
    MessageOut,
    ProposalDraftOut,
    ProposalExportOut,
    ProposalExportRequest,
    ProposalPreviewOut,
    FulfillmentFormOut,
    FulfillmentFormPatchIn,
    FulfillmentFormsOut,
)
from app.db.models import AgentModel, Chat
from app.platform.current_user import get_current_user, get_current_user_id, get_owned_chat
from app.db.session import get_db
from app.services.attachment_service import AttachmentService
from app.services.chat_run import ChatRunService, list_chat_messages
from app.services.stream_errors import user_facing_stream_error
from app.services.proposal_preview_service import get_chat_proposal_draft, get_chat_proposal_preview, load_chat_proposal_draft
from app.services.fulfillment_forms_service import (
    confirm_chat_fulfillment_form,
    get_chat_fulfillment_forms,
    patch_chat_fulfillment_form,
    reject_chat_fulfillment_form,
)
from app.proposal.export_service import ProposalExportError, generate_proposal_docx
from app.artifacts.resolver import load_artifact_payload, load_preview_payload
from app.artifacts.storage import get_chat_artifact_format
from app.artifacts.preview_html import SLIDE_PREVIEW_CSP, prepare_html_ppt_preview_html, prepare_slide_preview_html

router = APIRouter(prefix="/chats", tags=["chats"])


def _chat_list_out(chat: Chat) -> ChatListOut:
    return ChatListOut(
        id=chat.id,
        agent_id=chat.agent_id,
        title=chat.title,
        created_at=chat.created_at.isoformat() if chat.created_at else None,
        updated_at=chat.updated_at.isoformat() if chat.updated_at else None,
    )


@router.get("", response_model=list[ChatListOut])
async def list_chats(
    agent_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[ChatListOut]:
    result = await db.execute(
        select(Chat)
        .where(
            Chat.user_id == user_id,
            Chat.agent_id == agent_id,
        )
        .order_by(Chat.updated_at.desc())
        .limit(50)
    )
    return [_chat_list_out(c) for c in result.scalars().all()]


@router.post("", response_model=ChatOut, status_code=201)
async def create_chat(
    body: ChatCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    agent = await db.get(AgentModel, body.agent_id)
    if agent is None or agent.slug is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    chat = Chat(
        user_id=user_id,
        agent_id=body.agent_id,
        title=body.title or "New Chat",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return ChatOut(id=chat.id, user_id=chat.user_id, agent_id=chat.agent_id, title=chat.title)


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    rows = await list_chat_messages(db, chat.id)
    return [MessageOut(**row) for row in rows]


@router.get("/{chat_id}/proposal/preview", response_model=ProposalPreviewOut)
async def get_proposal_preview(
    chat: Chat = Depends(get_owned_chat),
    draft: bool = True,
    db: AsyncSession = Depends(get_db),
) -> ProposalPreviewOut:
    try:
        payload = await get_chat_proposal_preview(db, chat.id, draft=draft)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProposalPreviewOut(**payload)


@router.get("/{chat_id}/proposal/draft", response_model=ProposalDraftOut)
async def get_proposal_draft(
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> ProposalDraftOut:
    try:
        payload = await get_chat_proposal_draft(db, chat.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProposalDraftOut(**payload)


@router.get("/{chat_id}/fulfillment/forms", response_model=FulfillmentFormsOut)
async def get_fulfillment_forms(
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentFormsOut:
    try:
        payload = await get_chat_fulfillment_forms(db, chat.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FulfillmentFormsOut(**payload)


@router.patch("/{chat_id}/fulfillment/forms/{form_id}", response_model=FulfillmentFormOut)
async def patch_fulfillment_form(
    form_id: str,
    body: FulfillmentFormPatchIn,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentFormOut:
    try:
        result = await patch_chat_fulfillment_form(db, chat.id, form_id, body.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FulfillmentFormOut(status="updated", form=result["form"])


@router.post("/{chat_id}/fulfillment/forms/{form_id}/confirm", response_model=FulfillmentFormOut)
async def confirm_fulfillment_form(
    form_id: str,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentFormOut:
    try:
        result = await confirm_chat_fulfillment_form(db, chat.id, form_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FulfillmentFormOut(
        status=result["status"],
        form=result["form"],
        fulfillment_item=result.get("fulfillment_item"),
    )


@router.post("/{chat_id}/fulfillment/forms/{form_id}/reject", response_model=FulfillmentFormOut)
async def reject_fulfillment_form(
    form_id: str,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentFormOut:
    try:
        result = await reject_chat_fulfillment_form(db, chat.id, form_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FulfillmentFormOut(status=result["status"], form=result["form"])


@router.post("/{chat_id}/proposal/export", response_model=ProposalExportOut)
async def export_proposal(
    body: ProposalExportRequest,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> ProposalExportOut:
    if body.format != "docx":
        raise HTTPException(status_code=422, detail="Only format=docx is supported.")
    try:
        draft = await load_chat_proposal_draft(db, chat.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not draft:
        raise HTTPException(status_code=422, detail="Proposal draft is not initialized.")
    try:
        payload = generate_proposal_docx(draft, chat_id=chat.id, force=body.force, persist=True)
    except ProposalExportError as exc:
        detail: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.code == "blocked":
            from app.proposal.draft import build_draft_preview

            preview = build_draft_preview(draft)
            detail["missing_required"] = (preview.get("completeness") or {}).get("missing_required") or []
        raise HTTPException(status_code=exc.http_status, detail=detail) from exc
    return ProposalExportOut(**payload)


@router.get("/{chat_id}/artifacts/{artifact_id}")
async def download_artifact(
    artifact_id: str,
    chat: Chat = Depends(get_owned_chat),
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _ = db
    variant = format.strip().lower() if format else None
    payload = load_artifact_payload(chat.id, artifact_id, variant=variant)
    if payload is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return StreamingResponse(
        iter([payload.data]),
        media_type=payload.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{payload.filename}"',
        },
    )


@router.get("/{chat_id}/artifacts/{artifact_id}/preview")
@router.get("/{chat_id}/artifacts/{artifact_id}/preview/")
async def preview_artifact_index(
    artifact_id: str,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    return await preview_artifact(artifact_id, "index.html", chat, db)


@router.get("/{chat_id}/artifacts/{artifact_id}/preview/{file_path:path}")
async def preview_artifact(
    artifact_id: str,
    file_path: str,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _ = db
    payload = load_preview_payload(chat.id, artifact_id, file_path)
    if payload is None:
        raise HTTPException(status_code=404, detail="Preview file not found")
    data = payload.data
    headers: dict[str, str] = {}
    if payload.media_type.startswith("text/html"):
        base_href = f"/api/v1/chats/{chat.id}/artifacts/{artifact_id}/preview/"
        deck_format = get_chat_artifact_format(chat.id, artifact_id)
        if deck_format == "html":
            data = prepare_html_ppt_preview_html(data, base_href=base_href)
        else:
            data = prepare_slide_preview_html(data, base_href=base_href)
        headers["Content-Security-Policy"] = SLIDE_PREVIEW_CSP
    return StreamingResponse(
        iter([data]),
        media_type=payload.media_type,
        headers=headers,
    )


@router.post("/{chat_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> AttachmentOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    service = AttachmentService(db)
    try:
        payload = await service.upload(
            chat.id,
            filename=file.filename,
            mime_type=mime_type,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"File upload failed: {exc}") from exc

    return AttachmentOut(
        id=uuid.UUID(payload["id"]),
        chat_id=chat.id,
        filename=payload["filename"],
        mime_type=payload["mime_type"],
        size_bytes=payload["size_bytes"],
        provider=payload["provider"],
        provider_file_id=payload["provider_file_id"],
        created_at=None,
    )


@router.post("/{chat_id}/messages")
async def post_message(
    body: MessageCreate,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatRunService(db)
    try:
        text = await service.run_message(
            chat.id,
            body.content,
            attachment_ids=body.attachment_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"chat_id": str(chat.id), "text": text}


@router.post("/{chat_id}/stream")
async def stream_message(
    body: MessageCreate,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    service = ChatRunService(db)

    def _stream_error_message(exc: Exception) -> str:
        return user_facing_stream_error(exc)

    async def event_generator():
        try:
            async for event in service.stream_message(
                chat.id,
                body.content,
                attachment_ids=body.attachment_ids,
            ):
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except ValueError as exc:
            payload = {"error": str(exc)}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            payload = {"error": _stream_error_message(exc)}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
