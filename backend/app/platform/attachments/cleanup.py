"""Best-effort removal of attachment originals and parsed artifacts."""

from __future__ import annotations

import logging
import shutil
import uuid

from app.agent_specific.proposal.blob_client import (
    blob_delete,
    blob_delete_prefix,
    blob_storage_enabled,
)
from app.db.models import ChatAttachment
from app.platform.attachments.storage import (
    inline_attachment_blob_path,
    is_inline_provider_file_id,
)
from app.platform.docstore.manifest import iter_manifest_storage_paths, manifest_parsed_prefix
from app.platform.docstore.paths import parsed_artifact_dir

logger = logging.getLogger(__name__)

_CHAT_BLOB_PREFIXES = (
    "chat-attachments",
    "chat-artifacts",
    "proposal-artifacts",
)


def attachment_uses_platform_storage(row: ChatAttachment) -> bool:
    return row.provider == "inline" or is_inline_provider_file_id(row.provider_file_id)


def blob_paths_for_attachment(row: ChatAttachment) -> list[str]:
    """Resolve blob pathnames from DB manifest + canonical inline original path."""
    if not blob_storage_enabled() or not attachment_uses_platform_storage(row):
        return []

    paths = iter_manifest_storage_paths(row.parsed_artifact_manifest)
    original = inline_attachment_blob_path(row.chat_id, row.id)
    if original not in paths:
        paths.insert(0, original)
    return paths


def delete_attachment_storage(row: ChatAttachment) -> None:
    """Remove platform-managed bytes for one attachment (blob first, best-effort)."""
    chat_id = row.chat_id
    attachment_id = row.id

    if not attachment_uses_platform_storage(row):
        return

    if blob_storage_enabled():
        for pathname in blob_paths_for_attachment(row):
            try:
                blob_delete(pathname)
            except Exception:
                logger.warning(
                    "Failed to delete blob object %s for attachment %s",
                    pathname,
                    attachment_id,
                    exc_info=True,
                )
        parsed_prefix = manifest_parsed_prefix(
            row.parsed_artifact_manifest,
            chat_id=chat_id,
            attachment_id=attachment_id,
        )
        try:
            blob_delete_prefix(parsed_prefix)
        except Exception:
            logger.warning(
                "Failed to delete parsed blob prefix %s for attachment %s",
                parsed_prefix,
                attachment_id,
                exc_info=True,
            )
        return

    from app.platform.attachments.storage import delete_inline_attachment

    try:
        delete_inline_attachment(chat_id, attachment_id)
    except OSError:
        logger.warning(
            "Failed to remove inline attachment %s for chat %s",
            attachment_id,
            chat_id,
            exc_info=True,
        )

    parsed_dir = parsed_artifact_dir(chat_id, attachment_id)
    if parsed_dir.is_dir():
        try:
            shutil.rmtree(parsed_dir)
        except OSError:
            logger.warning(
                "Failed to remove parsed artifacts for attachment %s in chat %s",
                attachment_id,
                chat_id,
                exc_info=True,
            )


def delete_chat_blob_storage(chat_id: uuid.UUID) -> None:
    """Delete all blob objects under known chat-scoped prefixes."""
    if not blob_storage_enabled():
        return
    chat_key = str(chat_id)
    for root in _CHAT_BLOB_PREFIXES:
        prefix = f"{root}/{chat_key}"
        try:
            blob_delete_prefix(prefix)
        except Exception:
            logger.warning("Failed to delete blob prefix %s", prefix, exc_info=True)
