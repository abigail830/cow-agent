"""Document Hub — user library folders, uploads, previews."""

from __future__ import annotations

import uuid

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HubFolder, HubItem
from app.db.repositories.chat_document_imports import ChatDocumentImportRepository
from app.db.repositories.hub_folders import HubFolderRepository
from app.db.repositories.hub_items import HubItemRepository
from app.db.session import get_db
from app.platform.auth.current_user import get_current_user_id, get_owned_chat
from app.platform.docstore.blob import load_parsed_artifact_scoped
from app.platform.docstore.content_types import parsed_artifact_media_type
from app.platform.docstore.figures import load_parsed_figure_scoped_resolved, normalize_figure_id
from app.platform.docstore.scope import DocumentScope
from app.config import get_settings
from app.platform.attachments.limits import attachment_limits
from app.platform.document_hub.blob_upload import handle_hub_blob_upload_request, hub_upload_mode
from app.platform.document_hub.metadata import hub_item_metadata
from app.platform.document_hub.service import DocumentHubService
from app.platform.document_hub.storage import load_hub_original
from app.platform.session_documents.imports import import_hub_items

router = APIRouter(prefix="/document-hub", tags=["document-hub"])


class HubFolderOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    sort_order: int


class HubFolderCreateIn(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class HubFolderRenameIn(BaseModel):
    name: str


class HubItemOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    item_kind: str
    filename: str
    mime_type: str
    size_bytes: int
    parse_status: str
    parse_pipeline_id: str | None = None
    parse_job_id: str | None = None
    parse_error_message: str | None = None
    parse_stage_snapshot: dict | None = None
    content_hash: str | None = None
    duplicate_of_existing: bool = False
    file_count: int = 1


class HubUploadConfigOut(BaseModel):
    mode: str
    max_bytes_per_file: int
    blob_upload_url: str | None = None
    blob_access: str | None = None


class HubPrepareUploadIn(BaseModel):
    folder_id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int


class HubPrepareUploadOut(BaseModel):
    item_id: uuid.UUID
    user_id: uuid.UUID
    pathname: str
    upload_mode: str


class HubCompleteUploadIn(BaseModel):
    size_bytes: int


class HubItemMoveIn(BaseModel):
    folder_id: uuid.UUID


class HubImportBatchIn(BaseModel):
    hub_item_ids: list[uuid.UUID] = Field(default_factory=list)


class ChatDocumentImportOut(BaseModel):
    id: uuid.UUID
    source: str
    ref_id: uuid.UUID
    filename: str | None = None
    parse_status: str | None = None
    imported_at: str | None = None


def _folder_out(row: HubFolder) -> HubFolderOut:
    return HubFolderOut(
        id=row.id,
        parent_id=row.parent_id,
        name=row.name,
        sort_order=row.sort_order,
    )


def _item_out(row: HubItem, *, file_count: int = 1, duplicate: bool = False) -> HubItemOut:
    return HubItemOut(
        id=row.id,
        folder_id=row.folder_id,
        item_kind=row.item_kind,
        filename=row.filename,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        parse_status=row.parse_status,
        parse_pipeline_id=row.parse_pipeline_id,
        parse_job_id=row.parse_job_id,
        parse_error_message=row.parse_error_message,
        parse_stage_snapshot=row.parse_stage_snapshot,
        content_hash=row.content_hash,
        duplicate_of_existing=duplicate,
        file_count=file_count,
    )


@router.get("/folders", response_model=list[HubFolderOut])
async def list_folders(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[HubFolderOut]:
    rows = await HubFolderRepository(db).list_for_user(user_id)
    return [_folder_out(row) for row in rows]


@router.post("/folders", response_model=HubFolderOut, status_code=201)
async def create_folder(
    payload: HubFolderCreateIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubFolderOut:
    repo = HubFolderRepository(db)
    if payload.parent_id is not None:
        parent = await repo.get_owned(user_id, payload.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    row = await repo.create(user_id=user_id, name=payload.name, parent_id=payload.parent_id)
    await db.commit()
    return _folder_out(row)


@router.patch("/folders/{folder_id}", response_model=HubFolderOut)
async def rename_folder(
    folder_id: uuid.UUID,
    payload: HubFolderRenameIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubFolderOut:
    repo = HubFolderRepository(db)
    row = await repo.get_owned(user_id, folder_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    row = await repo.rename(row, payload.name)
    await db.commit()
    return _folder_out(row)


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    confirm_name: str = Query(..., min_length=1, description="Must match folder name (prevents wrong-id deletes)"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = HubFolderRepository(db)
    row = await repo.get_owned(user_id, folder_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if row.name.strip() != confirm_name.strip():
        raise HTTPException(
            status_code=409,
            detail=f"Folder name does not match this id (id is «{row.name}», you sent «{confirm_name.strip()}»)",
        )
    service = DocumentHubService(db)
    try:
        await service.delete_folder_cascade(user_id, folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()


@router.get("/upload-config", response_model=HubUploadConfigOut)
async def get_hub_upload_config(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> HubUploadConfigOut:
    settings = get_settings()
    mode = hub_upload_mode()
    _, max_file_bytes, _, _, _ = attachment_limits(settings)
    blob_upload_url = "/document-hub/blob-upload" if mode == "blob" else None
    blob_access = settings.blob_access if mode == "blob" else None
    return HubUploadConfigOut(
        mode=mode,
        max_bytes_per_file=max_file_bytes,
        blob_upload_url=blob_upload_url,
        blob_access=blob_access,
    )


@router.post("/blob-upload")
async def create_hub_blob_upload(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> dict:
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    try:
        return handle_hub_blob_upload_request(user_id=user_id, body=body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/items/prepare-upload", response_model=HubPrepareUploadOut, status_code=201)
async def prepare_hub_upload(
    payload: HubPrepareUploadIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubPrepareUploadOut:
    service = DocumentHubService(db)
    try:
        meta = await service.prepare_client_upload(
            user_id,
            payload.folder_id,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return HubPrepareUploadOut(
        item_id=uuid.UUID(meta["item_id"]),
        user_id=user_id,
        pathname=meta["pathname"],
        upload_mode=meta["upload_mode"],
    )


@router.post("/items/{item_id}/complete-upload", response_model=HubItemOut)
async def complete_hub_upload(
    item_id: uuid.UUID,
    payload: HubCompleteUploadIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubItemOut:
    service = DocumentHubService(db)
    try:
        await service.complete_client_upload(
            user_id,
            item_id,
            size_bytes=payload.size_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = await HubItemRepository(db).get_owned(user_id, item_id)
    assert row is not None
    return _item_out(row)


@router.get("/items", response_model=list[HubItemOut])
async def list_items(
    folder_id: uuid.UUID,
    q: str | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[HubItemOut]:
    folders = HubFolderRepository(db)
    if await folders.get_owned(user_id, folder_id) is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    items = HubItemRepository(db)
    rows = await items.list_folder_items(user_id, folder_id, q=q)
    from app.platform.document_hub.parse_status import reconcile_hub_item_parse_status

    out: list[HubItemOut] = []
    status_changed = False
    for row in rows:
        prev_status = row.parse_status
        row = await reconcile_hub_item_parse_status(db, row)
        if row.parse_status != prev_status:
            status_changed = True
        file_count = 1
        if row.item_kind == "audio_capture" and row.capture_id:
            file_count = await items.count_parts(row.capture_id)
        out.append(_item_out(row, file_count=file_count))
    if status_changed:
        await db.commit()
    return out


@router.post("/captures", response_model=HubItemOut, status_code=201)
async def create_audio_capture(
    folder_id: uuid.UUID = Form(...),
    title: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubItemOut:
    from app.platform.document_hub.hub_audio_capture import create_hub_audio_capture

    folders = HubFolderRepository(db)
    if await folders.get_owned(user_id, folder_id) is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    parts: list[tuple[str, str, bytes]] = []
    for upload in files:
        parts.append(
            (
                upload.filename or "audio.m4a",
                upload.content_type or "audio/m4a",
                await upload.read(),
            )
        )
    try:
        row = await create_hub_audio_capture(
            db,
            user_id=user_id,
            folder_id=folder_id,
            title=title,
            parts=parts,
        )
        await db.commit()
        await db.refresh(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    file_count = await HubItemRepository(db).count_parts(row.capture_id) if row.capture_id else 1
    return _item_out(row, file_count=file_count)


@router.post("/items/upload", response_model=HubItemOut, status_code=201)
async def upload_item(
    folder_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubItemOut:
    data = await file.read()
    filename = file.filename or "upload.bin"
    mime_type = file.content_type or "application/octet-stream"
    service = DocumentHubService(db)
    try:
        meta = await service.upload_file(
            user_id,
            folder_id,
            filename=filename,
            mime_type=mime_type,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = await HubItemRepository(db).get(uuid.UUID(meta["id"]))
    assert row is not None
    return _item_out(row, duplicate=bool(meta.get("duplicate_of_existing")))


@router.get("/items/{item_id}", response_model=HubItemOut)
async def get_item(
    item_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubItemOut:
    row = await HubItemRepository(db).get_owned(user_id, item_id)
    if row is None or row.attachment_role == "audio_part":
        raise HTTPException(status_code=404, detail="Item not found")
    file_count = 1
    if row.capture_id:
        file_count = await HubItemRepository(db).count_parts(row.capture_id)
    return _item_out(row, file_count=file_count)


@router.patch("/items/{item_id}", response_model=HubItemOut)
async def move_item(
    item_id: uuid.UUID,
    payload: HubItemMoveIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubItemOut:
    service = DocumentHubService(db)
    try:
        row = await service.move_item(user_id, item_id, folder_id=payload.folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    file_count = 1
    if row.capture_id:
        file_count = await HubItemRepository(db).count_parts(row.capture_id)
    return _item_out(row, file_count=file_count)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = DocumentHubService(db)
    try:
        await service.delete_item(user_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()


@router.post("/items/{item_id}/retry-parse", response_model=HubItemOut)
async def retry_item_parse(
    item_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HubItemOut:
    service = DocumentHubService(db)
    try:
        await service.retry_parse(user_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    row = await HubItemRepository(db).get_owned(user_id, item_id)
    assert row is not None
    return _item_out(row)


@router.get("/items/{item_id}/original")
async def download_original(
    item_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await HubItemRepository(db).get_owned(user_id, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    try:
        data = load_hub_original(user_id, item_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Original not found") from exc
    return Response(content=data, media_type=row.mime_type or "application/octet-stream")


@router.get("/items/{item_id}/parsed/{artifact_key}")
async def download_parsed(
    item_id: uuid.UUID,
    artifact_key: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await HubItemRepository(db).get_owned(user_id, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    scope = DocumentScope.hub(user_id, item_id)
    try:
        data = load_parsed_artifact_scoped(scope, artifact_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    return Response(content=data, media_type=parsed_artifact_media_type(artifact_key))


@router.get("/items/{item_id}/parsed/figures/{figure_id}")
async def download_parsed_figure(
    item_id: uuid.UUID,
    figure_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await HubItemRepository(db).get_owned(user_id, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    try:
        normalized_figure_id = normalize_figure_id(figure_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid figure id") from exc
    scope = DocumentScope.hub(user_id, item_id)
    try:
        data, media_type = load_parsed_figure_scoped_resolved(scope, normalized_figure_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Figure not found") from exc
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Length": str(len(data)),
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/chats/{chat_id}/imports", response_model=list[ChatDocumentImportOut])
async def import_to_chat(
    chat_id: uuid.UUID,
    payload: HubImportBatchIn,
    chat=Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> list[ChatDocumentImportOut]:
    if chat.id != chat_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    try:
        rows = await import_hub_items(db, chat=chat, hub_item_ids=payload.hub_item_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return [
        ChatDocumentImportOut(
            id=uuid.UUID(r["import_id"]),
            source="hub_item",
            ref_id=uuid.UUID(r["ref_id"]),
            filename=r.get("filename"),
            parse_status=r.get("parse_status"),
        )
        for r in rows
    ]


@router.get("/chats/{chat_id}/imports", response_model=list[ChatDocumentImportOut])
async def list_chat_imports(
    chat_id: uuid.UUID,
    chat=Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> list[ChatDocumentImportOut]:
    if chat.id != chat_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    import_repo = ChatDocumentImportRepository(db)
    att_repo = HubItemRepository(db)
    from app.db.repositories.attachments import AttachmentRepository

    chat_att = AttachmentRepository(db)
    imports = await import_repo.list_for_chat(chat_id)
    out: list[ChatDocumentImportOut] = []
    for imp in imports:
        filename = None
        parse_status = None
        if imp.source == "hub_item":
            item = await att_repo.get(imp.ref_id)
            if item:
                filename = item.filename
                parse_status = item.parse_status
        else:
            att = await chat_att.get(imp.ref_id)
            if att:
                filename = att.filename
                parse_status = att.parse_status
        out.append(
            ChatDocumentImportOut(
                id=imp.id,
                source=imp.source,
                ref_id=imp.ref_id,
                filename=filename,
                parse_status=parse_status,
                imported_at=imp.imported_at.isoformat() if imp.imported_at else None,
            )
        )
    return out


@router.delete("/chats/{chat_id}/imports/{import_id}", status_code=204)
async def remove_chat_import(
    chat_id: uuid.UUID,
    import_id: uuid.UUID,
    chat=Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> None:
    if chat.id != chat_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    import_repo = ChatDocumentImportRepository(db)
    rows = await import_repo.list_for_chat(chat_id)
    target = next((r for r in rows if r.id == import_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Import not found")
    await import_repo.delete(target)
    await db.commit()
