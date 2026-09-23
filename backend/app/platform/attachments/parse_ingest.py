"""Post-upload parse routing (docstore + parse_pipeline)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment
from app.platform.attachments.kinds import AttachmentKind
from app.platform.docstore.models import PARSE_READY_STATUSES, ParseStatus
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.enqueue import enqueue_parse_job
from app.platform.parse_pipeline.router import PipelineRoute, resolve_pipeline


async def finalize_attachment_parse(
    session: AsyncSession,
    row: ChatAttachment,
    *,
    kind: AttachmentKind,
) -> ChatAttachment:
    resolution = resolve_pipeline(kind)
    docstore = DocstoreRepository(session)

    if resolution.action == PipelineRoute.SKIP.value:
        updated = await docstore.mark_parse_ready(row.id, skipped=True)
        return updated or row

    if resolution.action == PipelineRoute.REJECT.value:
        raise ValueError(f"Unsupported file type for parse: {row.mime_type or row.filename}")

    pipeline_id = resolution.pipeline_id
    assert pipeline_id is not None

    status = str(getattr(row, "parse_status", None) or ParseStatus.READY.value)
    if status in PARSE_READY_STATUSES and row.parse_pipeline_id == pipeline_id:
        return row

    return await enqueue_parse_job(session, row, pipeline_id=pipeline_id)
