# Migration MongoDB → Supabase (PostgreSQL)

## État actuel
- ✅ Dépendances installées : `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `psycopg2-binary`.
- ✅ `backend/database.py` : moteur async + session (lit `DATABASE_URL`).
- ✅ `backend/models_sql.py` : 14 modèles SQLAlchemy (JSONB pour les champs dynamiques : `attributes`, `lines`, `meta`, `snapshot`, …).
- ✅ `backend/migrate_mongo_to_supabase.py` : script de copie des données (idempotent, upsert par clé primaire, ne supprime rien dans MongoDB).
- ✅ Variables Supabase ajoutées dans `backend/.env` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`).
- ⏳ **BLOQUEUR** : `DATABASE_URL` est vide. Il faut l'URI **Transaction Pooler** (port 6543) avec le vrai mot de passe.
- ⏳ Réécriture des endpoints `server.py` (motor → SQLAlchemy) : à faire une fois la connexion établie et testable.

## Pourquoi l'URI fournie ne marche pas
`db.xmsxlochasjauhnxarvc.supabase.co:5432` (Direct Connection) ne résout pas en IPv4 dans cet environnement (testé : DNS échoue). Il faut l'URI Pooler :
```
postgresql://postgres.xmsxlochasjauhnxarvc:<MOT_DE_PASSE>@aws-0-<REGION>.pooler.supabase.com:6543/postgres
```
À récupérer : Supabase Dashboard → **Connect** → onglet **Transaction Pooler**.

## Étapes pour finaliser (une fois `DATABASE_URL` renseignée)
```bash
cd /app/backend
# 1. Créer le schéma (bootstrap)
python migrate_mongo_to_supabase.py --create-tables
# 2. Copier les données existantes depuis MongoDB
python migrate_mongo_to_supabase.py
```
3. Basculer la couche d'accès de `server.py` vers SQLAlchemy (repository pattern), endpoint par endpoint, avec tests de non-régression.
4. (Recommandé production) Mettre en place Alembic pour le versionnage du schéma.

## Sécurité
- `SUPABASE_SERVICE_ROLE_KEY` est ultra-sensible : usage serveur uniquement, jamais exposée au frontend, conservée hors dépôt Git (dans `.env`).
- RLS : désactivé par défaut sur les nouvelles tables. Comme on garde l'auth JWT applicative (et non Supabase Auth), laisser RLS désactivé OU ajouter des policies permissives côté Supabase.
