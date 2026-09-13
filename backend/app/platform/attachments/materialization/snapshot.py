"""Persist extracted document text on message metadata for history replay."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.platform.attachments.attachment_storage import (
    load_inline_attachment,
    parse_inline_attachment_id,
)
from app.platform.attachments.materialization.hash import format_content_hash, sha256_hex
from app.platform.attachments.unify_lite.types import ExtractedAttachment


EXTRACT_PIPELINE_VERSION = "unify_lite_v1"


def snapshot_from_extracted(
    item: ExtractedAttachment,
    *,
    content_hash: str | None = None,
) -> dict[str, Any]:
    digest = content_hash or ""
    if digest and not digest.startswith("sha256:"):
        digest = format_content_hash(digest)
    return {
        "content_hash": digest,
        "text": item.content,
        "truncated": item.truncated,
        "char_count": item.char_count,
        "extracted_at": datetime.now(UTC).isoformat(),
        "extract_pipeline_version": EXTRACT_PIPELINE_VERSION,
    }


def snapshot_materialize_failed(
    *,
    filename: str,
    attachment_id: str,
    reason: str,
    notice_text: str,
) -> dict[str, Any]:
    return {
        "materialize_failed": True,
        "failure_reason": reason,
        "failed_at": datetime.now(UTC).isoformat(),
        "text": notice_text,
        "char_count": len(notice_text),
        "truncated": False,
        "content_hash": "",
        "extracted_at": datetime.now(UTC).isoformat(),
    }


def compute_attachment_content_hash(chat_id: uuid.UUID, provider_file_id: str) -> str:
    attachment_id = parse_inline_attachment_id(provider_file_id)
    data = load_inline_attachment(chat_id, attachment_id)
    return format_content_hash(sha256_hex(data))


def enrich_metadata_with_extracted_snapshots(
    metadata: dict[str, Any],
    extracted: list[ExtractedAttachment],
    *,
    chat_id: uuid.UUID,
    attachments: list[Any],
) -> dict[str, Any]:
    """Merge ``extracted_snapshot`` into attachment dicts keyed by attachment id."""
    if not extracted:
        return metadata

    by_id = {str(item.attachment_id): item for item in extracted}
    provider_by_id = {str(att.id): str(att.provider_file_id) for att in attachments}
    raw_attachments = metadata.get("attachments")
    if not isinstance(raw_attachments, list):
        return metadata

    enriched: list[dict[str, Any]] = []
    for item in raw_attachments:
        if not isinstance(item, dict):
            enriched.append(item)
            continue
        att_id = str(item.get("id") or "")
        extracted_item = by_id.get(att_id)
        if extracted_item is None:
            enriched.append(dict(item))
            continue
        provider_file_id = provider_by_id.get(att_id) or str(item.get("provider_file_id") or "")
        content_hash = ""
        if provider_file_id:
            try:
                content_hash = compute_attachment_content_hash(chat_id, provider_file_id)
            except (OSError, ValueError):
                content_hash = format_content_hash(sha256_hex(extracted_item.content.encode("utf-8")))
        merged = {
            **item,
            "extracted_snapshot": snapshot_from_extracted(extracted_item, content_hash=content_hash),
        }
        enriched.append(merged)

    return {**metadata, "attachments": enriched}
