# Blueseatra — AI-Assisted B2B Quoting SaaS Platform

> Multi-tenant application (FastAPI + React + **Supabase/PostgreSQL**) that turns client
> requests ("work orders", "quote requests" as PDF / image / text) into **professional Pro Forma
> quotes**, using AI extraction, a flexible price catalog, and an advanced quote editor with
> PDF generation matching a precise business template.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Features](#2-features)
3. [Architecture & tech stack](#3-architecture--tech-stack)
4. [Project structure](#4-project-structure)
5. [Data model](#5-data-model)
6. [Environment variables](#6-environment-variables)
7. [Local installation (step by step)](#7-local-installation-step-by-step)
8. [Supabase database / migration](#8-supabase-database--migration)
9. [Security](#9-security)
10. [User guide](#10-user-guide)
11. [API reference](#11-api-reference)
12. [Frontend (routes & pages)](#12-frontend-routes--pages)
13. [Scripts & maintenance](#13-scripts--maintenance)
14. [Deployment](#14-deployment)
15. [Changelog (steps completed)](#15-changelog-steps-completed)
16. [Troubleshooting / FAQ](#16-troubleshooting--faq)

---

## 1. Overview

Blueseatra is a **multi-company (multi-tenant)** platform for SMBs in construction / all-trades /
maintenance. Each company ("tenant") has its own isolated workspace: users, price catalog,
requests and quotes.

Main business flow:

```
Client request (PDF / Image / Text)
        |  (AI extraction — Hermes AI / Ollama)
        v
Structured data (client, site, object, lines...)
        |  (catalog matching)
        v
Draft quote  -->  Quote editor  -->  Validated quote  -->  Pro Forma PDF
```

> **Default AI engine since July 2026:** [Hermes-3](https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B)
> via **Ollama** deployed on an **OVH VPS** (self-hosted, no third-party cloud dependency).
> Each tenant can override with OpenAI, Gemini or Anthropic via the Integrations settings.

---

## 2. Features

- **JWT authentication** + multi-tenant (roles: `owner`, `admin`, `operator`, `viewer`, `billing_admin`).
- **AI document extraction** (PDF / image / text) into structured data — **Hermes AI (Ollama/OVH VPS)** by default, with per-tenant configurable fallback (OpenAI, Gemini, Anthropic) via **litellm**.
- **"Open" catalog**: CSV import of **any column format** (auto-detection + adjustable manual mapping), with every column preserved as dynamic attributes.
- **Catalog management**: versions, activate/deactivate, delete, editable client code.
- **Professional quote editor**: typed lines (Labor, Material, Note, Page break), per-line VAT, margin hidden on the PDF, numeric quantities, catalog item picker.
- **Pro Forma PDF generation** matching a precise business template (ReportLab).
- **Company profile** (legal name, registration number, IBAN, legal mentions, terms...) injected into the PDF.
- **Audit log** of all sensitive actions.
- **Internationalization** FR / EN (react-i18next).
- **n8n webhook** configurable per tenant to automate post-quote workflows.

---

## 3. Architecture & tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, React Router, Tailwind CSS, Shadcn/UI (Radix), lucide-react, Sonner, axios, react-i18next |
| Backend | FastAPI (Python 3.11), Uvicorn, Pydantic v2 |
| Database | **Supabase PostgreSQL 17** (via SQLAlchemy 2 async + asyncpg) |
| AI / LLM — default | **Hermes-3 (Ollama)** on OVH VPS (`HERMES_BASE_URL`, `HERMES_DEFAULT_MODEL`) |
| AI / LLM — fallback | **litellm 1.80.0** (OpenAI / Anthropic / Gemini — configured per tenant) |
| PDF | ReportLab |
| Auth | JWT (python-jose) + bcrypt hashing (passlib) |
| Encryption | `cryptography` (Fernet) for secrets at rest |
| Process mgr | supervisor (backend + frontend) |

### Runtime layout

- **Frontend (port 3000)** → calls the backend via `REACT_APP_BACKEND_URL` with the `/api` prefix.
- **Backend (port 8001)** bound to `0.0.0.0:8001`. All routes are prefixed with `/api`.
- **Kubernetes ingress**: routes `/api/*` → backend (8001), everything else → frontend (3000).
- **Backend → PostgreSQL**: direct connection (asyncpg) via `DATABASE_URL` (Supabase Transaction Pooler).
- **Backend → Hermes AI**: HTTP requests to `HERMES_BASE_URL/api/chat` (Ollama REST API).

> ⚠️ **Important note**: the app does **NOT** use Supabase's PostgREST REST API. It connects directly to
> PostgreSQL with the owner role. An **adapter** (`pg_adapter.py`) exposes a "motor/MongoDB"-compatible
> API on top of SQLAlchemy, which made it possible to migrate the database **without rewriting**
> the business logic in `server.py`.

---

## 4. Project structure

```
/app
├── backend/
│   ├── server.py                      # FastAPI app: routes, auth, business logic
│   ├── ai_service.py                  # AI extraction — Hermes/Ollama by default, litellm fallback
│   ├── matching.py                    # Line <-> catalog matching + totals computation
│   ├── pdf_service.py                 # Pro Forma PDF generation (ReportLab)
│   ├── database.py                    # Async SQLAlchemy engine (reads DATABASE_URL)
│   ├── models_sql.py                  # 14 ORM models (JSONB for dynamic data)
│   ├── pg_adapter.py                  # motor-compatible adapter => SQLAlchemy/PostgreSQL
│   ├── migrate_mongo_to_supabase.py   # MongoDB => Supabase migration (one-shot, idempotent)
│   ├── enable_rls.py                  # Enables RLS + deny-all policy on all tables
│   ├── requirements.txt               # Python dependencies (pip freeze)
│   ├── SUPABASE_MIGRATION.md          # Dedicated migration guide
│   └── .env                           # Secrets & config (NOT versioned)
├── frontend/
│   ├── src/
│   │   ├── App.js                     # Route definitions
│   │   ├── i18n.js                    # FR / EN translations
│   │   ├── lib/api.js                 # axios client (base = REACT_APP_BACKEND_URL + /api)
│   │   ├── pages/                     # Landing, Auth, Dashboard, Requests, Catalogs, QuoteEditor...
│   │   └── components/ui/             # Shadcn/UI components
│   ├── package.json                   # JS dependencies (yarn)
│   └── .env                           # REACT_APP_BACKEND_URL
├── supabase/
│   └── migrations/                    # Versioned SQL migrations (RLS, blueseatra schema)
├── DEPLOIEMENT.md                     # Deployment guide: Hostinger + Render + Supabase
├── design_guidelines.md
└── README.en.md                       # ← this document
```

---

## 5. Data model

14 PostgreSQL tables in the **`blueseatra`** schema (primary keys as **UUID** strings). Dynamic/nested fields are stored as **JSONB**.

| Table | Purpose | JSONB fields |
|-------|---------|--------------|
| `users` | User accounts (unique email, bcrypt `password_hash`) | — |
| `tenants` | Companies / workspaces | — |
| `tenant_users` | User ↔ tenant membership + role | — |
| `catalogs` | Catalogs (name, `client_code`, `active_version_id`) | — |
| `catalog_versions` | Catalog versions (status, mapping...) | `columns`, `mapping` |
| `pricing_items` | Catalog items (label, price, VAT, margin...) | `suppliers`, `attributes` |
| `requests` | Client requests + AI extraction | `extracted` |
| `quotes` | Quotes (client, site, totals...) | `lines`, `meta`, `pricing_snapshot` |
| `quote_versions` | Quote version history | `snapshot` |
| `import_jobs` | CSV import logs | — |
| `import_errors` | Per-row import errors | `raw` |
| `audit_logs` | Audit log | `meta` |
| `settings_integrations` | Per-tenant AI/n8n settings (AI key **encrypted** Fernet) | — |
| `company_profiles` | Company profile for the PDF | — |

> **Multi-tenant isolation**: every query filters by `tenant_id`, and every mutation is preceded by an
> ownership check (an ID from another tenant returns 404).

---

## 6. Environment variables

### `backend/.env`

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase **Transaction Pooler** URI (port 6543). **Required.** |
| `SUPABASE_URL` | Supabase project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Public `anon` key (reserved for future Auth/Storage use) |
| `SUPABASE_SERVICE_ROLE_KEY` | `service_role` key (**highly sensitive**, server only) |
| `JWT_SECRET` | JWT signing secret — **must be strong** (≥ 32 chars, non-default) |
| `APP_ENCRYPTION_KEY` | Fernet key (base64) to encrypt tenant AI secrets at rest |
| `HERMES_BASE_URL` | Ollama instance URL (default: `http://localhost:11434`) |
| `HERMES_DEFAULT_MODEL` | Ollama model to use (default: `hermes-3`) |
| `MAX_UPLOAD_SIZE` | (optional) Max upload size in bytes (default 15 MB) |
| `CORS_ORIGINS` | (optional) Allowed origins, comma-separated |
| `MONGO_URL`, `DB_NAME` | Kept for the migration script (MongoDB source) |

> 🔐 **Never commit `.env`**. The backend **refuses to start** if `JWT_SECRET` is weak/default.
>
> ⚠️ `EMERGENT_LLM_KEY` **is no longer used** since July 2026 — the Emergent provider has been removed. Delete this variable from all your environments.

### `frontend/.env`

| Variable | Description |
|----------|-------------|
| `REACT_APP_BACKEND_URL` | Public backend URL (e.g. `https://blueseatra-api.onrender.com`). Hard-coded fallback if absent. |

#### Generate strong secrets

```bash
# JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"

# APP_ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 7. Local installation (step by step)

### Prerequisites

- Python **3.11**
- Node.js **20** + **Yarn** (do not use `npm`)
- A **Supabase** project (free) OR an accessible PostgreSQL
- **Ollama** installed locally with the `hermes-3` model (`ollama pull hermes-3`) — **or** an OpenAI/Anthropic/Gemini key to configure per tenant in the settings

### 1) Get the code

```bash
git clone <repo-url> blueseatra && cd blueseatra
```

### 2) Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` (see [section 6](#6-environment-variables)) with at minimum
`DATABASE_URL`, `JWT_SECRET`, `APP_ENCRYPTION_KEY`, `HERMES_BASE_URL`.

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 3) Frontend

```bash
cd ../frontend
yarn install
# Create frontend/.env with: REACT_APP_BACKEND_URL=http://localhost:8001
yarn start   # starts on port 3000
```

### 4) Ollama (local AI engine)

```bash
# Install Ollama: https://ollama.com/download
ollama pull hermes-3
ollama serve   # listens on http://localhost:11434
```

> For production, point `HERMES_BASE_URL` to your OVH VPS public URL.

---

## 8. Supabase database / migration

### Schema initialization

```bash
cd backend
python migrate_mongo_to_supabase.py   # one-shot, idempotent
python enable_rls.py                   # enable RLS + deny-all policy
```

The `blueseatra` schema and all 14 tables are created automatically by SQLAlchemy on first start (`create_all`). Incremental migrations are versioned in `supabase/migrations/`.

### Recommended connection

Use the **Transaction Pooler** (port **6543**) for the async backend (asyncpg). Do not use port 5432 directly in production.

```
postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

See `backend/SUPABASE_MIGRATION.md` for the full MongoDB migration guide.

---

## 9. Security

| Layer | Mechanism |
|-------|-----------|
| Authentication | JWT signed (`python-jose`), configurable expiration |
| Passwords | bcrypt hashing via `passlib` |
| Tenant AI secrets | Fernet encryption (`cryptography`) at rest in `settings_integrations` |
| Data isolation | `tenant_id` filter on all queries + ownership check |
| Database | PostgreSQL RLS enabled + deny-all policy (access only via the service role from backend) |
| Transport | HTTPS mandatory in production (Render / Hostinger) |
| Audit | `audit_logs` table for all sensitive actions |

**Pre-deployment checklist:**
- [ ] `JWT_SECRET`: at least 32 random characters, never the default value
- [ ] `APP_ENCRYPTION_KEY`: Fernet key generated via the command above
- [ ] `SUPABASE_SERVICE_ROLE_KEY`: **never exposed client-side**
- [ ] `.env` absent from the Git repo (`.gitignore` up to date)
- [ ] `EMERGENT_LLM_KEY` removed from all environments
- [ ] CORS restricted to production domains (`CORS_ORIGINS`)

---

## 10. User guide

### Standard flow

1. **Log in** → select tenant (company workspace)
2. **New request** → upload a PDF / image / text
3. The AI (Hermes-3) automatically extracts: client, site, object, work lines
4. **Review / correct** the extracted data
5. **Create the quote** → the quote editor opens with pre-filled lines
6. **Adjust** lines (quantities, prices, VAT, margin), add catalog items
7. **Generate the Pro Forma PDF** → immediate download
8. *(Optional)* Trigger the n8n webhook to automate the next steps (email, CRM...)

### Catalog management

- **CSV import**: any column format → auto-detection → manual mapping if needed
- **Versions**: each import creates a new version; activation is manual
- **Client code**: editable per version, used as reference in quotes

---

## 11. API reference

All routes are prefixed with `/api`. The backend exposes interactive documentation at:
- **Swagger UI**: `http://localhost:8001/api/docs`
- **ReDoc**: `http://localhost:8001/api/redoc`

### Authentication

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | Login — returns a JWT |
| `GET` | `/api/auth/me` | Authenticated user profile |

### Tenants & users

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/tenants` | List user's tenants |
| `POST` | `/api/tenants` | Create a tenant |
| `GET` | `/api/tenants/{id}/users` | Tenant members |
| `POST` | `/api/tenants/{id}/invite` | Invite a user |

### Requests

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/requests` | List tenant requests |
| `POST` | `/api/requests` | Create a request (file upload) |
| `GET` | `/api/requests/{id}` | Request detail |
| `POST` | `/api/requests/{id}/extract` | Trigger AI extraction |
| `DELETE` | `/api/requests/{id}` | Delete a request |

### Quotes

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/quotes` | List tenant quotes |
| `POST` | `/api/quotes` | Create a quote |
| `GET` | `/api/quotes/{id}` | Quote detail |
| `PUT` | `/api/quotes/{id}` | Update a quote |
| `POST` | `/api/quotes/{id}/pdf` | Generate Pro Forma PDF |
| `DELETE` | `/api/quotes/{id}` | Delete a quote |

### Catalogs

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/catalogs` | List catalogs |
| `POST` | `/api/catalogs` | Create a catalog |
| `POST` | `/api/catalogs/{id}/import` | Import a CSV |
| `GET` | `/api/catalogs/{id}/items` | Active catalog items |
| `PUT` | `/api/catalogs/{id}/versions/{vid}/activate` | Activate a version |

### Settings & integrations

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/settings/integrations` | Tenant AI/n8n settings |
| `PUT` | `/api/settings/integrations` | Update settings |
| `GET` | `/api/settings/company` | Company profile |
| `PUT` | `/api/settings/company` | Update company profile |

---

## 12. Frontend (routes & pages)

| Route | Page / Component | Description |
|-------|-----------------|-------------|
| `/` | `Landing` | Public home page |
| `/login` | `Auth/Login` | Login |
| `/register` | `Auth/Register` | Sign up |
| `/dashboard` | `Dashboard` | Tenant overview |
| `/requests` | `Requests/List` | Request list |
| `/requests/new` | `Requests/New` | New request (upload) |
| `/requests/:id` | `Requests/Detail` | Detail + AI extraction result |
| `/quotes` | `Quotes/List` | Quote list |
| `/quotes/:id` | `QuoteEditor` | Full quote editor |
| `/catalogs` | `Catalogs/List` | Catalog management |
| `/catalogs/:id` | `Catalogs/Detail` | Detail + CSV import |
| `/settings` | `Settings` | Tenant settings |
| `/settings/integrations` | `Settings/Integrations` | AI config (Hermes/OpenAI...) + n8n |
| `/settings/company` | `Settings/Company` | Company profile (PDF) |
| `/settings/users` | `Settings/Users` | Member management |

---

## 13. Scripts & maintenance

```bash
# Regenerate SQL schema (SQLAlchemy → PostgreSQL)
cd backend && python -c "from database import engine; from models_sql import Base; import asyncio; asyncio.run(Base.metadata.create_all(engine))"

# One-shot MongoDB → Supabase migration
python migrate_mongo_to_supabase.py

# Enable / verify RLS
python enable_rls.py

# Check Ollama / Hermes connectivity
curl http://<HERMES_BASE_URL>/api/tags

# Manual AI extraction test
curl -X POST http://localhost:8001/api/requests/<id>/extract \
     -H "Authorization: Bearer <JWT>"
```

---

## 14. Deployment

See **`DEPLOIEMENT.md`** for the full guide (Hostinger + Render + Supabase + OVH VPS).

### Quick summary

| Component | Service | Notes |
|-----------|---------|-------|
| Backend API | **Render** (Web Service, Python) | `uvicorn server:app --host 0.0.0.0 --port $PORT` |
| Frontend | **Hostinger** (Static / Node) | `yarn build` → `build/` folder |
| Database | **Supabase** (PostgreSQL 17) | Transaction Pooler port 6543 |
| AI engine | **OVH VPS** (Ollama + Hermes-3) | Port 11434, accessible from Render |

### Render environment variables (backend)

```
DATABASE_URL=postgresql+asyncpg://...supabase.com:6543/postgres
JWT_SECRET=<generated>
APP_ENCRYPTION_KEY=<generated>
HERMES_BASE_URL=https://<your-ovh-vps>:11434
HERMES_DEFAULT_MODEL=hermes-3
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
CORS_ORIGINS=https://<your-frontend-domain>
```

> ⚠️ Do NOT add `EMERGENT_LLM_KEY` — this variable is no longer used.

---

## 15. Changelog (steps completed)

### 🔄 July 2026 — Migration to Hermes AI / Ollama / OVH VPS

**Major changes:**
- ✅ **Complete removal of the Emergent provider** (`emergentintegrations` uninstalled, `EMERGENT_LLM_KEY` removed)
- ✅ **Hermes-3 via Ollama** on OVH VPS becomes the default AI engine (`ai_service.py` rewritten)
- ✅ **litellm updated to 1.80.0** as the abstraction layer for tenant fallbacks (OpenAI / Anthropic / Gemini)
- ✅ `HERMES_BASE_URL` and `HERMES_DEFAULT_MODEL` environment variables added
- ✅ `requirements.txt` updated (removed `emergentintegrations`, added `litellm==1.80.0`)
- ✅ `.env.example` updated (removed `EMERGENT_LLM_KEY`, added Hermes vars + `APP_ENCRYPTION_KEY`)
- ✅ README.md (FR) and README.en.md (EN) fully updated (sections 1–16)

### Previous steps

| Step | Description |
|------|-------------|
| MongoDB → Supabase migration | `pg_adapter.py` + `models_sql.py` + `migrate_mongo_to_supabase.py` |
| RLS activation | `enable_rls.py` — deny-all policy on all 14 tables |
| Quote editor v2 | Typed lines, per-line VAT, hidden margin, catalog picker |
| Universal CSV import | Column auto-detection + manual mapping + dynamic attributes |
| Pro Forma PDF generation | ReportLab — full business template with company profile |
| Multi-tenant RBAC | Roles: `owner` / `admin` / `operator` / `viewer` / `billing_admin` |
| Internationalization | react-i18next — FR / EN |
| n8n webhook | Configurable per tenant in integration settings |
| Audit log | `audit_logs` table — all sensitive actions tracked |
| Company profile PDF | SIRET, IBAN, legal mentions, terms injected into the PDF |

---

## 16. Troubleshooting / FAQ

### Backend refuses to start

**Symptom:** `ValueError: JWT_SECRET is too weak or is the default value`
**Solution:** Generate a strong secret and add it to `backend/.env`:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

### PostgreSQL connection error

**Symptom:** `asyncpg.exceptions.InvalidAuthorizationSpecificationError`
**Solutions:**
- Make sure `DATABASE_URL` uses port **6543** (Transaction Pooler), not 5432
- Verify credentials in the Supabase Dashboard → Settings → Database
- Make sure the region in the URL is correct

---

### AI extraction fails

**Symptom:** `ConnectionRefusedError` or timeout on `/api/requests/{id}/extract`
**Solutions:**
1. Check that Ollama is running: `curl http://<HERMES_BASE_URL>/api/tags`
2. Check that `hermes-3` is downloaded: `ollama list`
3. If the OVH VPS is unreachable, configure an OpenAI fallback in the tenant's integration settings
4. Check logs: `docker logs ollama` or `journalctl -u ollama`

---

### `emergentintegrations` not found

**Symptom:** `ModuleNotFoundError: No module named 'emergentintegrations'`
**Solution:** This module was **removed** in July 2026. Update your installation:
```bash
pip install -r requirements.txt
```
Make sure `emergentintegrations` is no longer in your `requirements.txt`.

---

### CSV import — columns not detected

**Symptom:** All columns appear as "unmapped"
**Solutions:**
- Check the file encoding (UTF-8 or Latin-1 accepted)
- Check the separator (`,` or `;` — auto-detected)
- Use the manual mapping in the UI to associate your columns to standard fields

---

### Pro Forma PDF — missing company data

**Symptom:** The PDF does not contain the registration number / IBAN / logo
**Solution:** Fill in the company profile under **Settings → Company profile** for the relevant tenant.

---

### CORS error in development

**Symptom:** `Access to XMLHttpRequest blocked by CORS policy`
**Solution:** Add `http://localhost:3000` to `CORS_ORIGINS` in `backend/.env`:
```
CORS_ORIGINS=http://localhost:3000,https://<your-domain>
```

---

*Last updated: July 20, 2026 — Migration to Hermes AI / Ollama / OVH VPS*
