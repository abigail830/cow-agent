"""Internal parse-pipeline callbacks (GHA worker + webhooks). Not for browser use."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.platform.attachments.storage import load_inline_attachment
from app.platform.docstore.blob import save_parsed_artifact, save_parsed_figure
from app.platform.docstore.figures import load_parsed_figure_resolved, normalize_figure_id
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.job_builder import hash_run_token
from app.platform.parse_pipeline.repository import ParseJobRepository
from app.platform.parse_pipeline.status_report import report_parse_run_status
from app.platform.parse_pipeline.webhook import apply_webhook_event, verify_webhook_signature

router = APIRouter(prefix="/internal/parse/v1", tags=["parse-internal"])


class RunStatusBody(BaseModel):
    status: str = Field(description="failed | running | succeeded")
    error: dict[str, str] | None = None
    message: str | None = None


class AsrMintBody(BaseModel):
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)

_ARTIFACT_CONTENT_TYPES = {
    "content_md": "text/markdown; charset=utf-8",
    "meta_json": "application/json",
    "pageindex_json": "application/json",
}

_MIME_TO_EXT = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def _normalize_figure_id(raw: str) -> str:
    """Accept f1 or legacy f1.jpeg path segments; API route uses bare figure id."""
    try:
        return normalize_figure_id(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid figure_id") from exc


def _extension_from_content_type(content_type: str | None) -> str:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    ext = _MIME_TO_EXT.get(normalized)
    if ext is None:
        raise HTTPException(status_code=400, detail=f"unsupported figure content type: {content_type}")
    return ext


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return authorization.split(" ", 1)[1].strip()


@router.get("/run/{job_id}")
async def get_run_payload(
    job_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    row = await jobs.get_run_by_token_hash(job_id, hash_run_token(token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid or expired run token")
    return row.job_payload_json


@router.post("/run/{job_id}/status")
async def post_run_status(
    job_id: str,
    body: RunStatusBody,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    run_row = await jobs.get_run_by_token_hash(job_id, hash_run_token(token))
    if run_row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid or expired run token")

    status_norm = body.status.strip().lower()
    if status_norm == "failed":
        error = body.error or {}
        error_code = error.get("code") or "GHA_FAILED"
        error_message = error.get("message") or body.message or "Parse job failed"
        await report_parse_run_status(
            db,
            run_row=run_row,
            parse_status="failed",
            error_code=str(error_code),
            error_message=str(error_message),
            run_status="failed",
        )
    elif status_norm in {"running", "queued"}:
        await report_parse_run_status(
            db,
            run_row=run_row,
            parse_status="running",
            run_status=status_norm,
        )
    else:
        raise HTTPException(status_code=400, detail=f"unsupported status: {body.status}")

    await db.commit()
    return {"status": "ok"}


@router.get("/files/{attachment_id}/original")
async def get_original_file(
    attachment_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response

    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    row = await jobs.get_run_for_related_attachment_token(attachment_id, hash_run_token(token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    try:
        data = load_inline_attachment(row.chat_id, attachment_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="original not found") from exc
    return Response(content=data, media_type="application/octet-stream")


@router.put("/files/{attachment_id}/artifacts/{artifact_key}")
async def put_artifact(
    attachment_id: uuid.UUID,
    artifact_key: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if artifact_key not in _ARTIFACT_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported artifact: {artifact_key}")
    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    row = await jobs.get_run_for_related_attachment_token(attachment_id, hash_run_token(token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    data = await request.body()
    content_type = _ARTIFACT_CONTENT_TYPES[artifact_key]
    save_parsed_artifact(
        row.chat_id,
        attachment_id,
        artifact_key,
        data,
        content_type=content_type,
    )
    await DocstoreRepository(db).record_parsed_artifact(
        attachment_id,
        chat_id=row.chat_id,
        artifact_key=artifact_key,
        size_bytes=len(data),
        content_type=content_type,
    )
    from app.platform.audio_capture.webhook import maybe_finalize_capture_after_parsed_artifact

    await maybe_finalize_capture_after_parsed_artifact(
        db,
        attachment_id=attachment_id,
        artifact_key=artifact_key,
    )
    await db.commit()
    return {"status": "ok", "artifact": artifact_key}


@router.put("/files/{attachment_id}/figures/{figure_id}")
async def put_figure(
    attachment_id: uuid.UUID,
    figure_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    figure_id = _normalize_figure_id(figure_id)
    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    row = await jobs.get_run_for_attachment_token(attachment_id, hash_run_token(token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    content_type = request.headers.get("content-type")
    extension = _extension_from_content_type(content_type)
    data = await request.body()
    save_parsed_figure(
        row.chat_id,
        attachment_id,
        figure_id,
        extension,
        data,
        content_type=content_type or "application/octet-stream",
    )
    return {"status": "ok", "figure": figure_id, "extension": extension}


@router.get("/files/{attachment_id}/figures/{figure_id}")
async def get_figure(
    attachment_id: uuid.UUID,
    figure_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response

    figure_id = _normalize_figure_id(figure_id)
    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    row = await jobs.get_run_for_attachment_token(attachment_id, hash_run_token(token))
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    try:
        data, media_type = load_parsed_figure_resolved(row.chat_id, attachment_id, figure_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid figure_id") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="figure not found") from exc
    return Response(content=data, media_type=media_type)


@router.post("/run/{job_id}/asr-files/mint")
async def mint_asr_files(
    job_id: str,
    body: AsrMintBody,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.platform.audio_capture.signed_urls import mint_asr_download_url

    token = _extract_bearer(authorization)
    jobs = ParseJobRepository(db)
    run_row = await jobs.get_run_by_token_hash(job_id, hash_run_token(token))
    if run_row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    urls: list[dict[str, str | int]] = []
    for attachment_id in body.attachment_ids:
        if not jobs.payload_allows_attachment(run_row, attachment_id):
            raise HTTPException(status_code=403, detail=f"attachment not in job: {attachment_id}")
        download_url, expires_at = mint_asr_download_url(
            chat_id=run_row.chat_id,
            attachment_id=attachment_id,
        )
        urls.append(
            {
                "attachment_id": str(attachment_id),
                "url": download_url,
                "expires_at": expires_at,
            }
        )
    return {"urls": urls}


@router.post("/webhook")
async def parse_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_parse_webhook_id: str | None = Header(default=None, alias="X-Parse-Webhook-Id"),
    x_parse_timestamp: str | None = Header(default=None, alias="X-Parse-Timestamp"),
    x_parse_signature: str | None = Header(default=None, alias="X-Parse-Signature"),
) -> dict[str, str]:
    body = await request.body()
    if not x_parse_webhook_id or not x_parse_timestamp:
        raise HTTPException(status_code=400, detail="missing webhook headers")

    import json

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc

    job_id = str(payload.get("job_id") or "")
    if not job_id:
        raise HTTPException(status_code=400, detail="missing job_id")

    jobs = ParseJobRepository(db)
    run_row = await jobs.get_run(job_id)
    if run_row is None:
        raise HTTPException(status_code=404, detail="unknown job")

    if not verify_webhook_signature(
        secret=run_row.webhook_secret,
        timestamp=x_parse_timestamp,
        body=body,
        signature_header=x_parse_signature,
    ):
        raise HTTPException(status_code=401, detail="invalid signature")

    result = await apply_webhook_event(
        db,
        event_id=x_parse_webhook_id,
        body=body,
        run_row=run_row,
    )
    await db.commit()
    if result is None:
        return {"status": "duplicate"}
    return {"status": "ok"}
