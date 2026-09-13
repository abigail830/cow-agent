"""Attachment context materialization — snapshots, registry, replay."""

from app.platform.attachments.materialization.compaction import strip_attachment_heavy_payload
from app.platform.attachments.materialization.hash import format_content_hash, sha256_hex
from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.replay import (
    build_replay_user_message_contents,
    build_user_attachment_contents,
    count_image_data_blocks,
)
from app.platform.attachments.materialization.on_read import (
    materialize_row_attachments_sync,
)
from app.platform.attachments.materialization.snapshot import (
    enrich_metadata_with_extracted_snapshots,
    snapshot_from_extracted,
)
from app.platform.attachments.materialization.stub import (
    FORCE_REREAD_PHRASES,
    format_attachment_stub,
    user_requests_force_reread,
)

__all__ = [
    "AttachmentMaterializationRegistry",
    "FORCE_REREAD_PHRASES",
    "build_replay_user_message_contents",
    "build_user_attachment_contents",
    "count_image_data_blocks",
    "enrich_metadata_with_extracted_snapshots",
    "format_attachment_stub",
    "format_content_hash",
    "sha256_hex",
    "snapshot_from_extracted",
    "strip_attachment_heavy_payload",
    "user_requests_force_reread",
]
