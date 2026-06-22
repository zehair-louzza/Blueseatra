"""Enable Row Level Security (RLS) on all public tables.

Why: Supabase exposes public-schema tables through PostgREST (the auto REST API
reachable with the public `anon` key). Without RLS, that API could read/write
our data. This app does NOT use PostgREST — it connects directly to Postgres
with the table-owner role, which BYPASSES RLS. So enabling RLS with no policies
denies anon/authenticated access while leaving the app fully functional.

Idempotent: safe to run multiple times. Run after creating/altering tables.

    cd /app/backend && python enable_rls.py

FIXES applied:
  - No longer imports from pg_adapter (was a circular import risk).
    Now derives the table list directly from models_sql.ALL_MODELS.
  - engine.dispose() removed from enable_rls() — the caller decides when to
    dispose. Disposing inside the function crashed migrate_mongo_to_supabase.py
    when create_tables() called enable_rls() and then migrate() tried to use
    the same engine.
  - REVOKE for 'authenticated' role is now guarded — the role may not exist
    on projects that do not use Supabase Auth.
"""
import asyncio
import logging

from sqlalchemy import text

from database import engine
# FIX: use ALL_MODELS directly — avoids circular import through pg_adapter.
from models_sql import ALL_MODELS

logger = logging.getLogger(__name__)


async def enable_rls(dispose_after: bool = False):
    """Enable RLS and harden access on all application tables.

    Args:
        dispose_after: if True, call engine.dispose() when done.
                       Pass True only when this is the last DB operation in
                       the process (e.g. standalone `python enable_rls.py`).
    """
    if engine is None:
        raise SystemExit("DATABASE_URL not set.")
    tables = [m.__tablename__ for m in ALL_MODELS]
    async with engine.begin() as conn:
        # FIX: check whether the 'authenticated' role exists before revoking.
        result = await conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'authenticated'")
        )
        has_authenticated = result.scalar() is not None

        for t in tables:
            # ENABLE (not FORCE): the owner/admin role our app uses keeps full access.
            await conn.execute(text(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY;'))

            # Belt-and-suspenders: remove PostgREST anon access.
            await conn.execute(text(f'REVOKE ALL ON public."{t}" FROM anon;'))
            if has_authenticated:
                await conn.execute(text(f'REVOKE ALL ON public."{t}" FROM authenticated;'))

            # Explicit deny-all policy.
            await conn.execute(text(f'DROP POLICY IF EXISTS "deny_all" ON public."{t}";'))
            await conn.execute(text(
                f'CREATE POLICY "deny_all" ON public."{t}" FOR ALL '
                f'USING (false) WITH CHECK (false);'
            ))
            logger.info("RLS + deny-all policy + revoked privileges: public.%s", t)
            print(f"  RLS + deny-all policy + revoked privileges: public.{t}")

    # FIX: dispose only when explicitly requested (standalone run), NOT when
    # called from migrate_mongo_to_supabase.create_tables().
    if dispose_after:
        await engine.dispose()

    print(f"Done. RLS hardened on {len(tables)} tables.")


if __name__ == "__main__":
    asyncio.run(enable_rls(dispose_after=True))
