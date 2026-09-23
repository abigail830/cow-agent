from __future__ import annotations

from typing import Any

from app.db.models import ChatAttachment


def parse_progress_from_row(row: ChatAttachment) -> dict[str, Any] | None:
    snapshot = row.parse_stage_snapshot
    if not isinstance(snapshot, dict):
        return None
    return {
        "current_stage": snapshot.get("current_stage"),
        "message": snapshot.get("message"),
        "stages": snapshot.get("stages"),
    }


def resolve_parse_status_for_api(row: ChatAttachment) -> str:
    status = getattr(row, "parse_status", None)
    pipeline_id = row.parse_pipeline_id
    job_id = row.parse_job_id
    if status:
        return str(status)
    if pipeline_id or job_id:
        return "pending"
    return "ready"


def resolve_parse_status_from_payload(row: dict[str, Any]) -> str:
    status = row.get("parse_status")
    if status:
        return str(status)
    if row.get("parse_pipeline_id") or row.get("parse_job_id"):
        return "pending"
    return "ready"


def attachment_out_extras(row: ChatAttachment) -> dict[str, Any]:
    return {
        "parse_status": resolve_parse_status_for_api(row),
        "parse_pipeline_id": row.parse_pipeline_id,
        "parse_job_id": row.parse_job_id,
        "parse_error_message": row.parse_error_message,
        "parse_progress": parse_progress_from_row(row),
    }
