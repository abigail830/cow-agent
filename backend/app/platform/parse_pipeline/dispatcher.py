from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def dispatch_gha(
    *,
    job_id: str,
    run_token: str,
    pipeline_id: str,
) -> None:
    settings = get_settings()
    token = (settings.github_token or "").strip()
    repo = (settings.github_repo or "").strip()
    workflow = (settings.github_workflow_file or "parse-pipeline-run-job.yml").strip()
    ref = (settings.github_ref or "main").strip()
    public_base = (settings.parse_pipeline_public_base_url or "").strip()

    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPO required for GHA dispatch")

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    inputs = {
        "pipeline_id": pipeline_id,
        "platform_job_id": job_id,
        "platform_run_token": run_token,
        "platform_base_url": public_base,
        "job_id": job_id,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json={"ref": ref, "inputs": inputs}, headers=headers)
        if response.status_code not in (201, 204):
            logger.error("GHA dispatch failed status=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
