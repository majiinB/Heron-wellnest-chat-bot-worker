# app/config/datasource_config.py
"""
Async database configuration using SQLAlchemy 2.0 for direct SQL access.

Simplified for worker/services that:
- Query from existing tables (no ORM models)
- Perform read/write operations using raw SQL

Usage:
    from app.config.datasource_config import get_session, execute_query
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.env_config import env
from typing import AsyncGenerator


# --- Build database URL ---
def _build_db_url() -> str:
    return (
        f"postgresql+asyncpg://{env.DB_USER}:{env.DB_PASSWORD}"
        f"@{env.DB_HOST}:{env.DB_PORT}/{env.DB_NAME}"
    )


DATABASE_URL = _build_db_url()

# Global engine and session maker (will be initialized on first use)
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the async engine. Lazy initialization to avoid event loop issues."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            echo=getattr(env, "DB_ECHO", False),
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
    return _engine


def SessionLocal() -> AsyncSession:
    """Get or create the session maker. Lazy initialization."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession
        )
    return _SessionLocal()


# --- Helper to get a session (for use in workers or FastAPI deps) ---
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session