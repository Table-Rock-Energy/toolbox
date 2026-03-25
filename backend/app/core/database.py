"""Database configuration and session management."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create async engine
# For local dev: postgresql+asyncpg://user:pass@localhost:5432/toolbox
# For Supabase: postgresql+asyncpg://user:pass@host:5432/postgres
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# Sync engine/session for background threads (rrc_background.py)
# =============================================================================


def _get_sync_url() -> str:
    """Convert async database URL to sync for background threads."""
    return settings.database_url.replace("+asyncpg", "")


# Lazy sync engine (created on first use by background worker)
_sync_engine = None
_sync_session_factory = None


def get_sync_session_factory() -> sessionmaker:
    """Get or create sync session factory for background threads."""
    global _sync_engine, _sync_session_factory
    if _sync_session_factory is None:
        _sync_engine = create_engine(
            _get_sync_url(),
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
        )
        _sync_session_factory = sessionmaker(bind=_sync_engine)
    return _sync_session_factory


def get_sync_session() -> Session:
    """Get a new sync session for background thread usage."""
    factory = get_sync_session_factory()
    return factory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables (fallback when Alembic is not configured).

    Prefer `alembic upgrade head` for schema management.
    This only runs create_all if the alembic_version table does not exist.
    """
    from sqlalchemy import inspect

    async with engine.begin() as conn:
        from app.models import db_models  # noqa: F401

        def _check_and_create(sync_conn):
            inspector = inspect(sync_conn)
            if "alembic_version" not in inspector.get_table_names():
                Base.metadata.create_all(sync_conn)
                return True
            return False

        created = await conn.run_sync(_check_and_create)

    if created:
        logger.info("Database tables created via create_all (no Alembic)")
    else:
        logger.info("Alembic manages schema -- skipping create_all")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    if _sync_engine is not None:
        _sync_engine.dispose()
    logger.info("Database connections closed")
