# Migration MongoDB → Supabase (PostgreSQL)

## État actuel
- ✅ Dépendances installées : `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `psycopg2-binary`.
- ✅ `backend/database.py` : moteur async + session (lit `DATABASE_URL`).
- ✅ `backend/models_sql.py` : 14 modèles SQLAlchemy (JSONB pour les champs dynamiques : `attributes`, `lines`, `meta`, `snapshot`, …).
- ✅ `backend/migrate_mongo_to_supabase.py` : script de copie des données (idempotent, upsert par clé primaire, ne supprime rien dans MongoDB).
- ✅ Variables Supabase ajoutées dans `backend/.env` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`).
- ⏳ **BLOQUEUR** : `DATABASE_URL` est vide. Il faut l'URI **Transaction Pooler** (port 6543) avec le vrai mot de passe.
- ⏳ Réécriture des endpoints `server.py` (motor → pg_adapter) : à faire une fois la connexion établie et testable.

---

## Bugs corrigés dans cette version

### `database.py`
| # | Problème | Fix |
|---|---|---|
| 1 | `pool_pre_ping=False` — les connexions mortes ne sont jamais testées avant usage | `pool_pre_ping=True` |
| 2 | Le paramètre asyncpg s'appelle `prepared_statement_cache_size`, pas `statement_cache_size` — l'ancien nom était silencieusement ignoré, asyncpg continuait à utiliser des prepared statements qui crashent sur le Transaction Pooler | Clé corrigée |
| 3 | Support uniquement de `postgresql://` — Supabase émet parfois `postgres://` | Les deux schémas sont normalisés |
| 4 | Pas de SSL — Supabase impose TLS | `ssl='require'` ajouté dans `connect_args` |
| 5 | `pool_size=10 + max_overflow=5 = 15` — sature le quota Supavisor du free tier | Réduit à 8 + 2 = 10 |
| 6 | `pool_recycle=1800` — Supavisor ferme les connexions idle après ~5 min | Réduit à 600 s |

### `models_sql.py`
| # | Problème | Fix |
|---|---|---|
| 1 | `TenantUser` — pas de contrainte d'unicité sur `(tenant_id, user_id)` | `UniqueConstraint` ajouté |
| 2 | `CatalogVersion`, `Request`, `Quote` — index simple sur `status` seulement | Index composites `(tenant_id, status)` ajoutés |
| 3 | `PricingItem` — pas d'index composite `(tenant_id, catalog_id, version_id)` | Index ajouté |
| 4 | `ImportError` — pas de colonne `created_at` | Colonne `created_at` ajoutée |
| 5 | `CompanyProfile` — pas de colonnes `logo_url` / `logo_b64` (requis par `pdf_service.py`) | Colonnes ajoutées |

### `enable_rls.py`
| # | Problème | Fix |
|---|---|---|
| 1 | `engine.dispose()` appelé en fin de fonction — détruisait le moteur pour tout le processus si appelé depuis `migrate()` | Paramètre `dispose_after=False` — dispose uniquement si demandé explicitement |
| 2 | Import depuis `pg_adapter` (risque de circular import) | Import direct depuis `models_sql.ALL_MODELS` |
| 3 | `REVOKE ALL ... FROM authenticated` — le rôle n'existe pas toujours | Vérifié via `pg_roles` avant l'exécution |

### `migrate_mongo_to_supabase.py`
| # | Problème | Fix |
|---|---|---|
| 1 | `create_tables()` appelait `enable_rls()` → `engine.dispose()` → `migrate()` plantait | `enable_rls(dispose_after=False)` |
| 2 | `.to_list(100000)` — limite silencieuse, collections larges tronquées | Curseur async itéré ligne par ligne |
| 3 | Commit unique en fin de collection — pic mémoire | Commits par batch de 500 lignes |
| 4 | Un document corrompu abortait toute la collection | `try/except` par document + rollback + log |
| 5 | `MONGO_URL` / `DB_NAME` non validés avant connexion | Validation ajoutée avec `SystemExit` explicite |

### `pg_adapter.py`
| # | Problème | Fix |
|---|---|---|
| 1 | `delete_one` supprimait **toutes** les lignes correspondantes (PostgreSQL n'a pas `DELETE ... LIMIT 1`) | Sous-requête sur `ctid` pour supprimer exactement 1 ligne |
| 2 | `update_one` upsert — `INSERT` brut pouvait lever `IntegrityError` en cas de race condition | `pg_insert(...).on_conflict_do_update()` |
| 3 | `_find_list(length=None)` — retournait toutes les lignes sans limite | Plafond de sécurité à 10 000 lignes |
| 4 | `create_index` silencieusement no-op | `logger.warning()` ajouté |
| 5 | `_build_where` : colonne inconnue levait `AttributeError` opaque | `getattr(..., None)` + warning de log + skip |

---

## Pourquoi l'URI directe ne marche pas
`db.xmsxlochasjauhnxarvc.supabase.co:5432` (Direct Connection) ne résout pas en IPv4 dans cet environnement (DNS IPv6 uniquement). Il faut l'URI **Transaction Pooler** (Supavisor) :
```
postgresql://postgres.xmsxlochasjauhnxarvc:<MOT_DE_PASSE>@aws-0-<REGION>.pooler.supabase.com:6543/postgres
```
À récupérer : Supabase Dashboard → **Connect** → onglet **Transaction Pooler**.

> **Alternative** : l'URI Session Pooler (port 5432 sur le même host Supavisor) fonctionne aussi en IPv4 et supporte les prepared statements. À utiliser si vous avez besoin de prepared statements ou de transactions longues.

---

## Fichier `.env` requis

Créer `backend/.env` (ne jamais committer) :
```dotenv
# --- Supabase (Transaction Pooler) ---
DATABASE_URL=postgresql://postgres.VOTRE_REF:<MOT_DE_PASSE>@aws-0-REGION.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://VOTRE_REF.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...   # Serveur uniquement — jamais exposé au frontend

# --- MongoDB (source) ---
MONGO_URL=mongodb+srv://...
DB_NAME=blueseatra

# --- App ---
JWT_SECRET=changeme
```

---

## Étapes pour finaliser (une fois `DATABASE_URL` renseignée)
```bash
cd /app/backend

# Option A — Bootstrap rapide (dev uniquement)
python migrate_mongo_to_supabase.py --create-tables
python migrate_mongo_to_supabase.py

# Option B — Production (recommandée) : Alembic
alembic init alembic
# Editer alembic/env.py pour pointer sur database.py (voir section Alembic ci-dessous)
alembic revision --autogenerate -m "initial"
alembic upgrade head
python migrate_mongo_to_supabase.py
```

### Configuration Alembic (`alembic/env.py`)
```python
import asyncio
from alembic import context
from database import Base, DATABASE_URL  # sync URL for Alembic
import models_sql  # noqa: F401 — ensures all models are registered on Base.metadata

# Use synchronous psycopg2 URL for Alembic (replace asyncpg driver).
def get_sync_url():
    url = DATABASE_URL or ""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=get_sync_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from sqlalchemy import create_engine
    connectable = create_engine(get_sync_url())
    with connectable.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

3. Basculer la couche d'accès de `server.py` vers `pg_adapter.PGDatabase`, endpoint par endpoint, avec tests de non-régression.

---

## Sécurité
- `SUPABASE_SERVICE_ROLE_KEY` est ultra-sensible : usage serveur uniquement, jamais exposée au frontend, conservée hors dépôt Git (dans `.env`).
- RLS : activé sur toutes les tables avec une policy `deny_all`. L'application se connecte avec le rôle `postgres` (owner) qui bypasse RLS — accès complet côté backend, accès zéro via PostgREST/anon.
- SSL : `ssl='require'` forcé dans `database.py`. Toutes les connexions sont chiffrées.
- `ai_key` : valeurs chiffrées en application avec le préfixe `enc::`. Ne stocker que des clés chiffrées dans cette colonne.
