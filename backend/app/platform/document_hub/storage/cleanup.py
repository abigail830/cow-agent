"""Best-effort removal of hub item originals and parsed artifacts."""

from __future__ import annotations

import logging
import shutil

from app.db.models import HubItem
from app.platform.attachments.storage import is_inline_provider_file_id
from app.platform.blob.client import blob_delete, blob_delete_prefix, blob_storage_enabled
from app.platform.docstore.manifest import (
    hub_parsed_artifact_prefix,
    iter_manifest_storage_paths,
)
from app.platform.docstore.paths import scoped_parsed_artifact_path
from app.platform.docstore.scope import DocumentScope
from app.platform.document_hub.storage.originals import delete_hub_original_local
from app.platform.document_hub.storage.paths import hub_original_blob_path

logger = logging.getLogger(__name__)


def _hub_uses_platform_storage(row: HubItem) -> bool:
    return row.provider in {"inline", "platform"} or is_inline_provider_file_id(row.provider_file_id)


def blob_paths_for_hub_item(row: HubItem) -> list[str]:
    if not blob_storage_enabled() or not _hub_uses_platform_storage(row):
        return []
    paths = iter_manifest_storage_paths(row.parsed_artifact_manifest)
    original = hub_original_blob_path(row.user_id, row.id)
    if original not in paths:
        paths.insert(0, original)
    return paths


def delete_hub_item_storage(row: HubItem) -> None:
    """Remove platform-managed bytes for one hub item (original + parsed manifest)."""
    if not _hub_uses_platform_storage(row):
        return

    user_id = row.user_id
    item_id = row.id

    if blob_storage_enabled():
        for pathname in blob_paths_for_hub_item(row):
            try:
                blob_delete(pathname)
            except Exception:
                logger.warning(
                    "Failed to delete blob object %s for hub item %s",
                    pathname,
                    item_id,
                    exc_info=True,
                )
        parsed_prefix = hub_parsed_artifact_prefix(user_id, item_id)
        manifest_prefix = (row.parsed_artifact_manifest or {}).get("prefix")
        if isinstance(manifest_prefix, str) and manifest_prefix.strip():
            parsed_prefix = manifest_prefix.lstrip("/")
        try:
            blob_delete_prefix(parsed_prefix)
        except Exception:
            logger.warning(
                "Failed to delete parsed blob prefix %s for hub item %s",
                parsed_prefix,
                item_id,
                exc_info=True,
            )
        return

    delete_hub_original_local(user_id, item_id)
    scope = DocumentScope.hub(user_id, item_id)
    parsed_dir = scoped_parsed_artifact_path(scope, "content_md").parent
    if parsed_dir.is_dir():
        try:
            shutil.rmtree(parsed_dir)
        except OSError:
            logger.warning(
                "Failed to remove parsed artifacts for hub item %s",
                item_id,
                exc_info=True,
            )
