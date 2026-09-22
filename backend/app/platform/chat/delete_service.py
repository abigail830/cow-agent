"""Permanently delete a chat and every sidecar tied to that session."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat
from app.platform.chat.run_manager import get_run_manager
from app.platform.session.session_store import SessionStore

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_CHAT_FILE_ROOTS = (
    _BACKEND_ROOT / "data" / "chat-artifacts",
    _BACKEND_ROOT / "data" / "proposal-artifacts",
    _BACKEND_ROOT / "data" / "chat-attachments",
)


def _safe_chat_dir(root: Path, chat_id: uuid.UUID) -> Path:
    chat_dir = (root / str(chat_id)).resolve()
    root_resolved = root.resolve()
    if chat_dir != root_resolved and root_resolved not in chat_dir.parents:
        raise ValueError("Invalid chat file path")
    return chat_dir


def delete_chat_files(chat_id: uuid.UUID) -> list[Path]:
    """Best-effort removal of on-disk artifact / attachment folders for this chat."""
    removed: list[Path] = []
    for root in _CHAT_FILE_ROOTS:
        try:
            chat_dir = _safe_chat_dir(root, chat_id)
        except ValueError:
            logger.warning("Skipped unsafe chat file path under %s for %s", root, chat_id)
            continue
        if not chat_dir.is_dir():
            continue
        try:
            shutil.rmtree(chat_dir)
            removed.append(chat_dir)
        except OSError:
            logger.warning("Failed to remove chat files at %s", chat_dir, exc_info=True)
    return removed


async def delete_chat(db: AsyncSession, chat: Chat) -> None:
    """Cancel an active run, drop Redis/files, then delete the chat row (DB CASCADE)."""
    chat_id = chat.id
    try:
        await get_run_manager().discard_chat(chat_id)
    except Exception:
        logger.warning("Failed to discard in-flight run for chat %s", chat_id, exc_info=True)

    try:
        await SessionStore(db).delete_session(chat_id)
    except Exception:
        logger.warning("Failed to clear Redis session for chat %s", chat_id, exc_info=True)

    try:
        delete_chat_files(chat_id)
    except Exception:
        logger.warning("Failed to remove on-disk files for chat %s", chat_id, exc_info=True)

    await db.execute(delete(Chat).where(Chat.id == chat_id))
    await db.commit()
