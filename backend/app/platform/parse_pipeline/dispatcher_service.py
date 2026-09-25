"""Submit parse jobs to a standalone parse-pipeline HTTP service."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _service_base_url() -> str:
    settings = get_settings()
    raw = (settings.parse_pipeline_service_url or "http://127.0.0.1:8091").strip()
    return raw.rstrip("/")


def _service_auth() -> tuple[str, str]:
    settings = get_settings()
    api_key = (settings.parse_pipeline_service_api_key or "").strip()
    if not api_key:
        raise RuntimeError(
            "PARSE_PIPELINE_SERVICE_API_KEY is required for service dispatch "
            "(must match parse-pipeline PARSE_PIPELINE_API_KEYS)"
        )
    caller_id = (settings.parse_pipeline_service_caller_id or "agent-platform").strip()
    return api_key, caller_id


def _submit_body(payload: dict) -> dict:
    return {
        "schema_version": payload.get("schema_version") or "1.0",
        "job_id": payload.get("job_id"),
        "idempotency_key": payload.get("idempotency_key"),
        "pipeline_id": payload["pipeline_id"],
        "storage": payload["storage"],
        "source": payload.get("source") or {},
        "options": payload.get("options") or {},
        "callbacks": payload.get("callbacks") or {},
    }


async def dispatch_service(*, payload: dict) -> str:
    """POST job to parse-pipeline /v1/jobs; returns worker job_id (same as platform job_id when provided)."""

    api_key, caller_id = _service_auth()
    url = f"{_service_base_url()}/v1/jobs"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Parse-Caller-Id": caller_id,
        "Content-Type": "application/json",
    }
    body = _submit_body(payload)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            logger.error("parse service dispatch failed status=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
        data = response.json()
    job_id = str(data.get("job_id") or body.get("job_id") or "")
    if not job_id:
        raise RuntimeError("parse service returned no job_id")
    logger.info("dispatched parse job to service job_id=%s url=%s", job_id, url)
    return job_id
