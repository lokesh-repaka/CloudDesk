"""Async Database Core — SQLAlchemy 2.0 Engine and Session Management.

Provides async engine factories, sessionmaker singletons, and FastAPI
dependency injection helpers for transactional database interactions.
Supports SQLite (local demo & testing) and PostgreSQL (cloud production).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import get_settings
from backend.app.models.entities import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Return an active AsyncEngine, initializing a singleton if not already present."""
    global _engine
    if database_url is not None:
        return create_async_engine(database_url, echo=False)

    if _engine is None:
        settings = get_settings()
        url = settings.DATABASE_URL
        # In SQLite demo mode, pass check_same_thread=False for async compatibility
        connect_args = {"check_same_thread": False} if "sqlite" in url else {}
        _engine = create_async_engine(url, echo=False, connect_args=connect_args)
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to the active engine."""
    global _session_factory
    eng = engine or get_engine()
    if engine is not None:
        return async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    if _session_factory is None:
        _session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db(engine: AsyncEngine | None = None) -> AsyncGenerator[AsyncSession]:
    """Yield an async database session with automatic commit/rollback."""
    factory = get_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding an async database session from the default engine."""
    async for session in get_db():
        yield session


async def create_tables(engine: AsyncEngine | None = None) -> None:
    """Initialize database tables from SQLAlchemy metadata (used in demo mode and testing)."""
    eng = engine or get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Cleanly dispose of the global engine singleton (used on application shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
