"""Strip heavy attachment payloads during history compaction."""

from __future__ import annotations

from typing import Any

from app.platform.attachments.materialization.stub import format_compaction_placeholder
from app.platform.attachments.unify_lite.validation import is_unify_lite_image


def strip_attachment_heavy_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Replace inline extract text / vision markers with compaction placeholders."""
    if row.get("role") != "user" or row.get("message_type") != "text":
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
            new_item["extracted_snapshot"] = {
                **snapshot,
                "text": format_compaction_placeholder(
                    filename=filename,
                    attachment_id=att_id,
                    kind=kind,
                ),
                "compacted": True,
            }
            changed = True
        new_item["compaction_placeholder"] = True
        changed = True
        stripped.append(new_item)

    if not changed:
        return row
    return {**row, "metadata": {**metadata, "attachments": stripped}}
