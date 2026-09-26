"""Build DocumentOut rows for attachments and artifacts."""

from __future__ import annotations

import uuid
from typing import Any

from app.api.schemas import DocumentOut, ParsedArtifactsOut
from app.db.models import AgentModel, Chat, ChatAttachment
from app.platform.attachments.api_out import attachment_out
from app.platform.attachments.metadata import attachment_metadata
from app.platform.docstore.manifest import parsed_artifacts_flags_from_manifest
from app.platform.documents.list_helpers import parse_artifact_spec, slim_artifact_spec_for_list


def attachment_document_out(
    attachment: ChatAttachment,
    chat: Chat,
    agent: AgentModel,
) -> DocumentOut:
    payload = attachment_metadata(attachment)
    if attachment.created_at is not None:
        payload["created_at"] = attachment.created_at.isoformat()
    base = attachment_out(attachment.chat_id, payload)
    artifacts = ParsedArtifactsOut()
    if base.parse_status == "ready":
        artifacts = ParsedArtifactsOut(**parsed_artifacts_flags_from_manifest(attachment.parsed_artifact_manifest))
    return DocumentOut(
        source_type="attachment",
        id=base.id,
        chat_id=base.chat_id,
        filename=base.filename,
        created_at=base.created_at,
        mime_type=base.mime_type,
        size_bytes=base.size_bytes,
        provider=base.provider,
        provider_file_id=base.provider_file_id,
        parse_status=base.parse_status,
        parse_pipeline_id=base.parse_pipeline_id,
        parse_job_id=base.parse_job_id,
        parse_error_message=base.parse_error_message,
        parse_progress=base.parse_progress,
        agent_id=agent.id,
        agent_name=agent.name,
        agent_slug=agent.slug,
        chat_title=chat.title,
        has_parsed_content=artifacts.content_md,
        parsed_artifacts=artifacts,
        gist=(attachment.gist or "").strip() or None,
    )


def artifact_document_out(row: dict[str, Any]) -> DocumentOut | None:
    spec = parse_artifact_spec(row.get("display"))
    if spec is None:
        return None
    slim = slim_artifact_spec_for_list(spec)
    created_at = row.get("created_at")
    return DocumentOut(
        source_type="artifact",
        id=row["annotation_id"],
        chat_id=row["chat_id"],
        filename=str(spec.get("filename") or spec.get("title") or row.get("ref") or "artifact"),
        created_at=created_at.isoformat() if created_at is not None else None,
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        agent_slug=row.get("agent_slug"),
        chat_title=row.get("chat_title"),
        artifact_id=str(spec.get("artifact_id") or row.get("ref")),
        artifact_kind=spec.get("kind"),
        artifact_format=spec.get("format"),
        artifact_spec=slim,
    )
