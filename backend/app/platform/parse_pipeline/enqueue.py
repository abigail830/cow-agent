from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.dispatcher import dispatch_gha
from app.platform.parse_pipeline.inline_runner import schedule_inline_job
from app.platform.parse_pipeline.job_builder import (
    build_job_payload,
    hash_run_token,
    new_job_id,
    new_webhook_secret,
    run_expires_at,
)
from app.platform.parse_pipeline.repository import ParseJobRepository
from app.config import get_settings

logger = logging.getLogger(__name__)


async def enqueue_parse_job(
    session: AsyncSession,
    row: ChatAttachment,
    *,
    pipeline_id: str,
) -> ChatAttachment:
    settings = get_settings()
    job_id = new_job_id()
    webhook_secret = new_webhook_secret()
    dispatch_mode = (settings.parse_pipeline_dispatch or "auto").strip().lower()

    use_file_urls = dispatch_mode == "inline"
    if dispatch_mode == "auto":
        use_file_urls = not (settings.github_token and settings.github_repo)

    payload, run_token = build_job_payload(
        row,
        pipeline_id=pipeline_id,
        job_id=job_id,
        webhook_secret=webhook_secret,
        use_file_urls=use_file_urls,
    )

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

    effective_mode = "inline" if use_file_urls else "gha"
    try:
        if effective_mode == "gha":
            await dispatch_gha(job_id=job_id, run_token=run_token, pipeline_id=pipeline_id)
        else:
            schedule_inline_job(payload)
    except Exception as exc:
        logger.exception("parse dispatch failed job_id=%s", job_id)
        await docstore.apply_parse_webhook(
            row.id,
            status="failed",
            stage_snapshot=None,
            error_code="DISPATCH_FAILED",
            error_message=str(exc),
        )
        raise

    return updated
