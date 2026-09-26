from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.db.models import ChatAttachment
from app.db.session import get_async_session_factory
from app.platform.docstore.models import ParseStatus
from app.platform.parse_pipeline.repository import ParseJobRepository
from app.platform.parse_pipeline.status_report import report_parse_run_status

logger = logging.getLogger(__name__)

_RECONCILE_ATTEMPTS = 3
_RECONCILE_DELAY_SEC = 10.0


def schedule_gha_run_watch(*, job_id: str) -> None:
    asyncio.create_task(_watch_gha_run(job_id=job_id))


async def _watch_gha_run(*, job_id: str) -> None:
    settings = get_settings()
    token = (settings.github_token or "").strip()
    repo = (settings.github_repo or "").strip()
    workflow = (settings.github_workflow_file or "parse-pipeline-run-job.yml").strip()
    if not token or not repo:
        return

    poll_interval = max(5.0, float(settings.parse_pipeline_gha_watch_poll_sec))
    max_wait = max(300, int(settings.parse_pipeline_gha_watch_max_sec))
    started = datetime.now(timezone.utc)
    await asyncio.sleep(8.0)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
    run_name_prefix = f"platform-parse-{job_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        while (datetime.now(timezone.utc) - started).total_seconds() < max_wait:
            factory = get_async_session_factory()
            async with factory() as session:
                jobs = ParseJobRepository(session)
                run_row = await jobs.get_run(job_id)
                if run_row is None or run_row.status in {"failed", "succeeded"}:
                    return

            try:
                response = await client.get(
                    url,
                    params={"per_page": 15, "event": "workflow_dispatch"},
                    headers=headers,
                )
                response.raise_for_status()
                runs = response.json().get("workflow_runs") or []
            except Exception:
                logger.exception("GHA watch poll failed job_id=%s", job_id)
                await asyncio.sleep(poll_interval)
                continue

            matched = next(
                (
                    run
                    for run in runs
                    if str(run.get("name") or "").startswith(run_name_prefix)
                    or str(run.get("display_title") or "").startswith(run_name_prefix)
                ),
                None,
            )
            if matched is None:
                await asyncio.sleep(poll_interval)
                continue

            status = str(matched.get("status") or "")
            if status != "completed":
                html_url = str(matched.get("html_url") or "")
                message = "GitHub Actions job in progress…"
                if html_url:
                    message = f"{message} ({html_url})"
                await _mark_job_running_if_pending(
                    job_id=job_id,
                    message=message,
                    current_stage="fetch",
                )
                await asyncio.sleep(poll_interval)
                continue

            conclusion = str(matched.get("conclusion") or "")
            if conclusion == "success":
                await _reconcile_gha_success(job_id=job_id, matched=matched)
                return

            html_url = str(matched.get("html_url") or "")
            message = "GitHub Actions parse job failed"
            if html_url:
                message = f"{message} ({html_url})"
            await _mark_job_failed(job_id=job_id, error_code="GHA_FAILED", error_message=message)
            return

        await asyncio.sleep(poll_interval)

    await _mark_job_failed(
        job_id=job_id,
        error_code="PARSE_TIMEOUT",
        error_message="Timed out waiting for GitHub Actions parse job to finish",
    )


async def _reconcile_gha_success(*, job_id: str, matched: dict) -> None:
    """GHA succeeded — verify platform received artifacts / ready status via webhook."""
    from app.platform.docstore.manifest import parsed_artifact_in_manifest

    for attempt in range(_RECONCILE_ATTEMPTS):
        factory = get_async_session_factory()
        async with factory() as session:
            jobs = ParseJobRepository(session)
            run_row = await jobs.get_run(job_id)
            if run_row is None:
                return
            if run_row.status in {"failed", "succeeded"}:
                return

            attachment = await session.get(ChatAttachment, run_row.attachment_id)
            if attachment is not None and attachment.parse_status == ParseStatus.READY.value:
                await jobs.update_run_status(job_id, "succeeded")
                await session.commit()
                return

            if attachment is not None and parsed_artifact_in_manifest(
                attachment.parsed_artifact_manifest,
                "meta_json",
            ):
                await report_parse_run_status(
                    session,
                    run_row=run_row,
                    parse_status=ParseStatus.READY.value,
                    run_status="succeeded",
                    stage_snapshot={
                        "current_stage": "finalize",
                        "message": "Parse complete (reconciled after GHA success)",
                        "stages": [],
                    },
                )
                await session.commit()
                return

        if attempt + 1 < _RECONCILE_ATTEMPTS:
            await asyncio.sleep(_RECONCILE_DELAY_SEC)

    html_url = str(matched.get("html_url") or "")
    message = "GitHub Actions succeeded but platform did not receive parse results"
    if html_url:
        message = f"{message} ({html_url})"
    await _mark_job_failed(job_id=job_id, error_code="WEBHOOK_DELIVERY_LOST", error_message=message)


async def _mark_job_running_if_pending(
    *,
    job_id: str,
    message: str,
    current_stage: str = "fetch",
) -> None:
    factory = get_async_session_factory()
    async with factory() as session:
        jobs = ParseJobRepository(session)
        run_row = await jobs.get_run(job_id)
        if run_row is None or run_row.status in {"failed", "succeeded"}:
            return
        attachment = await session.get(ChatAttachment, run_row.attachment_id)
        if attachment is None or attachment.parse_status != ParseStatus.PENDING.value:
            return
        await report_parse_run_status(
            session,
            run_row=run_row,
            parse_status=ParseStatus.RUNNING.value,
            run_status="running",
            stage_snapshot={
                "current_stage": current_stage,
                "message": message,
                "stages": [],
            },
        )
        await session.commit()


async def _mark_job_failed(*, job_id: str, error_code: str, error_message: str) -> None:
    factory = get_async_session_factory()
    async with factory() as session:
        jobs = ParseJobRepository(session)
        run_row = await jobs.get_run(job_id)
        if run_row is None or run_row.status in {"failed", "succeeded"}:
            return
        await report_parse_run_status(
            session,
            run_row=run_row,
            parse_status=ParseStatus.FAILED.value,
            error_code=error_code,
            error_message=error_message,
            run_status="failed",
        )
        await session.commit()
