"""Format attachment catalog blocks for ContextProvider injection."""

from __future__ import annotations

from app.platform.attachments.run_state import AttachmentRecord
from app.platform.attachments.unify_lite.validation import is_unify_lite_image


def attachment_kind(record: AttachmentRecord) -> str:
    if is_unify_lite_image(filename=record.filename, mime_type=record.mime_type):
        return "image"
    return "doc"


def format_catalog_block(records: list[AttachmentRecord]) -> str:
    if not records:
        return ""
    sorted_records = sorted(records, key=lambda item: str(item.attachment_id))
    lines = [
        "[Chat attachments — availability index; see attachment facts + budget for visibility and costs]",
    ]
    for record in sorted_records:
        gist = (record.gist or record.filename).replace("\n", " ").strip()
        kind = attachment_kind(record)
        lines.append(
            f"- id={record.attachment_id} filename={record.filename} "
            f'gist="{gist}" kind={kind}'
        )
    return "\n".join(lines)
