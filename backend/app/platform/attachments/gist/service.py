"""Generate attachment gist via utility LLM and persist to DB."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.gist.prompt import (
    GIST_SYSTEM_INSTRUCTIONS,
    build_gist_user_prompt,
    section_titles_from_meta,
    truncate_markdown_for_gist,
)
from app.platform.attachments.gist.schema import parse_gist_metadata
from app.platform.attachments.kinds import classify_attachment
from app.platform.docstore.manifest import parsed_artifact_in_manifest
from app.platform.docstore.models import ParseStatus
from app.platform.doc_retrieval.store import is_document_kind, load_content_md, load_meta_json
from app.platform.llm.utility_models import UtilityModelRegistry, UtilityPurpose

logger = logging.getLogger(__name__)


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def generate_and_save_attachment_gist(
    session: AsyncSession,
    attachment_id: uuid.UUID,
) -> bool:
    settings = get_settings()
    if not settings.attachment_gist_enabled:
        return False
    if not settings.attachment_gist_api_key():
        logger.warning("attachment gist skipped: no ATTACHMENT_GIST_MODEL_API_KEY or DASHSCOPE_API_KEY")
        return False

    repo = AttachmentRepository(session)
    row = await repo.get(attachment_id)
    if row is None:
        return False
    if getattr(row, "attachment_role", None) == "audio_part":
        return False
    if str(row.parse_status or "") != ParseStatus.READY.value:
        return False
    manifest = row.parsed_artifact_manifest
    if not parsed_artifact_in_manifest(manifest, "content_md"):
        return False

    kind = classify_attachment(filename=row.filename, mime_type=row.mime_type)
    if not is_document_kind(kind.value):
        return False

    try:
        full_content = load_content_md(row.chat_id, row.id)
    except FileNotFoundError:
        logger.warning("attachment gist skipped: content_md missing attachment_id=%s", attachment_id)
        return False

    content_sha = content_sha256(full_content)
    if row.gist and row.gist_content_sha256 == content_sha:
        return True

    meta = None
    if parsed_artifact_in_manifest(manifest, "meta_json"):
        try:
            meta = load_meta_json(row.chat_id, row.id)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            meta = None

    truncated = truncate_markdown_for_gist(
        full_content,
        max_chars=settings.attachment_gist_max_input_chars,
    )
    user_prompt = build_gist_user_prompt(
        filename=row.filename,
        mime_type=row.mime_type,
        markdown=truncated,
        section_titles=section_titles_from_meta(meta),
    )

    registry = UtilityModelRegistry()
    raw = await registry.complete(
        UtilityPurpose.ATTACHMENT_GIST,
        prompt=user_prompt,
        max_tokens=settings.attachment_gist_max_output_tokens,
        instructions=GIST_SYSTEM_INSTRUCTIONS,
        temperature=settings.attachment_gist_temperature,
    )
    metadata = parse_gist_metadata(raw)
    if metadata is None:
        raw_retry = await registry.complete(
            UtilityPurpose.ATTACHMENT_GIST,
            prompt=user_prompt + "\n\nYour previous reply was not valid JSON. Reply with JSON only.",
            max_tokens=settings.attachment_gist_max_output_tokens,
            instructions=GIST_SYSTEM_INSTRUCTIONS,
            temperature=settings.attachment_gist_temperature,
        )
        metadata = parse_gist_metadata(raw_retry)
    if metadata is None:
        logger.warning("attachment gist parse failed attachment_id=%s", attachment_id)
        return False

    gist_text = metadata.to_gist_text()
    if not gist_text:
        return False

    try:
        verify_content = load_content_md(row.chat_id, row.id)
    except FileNotFoundError:
        return False
    if content_sha256(verify_content) != content_sha:
        logger.info("attachment gist stale after LLM attachment_id=%s", attachment_id)
        return False

    updated = await repo.save_gist_metadata(
        attachment_id,
        gist=gist_text,
        content_sha256=content_sha,
        generated_at=datetime.now(timezone.utc),
    )
    if updated is None:
        logger.info("attachment gist not written (not ready or missing) attachment_id=%s", attachment_id)
        return False
    logger.info("attachment gist saved attachment_id=%s len=%s", attachment_id, len(gist_text))
    return True
