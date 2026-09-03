"""Resolve the authenticated platform user from cookie session or dev bypass."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import DEV_USER_ID, Chat, User
from app.db.session import get_db
from app.platform.auth_sessions import get_user_for_session_token

__all__ = ["get_current_user", "get_current_user_id", "get_owned_chat"]


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    settings = get_settings()
    if settings.auth_disabled:
        user = await db.get(User, DEV_USER_ID)
        if user is None:
            raise HTTPException(status_code=503, detail="Platform dev user is not seeded")
        return user

    token = request.cookies.get(settings.auth_cookie_name)
    user = await get_user_for_session_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_current_user_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    return user.id


async def get_owned_chat(
    chat_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Chat:
    chat = await db.get(Chat, chat_id)
    if chat is None or chat.user_id != user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat
