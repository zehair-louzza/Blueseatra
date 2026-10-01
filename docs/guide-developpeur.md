# Guide développeur

Installation locale, variables d'environnement, tests et dépannage. Pour la vue d'ensemble, lire d'abord [`architecture.md`](./architecture.md) ; pour la production, [`exploitation.md`](./exploitation.md).

## Installation locale

![Architecture Blueseatra](./assets/schema-architecture.png)

### Pré‑requis

- Python **3.11**
- Node.js **20** et npm (installer avec `npm install --legacy-peer-deps`)
- Un projet **Supabase** (gratuit) OU un PostgreSQL accessible
- **Ollama** installé localement avec le modèle `hermes-3` (`ollama pull hermes-3`) — **ou** une clé OpenAI/Anthropic/Gemini à configurer par tenant dans les paramètres

### 1) Récupérer le code

```bash
git clone https://github.com/zehair-louzza/Blueseatra.git blueseatra && cd blueseatra
```

### 2) Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

Créez `backend/.env` (voir [Variables d'environnement](#variables-denvironnement)) en renseignant au minimum `DATABASE_URL`, `JWT_SECRET`, `APP_ENCRYPTION_KEY`, `HERMES_BASE_URL`.

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 3) Frontend

```bash
cd ../frontend
npm install --legacy-peer-deps
# Créez frontend/.env avec REACT_APP_BACKEND_URL=http://localhost:8001
npm start   # démarre sur le port 3000
```

### 4) Ollama (moteur IA local)

```bash
# Installer Ollama : https://ollama.com/download
ollama pull hermes-3
ollama serve   # écoute sur http://localhost:11434
```

> Pour utiliser le VPS OVH en dev, pointez `HERMES_BASE_URL` vers l'URL publique de votre instance Ollama distante.

## Variables d'environnement

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


#### Variables ajoutées depuis septembre 2026

| Variable | Description |
|----------|-------------|
| `DATABASE_URL_APP` | Connexion avec le rôle **`blueseatra_app`** (non propriétaire) : c'est elle qui applique la RLS en production. Voir [`runbook-render-database-url-app.md`](./runbook-render-database-url-app.md) |
| `DATABASE_URL_AUTH` | **Obsolète.** Encore détectée pour avertir au démarrage ; ne plus la définir |
| `DB_SCHEMA` | Schéma PostgreSQL, `blueseatra`. La CI refuse `public` |
| `BLUESEATRA_QUOTAS_APPLIQUES` | `0` : les quotas sont comptés sans bloquer (observation). `1` : une offre épuisée bloque les nouvelles lectures IA |
| `REDIS_URL` | File d'extraction séquentielle et cache catalogue (facultatif ; repli en mémoire) |
| `OLLAMA_MAX_CONCURRENCY` | Nombre de lectures IA simultanées envoyées au VPS |
| `HERMES_OCR_MODEL`, `HERMES_OCR_SECONDARY_MODEL`, `HERMES_OCR_TERTIARY_MODEL`, `HERMES_OCR_ESCALATION_MODEL`, `HERMES_OCR_GLM_MODEL` | Cascade OCR (voir [`decisions/ADR-OCR-CASCADE.md`](./decisions/ADR-OCR-CASCADE.md)) |
| `HERMES_STRUCTURING_MODEL_1..3`, `HERMES_REASONING_EFFORT` | Modèles de structuration en lots et effort de raisonnement |
| `HERMES_GATEWAY_URL`, `HERMES_GATEWAY_KEY`, `HERMES_GATEWAY_MODEL` | Passerelle IA facultative |
| `MCP_API_KEY`, `MCP_TENANT_ID` | Pont MCP (`/mcp`), voir [`MCP-PERPLEXITY.md`](./MCP-PERPLEXITY.md) |
| `BLUESEATRA_IA_COUPURE` | Coupure d'urgence de l'IA : vide (normal), `repli` ou `arret` |
| `BLUESEATRA_IA_REPLI_PROVIDER`, `BLUESEATRA_IA_REPLI_MODEL`, `BLUESEATRA_IA_REPLI_KEY` | Fournisseur de repli utilisé quand `BLUESEATRA_IA_COUPURE=repli` |
| `MISTRAL_API_KEY` | Clé Mistral de la plateforme, utilisée par les entreprises sans clé propre |
| `MISTRAL_MODEL` | Modèle Mistral par défaut (`mistral-medium-latest`) |
| `BLUESEATRA_IA_FOURNISSEUR_DEFAUT` | `mistral` pour faire de Mistral le moteur des entreprises sans réglage (défaut `hermes`) |
| `STRIPE_SECRET_KEY` | Clé secrète Stripe (`sk_test_…` ; une clé live est refusée sans `BLUESEATRA_STRIPE_LIVE=1`) |
| `STRIPE_WEBHOOK_SECRET` | Secret de signature du point de terminaison webhook (`whsec_…`) |
| `BLUESEATRA_STRIPE_LIVE` | `1` uniquement après validation de la bascule en production (Epic 7) |
| `BLUESEATRA_APP_URL` | Adresse du site pour les retours de paiement (défaut `https://blueseatra.com`) |
| `LOG_FORMAT` | `json` pour des journaux structurés (automatique sur Render), `texte` sinon |
| `BLUESEATRA_METRICS_TOKEN` | Active `GET /api/exploitation/mesures` ; à lire avec l'en-tête `X-Metrics-Token` |
| `LOG_PSEUDO_SEL` | Sel des empreintes d'e-mail et d'entreprise dans les journaux |
| `RENDER_GIT_COMMIT` | Fourni par Render ; renvoyé par `/api/health` pour savoir quelle version tourne |

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

## Base de données et migrations

### Migrations

Les **14 migrations** versionnées dans [`supabase/migrations/`](../supabase/migrations) sont la référence du schéma `blueseatra` (catalogue commun, RLS, quotas, module Clients…). Elles sont **additives et rejouables** (`IF NOT EXISTS`) et contrôlées par la CI (`ci-infra.yml`).

- Production : appliquées sur Supabase, une par une, après relecture. Aucune migration ne supprime de données.
- Local : appliquer les fichiers dans l'ordre sur un PostgreSQL 17 après `.github/ci/amorce_tests.sql`.
- Les tables historiques sont encore créées par SQLAlchemy au premier démarrage (`create_all`) ; `migrate_mongo_to_supabase.py` et `enable_rls.py` ne servent qu'à la migration de juillet 2026.

### Isolation des entreprises (RLS)

![Isolation des entreprises](./assets/schema-isolation.png)

L'API se connecte avec le rôle **`blueseatra_app`** (`DATABASE_URL_APP`), qui n'est pas propriétaire des tables. Chaque transaction fixe `app.tenant_id`, et chaque politique compare `tenant_id` à `blueseatra.current_tenant()`. Le détail et l'historique sont dans [`audit-isolation-tenants-2026-09-12.md`](./audit-isolation-tenants-2026-09-12.md).

### Connexion recommandée

Utilisez le **Transaction Pooler** (port **6543**) de Supabase pour le backend asynchrone (asyncpg). Ne pas utiliser le port 5432 direct en production.

```
postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Consultez `backend/SUPABASE_MIGRATION.md` pour le guide complet de migration depuis MongoDB.

## Tests

| Suite | Contenu | Commande |
|---|---|---|
| `backend/tests_security` | Isolation entre entreprises (statique et réelle), garde-fou `DB_SCHEMA`, fonctions de recherche sous RLS (sur base jetable) | `cd backend && python -m pytest tests_security -q` |
| `backend/tests_clients` | Règles de relance, migration Clients, API de bout en bout | voir ci-dessous |
| `backend/tests_quotas` | Registre de consommation, réservation, remboursement | voir ci-dessous |
| `backend/tests` | Extraction IA, cache catalogue, file d'extraction | `cd backend && python -m pytest tests -q` |

Les tests SQL tournent **uniquement sur une base PostgreSQL jetable**, jamais sur Supabase (les tests le vérifient) :

```bash
createdb ci && psql -d ci -f .github/ci/amorce_tests.sql
TEST_PG_DSN='postgresql://postgres@localhost:5432/ci' \
  python -m pytest backend/tests_clients/test_relances_regles.py \
                   backend/tests_clients/test_module_clients_sql.py \
                   backend/tests_quotas/test_quotas_sql.py \
                   backend/tests_security/test_offres_candidates_sql.py -q
```

`test_offres_candidates_sql.py` crée lui-même un jeu d'offres avec les vraies politiques RLS (extension `pg_trgm` requise) et vérifie les fonctions de recherche : isolation, injection, droits, exactitude des deux chemins (trigramme et index par prix), filtre de famille.

Les tests de bout en bout de l'API (`test_module_clients_api.py`, `test_quotas_module.py`) demandent une base complète et un rôle de connexion membre de `blueseatra_app` : variables `TEST_PG_URL` et `TEST_PG_URL_APP`.

### Intégration continue

![Chaîne de livraison](./assets/schema-livraison.png)

| Workflow | Contrôles |
|---|---|
| [`ci-infra.yml`](../.github/workflows/ci-infra.yml) | lint Python, cohérence des migrations, recherche de secrets |
| [`securite.yml`](../.github/workflows/securite.yml) | isolation inter-tenants, `DB_SCHEMA` jamais `public` |
| [`tests-metier.yml`](../.github/workflows/tests-metier.yml) | règles de relance, quotas et module Clients sur PostgreSQL 17 |

## Référence API

La liste complète des routes est générée depuis le code : [`reference-api.md`](./reference-api.md). Pour la régénérer :

```bash
python scripts/docs/generer_reference_api.py
```

## Scripts et maintenance

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

## Dépannage

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

