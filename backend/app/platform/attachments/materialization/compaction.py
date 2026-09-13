"""Strip heavy attachment payloads during history compaction (scoped by turn age)."""

from __future__ import annotations

from typing import Any

from app.platform.attachments.materialization.stub import format_compaction_placeholder
from app.platform.attachments.unify_lite.validation import is_unify_lite_image
from app.platform.memory.memory_config import AttachmentCompactionConfig, MemoryConfig

__all__ = [
    "compact_working_set_attachment_rows",
    "row_has_full_attachment_payload",
    "should_strip_attachment_row",
    "strip_attachment_heavy_payload",
]


def row_has_full_attachment_payload(item: dict[str, Any]) -> bool:
    if item.get("compaction_placeholder"):
        return False
    snapshot = item.get("extracted_snapshot")
    if isinstance(snapshot, dict):
        if snapshot.get("materialize_failed"):
            return False
        if snapshot.get("compacted"):
            return False
        text = str(snapshot.get("text") or "")
        if text and not text.lstrip().startswith("[Attachment compacted]"):
            return True
    if is_unify_lite_image(
        filename=str(item.get("filename") or ""),
        mime_type=str(item.get("mime_type") or ""),
    ):
        return not item.get("compaction_placeholder")
    provider_file_id = str(item.get("provider_file_id") or "")
    return bool(provider_file_id) and not item.get("compaction_placeholder")


def _user_turn_sequences(rows: list[dict[str, Any]]) -> list[int]:
    return [
        int(row.get("sequence") or 0)
        for row in rows
        if row.get("role") == "user" and row.get("message_type") == "text"
    ]


def should_strip_attachment_row(
    row: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    keep_full_turns: int,
) -> bool:
    if row.get("role") != "user" or row.get("message_type") != "text":
        return False
    metadata = row.get("metadata") or {}
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list) or not attachments:
        return False
    seq = int(row.get("sequence") or 0)
    user_seqs = _user_turn_sequences(rows)
    if seq not in user_seqs:
        return False
    idx = user_seqs.index(seq)
    threshold_idx = max(0, len(user_seqs) - keep_full_turns)
    return idx < threshold_idx


def strip_attachment_heavy_payload(
    row: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
    compaction: AttachmentCompactionConfig | None = None,
) -> dict[str, Any]:
    """Replace inline extract text / vision markers with compaction placeholders."""
    if row.get("role") != "user" or row.get("message_type") != "text":
        return row

    cfg = compaction or AttachmentCompactionConfig()
    if not cfg.enabled:
        return row
    if rows is not None and not should_strip_attachment_row(row, rows, keep_full_turns=cfg.keep_full_turns):
        return row

    metadata = dict(row.get("metadata") or {})
    attachments = metadata.get("attachments")
    if not isinstance(attachments, list) or not attachments:
        return row

    stripped: list[Any] = []
    changed = False
    for item in attachments:
        if not isinstance(item, dict):
            stripped.append(item)
            continue
        if item.get("compaction_placeholder"):
            stripped.append(dict(item))
            continue

        filename = str(item.get("filename") or "attachment")
        att_id = str(item.get("id") or "")
        mime_type = str(item.get("mime_type") or "")
        kind = "图片" if is_unify_lite_image(filename=filename, mime_type=mime_type) else "文档"
        new_item = dict(item)
        snapshot = new_item.get("extracted_snapshot")
        if isinstance(snapshot, dict) and snapshot.get("text"):
            summary = format_compaction_placeholder(
                filename=filename,
                attachment_id=att_id,
                kind=kind,
            )
            new_item["extracted_snapshot"] = {
                **snapshot,
                "text": summary[: cfg.doc_summary_chars],
                "compacted": True,
            }
            changed = True
        new_item["compaction_placeholder"] = True
        changed = True
        stripped.append(new_item)

    if not changed:
        return row
    return {**row, "metadata": {**metadata, "attachments": stripped}}


def compact_working_set_attachment_rows(
    rows: list[dict[str, Any]],
    memory_config: MemoryConfig,
) -> list[dict[str, Any]]:
    """P3-b: compact oldest in-window attachment payloads before turn trim."""
    if not memory_config.attachment_compaction.enabled:
        return rows
    return [
        strip_attachment_heavy_payload(
            row,
            rows=rows,
            compaction=memory_config.attachment_compaction,
        )
        for row in rows
    ]
