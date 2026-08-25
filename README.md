# Blueseatra — Plateforme SaaS B2B de devis assistés par IA

> Application multi‑tenant (FastAPI + React + **Supabase/PostgreSQL**) qui transforme des demandes clients (« ordres de mission », « demandes de devis » au format PDF / image / texte) en **devis Pro Forma professionnels**, grâce à l'extraction IA, un catalogue de prix flexible et un éditeur de devis avancé avec génération PDF conforme à un gabarit métier.

---

> 📋 **Journal des changements** : voir **[`CHANGELOG.md`](./CHANGELOG.md)** pour l'historique détaillé PR par PR. Contexte infra IA locale (VPS OVH) et backlog : **[`HANDOFF.md`](./HANDOFF.md)**. Livrables infra dédiés : **[`ovh-ai-stack-corrige/`](./ovh-ai-stack-corrige/)**.

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
| `HERMES_BASE_URL` | URL Caddy OVH (prod) ou `http://localhost:11434` (dev) |
| `HERMES_DEFAULT_MODEL` | Modèle Ollama de secours final (défaut : `hermes-3`) |
| `HERMES_API_KEY` | Clé `X-Api-Key` (identique à `OLLAMA_API_KEY` du VPS) |
| `HERMES_REASONING_MODEL` | Modèle pour le rôle `reason` (extraction, raisonnement, expansion de devis) — défaut : `gpt-oss:20b` |
| `HERMES_EXTRACT_MODEL` | Modèle pour le rôle `extract` (texte collé manuellement, sans vision) — défaut : `qwen2.5:7b` |
| `HERMES_VISION_MODEL` | Modèle vision pour fichiers importés (PDF/image illisibles) — défaut : `qwen2.5vl:7b`. ⚠️ si vide, retombe sur `HERMES_REASONING_MODEL` (voir `ai_service.py`) — toujours le définir explicitement pour ne jamais hériter d'un modèle sans capacité vision. |
| `HERMES_DESCRIPTION_MODEL` | Modèle pour le rôle `describe` — **uniquement** les champs Description des travaux + Étapes à suivre, jamais le calcul/chiffrage — défaut : `glm-4.7-flash:Q3_K_M` (voir ADR correspondant dans `docs/decisions/` du dépôt `ovh-ai-stack`) |
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

Créez `backend/.env` (voir [section 6](#6-variables-denvironnement)) en renseignant au minimum `DATABASE_URL`, `JWT_SECRET`, `APP_ENCRYPTION_KEY`, `HERMES_BASE_URL`.

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 3) Frontend

```bash
cd ../frontend
yarn install
# Créez frontend/.env avec REACT_APP_BACKEND_URL=http://localhost:8001
yarn start   # démarre sur le port 3000
```

### 4) Ollama (moteur IA local)

```bash
# Installer Ollama : https://ollama.com/download
ollama pull hermes-3
ollama serve   # écoute sur http://localhost:11434
```

> Pour utiliser le VPS OVH en dev, pointez `HERMES_BASE_URL` vers l'URL publique de votre instance Ollama distante.

---

## 8. Base de données Supabase / migration

### Initialisation du schéma

```bash
cd backend
python migrate_mongo_to_supabase.py   # one-shot, idempotent
python enable_rls.py                   # active RLS + policy deny-all
```

Le schéma `blueseatra` et les 14 tables sont créés automatiquement par SQLAlchemy au premier démarrage (`create_all`). Les migrations incrémentales sont versionnées dans `supabase/migrations/`.

### Connexion recommandée

Utilisez le **Transaction Pooler** (port **6543**) de Supabase pour le backend asynchrone (asyncpg). Ne pas utiliser le port 5432 direct en production.

```
postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Consultez `backend/SUPABASE_MIGRATION.md` pour le guide complet de migration depuis MongoDB.

---

## 9. Sécurité

| Couche | Mécanisme |
|--------|-----------|
| Authentification | JWT signé (`python-jose`), expiration configurable |
| Mots de passe | Hachage bcrypt via `passlib` |
| Secrets IA des tenants | Chiffrement Fernet (`cryptography`) au repos dans `settings_integrations` |
| Isolation des données | Filtre `tenant_id` sur toutes les requêtes + contrôle de propriété |
| Base de données | RLS PostgreSQL activé + policy deny-all (accès uniquement par le backend via le rôle service) |
| Transport | HTTPS obligatoire en production (Render / Hostinger) |
| Audit | Journal `audit_logs` pour toutes les actions sensibles |

**Checklist avant déploiement :**
- [ ] `JWT_SECRET` : au moins 32 caractères aléatoires, jamais la valeur par défaut
- [ ] `APP_ENCRYPTION_KEY` : clé Fernet générée via la commande ci-dessus
- [ ] `SUPABASE_SERVICE_ROLE_KEY` : **jamais exposée côté frontend**
- [ ] `.env` absent du dépôt Git (`.gitignore` à jour)
- [ ] `EMERGENT_LLM_KEY` supprimée de tous les environnements
- [ ] CORS restreint aux domaines de production (`CORS_ORIGINS`)

---

## 10. Mode d'emploi (utilisateur final)

### Flux standard

1. **Connexion** → sélection du tenant (espace entreprise)
2. **Nouvelle demande** → déposer un PDF / image / texte
3. L'IA (Hermes-3) extrait automatiquement : client, site, objet, lignes de travaux
4. **Vérifier / corriger** les données extraites
5. **Créer le devis** → l'éditeur de devis s'ouvre avec les lignes pré-remplies
6. **Ajuster** les lignes (quantités, prix, TVA, marge), ajouter des articles du catalogue
7. **Générer le PDF Pro Forma** → téléchargement immédiat
8. *(Optionnel)* Déclencher le webhook n8n pour automatiser la suite (envoi email, CRM…)

### Gestion du catalogue

- **Import CSV** : n'importe quel format de colonnes → auto-détection → mapping manuel si besoin
- **Versions** : chaque import crée une nouvelle version ; l'activation est manuelle
- **Code client** : éditable par version, utilisé comme référence dans les devis

---

## 11. Référence API

Toutes les routes sont préfixées par `/api` (routeur `APIRouter(prefix="/api")` dans `backend/server.py`). Table générée à partir des routes réellement déclarées — à tenir à jour à chaque route ajoutée/retirée (`grep -n "^@api\." backend/server.py` pour vérifier).

### Authentification

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/auth/signup` | Création de compte + tenant |
| `POST` | `/api/auth/login` | Connexion — retourne un JWT |
| `GET` | `/api/auth/me` | Profil de l'utilisateur connecté + tenants |
| `POST` | `/api/auth/switch-tenant/{tenant_id}` | Basculer le tenant actif |

### Membres (rôles owner / admin / operator / viewer / billing_admin)

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/members` | Liste des membres du tenant |
| `POST` | `/api/members` | Ajouter un membre (owner/admin) |
| `PATCH` | `/api/members/{user_id}` | Modifier rôle et/ou nom (owner/admin) ; le champ `password` est réservé au **owner** (403 sinon) |
| `DELETE` | `/api/members/{user_id}` | Retirer un membre (owner/admin) — refuse de retirer le dernier owner ou soi-même |

### Demandes (Requests)

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/requests` | Créer une demande (texte collé ou fichier) — mise en file d'extraction séquentielle, statut initial `queued` |
| `GET` | `/api/requests` | Liste des demandes du tenant, avec `queue_position` pour les demandes `queued` |
| `GET` | `/api/requests/{id}` | Détail d'une demande (avec `queue_position` si `queued`) |
| `GET` | `/api/requests/{id}/file` | Fichier original (images uniquement — les PDF ne sont jamais persistés) |
| `POST` | `/api/requests/{id}/process` | Retraiter (remise en file) |
| `POST` | `/api/requests/{id}/deep-vision` | Escalade vers un modèle de vision plus lent (photos importées uniquement) |
| `PATCH` | `/api/requests/{id}` | Modifier le titre / texte source |
| `DELETE` | `/api/requests/{id}` | Supprimer une demande |

> Traitement IA **séquentiel** (une seule extraction à la fois, voir `_extraction_worker_loop` dans `backend/server.py`) : le VPS d'inférence n'a pas de GPU, traiter plusieurs demandes en parallèle les fait ralentir/bloquer mutuellement. Détail : [`docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md`](./docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md).

### Catalogues

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/catalogs` | Liste des catalogues du tenant |
| `GET` | `/api/catalogs/{id}/items` | Articles d'un catalogue |
| `GET` | `/api/catalog-template.csv` | Modèle CSV à télécharger |
| `POST` | `/api/catalogs/import/preview` | Aperçu d'un import avant validation |
| `POST` | `/api/catalogs/import` | Importer un CSV (nouvelle version) |
| `GET` | `/api/import-jobs/{job_id}/errors` | Erreurs détaillées d'un import |
| `POST` | `/api/catalogs/{id}/activate/{version_id}` | Activer une version (une seule version active à la fois) |
| `PATCH` | `/api/catalogs/{id}` | Modifier le catalogue (ex. code client) |
| `POST` | `/api/catalogs/{id}/deactivate` | Désactiver le catalogue actif |
| `DELETE` | `/api/catalogs/{id}` | Supprimer définitivement un catalogue et ses versions |
| `GET` | `/api/catalog/active` | Catalogue actif complet (cache court) |
| `GET` | `/api/catalog/search` | Recherche d'articles (utilisée par l'éditeur de devis) |

### Devis (Quotes)

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/quotes/draft` | Créer un ou plusieurs brouillons de devis depuis une demande (options exclusives → devis distincts) |
| `GET` | `/api/quotes` | Liste des devis du tenant |
| `GET` | `/api/quotes/{id}` | Détail d'un devis |
| `PATCH` | `/api/quotes/{id}` | Mettre à jour un devis (brouillon) |
| `POST` | `/api/quotes/{id}/validate` | Valider — gèle les prix (`pricing_snapshot`) |
| `POST` | `/api/quotes/{id}/send` | Marquer comme envoyé |
| `POST` | `/api/quotes/{id}/reopen` | Rouvrir un devis validé/envoyé en brouillon |
| `POST` | `/api/quotes/{id}/duplicate` | Dupliquer un devis |
| `POST` | `/api/quotes/{id}/rematch` | Recalculer le rapprochement catalogue des lignes |
| `DELETE` | `/api/quotes/{id}` | Supprimer un devis |
| `GET` | `/api/quotes/{id}/pdf` | Générer et télécharger le PDF Pro Forma |

### Paramètres, tableau de bord & audit

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` / `PUT` | `/api/settings/integrations` | Réglages IA / webhook n8n du tenant |
| `GET` / `PUT` | `/api/company-profile` | Profil entreprise (en-tête/pied de page des PDF) |
| `GET` | `/api/dashboard` | Indicateurs du tenant |
| `GET` | `/api/audit` | Journal d'audit du tenant |
| `GET` | `/api/health` | Statut de santé (`{"status": "healthy", "commit": "..."}`) — utilisé comme `healthCheckPath` Render |

---

## 12. Frontend (routes & pages)

Routes réelles (`frontend/src/App.js`) :

| Route | Page / Composant | Description |
|-------|-----------------|-------------|
| `/` | `Landing` | Page d'accueil publique |
| `/login` | `LoginPage` | Connexion |
| `/signup` | `SignupPage` | Inscription |
| `/app` | `Dashboard` | Vue d'ensemble du tenant |
| `/app/requests` | `Requests` | Liste des demandes (nouvelle demande, statut, position en file) |
| `/app/requests/:id` | `RequestDetail` | Détail + résultat extraction IA + escalade vision approfondie |
| `/app/catalogs` | `Catalogs` | Gestion des catalogues |
| `/app/catalogs/import` | `CatalogImport` | Import CSV (aperçu → mapping → validation) |
| `/app/quotes` | `Quotes` | Liste des devis |
| `/app/quotes/:id` | `QuoteEditor` | Éditeur de devis complet (lignes, marge, PDF) |
| `/app/members` | `Members` | Membres : rôle, modifier le nom, supprimer, changer le mot de passe (owner uniquement) |
| `/app/audit` | `Audit` | Journal d'audit du tenant |
| `/app/settings` | `Settings` | Intégrations IA/n8n + profil entreprise |
| `/app/billing` | `Billing` | Facturation (Stripe — phase ultérieure) |

---

## 13. Scripts & maintenance

```bash
# Régénérer le schéma SQL (SQLAlchemy → PostgreSQL)
cd backend && python -c "from database import engine; from models_sql import Base; import asyncio; asyncio.run(Base.metadata.create_all(engine))"

# Migration one-shot MongoDB → Supabase
python migrate_mongo_to_supabase.py

# Activer / vérifier RLS
python enable_rls.py

# Vérifier la connexion à Ollama / Hermes
curl http://<HERMES_BASE_URL>/api/tags

# Lancer un test d'extraction IA manuel
curl -X POST http://localhost:8001/api/requests/<id>/extract \
     -H "Authorization: Bearer <JWT>"
```

---

## 14. Déploiement

Consultez **`DEPLOIEMENT.md`** pour le guide complet (Hostinger + Render + Supabase + VPS OVH).

### Résumé rapide

| Composant | Service | Notes |
|-----------|---------|-------|
| Backend API | **Render** (Web Service, Python) | `uvicorn server:app --host 0.0.0.0 --port $PORT` |
| Frontend | **Hostinger** (Static / Node) | `yarn build` → dossier `build/` |
| Base de données | **Supabase** (PostgreSQL 17) | Transaction Pooler port 6543 |
| Moteur IA | **VPS OVH** (Ollama + Hermes-3) | Port 11434, accessible depuis Render |

### Variables d'environnement Render (backend)

```
DATABASE_URL=postgresql+asyncpg://...supabase.com:6543/postgres
JWT_SECRET=<généré>
APP_ENCRYPTION_KEY=<généré>
HERMES_BASE_URL=https://ia.blueseatra.com
HERMES_DEFAULT_MODEL=hermes-3
HERMES_API_KEY=<secret ovh-ai-stack>
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<clé anon>
SUPABASE_SERVICE_ROLE_KEY=<clé service_role>
CORS_ORIGINS=https://<votre-domaine-frontend>
```

> ⚠️ Ne pas ajouter `EMERGENT_LLM_KEY` — cette variable n'est plus utilisée.

---

## 15. Historique des étapes réalisées (changelog)

> Grands jalons ci-dessous. Détail PR par PR depuis août 2026 (rôles IA, gestion des membres, file d'extraction séquentielle, correctifs…) : voir **[`CHANGELOG.md`](./CHANGELOG.md)**.

### 🔄 Juillet 2026 — Migration Hermes AI / Ollama / OVH VPS

**Changements majeurs :**
- ✅ **Suppression totale du provider Emergent** (`emergentintegrations` désinstallé, `EMERGENT_LLM_KEY` supprimée)
- ✅ **Hermes-3 via Ollama** sur VPS OVH devient le moteur IA par défaut (`ai_service.py` réécrit)
- ✅ **litellm mis à jour vers 1.80.0** comme couche d'abstraction pour les fallbacks tenant (OpenAI / Anthropic / Gemini)
- ✅ Variables d'environnement `HERMES_BASE_URL` et `HERMES_DEFAULT_MODEL` ajoutées
- ✅ `requirements.txt` mis à jour (suppression `emergentintegrations`, ajout `litellm==1.80.0`)
- ✅ README complet mis à jour (sections 1-16)

### Étapes précédentes

| Étape | Description |
|-------|-------------|
| Migration MongoDB → Supabase | `pg_adapter.py` + `models_sql.py` + `migrate_mongo_to_supabase.py` |
| Activation RLS | `enable_rls.py` — policy deny-all sur toutes les tables |
| Éditeur de devis v2 | Lignes typées, TVA par ligne, marge masquée, sélecteur catalogue |
| Import CSV universel | Auto-détection colonnes + mapping manuel + attributs dynamiques |
| Génération PDF Pro Forma | ReportLab — gabarit métier complet avec profil entreprise |
| Multi-tenant RBAC | Rôles `owner` / `admin` / `operator` / `viewer` / `billing_admin` |
| Internationalisation | react-i18next — FR / EN |
| Webhook n8n | Configurable par tenant dans les paramètres d'intégration |
| Journal d'audit | Table `audit_logs` — toutes les actions sensibles tracées |
| Profil entreprise PDF | SIRET, IBAN, mentions légales, conditions injectés dans le PDF |

---

## 16. Dépannage / FAQ

### Le backend ne démarre pas

**Symptôme :** `ValueError: JWT_SECRET is too weak or is the default value`
**Solution :** Générez un secret fort et ajoutez-le à `backend/.env` :
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

### Erreur de connexion PostgreSQL

**Symptôme :** `asyncpg.exceptions.InvalidAuthorizationSpecificationError`
**Solutions :**
- Vérifiez que `DATABASE_URL` utilise le port **6543** (Transaction Pooler), pas 5432
- Vérifiez les credentials dans le dashboard Supabase → Settings → Database
- Assurez-vous que la région est correcte dans l'URL

---

### L'extraction IA échoue

**Symptôme :** `ConnectionRefusedError` ou timeout sur `/api/requests/{id}/extract`
**Solutions :**
1. Vérifiez qu'Ollama tourne : `curl http://<HERMES_BASE_URL>/api/tags`
2. Vérifiez que le modèle `hermes-3` est bien téléchargé : `ollama list`
3. Si le VPS OVH est inaccessible, configurez un fallback OpenAI dans les paramètres d'intégration du tenant
4. Consultez les logs : `docker logs ollama` ou `journalctl -u ollama`

---

### `emergentintegrations` introuvable

**Symptôme :** `ModuleNotFoundError: No module named 'emergentintegrations'`
**Solution :** Ce module a été **supprimé** en juillet 2026. Mettez à jour votre installation :
```bash
pip install -r requirements.txt
```
Assurez-vous de ne plus avoir `emergentintegrations` dans votre `requirements.txt`.

---

### Import CSV — colonnes non détectées

**Symptôme :** Toutes les colonnes apparaissent comme « non mappées »
**Solutions :**
- Vérifiez l'encodage du fichier (UTF-8 ou Latin-1 acceptés)
- Vérifiez le séparateur (`,` ou `;` — auto-détecté)
- Utilisez le mapping manuel dans l'interface pour associer vos colonnes aux champs standard

---

### PDF Pro Forma — données entreprise manquantes

**Symptôme :** Le PDF ne contient pas le SIRET / IBAN / logo
**Solution :** Renseignez le profil entreprise dans **Paramètres → Profil entreprise** pour le tenant concerné.

---

### Erreur CORS en développement

**Symptôme :** `Access to XMLHttpRequest blocked by CORS policy`
**Solution :** Ajoutez `http://localhost:3000` dans `CORS_ORIGINS` de `backend/.env` :
```
CORS_ORIGINS=http://localhost:3000,https://<votre-domaine>
```

---

*Dernière mise à jour : 20 juillet 2026 — Migration Hermes AI / Ollama / OVH VPS*
