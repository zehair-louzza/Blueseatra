"""Async SQLAlchemy engine/session for Supabase PostgreSQL.

The app currently runs on MongoDB. This module is the foundation for the
Supabase (PostgreSQL) migration. It is only active once DATABASE_URL is set in
backend/.env to a valid Supabase *Transaction Pooler* URI (port 6543).

FIXES applied:
  - pool_pre_ping=True  (was False — dead connections were never tested)
  - asyncpg connect_args key is `prepared_statement_cache_size` (not `statement_cache_size`)
  - Handle both 'postgres://' and 'postgresql://' URI schemes (Supabase issues either)
  - Added ssl='require' to connect_args (Supabase mandates TLS)
  - Reduced pool_size to 8 + max_overflow=2 to stay under the free-tier
    Supavisor limit of 15 client connections per service.
  - pool_timeout lowered to 20 s (30 s was too long for a web request cycle)
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

load_dotenv(Path(__file__).parent / '.env')

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

# Schema that holds the Blueseatra tables. Tables were created in a dedicated
# 'blueseatra' schema (not 'public'). asyncpg is told to use it via search_path
# so the existing SQLAlchemy models (which reference unqualified table names)
# resolve correctly. Override with DB_SCHEMA if you ever move the tables.
DB_SCHEMA = os.environ.get('DB_SCHEMA', 'blueseatra').strip() or 'blueseatra'

Base = declarative_base()

engine = None
AsyncSessionLocal = None


def _build_connect_args(url: str) -> dict:
    args = {
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "command_timeout": 30,
        "server_settings": {"search_path": f"{DB_SCHEMA},public"},
    }
    # Supabase impose TLS, mais un PostgreSQL LOCAL (tests) n'a pas de SSL.
    if not any(h in url for h in ("localhost", "127.0.0.1")):
        args["ssl"] = "require"
    return args


if DATABASE_URL:
    # FIX: support both 'postgres://' (Supabase default) and 'postgresql://'.
    _url = DATABASE_URL
    if _url.startswith('postgres://'):
        _url = 'postgresql' + _url[len('postgres'):]
    # asyncpg driver for runtime; psycopg2 (sync) is used by Alembic separately.
    ASYNC_DATABASE_URL = _url.replace('postgresql://', 'postgresql+asyncpg://', 1)

    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        # FIX: pool_size=8 + max_overflow=2 = 10 max connections.
        # Supabase free tier Supavisor transaction mode default pool limit = 15.
        # Keeping 10 leaves headroom for other services (PostgREST, Storage, etc.).
        pool_size=8,
        max_overflow=2,
        pool_timeout=20,
        pool_recycle=600,        # recycle connections every 10 min (Supavisor drops idle after ~5 min)
        # FIX: pool_pre_ping=True so SQLAlchemy tests connections before handing them out.
        # Without this, stale / recycled connections crash on first use.
        pool_pre_ping=True,
        echo=False,
        connect_args=_build_connect_args(_url),
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
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
