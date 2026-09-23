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


def attachment_out_extras(row: ChatAttachment) -> dict[str, Any]:
    return {
        "parse_status": getattr(row, "parse_status", None) or "ready",
        "parse_pipeline_id": row.parse_pipeline_id,
        "parse_job_id": row.parse_job_id,
        "parse_error_message": row.parse_error_message,
        "parse_progress": parse_progress_from_row(row),
    }
