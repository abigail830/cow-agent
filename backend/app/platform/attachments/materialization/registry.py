"""Per-chat attachment materialization registry for deduplicated context injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.platform.attachments.materialization.compaction import row_has_full_attachment_payload
from app.platform.attachments.materialization.stub import user_requests_force_reread
from app.platform.attachments.materialization.visibility import VisibilityIndex, project_rows_for_visibility
from app.platform.memory.memory_config import AttachmentPullConfig, MemoryConfig

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

    def get_entry(self, attachment_id: str) -> MaterializationEntry | None:
        return self._entries.get(attachment_id)

    def seed_from_prior_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        memory_config: MemoryConfig | None = None,
        pull_config: AttachmentPullConfig | None = None,
    ) -> None:
        """Replay prior user turns to populate registry state (send path)."""
        from app.platform.attachments.materialization.plan import MaterializationAction, compute_attachment_plan

        projected = project_rows_for_visibility(rows, memory_config)
        visibility = VisibilityIndex()
        pull = pull_config or (memory_config.attachment_pull if memory_config else AttachmentPullConfig(enabled=False))
        for row in projected:
            if row.get("role") != "user" or row.get("message_type") != "text":
                continue
            metadata = row.get("metadata") or {}
            items = _attachment_items(metadata)
            if not items:
                continue
            turn_sequence = int(row.get("sequence") or 0)
            user_text = str(row.get("content") or "")
            plan = compute_attachment_plan(
                items=items,
                registry=self,
                visibility=visibility,
                user_text=user_text,
                turn_sequence=turn_sequence,
                pull_config=pull,
            )
            for item, plan_item in zip(_dedupe_items(items), plan):
                if plan_item.action != MaterializationAction.FULL:
                    continue
                if item.get("compaction_placeholder"):
                    continue
                if not row_has_full_attachment_payload(item):
                    continue
                att_id = str(item.get("id") or "")
                if not att_id:
                    continue
                self.record_full_materialize(
                    attachment_id=att_id,
                    content_hash=_attachment_content_hash(item),
                    materialized_kind=resolve_materialized_kind(
                        item,
                        attachment_mode=str(metadata.get("attachment_mode") or ""),
                    ),
                    filename=str(item.get("filename") or "attachment"),
                    turn_sequence=turn_sequence,
                )
                visibility.register_full(att_id, turn_sequence)

    def should_full_materialize(
        self,
        attachment_id: str,
        content_hash: str,
        *,
        force_reread: bool = False,
        visibility: VisibilityIndex | None = None,
    ) -> tuple[bool, bool]:
        """Return (full_materialize, hash_changed)."""
        if force_reread:
            return True, False
        entry = self._entries.get(attachment_id)
        if entry is None:
            return True, False
        if content_hash and entry.content_hash and entry.content_hash != content_hash:
            return True, True
        if visibility is not None:
            anchor = entry.last_full_inject_turn_sequence
            if not visibility.anchor_still_visible(attachment_id, anchor):
                return True, False
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

    def last_full_inject_turn(self, attachment_id: str) -> int:
        entry = self._entries.get(attachment_id)
        return entry.last_full_inject_turn_sequence if entry else 0

    def first_inject_turn(self, attachment_id: str) -> int:
        entry = self._entries.get(attachment_id)
        return entry.first_inject_turn_sequence if entry else 0


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        att_id = str(item.get("id") or "")
        if att_id and att_id in seen:
            continue
        if att_id:
            seen.add(att_id)
        deduped.append(item)
    return deduped


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
    from app.platform.attachments.unify_lite.validation import is_unify_lite_image, is_unify_lite_text

    filename = str(item.get("filename") or "")
    mime_type = str(item.get("mime_type") or "")
    if is_unify_lite_image(filename=filename, mime_type=mime_type):
        return "vision"
    snapshot = item.get("extracted_snapshot")
    if isinstance(snapshot, dict) and is_unify_lite_text(filename=filename, mime_type=mime_type):
        return "extract_text"
    if attachment_mode == "unify_lite" and isinstance(snapshot, dict):
        return "extract_text"
    return "hosted_file"
