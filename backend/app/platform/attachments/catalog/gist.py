"""Bootstrap and persist attachment catalog gist strings."""

from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.unify_lite.validation import is_unify_lite_image

_DOC_GIST_CHARS = 120
_WHITESPACE = re.compile(r"\s+")


def bootstrap_gist(
    *,
    filename: str,
    mime_type: str,
    snapshot_text: str | None = None,
    existing_gist: str | None = None,
) -> str:
    if existing_gist and existing_gist.strip():
        return existing_gist.strip()
    if is_unify_lite_image(filename=filename, mime_type=mime_type):
        return filename
    text = (snapshot_text or "").strip()
    if text:
        collapsed = _WHITESPACE.sub(" ", text)
        if len(collapsed) > _DOC_GIST_CHARS:
            return collapsed[: _DOC_GIST_CHARS - 1].rstrip() + "…"
        return collapsed
    return filename


async def ensure_attachment_gists(
    db: AsyncSession,
    chat_id: uuid.UUID,
    *,
    snapshot_by_id: dict[str, str] | None = None,
) -> None:
    repo = AttachmentRepository(db)
    rows = await repo.list_for_chat(chat_id)
    snapshots = snapshot_by_id or {}
    for row in rows:
        att_id = str(row.id)
        gist = bootstrap_gist(
            filename=row.filename,
            mime_type=row.mime_type,
            snapshot_text=snapshots.get(att_id),
            existing_gist=row.gist,
        )
        if gist != (row.gist or ""):
            await repo.update_gist(row.id, gist)
