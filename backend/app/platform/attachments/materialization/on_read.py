"""Materialize-on-read: lazy snapshot backfill with graceful fallback (legacy + mode drift)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.db.repositories.attachments import AttachmentRepository
from app.db.repositories.messages import MessageRepository
from app.platform.attachments.attachment_storage import (
    is_inline_provider_file_id,
    load_inline_attachment,
    parse_inline_attachment_id,
)
from app.platform.attachments.materialization.hash import format_content_hash, sha256_hex
from app.platform.attachments.materialization.snapshot import (
    EXTRACT_PIPELINE_VERSION,
    snapshot_from_extracted,
    snapshot_materialize_failed,
)
from app.platform.attachments.materialization.stub import format_unmaterialized_attachment_notice
from app.platform.attachments.unify_lite.extractors.registry import extract_bytes
from app.platform.attachments.unify_lite.truncate import truncate_chars
from app.platform.attachments.unify_lite.types import ExtractedAttachment
from app.platform.attachments.unify_lite.validation import is_unify_lite_image, is_unify_lite_text

logger = logging.getLogger(__name__)

_extract_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="attachment-extract")
_materialize_locks: dict[str, asyncio.Lock] = {}
_materialize_locks_guard = asyncio.Lock()


@dataclass(frozen=True)
class LazyExtractOutcome:
    ok: bool
    item: dict[str, Any]
    persisted: bool = False


def snapshot_is_resolved(item: dict[str, Any]) -> bool:
    """Return True when no further lazy materialization is needed."""
    snapshot = item.get("extracted_snapshot")
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("materialize_failed"):
        return True
    text = str(snapshot.get("text") or "")
    if not text:
        return False
    if snapshot.get("compacted"):
        return False
    if text.lstrip().startswith("[Attachment compacted]"):
        return False
    return True


def attachment_needs_lazy_materialization(item: dict[str, Any]) -> bool:
    """True when this attachment should attempt lazy extract before replay."""
    if item.get("compaction_placeholder"):
        return False
    if snapshot_is_resolved(item):
        return False
    filename = str(item.get("filename") or "attachment")
    mime_type = str(item.get("mime_type") or "")
    if is_unify_lite_image(filename=filename, mime_type=mime_type):
        return False
    if not is_unify_lite_text(filename=filename, mime_type=mime_type):
        return False
    provider_file_id = str(item.get("provider_file_id") or "")
    if not is_inline_provider_file_id(provider_file_id):
        return False
    return True


def _extract_inline_text_sync(
    *,
    chat_id: uuid.UUID,
    item: dict[str, Any],
    timeout_seconds: float,
) -> tuple[ExtractedAttachment | None, str | None]:
    filename = str(item.get("filename") or "attachment")
    mime_type = str(item.get("mime_type") or "")
    provider_file_id = str(item.get("provider_file_id") or "")

    def _run() -> tuple[ExtractedAttachment | None, str | None]:
        try:
            attachment_id = parse_inline_attachment_id(provider_file_id)
            data = load_inline_attachment(chat_id, attachment_id)
        except OSError:
            return None, "blob_missing"
        except ValueError as exc:
            return None, str(exc)

        try:
            content, warnings, extract_ms = extract_bytes(
                filename=filename,
                mime_type=mime_type,
                data=data,
            )
        except ValueError:
            return None, "unsupported_format"
        except Exception:
            logger.exception("Lazy extract failed for attachment %s", item.get("id"))
            return None, "extract_error"

        settings = get_settings()
        truncated = False
        if len(content) > settings.unify_lite_max_chars_per_file:
            content, truncated = truncate_chars(content, settings.unify_lite_max_chars_per_file)

        att_uuid = uuid.UUID(str(item.get("id"))) if item.get("id") else attachment_id
        extracted = ExtractedAttachment(
            attachment_id=att_uuid,
            filename=filename,
            mime_type=mime_type,
            content=content,
            truncated=truncated,
            char_count=len(content),
            extract_ms=extract_ms,
            warnings=list(warnings),
        )
        if warnings:
            logger.debug("Lazy extract warnings for %s: %s", att_uuid, warnings)
        return extracted, None

    future = _extract_executor.submit(_run)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        return None, "extract_timeout"


def _merge_attachment_item(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    if "extracted_snapshot" in patch:
        snapshot = patch["extracted_snapshot"]
        if isinstance(snapshot, dict):
            merged["extracted_snapshot"] = {**dict(base.get("extracted_snapshot") or {}), **snapshot}
    for key, value in patch.items():
        if key != "extracted_snapshot":
            merged[key] = value
    return merged


def _apply_extract_success(item: dict[str, Any], extracted: ExtractedAttachment, *, chat_id: uuid.UUID) -> dict[str, Any]:
    provider_file_id = str(item.get("provider_file_id") or "")
    content_hash = str(item.get("content_hash") or "")
    if not content_hash and provider_file_id:
        try:
            data = load_inline_attachment(chat_id, parse_inline_attachment_id(provider_file_id))
            content_hash = format_content_hash(sha256_hex(data))
        except (OSError, ValueError):
            content_hash = format_content_hash(sha256_hex(extracted.content.encode("utf-8")))
    snapshot = snapshot_from_extracted(extracted, content_hash=content_hash or None)
    snapshot["extract_pipeline_version"] = EXTRACT_PIPELINE_VERSION
    snapshot["materialized_via"] = "lazy_on_read"
    return _merge_attachment_item(item, {"extracted_snapshot": snapshot, "content_hash": content_hash or item.get("content_hash")})


def _apply_extract_failure(item: dict[str, Any], *, reason: str) -> dict[str, Any]:
    filename = str(item.get("filename") or "attachment")
    att_id = str(item.get("id") or "")
    notice = format_unmaterialized_attachment_notice(filename=filename, attachment_id=att_id)
    snapshot = snapshot_materialize_failed(
        filename=filename,
        attachment_id=att_id,
        reason=reason,
        notice_text=notice,
    )
    return _merge_attachment_item(item, {"extracted_snapshot": snapshot})


def materialize_attachment_item_sync(
    *,
    chat_id: uuid.UUID,
    item: dict[str, Any],
    timeout_seconds: float | None = None,
) -> LazyExtractOutcome:
    """In-memory lazy materialize (no DB). Used by tests and as extract core."""
    if not attachment_needs_lazy_materialization(item):
        return LazyExtractOutcome(ok=True, item=dict(item))

    settings = get_settings()
    timeout = timeout_seconds if timeout_seconds is not None else settings.attachment_lazy_extract_timeout_seconds
    extracted, failure_reason = _extract_inline_text_sync(
        chat_id=chat_id,
        item=item,
        timeout_seconds=timeout,
    )
    if extracted is not None:
        return LazyExtractOutcome(
            ok=True,
            item=_apply_extract_success(item, extracted, chat_id=chat_id),
        )
    return LazyExtractOutcome(
        ok=False,
        item=_apply_extract_failure(item, reason=failure_reason or "unknown"),
    )


async def _get_materialize_lock(key: str) -> asyncio.Lock:
    async with _materialize_locks_guard:
        lock = _materialize_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _materialize_locks[key] = lock
        return lock


async def _load_attachment_item_from_db(
    repo: MessageRepository,
    *,
    message_id: uuid.UUID,
    attachment_id: str,
) -> dict[str, Any] | None:
    message = await repo.get(message_id)
    if message is None:
        return None
    metadata = message.message_metadata or {}
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list):
        return None
    for raw in attachments:
        if isinstance(raw, dict) and str(raw.get("id") or "") == attachment_id:
            return dict(raw)
    return None


async def _persist_attachment_item(
    repo: MessageRepository,
    *,
    message_id: uuid.UUID,
    attachment_id: str,
    item: dict[str, Any],
) -> bool:
    message = await repo.get(message_id)
    if message is None:
        return False
    metadata = dict(message.message_metadata or {})
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list):
        return False

    replaced = False
    new_attachments: list[Any] = []
    for raw in attachments:
        if not isinstance(raw, dict):
            new_attachments.append(raw)
            continue
        if str(raw.get("id") or "") != attachment_id:
            new_attachments.append(raw)
            continue
        if snapshot_is_resolved(raw):
            item = raw
            replaced = True
            new_attachments.append(dict(raw))
            continue
        new_attachments.append(dict(item))
        replaced = True

    if not replaced:
        return False
    metadata["attachments"] = new_attachments
    message.message_metadata = metadata
    flag_modified(message, "message_metadata")
    await repo.flush()
    return True


async def _verify_attachment_in_chat(
    attachments: AttachmentRepository,
    *,
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> bool:
    row = await attachments.get(attachment_id)
    return row is not None and row.chat_id == chat_id


async def materialize_attachment_item_async(
    session: AsyncSession,
    *,
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    item: dict[str, Any],
) -> LazyExtractOutcome:
    """Lazy materialize one attachment with DB backfill and concurrency guard."""
    att_id = str(item.get("id") or "")
    if not att_id or not attachment_needs_lazy_materialization(item):
        return LazyExtractOutcome(ok=True, item=dict(item))

    lock = await _get_materialize_lock(f"{message_id}:{att_id}")
    async with lock:
        messages = MessageRepository(session)
        attachments = AttachmentRepository(session)

        if not await _verify_attachment_in_chat(
            attachments,
            chat_id=chat_id,
            attachment_id=uuid.UUID(att_id),
        ):
            failed = _apply_extract_failure(item, reason="access_denied")
            return LazyExtractOutcome(ok=False, item=failed)

        fresh = await _load_attachment_item_from_db(
            messages,
            message_id=message_id,
            attachment_id=att_id,
        )
        if fresh is not None and snapshot_is_resolved(fresh):
            return LazyExtractOutcome(ok=not fresh.get("extracted_snapshot", {}).get("materialize_failed"), item=fresh)

        settings = get_settings()
        loop = asyncio.get_running_loop()
        outcome = await loop.run_in_executor(
            _extract_executor,
            lambda: materialize_attachment_item_sync(
                chat_id=chat_id,
                item=fresh or item,
                timeout_seconds=settings.attachment_lazy_extract_timeout_seconds,
            ),
        )
        persisted = await _persist_attachment_item(
            messages,
            message_id=message_id,
            attachment_id=att_id,
            item=outcome.item,
        )
        return LazyExtractOutcome(ok=outcome.ok, item=outcome.item, persisted=persisted)


def materialize_row_attachments_sync(
    row: dict[str, Any],
    *,
    chat_id: uuid.UUID | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Resolve attachments on one history row in memory (no DB write)."""
    metadata = dict(row.get("metadata") or {})
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list) or not attachments:
        return row

    chat_uuid = chat_id or uuid.UUID(str(row.get("chat_id")))
    resolved: list[Any] = []
    changed = False
    for raw in attachments:
        if not isinstance(raw, dict):
            resolved.append(raw)
            continue
        outcome = materialize_attachment_item_sync(
            chat_id=chat_uuid,
            item=raw,
            timeout_seconds=timeout_seconds,
        )
        resolved.append(outcome.item)
        if outcome.item != raw:
            changed = True

    if not changed:
        return row
    return {**row, "metadata": {**metadata, "attachments": resolved}}


async def materialize_rows_on_read(
    session: AsyncSession,
    rows: list[dict[str, Any]],
    *,
    chat_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Backfill missing attachment snapshots before replay; persists successful/failed outcomes."""
    if not rows:
        return rows

    materialized: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata") or {}
        attachments = metadata.get("attachments")
        if row.get("role") != "user" or row.get("message_type") != "text":
            materialized.append(row)
            continue
        if not isinstance(attachments, list) or not attachments:
            materialized.append(row)
            continue

        message_id_raw = row.get("id")
        if not message_id_raw:
            materialized.append(materialize_row_attachments_sync(row, chat_id=chat_id))
            continue

        message_id = uuid.UUID(str(message_id_raw))
        new_metadata = dict(metadata)
        resolved_items: list[Any] = []
        for raw in attachments:
            if not isinstance(raw, dict):
                resolved_items.append(raw)
                continue
            if not attachment_needs_lazy_materialization(raw):
                resolved_items.append(raw)
                continue
            outcome = await materialize_attachment_item_async(
                session,
                chat_id=chat_id,
                message_id=message_id,
                item=raw,
            )
            resolved_items.append(outcome.item)

        if resolved_items != attachments:
            new_metadata["attachments"] = resolved_items
            materialized.append({**row, "metadata": new_metadata})
        else:
            materialized.append(row)

    return materialized
