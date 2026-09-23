from __future__ import annotations

import uuid

from app.db.models import ChatAttachment
from app.platform.docstore.models import PARSE_READY_STATUSES


def assert_parse_ready(rows: list[ChatAttachment]) -> None:
    for row in rows:
        status = str(getattr(row, "parse_status", None) or "ready")
        if status not in PARSE_READY_STATUSES:
            raise ValueError(f"Attachment still parsing: {row.filename}")


def assert_parse_ready_ids(rows: list[ChatAttachment], attachment_ids: list[uuid.UUID]) -> None:
    if not attachment_ids:
        return
    assert_parse_ready(rows)
