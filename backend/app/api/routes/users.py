from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import UserCreate, UserOut
from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.platform.current_user import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut, deprecated=True)
async def get_current_user_route(user: User = Depends(get_current_user)) -> UserOut:
    """Deprecated: use GET /auth/me."""
    return UserOut(id=user.id, email=user.email, name=user.name)


@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)) -> UserOut:
    """Dev-only user bootstrap when AUTH_DISABLED=true."""
    if not get_settings().auth_disabled:
        raise HTTPException(status_code=403, detail="User registration is disabled")
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(email=body.email, name=body.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut(id=user.id, email=user.email, name=user.name)
