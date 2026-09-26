"""Fire-and-forget attachment gist generation."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.config import get_settings
from app.db.session import get_async_session_factory
from app.platform.attachments.gist.service import generate_and_save_attachment_gist

logger = logging.getLogger(__name__)

_inflight: set[uuid.UUID] = set()


def schedule_attachment_gist(attachment_id: uuid.UUID) -> None:
    """Schedule gist generation after parse webhook commit (non-blocking)."""
    settings = get_settings()
    if not settings.attachment_gist_enabled:
        return
    if attachment_id in _inflight:
        return
    _inflight.add(attachment_id)
    asyncio.create_task(_generate_gist_safe(attachment_id))


async def _generate_gist_safe(attachment_id: uuid.UUID) -> None:
    try:
        await _generate_gist_for_attachment(attachment_id)
    except Exception:
        logger.exception("attachment gist generation failed attachment_id=%s", attachment_id)
    finally:
        _inflight.discard(attachment_id)


async def _generate_gist_for_attachment(attachment_id: uuid.UUID) -> None:
    factory = get_async_session_factory()
    async with factory() as session:
        await generate_and_save_attachment_gist(session, attachment_id)
        await session.commit()
