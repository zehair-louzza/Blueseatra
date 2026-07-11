# Déploiement Blueseatra — Frontend (Hostinger) + Backend (Supabase)

Ce document récapitule la configuration mise en place et les étapes pour
déployer l'application.

## Architecture

```
Navigateur ──(REACT_APP_BACKEND_URL)/api──▶  Backend FastAPI  ──(DATABASE_URL)──▶  Supabase Postgres
   (React/CRA build statique)                 (Python)                              schéma "blueseatra"
```

- Le **frontend** est une SPA React (Create React App + CRACO) servie en statique.
  Il appelle **uniquement le backend** via `src/lib/api.js`
  (`${REACT_APP_BACKEND_URL}/api/...`). Auth maison : token `bs_token` en localStorage.
- Le **backend** (FastAPI) détient les identifiants Supabase et parle à Postgres
  via un adaptateur compatible Mongo (`pg_adapter.py` + SQLAlchemy/asyncpg).
- Les **14 tables** vivent dans le schéma dédié **`blueseatra`** (et non `public`).

## Ce qui a été fait

1. **`frontend/package.json`** réparé (JSON invalide : virgule manquante ;
   `@supabase/supabase-js` déplacé dans `dependencies`). Le build passe désormais.
2. **`frontend/public/.htaccess`** ajouté → routing React Router sur Apache/Hostinger
   (plus de 404 au rafraîchissement) + cache des assets.
3. **`frontend/src/db.js`** supprimé (code mort, jamais importé, plantait au
   chargement avec `createClient(undefined, undefined)` sur une table inexistante).
4. **14 tables créées dans Supabase** (schéma `blueseatra`) avec UUID, JSONB,
   index composites et contraintes, d'après `backend/models_sql.py`.
5. **RLS activé** sur les 14 tables + policies tenant-scoped (`tenant_id` lu dans
   le claim JWT via `blueseatra.current_tenant()`). La table `users` est verrouillée
   (accès service_role uniquement, car elle contient `password_hash`).
6. **`backend/database.py`** patché : la connexion force `search_path=blueseatra,public`
   (via `DB_SCHEMA`), donc les modèles SQLAlchemy non qualifiés trouvent les tables.
7. **`.env.example`** ajoutés côté frontend et backend.

## Étape 1 — Frontend (Hostinger, upload manuel, racine du domaine)

```bash
cd frontend
cp .env.example .env          # puis renseigner REACT_APP_BACKEND_URL
yarn install
yarn build
```

- Uploadez le **contenu** de `frontend/build/` directement dans `public_html/`
  (pas le dossier `build/` lui-même : `index.html` doit être à la racine).
- Le `.htaccess` est inclus automatiquement dans le build.

## Étape 2 — Backend + base Supabase

1. Récupérez la **Transaction Pooler URI** (port 6543) :
   Supabase Dashboard → Project Settings → Database → Connection string → *Transaction pooler*.
   Format :
   ```
   postgresql://postgres.umoayrslyezwbbazpbdl:[MOT-DE-PASSE]@aws-0-eu-west-3.pooler.supabase.com:6543/postgres
   ```
2. `cd backend && cp .env.example .env`, puis renseignez `DATABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`, etc.
3. (Migration des données existantes depuis MongoDB, optionnel)
   ```bash
   python migrate_mongo_to_supabase.py        # MONGO_URL + DB_NAME requis
   ```
   Les tables existent déjà — pas besoin de `--create-tables`.
4. Lancez le backend (uvicorn/gunicorn selon votre hébergement) et pointez
   `REACT_APP_BACKEND_URL` dessus.

## Note sécurité — policies RLS et accès client direct

Les policies attendent un JWT contenant un claim `tenant_id`. Votre auth est
maison (pas Supabase Auth), donc l'accès **direct navigateur → Supabase** ne
fonctionnera que si vous émettez des JWT signés avec la clé Supabase incluant
ce claim. En l'état, c'est le **backend** (service_role, qui bypass le RLS) qui
accède aux données — l'app fonctionne immédiatement.


---

## Changelog — Mise a jour du 2026-07-11

### 1. Suppression du branding Emergent

- **`frontend/public/index.html`** : suppression des scripts de tracking et du titre Emergent
- **`frontend/src/App.js`** : ajout d'un `useEffect` avec `MutationObserver` qui :
  - Force `document.title = 'Blueseatra'`
  - Supprime l'element `#emergent-badge` injecte par la plateforme Hostinger
- **`frontend/src/index.css`** : ajout de regles CSS `display: none !important` sur `#emergent-badge` et tout lien `emergent.sh` (double protection CSS + JS)

### 2. Fix critique : REACT_APP_BACKEND_URL manquante en production

- **`frontend/src/lib/api.js`** : ajout d'un fallback hardcode :
  ```js
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://blueseatra-api.onrender.com';
  ```
- **Hostinger > Environment variables** : ajout de `REACT_APP_BACKEND_URL=https://blueseatra-api.onrender.com`
- **Rebuild automatique Hostinger** : le site a ete reconstruit avec la variable correcte (deploy `019f519c`, 2026-07-11 16:39, 2m31s)
- **Impact** : le bouton Connexion envoyait toutes les requetes vers `undefined/api/...` -> echec silencieux. Desormais correctement route vers `https://blueseatra-api.onrender.com/api/...`

### 3. Securite Supabase : politiques RLS sur blueseatra.users

- **Probleme** : `blueseatra.users` avait RLS active mais aucune politique -> bloquait toutes les operations par defaut
- **Solution** : creation de 4 politiques `service_role only` :
  - `users_select_service_only` — SELECT
  - `users_insert_service_only` — INSERT
  - `users_update_service_only` — UPDATE
  - `users_delete_service_only` — DELETE
- **Migration SQL** : `supabase/migrations/20260711000000_rls_blueseatra_users.sql`
- **Resultat** : Security Advisor Supabase passe a 0 erreurs, 0 warnings, 0 suggestions
- **Logique** : le backend FastAPI utilise `service_role` (bypass RLS natif) -> acces complet. `anon`/`authenticated` -> bloques sur toute la table (protection du `password_hash` et `email`)
