from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.db.session import get_async_session_factory
from app.platform.parse_pipeline.repository import ParseJobRepository
from app.platform.parse_pipeline.status_report import report_parse_run_status

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SEC = 20.0
_MAX_WAIT_SEC = 45 * 60


def schedule_gha_run_watch(*, job_id: str) -> None:
    asyncio.create_task(_watch_gha_run(job_id=job_id))


async def _watch_gha_run(*, job_id: str) -> None:
    settings = get_settings()
    token = (settings.github_token or "").strip()
    repo = (settings.github_repo or "").strip()
    workflow = (settings.github_workflow_file or "parse-pipeline-run-job.yml").strip()
    if not token or not repo:
        return

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
        while (datetime.now(timezone.utc) - started).total_seconds() < _MAX_WAIT_SEC:
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
                await asyncio.sleep(_POLL_INTERVAL_SEC)
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
                await asyncio.sleep(_POLL_INTERVAL_SEC)
                continue

            status = str(matched.get("status") or "")
            if status != "completed":
                await asyncio.sleep(_POLL_INTERVAL_SEC)
                continue

            conclusion = str(matched.get("conclusion") or "")
            if conclusion == "success":
                return

            html_url = str(matched.get("html_url") or "")
            message = "GitHub Actions parse job failed"
            if html_url:
                message = f"{message} ({html_url})"

            factory = get_async_session_factory()
            async with factory() as session:
                jobs = ParseJobRepository(session)
                run_row = await jobs.get_run(job_id)
                if run_row is None or run_row.status in {"failed", "succeeded"}:
                    return
                await report_parse_run_status(
                    session,
                    run_row=run_row,
                    parse_status="failed",
                    error_code="GHA_FAILED",
                    error_message=message,
                    run_status="failed",
                )
                await session.commit()
            return
