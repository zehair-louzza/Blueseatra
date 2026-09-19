"""Create the Blueseatra base tables (SQLAlchemy models) on the target database.

Used by scripts/migrate.sh on a FRESH database BEFORE applying the Supabase
SQL migrations. The base tables (users, tenants, requests, quotes, ...) are
defined by backend/models_sql.py; the SQL migrations then add the RLS
policies, the restricted role and the fournisseur module tables.

Run inside the api image (the target database is selected by DATABASE_URL):

    docker compose --env-file .env.preprod --profile app run --rm \
        -e DATABASE_URL=postgresql://user:pass@postgres:5432/targetdb \
        api python /preprod-scripts/init_schema.py
"""
import asyncio

from database import Base, engine  # engine reuses the app's own TLS/search_path handling
import models_sql  # noqa: F401  (imports register every model on Base.metadata)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    tables = sorted(Base.metadata.tables)
    print(f"init_schema: created {len(tables)} tables")
    print("init_schema: " + ", ".join(tables))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
