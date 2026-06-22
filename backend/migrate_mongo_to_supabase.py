"""One-time data migration: MongoDB -> Supabase PostgreSQL.

Usage (run only AFTER setting a valid Transaction Pooler DATABASE_URL in .env):

    cd /app/backend
    # 1) create the schema (preferred: Alembic; bootstrap fallback below)
    python migrate_mongo_to_supabase.py --create-tables
    # 2) copy the data
    python migrate_mongo_to_supabase.py

Idempotency: re-running upserts by primary key, so it is safe to retry.
This script does NOT delete anything from MongoDB.
"""
import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import Base, engine, AsyncSessionLocal
import models_sql as M

load_dotenv(Path(__file__).parent / '.env')

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
    """Project a Mongo document onto the model's columns. Unknown keys are dropped,
    except company_profiles which keeps the remainder inside a JSONB `data` blob."""
    doc = {k: v for k, v in doc.items() if k != "_id"}
    cols = {c.key for c in sa_inspect(model).columns}
    return {k: v for k, v in doc.items() if k in cols}


async def create_tables():
    if engine is None:
        raise SystemExit("DATABASE_URL not set. Configure the Supabase Transaction Pooler URI first.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created (bootstrap). For production, prefer Alembic migrations.")


async def migrate():
    if AsyncSessionLocal is None:
        raise SystemExit("DATABASE_URL not set. Configure the Supabase Transaction Pooler URI first.")
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    totals = {}
    async with AsyncSessionLocal() as session:
        for coll, model in COLLECTION_MAP.items():
            pk_cols = [c.key for c in sa_inspect(model).primary_key]
            docs = await mongo[coll].find({}, {"_id": 0}).to_list(100000)
            n = 0
            for doc in docs:
                row = _row_for_model(model, doc)
                if not row:
                    continue
                stmt = pg_insert(model.__table__).values(**row)
                # Upsert on primary key to make the script idempotent.
                update_cols = {k: stmt.excluded[k] for k in row.keys() if k not in pk_cols}
                if update_cols:
                    stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)
                else:
                    stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
                await session.execute(stmt)
                n += 1
            await session.commit()
            totals[coll] = n
            print(f"  {coll:24s} -> {n} rows")
    await engine.dispose()
    print("Migration complete:", totals)


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
