## 📄 `README.md` — copie intégrale

```markdown
# Blueseatra — Plateforme SaaS B2B de devis assistés par IA

> Application multi‑tenant (FastAPI + React + **Supabase/PostgreSQL**) qui transforme des demandes clients (« ordres de mission », « demandes de devis » au format PDF / image / texte) en **devis Pro Forma professionnels**, grâce à l'extraction IA, un catalogue de prix flexible et un éditeur de devis avancé avec génération PDF conforme à un gabarit métier.

---

## Table des matières

1. [Présentation](#1-présentation)
2. [Fonctionnalités](#2-fonctionnalités)
3. [Architecture & stack technique](#3-architecture--stack-technique)
4. [Structure du projet](#4-structure-du-projet)
5. [Modèle de données](#5-modèle-de-données)
6. [Variables d'environnement](#6-variables-denvironnement)
7. [Installation locale (pas à pas)](#7-installation-locale-pas-à-pas)
8. [Base de données Supabase / migration](#8-base-de-données-supabase--migration)
9. [Sécurité](#9-sécurité)
10. [Mode d'emploi (utilisateur final)](#10-mode-demploi-utilisateur-final)
11. [Référence API](#11-référence-api)
12. [Frontend (routes & pages)](#12-frontend-routes--pages)
13. [Scripts & maintenance](#13-scripts--maintenance)
14. [Déploiement](#14-déploiement)
15. [Historique des étapes réalisées (changelog)](#15-historique-des-étapes-réalisées-changelog)
16. [Dépannage / FAQ](#16-dépannage--faq)

---

## 1. Présentation

Blueseatra est une plateforme **multi‑entreprises (multi‑tenant)** destinée aux PME du BTP / TCE / maintenance. Chaque entreprise (« tenant ») dispose de son propre espace isolé : utilisateurs, catalogue de prix, demandes et devis.

Le flux métier principal :

```
Demande client (PDF / Image / Texte)
        │  (extraction IA — Hermes AI / Ollama)
        ▼
Données structurées (client, site, objet, lignes…)
        │  (rapprochement avec le catalogue)
        ▼
Brouillon de devis ──► Éditeur de devis ──► Devis validé ──► PDF Pro Forma
```

> **Moteur IA par défaut depuis juillet 2026 :** [Hermes-3](https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B) via **Ollama** déployé sur un **VPS OVH** (auto-hébergé, sans dépendance cloud tierce). Chaque tenant peut surcharger avec OpenAI, Gemini ou Anthropic via les paramètres d'intégration.

---

## 2. Fonctionnalités

- **Authentification JWT** + multi‑tenant (rôles : `owner`, `admin`, `operator`, `viewer`, `billing_admin`).
- **Extraction IA** de documents (PDF / image / texte) en données structurées — moteur **Hermes AI (Ollama/OVH VPS)** par défaut, avec fallback configurable par tenant (OpenAI, Gemini, Anthropic) via **litellm**.
- **Catalogue « ouvert »** : import CSV de **n'importe quel format de colonnes** (auto‑détection des champs + mapping manuel ajustable), stockage de toutes les colonnes en attributs dynamiques.
- **Gestion des catalogues** : versions, activation/désactivation, suppression, code client éditable.
- **Éditeur de devis professionnel** : lignes typées (Main d'œuvre, Matériel, Note, Saut de page), TVA par ligne, marge masquée sur le PDF, quantités numériques, sélecteur d'articles depuis le catalogue.
- **Génération PDF Pro Forma** conforme à un gabarit métier précis (ReportLab).
- **Profil entreprise** (raison sociale, SIRET, IBAN, mentions, conditions…) injecté dans le PDF.
- **Journal d'audit** de toutes les actions sensibles.
- **Internationalisation** FR / EN (react‑i18next).
- **Webhook n8n** configurable par tenant pour automatiser les flux post-devis.

---

## 3. Architecture & stack technique

| Couche | Technologie |
|--------|-------------|
| Frontend | React 18, React Router, Tailwind CSS, Shadcn/UI (Radix), lucide‑react, Sonner, axios, react‑i18next |
| Backend | FastAPI (Python 3.11), Uvicorn, Pydantic v2 |
| Base de données | **Supabase PostgreSQL 17** (via SQLAlchemy 2 async + asyncpg) |
| IA / LLM — défaut | **Hermes-3 (Ollama)** sur VPS OVH (`HERMES_BASE_URL`, `HERMES_DEFAULT_MODEL`) |
| IA / LLM — fallback | **litellm 1.80.0** (OpenAI / Anthropic / Gemini — configuré par tenant) |
| PDF | ReportLab |
| Auth | JWT (python‑jose) + hachage bcrypt (passlib) |
| Chiffrement | `cryptography` (Fernet) pour les secrets au repos |
| Process mgr | supervisor (backend + frontend) |

### Schéma d'exécution

- **Frontend (port 3000)** → appelle le backend via `REACT_APP_BACKEND_URL` avec le préfixe `/api`.
- **Backend (port 8001)** lié à `0.0.0.0:8001`. Toutes les routes sont préfixées par `/api`.
- **Ingress Kubernetes** : route `/api/*` → backend (8001), tout le reste → frontend (3000).
- **Backend → PostgreSQL** : connexion directe (asyncpg) via `DATABASE_URL` (Supabase Transaction Pooler).
- **Backend → Hermes AI** : requêtes HTTP vers `HERMES_BASE_URL/api/chat` (Ollama REST API).

> ⚠️ **Particularité importante** : l'application **n'utilise pas l'API REST PostgREST de Supabase**. Elle se connecte directement à PostgreSQL avec le rôle propriétaire. Un **adaptateur** (`pg_adapter.py`) expose une API compatible « motor/MongoDB » au‑dessus de SQLAlchemy, ce qui a permis de migrer la base **sans réécrire** la logique métier de `server.py`.

---

## 4. Structure du projet

```
/app
├── backend/
│   ├── server.py                      # Application FastAPI : routes, auth, logique métier
│   ├── ai_service.py                  # Extraction IA — Hermes/Ollama par défaut, litellm en fallback
│   ├── matching.py                    # Rapprochement lignes <-> catalogue + calcul des totaux
│   ├── pdf_service.py                 # Génération du PDF Pro Forma (ReportLab)
│   ├── database.py                    # Moteur SQLAlchemy async (lit DATABASE_URL)
│   ├── models_sql.py                  # 14 modèles ORM (JSONB pour les données dynamiques)
│   ├── pg_adapter.py                  # Adaptateur API motor-compatible => SQLAlchemy/PostgreSQL
│   ├── migrate_mongo_to_supabase.py   # Script de migration MongoDB => Supabase (one-shot, idempotent)
│   ├── enable_rls.py                  # Active RLS + policy deny-all sur toutes les tables
│   ├── requirements.txt               # Dépendances Python (pip freeze)
│   ├── SUPABASE_MIGRATION.md          # Guide dédié à la migration
│   └── .env                           # Secrets & configuration (NON versionné)
├── frontend/
│   ├── src/
│   │   ├── App.js                     # Définition des routes
│   │   ├── i18n.js                    # Traductions FR / EN
│   │   ├── lib/api.js                 # Client axios (base = REACT_APP_BACKEND_URL + /api)
│   │   ├── pages/                     # Landing, Auth, Dashboard, Requests, Catalogs, QuoteEditor…
│   │   └── components/ui/             # Composants Shadcn/UI
│   ├── package.json                   # Dépendances JS (yarn)
│   └── .env                           # REACT_APP_BACKEND_URL
├── supabase/
│   └── migrations/                    # Migrations SQL versionnées (RLS, schéma blueseatra)
├── DEPLOIEMENT.md                     # Guide de déploiement Hostinger + Render + Supabase
├── design_guidelines.md
└── README.md                          # ← ce document
```

---

## 5. Modèle de données

14 tables PostgreSQL dans le schéma **`blueseatra`** (clés primaires en **UUID** string). Les champs dynamiques/imbriqués sont stockés en **JSONB**.

| Table | Rôle | Champs JSONB |
|-------|------|--------------|
| `users` | Comptes utilisateurs (email unique, `password_hash` bcrypt) | — |
| `tenants` | Entreprises / espaces | — |
| `tenant_users` | Appartenance utilisateur ↔ tenant + rôle | — |
| `catalogs` | Catalogues (nom, `client_code`, `active_version_id`) | — |
| `catalog_versions` | Versions d'un catalogue (statut, mapping…) | `columns`, `mapping` |
| `pricing_items` | Articles de catalogue (label, prix, TVA, marge…) | `suppliers`, `attributes` |
| `requests` | Demandes client + extraction IA | `extracted` |
| `quotes` | Devis (client, site, totaux…) | `lines`, `meta`, `pricing_snapshot` |
| `quote_versions` | Historique des versions de devis | `snapshot` |
| `import_jobs` | Journaux d'import CSV | — |
| `import_errors` | Erreurs ligne par ligne d'import | `raw` |
| `audit_logs` | Journal d'audit | `meta` |
| `settings_integrations` | Réglages IA/n8n par tenant (clé IA **chiffrée** Fernet) | — |
| `company_profiles` | Profil entreprise pour le PDF | — |

> **Isolation multi‑tenant** : chaque requête filtre par `tenant_id`, et toute modification est précédée d'un contrôle de propriété (un identifiant d'un autre tenant renvoie 404).

---

## 6. Variables d'environnement

### `backend/.env`

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URI **Transaction Pooler** Supabase (port 6543). **Obligatoire.** |
| `SUPABASE_URL` | URL du projet Supabase (`https://<ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Clé publique `anon` (usage futur Auth/Storage) |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé `service_role` (**ultra‑sensible**, serveur uniquement) |
| `JWT_SECRET` | Secret de signature JWT — **doit être fort** (≥ 32 car., non par défaut) |
| `APP_ENCRYPTION_KEY` | Clé Fernet (base64) pour chiffrer les secrets IA des tenants au repos |
| `HERMES_BASE_URL` | URL de l'instance Ollama (défaut : `http://localhost:11434`) |
| `HERMES_DEFAULT_MODEL` | Modèle Ollama à utiliser (défaut : `hermes-3`) |
| `MAX_UPLOAD_SIZE` | (optionnel) Taille max d'upload en octets (défaut 15 Mo) |
| `CORS_ORIGINS` | (optionnel) Origines autorisées séparées par virgule |
| `MONGO_URL`, `DB_NAME` | Conservés pour le script de migration (source MongoDB) |

> 🔐 **Ne jamais committer `.env`**. Le backend **refuse de démarrer** si `JWT_SECRET` est faible/par défaut.
>
> ⚠️ `EMERGENT_LLM_KEY` **n'est plus utilisée** depuis juillet 2026 — le provider Emergent a été supprimé. Supprimez cette variable de vos environnements.

### `frontend/.env`

| Variable | Description |
|----------|-------------|
| `REACT_APP_BACKEND_URL` | URL publique du backend (ex. `https://blueseatra-api.onrender.com`). Fallback codé en dur si absent. |

#### Générer des secrets forts

```bash
# JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"

# APP_ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 7. Installation locale (pas à pas)

### Pré‑requis

- Python **3.11**
- Node.js **20** + **Yarn** (ne pas utiliser `npm`)
- Un projet **Supabase** (gratuit) OU un PostgreSQL accessible
- **Ollama** installé localement avec le modèle `hermes-3` (`ollama pull hermes-3`) — **ou** une clé OpenAI/Anthropic/Gemini à configurer par tenant dans les paramètres

### 1) Récupérer le code

```bash
git clone <url-du-repo> blueseatra && cd blueseatra
```

### 2) Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

Créez `backend/.env` (voir [section 6](#6-variables-denvironnement)) en renseignant au minimum `DATABASE_URL`,
