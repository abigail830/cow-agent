"""Hub parse status helpers (reconcile DB vs stored artifacts)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HubItem
from app.platform.docstore.manifest import parsed_artifact_in_manifest
from app.platform.docstore.models import ParseStatus
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.repository import ParseJobRepository

_ACTIVE = frozenset({ParseStatus.PENDING.value, ParseStatus.RUNNING.value})


async def reconcile_hub_item_parse_status(session: AsyncSession, row: HubItem) -> HubItem:
    """If artifacts were written but terminal webhook failed, mark item ready."""
    if row.parse_status not in _ACTIVE:
        return row
    if not parsed_artifact_in_manifest(row.parsed_artifact_manifest, "content_md"):
        return row

    job_id = row.parse_job_id
    docstore = DocstoreRepository(session)
    updated = await docstore.apply_parse_webhook(
        row.id,
        status=ParseStatus.READY.value,
        stage_snapshot={
            "current_stage": "finalize",
            "message": "Parse complete.",
            "stages": [],
        },
    )
    if updated is None:
        return row
    updated.parse_job_id = None
    await session.flush()

    if job_id:
        jobs = ParseJobRepository(session)
        await jobs.update_run_status(job_id, "succeeded")

    return updated
