# Déploiement Blueseatra — Frontend (Hostinger) + Backend (Render) + IA (OVH VPS)

Ce document récapitule la configuration mise en place et les étapes pour déployer l'application.

## Architecture

```
Navigateur ──(REACT_APP_BACKEND_URL)/api──▶ Backend FastAPI ──(DATABASE_URL)──▶ Supabase Postgres
  (React/CRA build statique, Hostinger)       (Python, Render)                    schéma "blueseatra"
                                                    │
                                                    └──(HERMES_BASE_URL)──▶ Ollama / Hermes-3
                                                                              (VPS OVH)
```

- Le **frontend** est une SPA React (Create React App + CRACO) servie en statique. Il appelle **uniquement le backend** via `src/lib/api.js` (`${REACT_APP_BACKEND_URL}/api/...`). Auth maison : token `bs_token` en localStorage.
- Le **backend** (FastAPI) détient les identifiants Supabase et parle à Postgres via un adaptateur compatible Mongo (`pg_adapter.py` + SQLAlchemy/asyncpg).
- Les **14 tables** vivent dans le schéma dédié **`blueseatra`** (et non `public`).
- Le **moteur IA** est **Hermes-3 via Ollama** hébergé sur un VPS OVH (`HERMES_BASE_URL`). Chaque tenant peut surcharger avec OpenAI / Anthropic / Gemini via `litellm`.

---

## Ce qui a été fait

1. **`frontend/package.json`** réparé (JSON invalide : virgule manquante ; `@supabase/supabase-js` déplacé dans `dependencies`). Le build passe désormais.
2. **`frontend/public/.htaccess`** ajouté → routing React Router sur Apache/Hostinger (plus de 404 au rafraîchissement) + cache des assets.
3. **`frontend/src/db.js`** supprimé (code mort, jamais importé, plantait au chargement avec `createClient(undefined, undefined)` sur une table inexistante).
4. **14 tables créées dans Supabase** (schéma `blueseatra`) avec UUID, JSONB, index composites et contraintes, d'après `backend/models_sql.py`.
5. **RLS activé** sur les 14 tables + policies `service_role only`. La table `users` est verrouillée (accès service_role uniquement, car elle contient `password_hash`).
6. **`backend/database.py`** patché : la connexion force `search_path=blueseatra,public` (via `DB_SCHEMA`), donc les modèles SQLAlchemy non qualifiés trouvent les tables.
7. **`.env.example`** ajoutés côté frontend et backend.

---

## Étape 1 — Frontend (Hostinger, upload manuel, racine du domaine)

```bash
cd frontend
cp .env.example .env  # puis renseigner REACT_APP_BACKEND_URL
yarn install
yarn build
```

- Uploadez le **contenu** de `frontend/build/` directement dans `public_html/` (pas le dossier `build/` lui-même : `index.html` doit être à la racine).
- Le `.htaccess` est inclus automatiquement dans le build.
- Variable obligatoire : `REACT_APP_BACKEND_URL=https://blueseatra-api.onrender.com`

---

## Étape 2 — Backend (Render) + base Supabase

1. Récupérez la **Transaction Pooler URI** (port 6543) : Supabase Dashboard → Project Settings → Database → Connection string → Transaction pooler :
   ```
   postgresql://postgres.umoayrslyezwbbazpbdl:[MOT-DE-PASSE]@aws-0-eu-west-3.pooler.supabase.com:6543/postgres
   ```
2. `cd backend && cp .env.example .env`, puis renseignez toutes les variables (voir tableau ci-dessous).
3. (Migration des données existantes depuis MongoDB, optionnel) :
   ```bash
   python migrate_mongo_to_supabase.py  # MONGO_URL + DB_NAME requis
   ```
   Les tables existent déjà — pas besoin de `--create-tables`.
4. Déployez sur Render (service Web, Python, `uvicorn server:app --host 0.0.0.0 --port 8001`).

### Variables d'environnement backend

| Variable | Description | Obligatoire |
|----------|-------------|-------------|
| `DATABASE_URL` | URI Transaction Pooler Supabase (port 6543) | ✅ |
| `SUPABASE_URL` | URL projet Supabase | ✅ |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé service_role (ultra-sensible) | ✅ |
| `JWT_SECRET` | Secret JWT ≥ 32 caractères | ✅ |
| `APP_ENCRYPTION_KEY` | Clé Fernet pour chiffrer les clés IA tenant | ✅ |
| `HERMES_BASE_URL` | URL Ollama sur VPS OVH (ex. `http://IP:11434`) | ✅ |
| `HERMES_DEFAULT_MODEL` | Modèle Ollama (défaut : `hermes-3`) | optionnel |
| `CORS_ORIGINS` | Origines autorisées (ex. `https://blueseatra.com`) | optionnel |
| `MAX_UPLOAD_SIZE` | Taille max upload en octets (défaut 15 Mo) | optionnel |
| `MONGO_URL`, `DB_NAME` | Source MongoDB (migration uniquement) | optionnel |

> ⚠️ `EMERGENT_LLM_KEY` **n'est plus utilisée** — le provider Emergent a été entièrement supprimé en juillet 2026. Retirez cette variable de vos environnements.

---

## Étape 3 — Hermes AI (Ollama sur VPS OVH)

1. Sur votre VPS OVH, installez Ollama :
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull hermes-3
   ollama serve  # port 11434 par défaut
   ```
2. Ouvrez le port 11434 dans le firewall OVH (ou utilisez un tunnel SSH/nginx reverse proxy).
3. Renseignez `HERMES_BASE_URL=http://<IP-VPS>:11434` dans le `.env` du backend.
4. Le backend communique via `POST ${HERMES_BASE_URL}/api/chat` (Ollama REST API).

> Les tenants peuvent surcharger le moteur IA depuis Paramètres → Intégrations (OpenAI, Anthropic, Gemini via litellm).

---

## Note sécurité — policies RLS et accès client direct

Les policies attendent un JWT contenant un claim `tenant_id`. Votre auth est maison (pas Supabase Auth), donc l'accès **direct navigateur → Supabase** ne fonctionnera que si vous émettez des JWT signés avec la clé Supabase incluant ce claim. En l'état, c'est le **backend** (service_role, qui bypass le RLS) qui accède aux données — l'app fonctionne immédiatement.

---

## Changelog

### 2026-07-20 — Migration Hermes AI / Suppression Emergent

#### 1. Remplacement complet du moteur IA

- **`backend/ai_service.py`** entièrement réécrit : Hermes AI (Ollama/OVH VPS) devient le moteur par défaut. Suppression de `emergentintegrations`.
- **`backend/server.py`** : suppression des providers `oracle` et `emergent`. Provider par défaut = `hermes`.
- **`backend/requirements.txt`** : suppression de l'URL wheel Emergent, ajout de `litellm==1.80.0` (PyPI standard).
- **`frontend/src/pages/Settings.js`** : Hermes remplace Emergent comme provider par défaut dans l'UI.
- **`backend/models_sql.py` / `SettingsIntegration`** : valeur par défaut `ai_provider` mise à jour de `emergent` → `hermes`.

#### 2. Providers disponibles (server.py PROVIDER_MODELS)

| Provider | Modèles disponibles |
|----------|--------------------|
| `hermes` | `hermes-3`, `llama-3.3-70b`, `qwen2.5-72b`, `deepseek-r1-70b` |
| `openai` | `gpt-5.4`, `gpt-5.4-mini`, `gpt-4o`, `gpt-4.1` |
| `gemini` | `gemini-3.1-pro-preview`, `gemini-3-flash-preview`, `gemini-2.5-flash` |
| `anthropic` | `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001` |

#### 3. Nouvelles variables d'environnement

- `HERMES_BASE_URL` (défaut : `http://localhost:11434`)
- `HERMES_DEFAULT_MODEL` (défaut : `hermes-3`)

---

### 2026-07-11 — Emergent removal, BACKEND_URL fix, Supabase RLS

#### 1. Suppression du branding Emergent

- **`frontend/public/index.html`** : suppression des scripts de tracking et du titre Emergent.
- **`frontend/src/App.js`** : ajout d'un `useEffect` avec `MutationObserver` qui force `document.title = 'Blueseatra'` et supprime `#emergent-badge`.
- **`frontend/src/index.css`** : règles CSS `display: none !important` sur `#emergent-badge` et tout lien `emergent.sh`.

#### 2. Fix critique : REACT_APP_BACKEND_URL manquante en production

- **`frontend/src/lib/api.js`** : ajout d'un fallback hardcodé :
  ```js
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://blueseatra-api.onrender.com';
  ```
- **Hostinger > Environment variables** : `REACT_APP_BACKEND_URL=https://blueseatra-api.onrender.com`.
- **Impact** : le bouton Connexion envoyait toutes les requêtes vers `undefined/api/...` → désormais correctement routé.

#### 3. Sécurité Supabase : politiques RLS sur blueseatra.users

- **Problème** : `blueseatra.users` avait RLS activé mais aucune politique → bloquait toutes les opérations.
- **Solution** : création de 4 politiques `service_role only` (SELECT / INSERT / UPDATE / DELETE).
- **Migration SQL** : `supabase/migrations/20260711000000_rls_blueseatra_users.sql`.
- **Résultat** : Security Advisor Supabase → 0 erreurs, 0 warnings, 0 suggestions.
