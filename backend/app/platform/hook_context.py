"""Runtime context passed when building hook middleware."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.platform.session_store import SessionStore


@dataclass(frozen=True)
class HookBuildContext:
    db: AsyncSession | None = None
    chat_id: uuid.UUID | None = None
    session_store: SessionStore | None = None
