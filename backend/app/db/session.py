from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

_engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


def init_db_engine() -> None:
    global _engine, async_session_factory
    settings = get_settings()
    _engine = create_async_engine(
        settings.async_database_url,
        connect_args=settings.async_database_connect_args,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def check_db_connection() -> bool:
    if async_session_factory is None:
        init_db_engine()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return True


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    if async_session_factory is None:
        init_db_engine()
    assert async_session_factory is not None
    return async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    async with factory() as session:
        yield session
