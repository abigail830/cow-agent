"""Server-side auth sessions stored in Postgres."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AuthSession, User


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = get_settings()
    token = new_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.auth_session_ttl_seconds)
    db.add(
        AuthSession(
            user_id=user_id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )
    )
    await db.flush()
    return token


async def get_user_for_session_token(db: AsyncSession, token: str | None) -> User | None:
    if not token or not token.strip():
        return None
    token_hash = hash_session_token(token.strip())
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.expires_at > now,
            User.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def revoke_session_token(db: AsyncSession, token: str | None) -> None:
    if not token or not token.strip():
        return
    token_hash = hash_session_token(token.strip())
    await db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
