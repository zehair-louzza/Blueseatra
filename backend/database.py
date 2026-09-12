"""Async SQLAlchemy engine/session for Supabase PostgreSQL.

2026-09-12 : la migration Supabase est TERMINEE. La production tourne sur
PostgreSQL (schema `blueseatra`). L'ancien avertissement "The app currently
runs on MongoDB" etait perime et a deja induit un diagnostic errone.

Ce module est aussi le point d'injection du contexte de tenant pour RLS :
voir set_current_tenant() / tenant_session() plus bas.

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
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
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


# ===========================================================================
# Contexte de tenant pour Row Level Security -- ETAPE 2/3 du durcissement
# ===========================================================================
# Constat de l'audit du 12/09/2026 : RLS est activee sur les 14 tables avec
# des politiques correctes, mais elle est INERTE sur le chemin applicatif.
# blueseatra.current_tenant() lit `request.jwt.claims`, renseigne par
# PostgREST et non par la connexion asyncpg directe, ou il vaut NULL.
#
# Ce module publie donc le tenant courant a la base, pour que les politiques
# puissent enfin s'appliquer.
#
#   ETAPE 1 (migration SQL) : current_tenant() accepte app.tenant_id en repli
#   ETAPE 2 (ce code)       : chaque session emet la valeur
#   ETAPE 3 (a venir)       : role non-proprietaire + FORCE ROW LEVEL SECURITY
#
# Tant que l'etape 3 n'est pas faite, ce code n'a AUCUN effet observable : le
# role du backend contourne RLS. C'est voulu -- on installe la plomberie
# avant d'ouvrir l'eau, pour que l'etape 3 ne soit qu'un interrupteur.
# ===========================================================================

# ContextVar et non variable globale : chaque requete asyncio a son propre
# contexte. Avec une globale, deux requetes concurrentes de deux tenants
# differents s'ecraseraient mutuellement -- exactement la fuite que ce
# mecanisme est censee empecher.
_tenant_ctx: ContextVar = ContextVar("blueseatra_tenant_id", default=None)


def set_current_tenant(tenant_id):
    """Declare le tenant de l'unite de travail courante. Rend un jeton de reset."""
    return _tenant_ctx.set(tenant_id)


def reset_current_tenant(token) -> None:
    _tenant_ctx.reset(token)


def get_current_tenant():
    return _tenant_ctx.get()


@asynccontextmanager
async def tenant_context(tenant_id):
    """Fixe le tenant pour la duree du bloc, puis restaure l'etat precedent.

    A utiliser dans toute tache de fond ou boucle de worker, qui recoivent
    leur tenant en parametre et non via une requete HTTP.
    """
    token = _tenant_ctx.set(tenant_id)
    try:
        yield
    finally:
        _tenant_ctx.reset(token)


# set_config(..., is_local => true) est l'equivalent PARAMETRABLE de
# `SET LOCAL`. On ne peut pas ecrire `SET LOCAL app.tenant_id = :t` : la
# syntaxe SET n'accepte aucun parametre lie, ce qui imposerait une
# concatenation de chaine -- donc une injection SQL sur la valeur meme qui
# porte le cloisonnement. set_config evite entierement ce piege.
_SET_TENANT = text("SELECT set_config('app.tenant_id', :tenant_id, true)")


@asynccontextmanager
async def tenant_session():
    """Session applicative, portant le tenant courant s'il est connu.

    `is_local => true` (equivalent SET LOCAL) est OBLIGATOIRE : la portee est
    la TRANSACTION. Avec un `SET` global, la valeur survivrait sur la
    connexion, et comme le pool en recycle 8 a 10, le tenant fuirait d'une
    requete vers la suivante -- un bug strictement pire que l'absence de
    cloisonnement, car intermittent et quasi impossible a reproduire. Le
    pooler de transactions Supabase (port 6543) rend ce point encore plus
    critique.

    Absence de tenant : aucune valeur n'est emise. Ce n'est pas un oubli mais
    le cas des operations SYSTEME -- _requeue_stuck_on_startup au demarrage,
    ou l'authentification qui doit lire `users` AVANT de connaitre le tenant.
    Voir le plan de l'etape 3 pour le traitement de ces chemins.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured (Supabase not connected yet).")
    async with AsyncSessionLocal() as session:
        tenant_id = _tenant_ctx.get()
        if tenant_id:
            # Emis AVANT toute requete : set_config ouvre la transaction et la
            # valeur reste valide jusqu'au commit ou rollback, donc pour
            # toutes les requetes de cette session.
            await session.execute(_SET_TENANT, {"tenant_id": tenant_id})
        yield session


def with_tenant(fn):
    """Decorateur : fixe le contexte de tenant depuis l'argument `tenant_id`.

    Destine aux taches de fond et boucles de worker, qui recoivent leur
    tenant en parametre au lieu de le tirer d'une requete HTTP. Sans lui,
    ces chemins ouvriraient des sessions sans contexte et seraient les
    premiers a casser a l'etape 3.

    Prefere a un `async with tenant_context(...)` manuel dans chaque corps
    de fonction : impossible de l'oublier au milieu d'un refactoring, et
    aucune reindentation du code existant.
    """
    import functools
    import inspect

    signature = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            lies = signature.bind_partial(*args, **kwargs)
            tenant_id = lies.arguments.get("tenant_id")
        except TypeError:
            tenant_id = None
        async with tenant_context(tenant_id):
            return await fn(*args, **kwargs)

    return wrapper
