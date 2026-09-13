"""Per-chat attachment materialization registry for deduplicated context injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.platform.attachments.materialization.stub import user_requests_force_reread

MaterializedKind = Literal["extract_text", "vision", "hosted_file"]


@dataclass
class MaterializationEntry:
    attachment_id: str
    content_hash: str
    materialized_kind: MaterializedKind
    filename: str
    first_inject_turn_sequence: int
    last_full_inject_turn_sequence: int


class AttachmentMaterializationRegistry:
    """Track which attachments received a full inject within the current row stream."""

    def __init__(self) -> None:
        self._entries: dict[str, MaterializationEntry] = {}

    def seed_from_prior_rows(self, rows: list[dict[str, Any]]) -> None:
        """Replay prior user turns to populate registry state (send path)."""
        for row in rows:
            if row.get("role") != "user" or row.get("message_type") != "text":
                continue
            metadata = row.get("metadata") or {}
            if not metadata.get("attachments"):
                continue
            self._register_row_materializations(row, force_all_full=False)

    def should_full_materialize(
        self,
        attachment_id: str,
        content_hash: str,
        *,
        force_reread: bool = False,
    ) -> tuple[bool, bool]:
        """Return (full_materialize, hash_changed)."""
        if force_reread:
            return True, False
        entry = self._entries.get(attachment_id)
        if entry is None:
            return True, False
        if content_hash and entry.content_hash and entry.content_hash != content_hash:
            return True, True
        return False, False

    def record_full_materialize(
        self,
        *,
        attachment_id: str,
        content_hash: str,
        materialized_kind: MaterializedKind,
        filename: str,
        turn_sequence: int,
    ) -> None:
        existing = self._entries.get(attachment_id)
        if existing is None:
            self._entries[attachment_id] = MaterializationEntry(
                attachment_id=attachment_id,
                content_hash=content_hash,
                materialized_kind=materialized_kind,
                filename=filename,
                first_inject_turn_sequence=turn_sequence,
                last_full_inject_turn_sequence=turn_sequence,
            )
            return
        existing.content_hash = content_hash or existing.content_hash
        existing.last_full_inject_turn_sequence = turn_sequence
        if existing.first_inject_turn_sequence <= 0:
            existing.first_inject_turn_sequence = turn_sequence

    def first_inject_turn(self, attachment_id: str) -> int:
        entry = self._entries.get(attachment_id)
        return entry.first_inject_turn_sequence if entry else 0

    def _register_row_materializations(self, row: dict[str, Any], *, force_all_full: bool) -> None:
        metadata = row.get("metadata") or {}
        attachment_mode = str(metadata.get("attachment_mode") or "")
        turn_sequence = int(row.get("sequence") or 0)
        user_text = str(row.get("content") or "")
        force = user_requests_force_reread(user_text) if not force_all_full else False

        for item in _attachment_items(metadata):
            att_id = str(item.get("id") or "")
            if not att_id:
                continue
            if item.get("compaction_placeholder"):
                continue
            content_hash = _attachment_content_hash(item)
            kind = resolve_materialized_kind(item, attachment_mode=attachment_mode)
            full, _ = (True, False) if force_all_full else self.should_full_materialize(
                att_id, content_hash, force_reread=force
            )
            if full:
                self.record_full_materialize(
                    attachment_id=att_id,
                    content_hash=content_hash,
                    materialized_kind=kind,
                    filename=str(item.get("filename") or "attachment"),
                    turn_sequence=turn_sequence,
                )


def _attachment_items(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    raw = metadata.get("attachments")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _attachment_content_hash(item: dict[str, Any]) -> str:
    snapshot = item.get("extracted_snapshot")
    if isinstance(snapshot, dict):
        value = str(snapshot.get("content_hash") or "")
        if value:
            return value
    value = str(item.get("content_hash") or "")
    return value


def resolve_materialized_kind(item: dict[str, Any], *, attachment_mode: str) -> MaterializedKind:
    from app.platform.attachments.unify_lite.validation import is_unify_lite_image

    filename = str(item.get("filename") or "")
    mime_type = str(item.get("mime_type") or "")
    if is_unify_lite_image(filename=filename, mime_type=mime_type):
        return "vision"
    if attachment_mode == "unify_lite" and isinstance(item.get("extracted_snapshot"), dict):
        return "extract_text"
    return "hosted_file"
