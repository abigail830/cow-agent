"""Build AttachmentOut API models from DB rows."""

from __future__ import annotations

import uuid
from typing import Any

from app.api.schemas import AttachmentOut, ParseProgressOut, ParseStageOut
from app.platform.parse_pipeline.serialization import resolve_parse_status_from_payload


def attachment_out(chat_id: uuid.UUID, row: dict[str, Any]) -> AttachmentOut:
    progress_raw = row.get("parse_progress")
    progress = None
    if isinstance(progress_raw, dict):
        stages_raw = progress_raw.get("stages")
        stages = None
        if isinstance(stages_raw, list):
            stages = [
                ParseStageOut(
                    stage_id=s.get("stage_id") if isinstance(s, dict) else None,
                    status=s.get("status") if isinstance(s, dict) else None,
                )
                for s in stages_raw
            ]
        progress = ParseProgressOut(
            current_stage=progress_raw.get("current_stage"),
            message=progress_raw.get("message"),
            stages=stages,
        )
    return AttachmentOut(
        id=uuid.UUID(row["id"]),
        chat_id=chat_id,
        filename=row["filename"],
        mime_type=row["mime_type"],
        size_bytes=row["size_bytes"],
        provider=row["provider"],
        provider_file_id=row["provider_file_id"],
        created_at=row.get("created_at"),
        parse_status=resolve_parse_status_from_payload(row),
        parse_pipeline_id=row.get("parse_pipeline_id"),
        parse_job_id=row.get("parse_job_id"),
        parse_error_message=row.get("parse_error_message"),
        parse_progress=progress,
    )
