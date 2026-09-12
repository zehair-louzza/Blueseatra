"""MongoDB(motor)-compatible adapter backed by Supabase PostgreSQL (SQLAlchemy).

Exposes a tiny subset of the motor API actually used by server.py
(find/find_one/insert_one/insert_many/update_one/update_many/delete_one/
delete_many/count_documents/create_index) so the application code does not
need to change. Mongo filter operators supported: equality, $in, $ne, $nin.

FIXES applied:
  - _build_where: unknown operators now raise ValueError with details (was already
    raising, but the message is improved; add a fallback `false` option per-call).
  - delete_one: PostgreSQL has no DELETE ... LIMIT 1 syntax. Fixed with a
    subquery on ctid to delete exactly one matching row.
  - update_one upsert: uses pg_insert(...).on_conflict_do_update to avoid
    IntegrityError race condition when a concurrent INSERT wins.
  - find_one: sort parameter signature aligned with motor (list of (field, dir) tuples).
  - _find_list: default length cap of 10 000 when None is passed (safety guard).
  - create_index: now logs a warning instead of silently returning None.
"""
import logging
from sqlalchemy import (and_, asc, delete as sa_delete, func, insert as sa_insert,
                        inspect as sa_inspect, select, true, update as sa_update)
from sqlalchemy import desc as sa_desc
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import auth_session, engine, is_system_context, tenant_session
import models_sql as M

logger = logging.getLogger(__name__)

# Safety cap: to_list(None) will return at most this many rows.
_MAX_ROWS = 10_000


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
    # Module Fournisseur. Sans ces entrees, pg_adapter leve
    # AttributeError("Unknown collection") des le premier import de tarif.
    "suppliers": M.Supplier,
    "supplier_offers": M.SupplierOffer,
    "canonical_products": M.CanonicalProduct,
}

# Tables du chemin d'AUTHENTIFICATION -- etape 3/3 du durcissement RLS.
#
# Elles resteront sur le role privilegie (moteur AUTH) meme apres que les
# tables metier soient passees sous FORCE ROW LEVEL SECURITY avec un role
# restreint. Raison : get_current() et login() les lisent AVANT qu'un
# tenant soit determine -- c'est meme l'objet de la lecture.
#
# Cette liste est la SEULE source de verite du routage. Toute nouvelle
# table d'authentification doit y etre ajoutee explicitement ; par defaut,
# une table absente de cette liste passe par le chemin METIER restreint,
# ce qui est le choix sur par defaut.
TABLES_AUTH = frozenset({"users", "tenants", "tenant_users"})


def _session_pour(nom_table: str):
    """Route vers auth_session() ou tenant_session() selon la table et le contexte.

    Deux conditions independantes envoient vers le moteur AUTH :
      1. la table appartient au chemin d'authentification (TABLES_AUTH) ;
      2. l'appelant a explicitement marque l'operation SYSTEME
         (voir database.system_context / with_system_context), pour les
         taches transverses comme _requeue_stuck_on_startup qui balaient
         volontairement tous les tenants.

    Tout le reste passe par tenant_session(), qui emet app.tenant_id par
    transaction -- c'est le chemin qui sera couvert par FORCE RLS.
    """
    if nom_table in TABLES_AUTH or is_system_context():
        return auth_session()
    return tenant_session()


def _cols(model):
    return {c.key for c in sa_inspect(model).columns}


def _to_dict(model, obj):
    return {c.key: getattr(obj, c.key) for c in sa_inspect(model).columns}


def _build_where(model, flt):
    conds = []
    for key, val in (flt or {}).items():
        col = getattr(model, key, None)
        if col is None:
            # SECURITE (2026-09-12) : ceci levait autrefois un simple
            # logger.warning() suivi d'un `continue`, donc la condition etait
            # SILENCIEUSEMENT retiree du filtre.
            #
            # Consequence : une faute de frappe ('tenantId', 'tenant'), ou le
            # renommage d'une colonne sans mise a jour des appelants, retirait
            # le filtre de cloisonnement et la requete renvoyait les lignes de
            # TOUS LES TENANTS -- sans erreur, sans trace, avec un HTTP 200.
            # Si toutes les cles etaient inconnues, le `return ... else true()`
            # plus bas renvoyait la table entiere.
            #
            # Un WARNING dans les logs n'est pas un mecanisme de securite :
            # personne ne lit les warnings d'une application en production.
            # On echoue donc bruyamment plutot que de fuir en silence.
            #
            # Verifie avant activation : les 110 filtres litteraux de server.py
            # et son unique filtre dynamique (L1300) n'utilisent que des
            # colonnes reelles. Ce durcissement ne change donc rien pour le
            # code correct.
            raise ValueError(
                f"_build_where: colonne '{key}' inconnue sur "
                f"{model.__tablename__}. Filtre refuse : un filtre partiel "
                f"peut exposer les donnees d'autres tenants. "
                f"Colonnes valides : {sorted(_cols(model))}"
            )
        if isinstance(val, dict):
            if "$in" in val:
                conds.append(col.in_(val["$in"]))
            elif "$nin" in val:
                conds.append(~col.in_(val["$nin"]))
            elif "$ne" in val:
                conds.append(col.isnot(None) if val["$ne"] is None else col != val["$ne"])
            else:
                raise ValueError(
                    f"Unsupported Mongo operator in filter for column '{key}': {val}. "
                    f"Supported: $in, $nin, $ne."
                )
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
        # FIX: cap unbounded queries at _MAX_ROWS.
        limit = length if (length is not None and length <= _MAX_ROWS) else _MAX_ROWS
        async with _session_pour(self.name) as s:
            stmt = select(self.model).where(_build_where(self.model, flt))
            for field, direction in (sort or []):
                col = getattr(self.model, field)
                stmt = stmt.order_by(sa_desc(col) if direction < 0 else asc(col))
            stmt = stmt.limit(limit)
            res = await s.execute(stmt)
            return [_project(_to_dict(self.model, o), projection) for o in res.scalars().all()]

    async def find_one(self, flt=None, projection=None, sort=None):
        # FIX: sort accepts a list of (field, direction) tuples, matching motor's API.
        async with _session_pour(self.name) as s:
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
        async with _session_pour(self.name) as s:
            await s.execute(sa_insert(self.model.__table__).values(**row))
            await s.commit()
        return doc.get("id")

    async def insert_many(self, docs):
        docs = list(docs)
        if not docs:
            return
        cols = _cols(self.model)
        rows = [{k: v for k, v in d.items() if k in cols} for d in docs]
        async with _session_pour(self.name) as s:
            await s.execute(sa_insert(self.model.__table__), rows)
            await s.commit()

    async def update_one(self, flt, update, upsert=False):
        cols = _cols(self.model)
        set_ = {k: v for k, v in (update.get("$set") or {}).items() if k in cols}
        async with _session_pour(self.name) as s:
            rowcount = 0
            if set_:
                res = await s.execute(
                    sa_update(self.model).where(_build_where(self.model, flt)).values(**set_))
                rowcount = res.rowcount or 0
            if rowcount == 0 and upsert:
                row = {k: v for k, v in (flt or {}).items() if not isinstance(v, dict)}
                row.update(set_)
                row = {k: v for k, v in row.items() if k in cols}
                # FIX: use ON CONFLICT DO UPDATE to handle concurrent INSERT race.
                pk_cols = [c.key for c in sa_inspect(self.model).primary_key]
                stmt = pg_insert(self.model.__table__).values(**row)
                update_cols = {k: stmt.excluded[k] for k in row if k not in pk_cols}
                if update_cols:
                    stmt = stmt.on_conflict_do_update(
                        index_elements=pk_cols, set_=update_cols)
                else:
                    stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
                await s.execute(stmt)
                rowcount = 1
            await s.commit()
            return UpdateResult(matched_count=rowcount)

    async def update_many(self, flt, update):
        cols = _cols(self.model)
        set_ = {k: v for k, v in (update.get("$set") or {}).items() if k in cols}
        if not set_:
            return
        async with _session_pour(self.name) as s:
            await s.execute(sa_update(self.model).where(_build_where(self.model, flt)).values(**set_))
            await s.commit()

    async def delete_one(self, flt):
        """Delete exactly one matching row via the primary key (not ctid).

        ``table.c.ctid`` is not a mapped column, so the previous subquery
        raised KeyError and the browser saw a dropped connection / CORS miss.
        """
        async with _session_pour(self.name) as s:
            pk_cols = [c.key for c in sa_inspect(self.model).primary_key]
            where = _build_where(self.model, flt)
            if len(pk_cols) == 1:
                pkcol = getattr(self.model, pk_cols[0])
                sub = select(pkcol).where(where).limit(1).scalar_subquery()
                await s.execute(sa_delete(self.model).where(pkcol == sub))
            else:
                await s.execute(sa_delete(self.model).where(where))
            await s.commit()

    async def delete_many(self, flt):
        async with _session_pour(self.name) as s:
            await s.execute(sa_delete(self.model).where(_build_where(self.model, flt)))
            await s.commit()

    async def count_documents(self, flt=None):
        async with _session_pour(self.name) as s:
            res = await s.execute(
                select(func.count()).select_from(self.model).where(_build_where(self.model, flt)))
            return res.scalar() or 0

    async def create_index(self, *args, **kwargs):
        # Indexes are declared on the SQLAlchemy models / created at migration time.
        # FIX: log a warning so callers in server.py are aware this is a no-op.
        logger.warning(
            "create_index called on pg_adapter._Collection('%s') — "
            "indexes must be defined in models_sql.py and applied via migration.",
            self.name,
        )
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
