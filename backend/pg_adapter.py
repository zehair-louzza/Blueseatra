"""MongoDB(motor)-compatible adapter backed by Supabase PostgreSQL (SQLAlchemy).

Exposes a tiny subset of the motor API actually used by server.py
(find/find_one/insert_one/insert_many/update_one/update_many/delete_one/
delete_many/count_documents/create_index) so the application code does not
need to change. Mongo filter operators supported: equality, $in, $ne, $nin.
"""
from sqlalchemy import (and_, asc, delete as sa_delete, func, insert as sa_insert,
                        inspect as sa_inspect, select, true, update as sa_update)
from sqlalchemy import desc as sa_desc
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import AsyncSessionLocal, engine
import models_sql as M


class UpdateResult:
    """Mock motor UpdateResult for compatibility."""
    def __init__(self, matched_count, modified_count=None):
        self.matched_count = matched_count
        self.modified_count = modified_count if modified_count is not None else matched_count


MODELS = {
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


def _cols(model):
    return {c.key for c in sa_inspect(model).columns}


def _to_dict(model, obj):
    return {c.key: getattr(obj, c.key) for c in sa_inspect(model).columns}


def _build_where(model, flt):
    conds = []
    for key, val in (flt or {}).items():
        col = getattr(model, key)
        if isinstance(val, dict):
            if "$in" in val:
                conds.append(col.in_(val["$in"]))
            elif "$nin" in val:
                conds.append(~col.in_(val["$nin"]))
            elif "$ne" in val:
                conds.append(col.isnot(None) if val["$ne"] is None else col != val["$ne"])
            else:
                raise ValueError(f"Unsupported operator in filter: {val}")
        else:
            conds.append(col == val)
    return and_(*conds) if conds else true()


def _project(d, projection):
    if not projection:
        return d
    inc = {k for k, v in projection.items() if v == 1 and k != "_id"}
    if inc:
        return {k: v for k, v in d.items() if k in inc}
    exc = {k for k, v in projection.items() if v == 0}
    if exc:
        return {k: v for k, v in d.items() if k not in exc}
    return d


class _Cursor:
    def __init__(self, coll, flt, projection):
        self._coll = coll
        self._flt = flt
        self._projection = projection
        self._sort = None

    def sort(self, field, direction=1):
        self._sort = [(field, direction)]
        return self

    async def to_list(self, length=None):
        return await self._coll._find_list(self._flt, self._projection, self._sort, length)


class _Collection:
    def __init__(self, name, model):
        self.name = name
        self.model = model

    def find(self, flt=None, projection=None):
        return _Cursor(self, flt, projection)

    async def _find_list(self, flt, projection, sort, length):
        async with AsyncSessionLocal() as s:
            stmt = select(self.model).where(_build_where(self.model, flt))
            for field, direction in (sort or []):
                col = getattr(self.model, field)
                stmt = stmt.order_by(sa_desc(col) if direction < 0 else asc(col))
            if length:
                stmt = stmt.limit(length)
            res = await s.execute(stmt)
            return [_project(_to_dict(self.model, o), projection) for o in res.scalars().all()]

    async def find_one(self, flt=None, projection=None, sort=None):
        async with AsyncSessionLocal() as s:
            stmt = select(self.model).where(_build_where(self.model, flt))
            for field, direction in (sort or []):
                col = getattr(self.model, field)
                stmt = stmt.order_by(sa_desc(col) if direction < 0 else asc(col))
            stmt = stmt.limit(1)
            res = await s.execute(stmt)
            o = res.scalar_one_or_none()
            return _project(_to_dict(self.model, o), projection) if o else None

    async def insert_one(self, doc):
        cols = _cols(self.model)
        row = {k: v for k, v in doc.items() if k in cols}
        async with AsyncSessionLocal() as s:
            await s.execute(sa_insert(self.model.__table__).values(**row))
            await s.commit()
        return doc.get("id")

    async def insert_many(self, docs):
        docs = list(docs)
        if not docs:
            return
        cols = _cols(self.model)
        rows = [{k: v for k, v in d.items() if k in cols} for d in docs]
        async with AsyncSessionLocal() as s:
            await s.execute(sa_insert(self.model.__table__), rows)
            await s.commit()

    async def update_one(self, flt, update, upsert=False):
        cols = _cols(self.model)
        set_ = {k: v for k, v in (update.get("$set") or {}).items() if k in cols}
        async with AsyncSessionLocal() as s:
            rowcount = 0
            if set_:
                res = await s.execute(
                    sa_update(self.model).where(_build_where(self.model, flt)).values(**set_))
                rowcount = res.rowcount or 0
            if rowcount == 0 and upsert:
                row = {k: v for k, v in (flt or {}).items() if not isinstance(v, dict)}
                row.update(set_)
                row = {k: v for k, v in row.items() if k in cols}
                await s.execute(pg_insert(self.model.__table__).values(**row))
                rowcount = 1
            await s.commit()
            return UpdateResult(matched_count=rowcount)

    async def update_many(self, flt, update):
        cols = _cols(self.model)
        set_ = {k: v for k, v in (update.get("$set") or {}).items() if k in cols}
        if not set_:
            return
        async with AsyncSessionLocal() as s:
            await s.execute(sa_update(self.model).where(_build_where(self.model, flt)).values(**set_))
            await s.commit()

    async def delete_one(self, flt):
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(self.model).where(_build_where(self.model, flt)))
            await s.commit()

    async def delete_many(self, flt):
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(self.model).where(_build_where(self.model, flt)))
            await s.commit()

    async def count_documents(self, flt=None):
        async with AsyncSessionLocal() as s:
            res = await s.execute(
                select(func.count()).select_from(self.model).where(_build_where(self.model, flt)))
            return res.scalar() or 0

    async def create_index(self, *args, **kwargs):
        # Indexes are declared on the SQLAlchemy models / created at migration time.
        return None


class PGDatabase:
    """Drop-in replacement for `motor` database object (db.<collection> / db[<collection>])."""

    def _collection(self, name):
        model = MODELS.get(name)
        if model is None:
            raise AttributeError(f"Unknown collection: {name}")
        return _Collection(name, model)

    def __getattr__(self, name):
        return self._collection(name)

    def __getitem__(self, name):
        return self._collection(name)

    async def dispose(self):
        if engine is not None:
            await engine.dispose()
