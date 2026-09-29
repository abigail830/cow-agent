from __future__ import annotations

from typing import Any

from app.db.models import HubItem


def hub_item_metadata(row: HubItem) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "folder_id": str(row.folder_id),
        "item_kind": row.item_kind,
        "filename": row.filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "content_hash": row.content_hash,
        "provider": row.provider,
        "provider_file_id": row.provider_file_id,
        "parse_status": row.parse_status,
        "parse_pipeline_id": row.parse_pipeline_id,
        "parse_job_id": row.parse_job_id,
        "parse_error_code": row.parse_error_code,
        "parse_error_message": row.parse_error_message,
        "parse_stage_snapshot": row.parse_stage_snapshot,
        "parsed_artifact_manifest": row.parsed_artifact_manifest,
        "attachment_role": row.attachment_role,
        "capture_id": str(row.capture_id) if row.capture_id else None,
        "gist": row.gist,
    }
