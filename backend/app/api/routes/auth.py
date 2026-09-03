from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import UserOut
from app.config import get_settings
from app.db.models import DEV_USER_ID, User
from app.db.session import get_db
from app.platform.auth_sessions import create_session, revoke_session_token
from app.platform.current_user import get_current_user
from app.platform.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    settings = get_settings()
    if settings.auth_disabled:
        user = await db.get(User, DEV_USER_ID)
        if user is None:
            raise HTTPException(status_code=503, detail="Platform dev user is not seeded")
        token = await create_session(db, user.id)
        await db.commit()
        _set_session_cookie(response, token)
        return _user_out(user)

    email = body.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    from datetime import datetime, timezone

    token = await create_session(db, user.id)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    _set_session_cookie(response, token)
    return _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    await revoke_session_token(db, token)
    await db.commit()
    _clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
async def auth_me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
