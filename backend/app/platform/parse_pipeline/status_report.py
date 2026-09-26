from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.docstore.models import ParseStatus
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.events import publish_attachment_parse_updated
from app.platform.parse_pipeline.repository import ParseJobRepository

logger = logging.getLogger(__name__)


def _snapshot_from_row(row) -> dict[str, Any] | None:
    raw = getattr(row, "parse_stage_snapshot", None)
    return raw if isinstance(raw, dict) else None


async def report_parse_run_status(
    session: AsyncSession,
    *,
    run_row,
    parse_status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    stage_snapshot: dict[str, Any] | None = None,
    run_status: str | None = None,
) -> dict[str, Any] | None:
    """Apply terminal/intermediate parse status and fan out SSE."""

    if parse_status not in {s.value for s in ParseStatus}:
        raise ValueError(f"invalid parse_status: {parse_status}")

    jobs = ParseJobRepository(session)
    docstore = DocstoreRepository(session)
    row = await docstore.apply_parse_webhook(
        run_row.attachment_id,
        status=parse_status,
        stage_snapshot=stage_snapshot,
        error_code=error_code,
        error_message=error_message,
    )
    if run_status:
        await jobs.update_run_status(run_row.job_id, run_status)

    if row is None:
        return None

    snapshot = stage_snapshot if stage_snapshot is not None else _snapshot_from_row(row)
    out = {
        "attachment_id": str(row.id),
        "chat_id": str(row.chat_id),
        "parse_status": row.parse_status,
        "parse_pipeline_id": row.parse_pipeline_id,
        "parse_job_id": row.parse_job_id,
        "parse_error_message": row.parse_error_message,
        "parse_progress": snapshot,
    }
    from app.platform.audio_capture.webhook import sync_capture_from_parse_webhook

    await sync_capture_from_parse_webhook(
        session,
        attachment_id=run_row.attachment_id,
        parse_status=parse_status,
        error_code=error_code,
        error_message=error_message,
    )

    publish_attachment_parse_updated(str(row.chat_id), out)
    return out
