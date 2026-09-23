from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db.models import ChatAttachment, ParseJobRun
from app.db.session import get_async_session_factory
from app.platform.docstore.models import ParseStatus
from app.platform.parse_pipeline.repository import ParseJobRepository
from app.platform.parse_pipeline.status_report import report_parse_run_status

logger = logging.getLogger(__name__)

_ACTIVE_RUN_STATUSES = frozenset({"queued", "running"})
_ACTIVE_PARSE_STATUSES = frozenset({ParseStatus.PENDING.value, ParseStatus.RUNNING.value})


async def sweep_stale_parse_jobs() -> int:
    """Mark expired / long-running parse jobs as failed. Returns rows updated."""

    settings = get_settings()
    stale_sec = max(300, int(settings.parse_pipeline_job_stale_sec))
    now = datetime.now(timezone.utc)
    updated = 0

    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ParseJobRun).where(ParseJobRun.status.in_(_ACTIVE_RUN_STATUSES))
        )
        runs = list(result.scalars().all())
        for run_row in runs:
            exp = run_row.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            created = run_row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_sec = (now - created).total_seconds()
            expired = exp < now or age_sec > stale_sec
            if not expired:
                continue

            attachment = await session.get(ChatAttachment, run_row.attachment_id)
            if attachment is None:
                continue
            if str(attachment.parse_status) not in _ACTIVE_PARSE_STATUSES:
                await ParseJobRepository(session).update_run_status(run_row.job_id, "failed")
                continue

            message = "Parse job timed out waiting for worker completion"
            if exp < now:
                message = "Parse run token expired before job completed"
            await report_parse_run_status(
                session,
                run_row=run_row,
                parse_status=ParseStatus.FAILED.value,
                error_code="PARSE_TIMEOUT",
                error_message=message,
                run_status="failed",
            )
            updated += 1

        if updated:
            await session.commit()
    if updated:
        logger.info("stale parse sweep marked %d job(s) failed", updated)
    return updated


async def run_stale_parse_job_sweep_loop() -> None:
    settings = get_settings()
    interval = max(60, int(settings.parse_pipeline_stale_sweep_interval_sec))
    while True:
        try:
            await sweep_stale_parse_jobs()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("stale parse job sweep failed")
        await asyncio.sleep(interval)
