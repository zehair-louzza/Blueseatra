"""Async SQLAlchemy engine/session for Supabase PostgreSQL.

The app currently runs on MongoDB. This module is the foundation for the
Supabase (PostgreSQL) migration. It is only active once DATABASE_URL is set in
backend/.env to a valid Supabase *Transaction Pooler* URI (port 6543).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

load_dotenv(Path(__file__).parent / '.env')

DATABASE_URL = os.environ.get('DATABASE_URL')

Base = declarative_base()

engine = None
AsyncSessionLocal = None

if DATABASE_URL:
    # asyncpg driver for runtime; psycopg2 (sync) is used by Alembic separately.
    ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        pool_size=10,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=False,
        echo=False,
        connect_args={
            # CRITICAL for Supabase transaction pooler (no prepared statements).
            "statement_cache_size": 0,
            "command_timeout": 30,
        },
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db():
    """FastAPI dependency yielding an async DB session."""
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured (Supabase not connected yet).")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
