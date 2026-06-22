"""Enable Row Level Security (RLS) on all public tables.

Why: Supabase exposes public-schema tables through PostgREST (the auto REST API
reachable with the public `anon` key). Without RLS, that API could read/write
our data. This app does NOT use PostgREST — it connects directly to Postgres
with the table-owner role, which BYPASSES RLS. So enabling RLS with no policies
denies anon/authenticated access while leaving the app fully functional.

Idempotent: safe to run multiple times. Run after creating/altering tables.

    cd /app/backend && python enable_rls.py
"""
import asyncio

from sqlalchemy import text

from database import engine
from pg_adapter import MODELS


async def enable_rls():
    if engine is None:
        raise SystemExit("DATABASE_URL not set.")
    tables = [m.__tablename__ for m in MODELS.values()]
    async with engine.begin() as conn:
        for t in tables:
            # ENABLE (not FORCE): the owner/admin role our app uses keeps full access.
            await conn.execute(text(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY;'))
            # Belt-and-suspenders: explicitly remove PostgREST role privileges.
            await conn.execute(text(f'REVOKE ALL ON public."{t}" FROM anon, authenticated;'))
            # Explicit deny-all policy: satisfies the linter ("RLS enabled, no policy")
            # while denying every non-owner role. The app's owner role bypasses RLS.
            await conn.execute(text(f'DROP POLICY IF EXISTS "deny_all" ON public."{t}";'))
            await conn.execute(text(
                f'CREATE POLICY "deny_all" ON public."{t}" FOR ALL USING (false) WITH CHECK (false);'))
            print(f"  RLS + deny-all policy + revoked privileges: public.{t}")
    await engine.dispose()
    print(f"Done. RLS hardened on {len(tables)} tables.")


if __name__ == "__main__":
    asyncio.run(enable_rls())
