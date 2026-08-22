# Journal complet des actions — Optimisation IA locale VPS OVH & Blueseatra

> Compte rendu chronologique de tout ce qui a été fait, du diagnostic à la passation.
> Projet : faire tourner l'IA locale de **Blueseatra** sur **VPS OVH (CPU seul)** efficacement,
> corriger les anomalies, résoudre l'extraction PDF (tableaux), viser 10-100 utilisateurs.

---

## Table des matières
1. [Contexte & matériel](#1-contexte--matériel)
2. [Diagnostic (cause racine)](#2-diagnostic-cause-racine)
3. [Chronologie détaillée des actions](#3-chronologie-détaillée-des-actions)
4. [Fichiers créés / modifiés](#4-fichiers-créés--modifiés)
5. [Résultats de tests](#5-résultats-de-tests)
6. [Résultats VPS (pull des modèles)](#6-résultats-vps-pull-des-modèles)
7. [Statut de validation](#7-statut-de-validation)
8. [Backlog / suggestions d'amélioration](#8-backlog--suggestions-damélioration)

---

## 1. Contexte & matériel
- **Blueseatra** : SaaS BTP (FastAPI + React + Supabase/PostgreSQL). Demande client → extraction IA → rapprochement catalogue → brouillon de devis TCE. L'IA ne fixe jamais un prix.
- **ovh-ai-stack** : infra auto-hébergée (Ollama, Hermes Agent, n8n, Caddy).
- **VPS OVH Roubaix, CPU seul** : 8 vCPU / 22 Go RAM / swap 4 Go / **aucun GPU**.
- **Objectifs** : trouver les anomalies, meilleure architecture, meilleur choix d'IA locale (efficacité/rapidité), extraction PDF tabulaire fiable, 10-100 utilisateurs simultanés.

## 2. Diagnostic (cause racine)
Des **modèles de 17-18 Go en raisonnement** (`gemma4:26b`, `qwen3.6:27b`, `Phi-4-reasoning-vision-15B`) tournaient sur un **VPS CPU 22 Go** → **80 s à 11 min/doc**, `598 Mo` RAM libres, OOM. Rustines aggravantes : `OLLAMA_KEEP_ALIVE=0`, `mem_limit=18g`, cascades de 4 modèles (jusqu'à 900 s/étage), `think=True` forcé.

**Vérification factuelle** : les modèles existent bien sur le registre Ollama officiel (contrôlé via l'API des manifests) — le problème est le **surdimensionnement pour du CPU**, pas des noms erronés.

**Solution** : parsing déterministe des tableaux (pdfplumber) AVANT le LLM + petits modèles rapides (`qwen2.5:7b`, `qwen2.5vl:7b`) + traitement asynchrone (file). ~80 % du gain sans code (variables d'env).

---

## 3. Chronologie détaillée des actions

### Phase A — Diagnostic
1. Clarification du besoin (specs VPS, usage IA, charge cible, moteur) via questions.
2. Clone en lecture seule du repo `ovh-ai-stack` + lecture de tous les fichiers (README, compose, Caddyfile, hermes/config.yaml, ADR-001→004, scripts, skills, docs RGPD/sécurité).
3. Découverte que `/app` contient **le SaaS Blueseatra** (dont `backend/ai_service.py`, la couche d'intégration OVH).
4. Vérification des modèles contre le **registre Ollama** (`registry.ollama.ai`) : tailles réelles confirmées (gemma4:26b = 18 Go, qwen3.6:27b = 17,4 Go, qwen2.5:7b = 4,7 Go, qwen2.5vl:7b = 6 Go…).
5. Lecture de `ai_service.py` : mise en évidence des **cascades** (structuration 4 modèles ×900 s, OCR 4 étages, escalade Phi-4-15B « 12,5 min/page », `_wants_think` forçant le raisonnement).

### Phase B — Livrables d'architecture (`/app/ovh-ai-stack-corrige/`)
6. Audit chiffré (`docs/AUDIT.md`) : anomalies infra **I1-I11** + SaaS **S1-S8**, architecture cible.
7. Infra corrigée : `compose.yaml` (petits modèles chauds, `KEEP_ALIVE=30m`, limites CPU, service extraction, Hermes optionnel), `caddy/Caddyfile` (+ correctif Bearer Hermes), `hermes/config.yaml`, `.env.example`, `scripts/pull-models.sh`.
8. **Service d'extraction runnable** (`services/extraction/`) : pdfplumber (tableaux) → LLM `format=json`. **Testé** : tableau 4 lignes extrait, JSON structuré, **0 prix reporté**.
9. **File durable** (`services/queue/`) : RQ (Redis), Supabase `SKIP LOCKED`, n8n. **Démo testée** : pic 100 devis acceptés < 1 ms, drainés sans dépasser la concurrence bornée.
10. **Chiffrage GPU OVH** (`docs/GPU-OVH-CHIFFRAGE.md`) : reco **L4 24 Go Gravelines** ~€680/mois (ou ~€260 en extinction nocturne).
11. Docs pratiques : `FIX-IMMEDIAT-ENV.md`, `RENDER-ENV-A-COLLER.md`, `FILE-ATTENTE-ASYNC.md`, `scripts/pull-and-benchmark.sh`, `scripts/test-extraction-e2e.py`.

### Phase C — Corrections du code SaaS
12. `backend/ai_service.py` : défauts modèles → `qwen2.5:7b` / `qwen2.5vl:7b` (fini gemma4/qwen3.6/deepseek-r1/Phi-4-15B) ; `extract_pdf_text` **injecte les tableaux via pdfplumber** ; ajout `_OLLAMA_SEMAPHORE` (`OLLAMA_MAX_CONCURRENCY`). Validé par import + test unitaire.

### Phase D — Boot local du SaaS (dans le pod, sans secrets prod)
13. Installé PostgreSQL local + dépendances backend manquantes (rapidfuzz, sqlalchemy…).
14. `backend/.env` de test (secrets générés) + `frontend/.env` (URL preview) ; patch `database.py` (SSL non requis en localhost) ; tables via `Base.metadata.create_all`.
15. Backend validé en direct : `signup` → JWT + tenant, `login`, `/catalogs` (catalogue démo), `/requests`, `/quotes` → **200**.
16. Frontend non démarrable (deps Node 22 vs pod Node 20) → tests **API uniquement**.

### Phase E — Tests & correctifs (testing_agent)
17. `testing_agent` backend-only → **iteration_6 : 50/50 OK**, **aucune régression** de `ai_service.py`. A trouvé **1 bug pré-existant** : cache catalogue (`_CATALOG_CACHE`, 45 s) jamais invalidé → **prix périmés**.
18. **Fix** : helper `_evict_catalog_cache` appelé sur import/activate/deactivate/delete/**patch**. `testing_agent` → **iteration_7 : 56/56 OK**, fenêtre de prix périmés supprimée. PATCH vérifié via repro + curl.

### Phase F — Items d'amélioration demandés
19. **« Un seul actif »** : `_deactivate_other_catalogs` — activer un catalogue désactive les autres du tenant.
20. **« Cache partagé »** : cache catalogue **Redis opt-in** (`REDIS_URL`) + `_load_active_catalog` ; fallback in-memory identique.
21. **« File durable » (wiring)** : `create_request` met le job en file **RQ** si `REDIS_URL` (+ pas d'octets vision, RGPD) ; sinon `BackgroundTasks`. Worker `backend/extraction_worker.py`.
22. **Vérifications manuelles** : `pytest` **56/56 en mode in-memory ET en mode Redis** ; **enqueue RQ end-to-end** constaté (POST → Redis → worker → statut mis à jour). *(testing_agent non relancé — passation demandée.)*

### Phase G — Documentation & passation
23. Créé `/app/HANDOFF.md` (passation complète) + section « Journal des changements » dans `/app/README.md` + enrichi `ovh-ai-stack-corrige/README.md` + MàJ `/app/memory/PRD.md` et `test_credentials.md`.

### Phase H — Déploiement modèles sur le VPS (fait par l'utilisateur)
24. `ollama pull qwen2.5:7b` + `qwen2.5vl:7b` sur le VPS → présents (4,7 Go + 6 Go).
25. Contrôle RAM : **21 Go disponibles / 22** (ollama à 196 Mo, aucun gros modèle chargé) → confirme la cause racine.
26. Réglage recommandé (intérim) : `OLLAMA_NUM_PARALLEL=2`, `MAX_LOADED_MODELS=2`, `KEEP_ALIVE=30m`, `CONTEXT_LENGTH=16384` ; mesure `--verbose` conseillée pour figer la valeur.

---

## 4. Fichiers créés / modifiés

### Code de production Blueseatra (`/app/backend/`)
| Fichier | Type | Quoi / Pourquoi |
|---|---|---|
| `ai_service.py` | modif | Défauts modèles 7B ; tableaux pdfplumber dans `extract_pdf_text` ; sémaphore de concurrence Ollama. |
| `server.py` | modif | Invalidation cache catalogue (5 sites) ; un seul catalogue actif ; cache Redis opt-in ; enqueue RQ opt-in. |
| `database.py` | modif | SSL non requis pour PostgreSQL `localhost` (Supabase inchangé en prod). |
| `extraction_worker.py` | nouveau | Worker RQ de la file d'extraction. |
| `requirements.txt` | modif | `redis==8.1.0`, `rq==2.11.0`. |

### Livrables infra (`/app/ovh-ai-stack-corrige/`)
`docs/AUDIT.md`, `docs/FIX-IMMEDIAT-ENV.md`, `docs/RENDER-ENV-A-COLLER.md`, `docs/GPU-OVH-CHIFFRAGE.md`, `docs/FILE-ATTENTE-ASYNC.md`, `compose.yaml`, `caddy/Caddyfile`, `hermes/config.yaml`, `.env.example`, `scripts/pull-models.sh`, `scripts/pull-and-benchmark.sh`, `scripts/test-extraction-e2e.py`, `services/extraction/*`, `services/queue/*`.

### Documentation
`/app/HANDOFF.md`, `/app/JOURNAL-ACTIONS.md` (ce document), section ajoutée à `/app/README.md`, `/app/memory/PRD.md`, `/app/memory/test_credentials.md`.

> ⚠️ `backend/.env`, `frontend/.env`, `backend/.env.test.template` = **artefacts de TEST** (gitignore, non versionnés). Toutes les nouveautés Redis sont **opt-in** : sans `REDIS_URL`, comportement identique à l'existant.

---

## 5. Résultats de tests
- **iteration_6** (testing_agent, backend-only) : **50/50** ✅ — aucune régression `ai_service.py` ; bug cache catalogue détecté.
- **iteration_7** (testing_agent) : **56/56** ✅ — fix cache validé, fenêtre de prix périmés supprimée.
- **pytest local** : **56/56** en mode in-memory **et** en mode Redis ✅.
- **File RQ** : enqueue → worker → traitement constaté end-to-end ✅.
- **Service d'extraction de référence** : tableau extrait + JSON structuré + 0 prix ✅.
- **Démo file** : pic 100 devis, concurrence bornée respectée ✅.

## 6. Résultats VPS (pull des modèles)
```
qwen2.5vl:7b    6.0 GB
qwen2.5:7b      4.7 GB
# (les gros modèles gemma4:26b / qwen3.6:27b / Phi-4-15B sont encore présents sur disque)

free -h : total 22Gi | used 1.5Gi | free 14Gi | available 21Gi
ollama container : 196 MiB (aucun modèle chargé)
```
➡️ **RAM saine (21 Go dispo)** — preuve que le goulet venait des modèles 17-18 Go, pas du VPS.

## 7. Statut de validation
| Élément | Statut |
|---|---|
| Flux métier (auth/catalogue/devis/PDF) | ✅ testing_agent 56/56 |
| Fix cache catalogue (prix périmés) | ✅ testing_agent + repro |
| `ai_service.py` (7B, tableaux, sémaphore) | ✅ testing_agent + unit |
| Single-active / cache Redis / file RQ | ⚠️ vérifié manuellement (pytest 56/56 + enqueue e2e) — **testing_agent à relancer** |
| Extraction IA réelle (vs VPS) | ❌ non testable dans le pod → `scripts/test-extraction-e2e.py` depuis Render→VPS |
| Frontend | ❌ non démarré (Node 22 vs 20) |

## 8. Backlog / suggestions d'amélioration
**P0** — `ollama pull` (fait ✅) ; mesurer le débit (`ollama run --verbose`) et figer `OLLAMA_NUM_PARALLEL` ; coller les env Render ; lancer le test e2e réel.
**P1** — déployer `compose.yaml` + `services/extraction/` ; provisionner Redis + worker en prod (ou Supabase `SKIP LOCKED`) ; corriger Bearer Hermes si exposé ; aligner les timeouts inter-couches ; relancer testing_agent sur les 3 items « ⚠️ ».
**P2** — GPU L4 Gravelines si synchrone rapide requis (a priori superflu) ; simplifier les cascades restantes ; `OLLAMA_CONTEXT_LENGTH=16384` ; healthcheck `ollama ps` ; limites `cpus:` par conteneur ; observabilité (temps par étape + modèle réellement utilisé) ; router au VLM uniquement les vrais scans ; retirer les gros modèles du disque VPS pour éviter tout rechargement accidentel.
**Dette** — `frontend/yarn.lock` généré en Node 20 (à ne pas committer si CI Node 22) ; cache in-memory reste local au process sans `REDIS_URL`.
