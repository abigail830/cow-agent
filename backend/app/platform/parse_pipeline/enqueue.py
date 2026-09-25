from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ChatAttachment
from app.platform.docstore.models import ParseStatus
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.dispatcher import dispatch_gha
from app.platform.parse_pipeline.dispatcher_service import dispatch_service
from app.platform.parse_pipeline.gha_watch import schedule_gha_run_watch
from app.platform.parse_pipeline.inline_runner import schedule_inline_job
from app.platform.parse_pipeline.job_builder import (
    build_job_payload,
    hash_run_token,
    new_job_id,
    new_webhook_secret,
    run_expires_at,
)
from app.platform.parse_pipeline.notify import notify_attachment_parse_updated
from app.platform.parse_pipeline.repository import ParseJobRepository

logger = logging.getLogger(__name__)


def _resolve_dispatch_mode() -> str:
    settings = get_settings()
    mode = (settings.parse_pipeline_dispatch or "auto").strip().lower()
    if mode != "auto":
        return mode
    if (settings.github_token or "").strip() and (settings.github_repo or "").strip():
        return "gha"
    return "service"


def _require_platform_base_url(*, mode: str) -> str:
    settings = get_settings()
    public_base = (settings.parse_pipeline_public_base_url or "").strip()
    if not public_base:
        raise RuntimeError(
            f"PARSE_PIPELINE_PUBLIC_BASE_URL is required for {mode} dispatch "
            "(backend URL reachable by parse-pipeline for file I/O + webhooks)"
        )
    return public_base


async def enqueue_parse_job(
    session: AsyncSession,
    row: ChatAttachment,
    *,
    pipeline_id: str,
    job_payload: dict | None = None,
    run_token: str | None = None,
) -> ChatAttachment:
    settings = get_settings()
    job_id = new_job_id()
    webhook_secret = new_webhook_secret()
    dispatch_mode = _resolve_dispatch_mode()

    use_internal_http = dispatch_mode in {"service", "gha"}

    if use_internal_http:
        _require_platform_base_url(mode=dispatch_mode)

    if dispatch_mode == "inline":
        logger.warning(
            "PARSE_PIPELINE_DISPATCH=inline is deprecated; prefer service (HTTP + webhook). "
            "See backend/scripts/setup_parse_inline.sh"
        )

    if job_payload is None:
        payload, resolved_run_token = build_job_payload(
            row,
            pipeline_id=pipeline_id,
            job_id=job_id,
            webhook_secret=webhook_secret,
            use_internal_http=use_internal_http,
        )
    else:
        payload = dict(job_payload)
        payload["job_id"] = job_id
        payload.setdefault("callbacks", {})["webhook_secret"] = webhook_secret
        auth_header = (
            ((payload.get("storage") or {}).get("read") or {}).get("headers") or {}
        ).get("Authorization", "")
        resolved_run_token = run_token or (
            auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else ""
        )
        if not resolved_run_token:
            raise ValueError("run_token is required when submitting a prebuilt job payload")
    run_token = resolved_run_token

    jobs = ParseJobRepository(session)
    await jobs.create_run(
        job_id=job_id,
        attachment_id=row.id,
        chat_id=row.chat_id,
        run_token_hash=hash_run_token(run_token),
        webhook_secret=webhook_secret,
        expires_at=run_expires_at(),
        job_payload_json=payload,
    )

    docstore = DocstoreRepository(session)
    updated = await docstore.mark_parse_pending(row.id, pipeline_id=pipeline_id, job_id=job_id)
    assert updated is not None

    try:
        if dispatch_mode == "gha":
            await dispatch_gha(job_id=job_id, run_token=run_token, pipeline_id=pipeline_id)
            schedule_gha_run_watch(job_id=job_id)
        elif dispatch_mode == "service":
            await dispatch_service(payload=payload)
        else:
            schedule_inline_job(payload)
    except Exception as exc:
        logger.exception("parse dispatch failed job_id=%s mode=%s", job_id, dispatch_mode)
        await docstore.apply_parse_webhook(
            row.id,
            status="failed",
            stage_snapshot=None,
            error_code="DISPATCH_FAILED",
            error_message=str(exc),
        )
        raise

    dispatch_message = {
        "gha": "Dispatched to GitHub Actions — waiting for worker to start…",
        "service": "Parse service accepted job — waiting for worker…",
        "inline": "Parse worker started (legacy inline subprocess)…",
    }.get(dispatch_mode, "Parse worker started…")

    await notify_attachment_parse_updated(
        session,
        updated.id,
        parse_status=ParseStatus.RUNNING.value,
        stage_snapshot={
            "current_stage": "fetch",
            "message": dispatch_message,
            "stages": [],
        },
    )

    return updated
