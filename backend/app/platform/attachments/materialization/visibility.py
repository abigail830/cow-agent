"""Visibility index — single source of truth for attachment payload recoverability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.platform.attachments.materialization.compaction import row_has_full_attachment_payload
from app.platform.memory.memory_config import MemoryConfig
from app.platform.memory.slimmer import HistoryProjection


@dataclass
class VisibilityIndex:
    """Maps attachment_id → turn sequences where a recoverable full payload exists."""

    full_inject_turns: dict[str, list[int]] = field(default_factory=dict)

    def has_full_at_turn(self, attachment_id: str, turn_sequence: int) -> bool:
        turns = self.full_inject_turns.get(attachment_id) or []
        return turn_sequence in turns

    def anchor_still_visible(self, attachment_id: str, anchor_turn: int) -> bool:
        if anchor_turn <= 0:
            return False
        return self.has_full_at_turn(attachment_id, anchor_turn)

    def register_full(self, attachment_id: str, turn_sequence: int) -> None:
        if turn_sequence <= 0:
            return
        turns = self.full_inject_turns.setdefault(attachment_id, [])
        if turn_sequence not in turns:
            turns.append(turn_sequence)


def project_rows_for_visibility(
    rows: list[dict[str, Any]],
    memory_config: MemoryConfig | None,
) -> list[dict[str, Any]]:
    """Apply Layer2 projection (slim + scoped attachment compaction) to rows."""
    if not rows:
        return []
    if memory_config is None:
        return [dict(row) for row in rows]
    if not memory_config.slim.enabled and not memory_config.attachment_compaction.enabled:
        return [dict(row) for row in rows]
    projection = HistoryProjection()
    return projection.project_rows(rows, memory_config)


def build_visibility_index(rows: list[dict[str, Any]]) -> VisibilityIndex:
    index = VisibilityIndex()
    for row in rows:
        if row.get("role") != "user" or row.get("message_type") != "text":
            continue
        turn_sequence = int(row.get("sequence") or 0)
        metadata = row.get("metadata") or {}
        attachments = metadata.get("attachments")
        if not isinstance(attachments, list):
            continue
        for item in attachments:
            if not isinstance(item, dict):
                continue
            att_id = str(item.get("id") or "")
            if not att_id:
                continue
            if row_has_full_attachment_payload(item):
                index.register_full(att_id, turn_sequence)
    return index
