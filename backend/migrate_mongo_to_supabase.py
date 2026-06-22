"""One-time data migration: MongoDB -> Supabase PostgreSQL.

Usage (run only AFTER setting a valid Transaction Pooler DATABASE_URL in .env):

    cd /app/backend
    # 1) create the schema (preferred: Alembic; bootstrap fallback below)
    python migrate_mongo_to_supabase.py --create-tables
    # 2) copy the data
    python migrate_mongo_to_supabase.py

Idempotency: re-running upserts by primary key, so it is safe to retry.
This script does NOT delete anything from MongoDB.

FIXES applied:
  - create_tables() no longer calls engine.dispose() via enable_rls();
    uses enable_rls(dispose_after=False) — the engine stays alive for migrate().
  - Removed hardcoded 100 000-row cap; uses async cursor iteration instead.
  - Batch commits every BATCH_SIZE rows to limit memory usage.
  - Per-document error handling: bad docs are logged and skipped, not fatal.
  - MONGO_URL / DB_NAME validated before connecting.
  - _row_for_model docstring clarified (no JSONB 'data' blob exists).
"""
import argparse
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import Base, engine, AsyncSessionLocal
import models_sql as M

load_dotenv(Path(__file__).parent / '.env')

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Commit every N rows per collection to bound memory usage.
BATCH_SIZE = 500

# Mongo collection name -> SQLAlchemy model
COLLECTION_MAP = {
    "users": M.User,
    "tenants": M.Tenant,
    "tenant_users": M.TenantUser,
    "catalogs": M.Catalog,
    "catalog_versions": M.CatalogVersion,
    "pricing_items": M.PricingItem,
    "requests": M.Request,
    "quotes": M.Quote,
    "quote_versions": M.QuoteVersion,
    "import_jobs": M.ImportJob,
    "import_errors": M.ImportError,
    "audit_logs": M.AuditLog,
    "settings_integrations": M.SettingsIntegration,
    "company_profiles": M.CompanyProfile,
}


def _row_for_model(model, doc: dict) -> dict:
    """Project a Mongo document onto the model's columns.

    Unknown keys are silently dropped — no JSONB 'data' blob is used.
    The '_id' ObjectId field is always excluded.
    """
    doc = {k: v for k, v in doc.items() if k != "_id"}
    cols = {c.key for c in sa_inspect(model).columns}
    return {k: v for k, v in doc.items() if k in cols}


async def create_tables():
    if engine is None:
        raise SystemExit("DATABASE_URL not set. Configure the Supabase Transaction Pooler URI first.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # FIX: pass dispose_after=False so the engine remains usable after this call.
    from enable_rls import enable_rls
    await enable_rls(dispose_after=False)
    print("Tables created (bootstrap) + RLS enabled. For production, prefer Alembic migrations.")


async def migrate():
    if AsyncSessionLocal is None:
        raise SystemExit("DATABASE_URL not set. Configure the Supabase Transaction Pooler URI first.")

    # FIX: validate env vars before attempting to connect.
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url:
        raise SystemExit("MONGO_URL is not set in .env")
    if not db_name:
        raise SystemExit("DB_NAME is not set in .env")

    mongo = AsyncIOMotorClient(mongo_url)[db_name]
    totals: dict[str, int] = {}
    errors: dict[str, int] = {}

    async with AsyncSessionLocal() as session:
        for coll, model in COLLECTION_MAP.items():
            pk_cols = [c.key for c in sa_inspect(model).primary_key]
            n = 0
            err = 0
            batch: list[dict] = []

            # FIX: iterate cursor instead of to_list(100000) — no row cap.
            async for doc in mongo[coll].find({}, {"_id": 0}):
                row = _row_for_model(model, doc)
                if not row:
                    continue
                batch.append(row)

                if len(batch) >= BATCH_SIZE:
                    err += await _flush_batch(session, model, pk_cols, batch)
                    n += len(batch) - err
                    batch = []

            # flush remainder
            if batch:
                batch_err = await _flush_batch(session, model, pk_cols, batch)
                err += batch_err
                n += len(batch) - batch_err

            totals[coll] = n
            errors[coll] = err
            print(f"  {coll:24s} -> {n} rows  ({err} errors)")

    await engine.dispose()
    print("Migration complete:", totals)
    if any(v for v in errors.values()):
        print("Rows skipped due to errors:", errors)


async def _flush_batch(session, model, pk_cols, rows: list[dict]) -> int:
    """Insert/upsert a batch of rows. Returns number of rows that failed."""
    failed = 0
    for row in rows:
        try:
            stmt = pg_insert(model.__table__).values(**row)
            update_cols = {k: stmt.excluded[k] for k in row if k not in pk_cols}
            if update_cols:
                stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
            await session.execute(stmt)
        except Exception as exc:
            logger.warning("Skipping bad row in %s: %s — %s", model.__tablename__, row.get("id"), exc)
            await session.rollback()
            failed += 1
            continue
    await session.commit()
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--create-tables", action="store_true", help="Bootstrap schema then exit")
    args = ap.parse_args()
    if args.create_tables:
        asyncio.run(create_tables())
    else:
        asyncio.run(migrate())


if __name__ == "__main__":
    main()
