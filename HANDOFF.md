# HANDOFF — Optimisation de l'IA locale (VPS OVH) & durcissement Blueseatra

> Document de passation pour le prochain agent IA / développeur.
> Période : juin 2026. Périmètre : faire tourner l'IA locale de Blueseatra sur VPS OVH
> (CPU seul) de façon efficace, corriger les anomalies, et durcir le SaaS.
> **Aucun test lancé sur cette dernière étape** (passation demandée). Statut de validation détaillé plus bas.

---

## 1. Contexte & objectif

- **Blueseatra** = SaaS BTP (FastAPI + React + Supabase/PostgreSQL) : demande client → extraction IA → rapprochement catalogue → brouillon de devis TCE. L'IA ne fixe jamais un prix.
- **ovh-ai-stack** = infra auto-hébergée (Ollama, Hermes Agent, n8n, Caddy) sur **VPS OVH Roubaix, CPU seul : 8 vCPU / 22 Go RAM / swap 4 Go, aucun GPU**.
- **Demande initiale** : lire le repo, trouver les anomalies, proposer la meilleure architecture et le meilleur choix d'IA locale (efficacité/rapidité), résoudre l'extraction PDF (surtout tableaux), tenir 10-100 utilisateurs simultanés.

## 2. Cause racine (résumé exécutif)

Des **modèles de 17-18 Go en mode raisonnement** (`gemma4:26b`, `qwen3.6:27b`, `Phi-4-reasoning-vision-15B`) tournaient sur un **VPS CPU de 22 Go**. Mesures réelles constatées : **80 s à 11 min par extraction**, `598 Mo` de RAM libres. Pour compenser, des rustines aggravantes s'étaient accumulées (`OLLAMA_KEEP_ALIVE=0`, `mem_limit=18g`, cascades de 4 modèles à 900 s/étage, `think=True` forcé).

**Solution retenue** : parsing déterministe des tableaux (pdfplumber) AVANT le LLM + petits modèles rapides (`qwen2.5:7b`, `qwen2.5vl:7b`) + traitement asynchrone (file). **~80 % du gain s'obtient sans code**, par variables d'environnement.

---

## 3. Actions réalisées (chronologique)

1. **Audit** du repo `ovh-ai-stack` (cloné en lecture seule) + du SaaS Blueseatra présent dans `/app` (module `backend/ai_service.py`). Vérification des modèles contre le **registre Ollama officiel** (les modèles existent bien, mais sont surdimensionnés pour du CPU).
2. **Livrable infra corrigé** dans `/app/ovh-ai-stack-corrige/` (compose, Caddyfile, hermes config, scripts, .env.example, service d'extraction, docs).
3. **Service d'extraction de référence** (`services/extraction/`) : pdfplumber (tableaux) → LLM `format=json`. Testé en isolation (tableau 4 lignes extrait, JSON structuré, 0 prix reporté).
4. **Correctifs code `backend/ai_service.py`** : défauts de modèles → `qwen2.5:7b` / `qwen2.5vl:7b` ; `extract_pdf_text` injecte les tableaux via **pdfplumber** ; ajout d'un `asyncio.Semaphore` (`OLLAMA_MAX_CONCURRENCY`).
5. **File durable** (`services/queue/`) : RQ (Redis), Supabase `SKIP LOCKED`, n8n — + démo testée (pic 100 devis, concurrence bornée).
6. **Chiffrage GPU OVH** (`docs/GPU-OVH-CHIFFRAGE.md`) : reco NVIDIA L4 24 Go Gravelines (~€680/mois 24/7, ~€260 en extinction nocturne).
7. **Boot local du SaaS dans le pod** (sans secrets prod) : PostgreSQL local, `backend/.env` de test, `frontend/.env`, patch `database.py` (SSL non requis en localhost), tables créées. Backend validé (auth/catalogue/devis → 200).
8. **testing_agent (backend-only)** : `iteration_6` = 50/50 OK (aucune régression `ai_service.py`) ; a trouvé un bug **pré-existant** de cache catalogue (prix périmés 45 s).
9. **Fix cache catalogue** : helper `_evict_catalog_cache` appelé sur import/activate/deactivate/delete/PATCH. `iteration_7` = 56/56 OK, fenêtre de prix périmés supprimée.
10. **Item « Un seul actif »** : `_deactivate_other_catalogs` — activer un catalogue désactive les autres du tenant.
11. **Item « Cache partagé »** : cache catalogue **opt-in Redis** (`REDIS_URL`), invalidation inter-workers/pods ; fallback in-memory identique à l'existant.
12. **Item « File durable » (wiring)** : `create_request` met le job en file Redis (RQ) si `REDIS_URL` + pas d'octets vision (RGPD) ; sinon `BackgroundTasks` (comportement historique). Worker `backend/extraction_worker.py`.

---

## 4. Fichiers modifiés / créés

### SaaS Blueseatra (`/app`) — code de production
| Fichier | Type | Quoi / Pourquoi |
|---|---|---|
| `backend/ai_service.py` | modif | Défauts modèles → 7B ; `extract_pdf_text` + tableaux pdfplumber ; `_OLLAMA_SEMAPHORE` (borne la concurrence Ollama). |
| `backend/server.py` | modif | `_evict_catalog_cache` (5 sites) ; `_deactivate_other_catalogs` (1 seul catalogue actif) ; cache **Redis opt-in** (`_redis_async`, `_load_active_catalog`) ; **enqueue RQ opt-in** (`_redis_sync`, `_enqueue_extraction`) dans `create_request`. |
| `backend/database.py` | modif | SSL non requis pour un PostgreSQL `localhost` (Supabase inchangé en prod : SSL requis). |
| `backend/extraction_worker.py` | **nouveau** | Worker RQ de la file d'extraction (`python extraction_worker.py`). |
| `backend/requirements.txt` | modif | Ajout `redis==8.1.0`, `rq==2.11.0`. |

### Infra + livrables (`/app/ovh-ai-stack-corrige/`) — à copier vers le repo `ovh-ai-stack`
| Chemin | Rôle |
|---|---|
| `docs/AUDIT.md` | Audit complet des 2 repos, anomalies chiffrées (I1-I11 infra, S1-S8 SaaS), architecture cible. |
| `docs/FIX-IMMEDIAT-ENV.md` | Correctif sans code (variables Render). |
| `docs/RENDER-ENV-A-COLLER.md` | Bloc de variables Render prêt à coller. |
| `docs/GPU-OVH-CHIFFRAGE.md` | Grille de prix GPU OVH + reco L4. |
| `docs/FILE-ATTENTE-ASYNC.md` | 3 options de file durable. |
| `compose.yaml`, `caddy/Caddyfile`, `hermes/config.yaml`, `.env.example` | Infra corrigée (petits modèles chauds, limites CPU, Bearer Hermes, Hermes optionnel). |
| `scripts/pull-models.sh`, `scripts/pull-and-benchmark.sh` | Pull des petits modèles + benchmark VPS. |
| `scripts/test-extraction-e2e.py` | **Test e2e RÉEL** de l'extraction contre `ia.blueseatra.com` (à lancer depuis Render/poste). |
| `services/extraction/` | Service d'extraction runnable (pdfplumber + Ollama). |
| `services/queue/` | File durable : RQ (`rq_worker.py`), Supabase (`supabase_queue.sql` + `supabase_worker.py`), démo (`queue_demo.py`). |

> ⚠️ **Fichiers `.env` non versionnés** (`.gitignore` : `.env`, `.env.*`, `*.env`). `backend/.env`, `frontend/.env`, `backend/.env.test.template` sont **des artefacts de TEST du pod** (secrets générés, DB locale) — **ne pas** les utiliser en prod, ils ne partent pas sur GitHub.

---

## 5. Statut de validation (honnête)

| Élément | Validé ? | Comment |
|---|---|---|
| `ai_service.py` (défauts 7B, tableaux pdfplumber, sémaphore) | ✅ | Import + test unitaire d'extraction de tableau. testing_agent iteration_6 (50/50, 0 régression). |
| Flux métier non-IA (auth, catalogue, devis, PDF, dashboard) | ✅ | testing_agent iteration_6/7 (jusqu'à 56/56). |
| Fix cache catalogue (prix périmés) | ✅ | testing_agent iteration_7 + repro + curl. |
| « Un seul actif », cache Redis, file RQ | ⚠️ **Non validé par testing_agent** | Vérifié manuellement dans le pod (pytest 56/56 en modes in-memory ET Redis ; enqueue RQ end-to-end constaté : POST → Redis → worker → statut mis à jour). **Le testing_agent n'a PAS été relancé** sur ces 3 derniers points (passation demandée). |
| Extraction IA réelle (contre le VPS) | ❌ **Impossible ici** | Ollama/OVH `ia.blueseatra.com` injoignable depuis le pod. À valider via `scripts/test-extraction-e2e.py` depuis Render/poste. |
| Frontend | ❌ **Non démarré** | Deps ciblant Node 22, pod en Node 20. Tests API uniquement. |

**➡️ Prochain agent : relancer le `testing_agent` sur les 3 points « ⚠️ » (single-active, cache Redis, file RQ) pour une validation faisant autorité.**

---

## 6. Environnement de test local (dans le pod)

- PostgreSQL local : `postgresql://blueseatra:blueseatra@localhost:5432/blueseatra`, schéma `public`, tables via `Base.metadata.create_all`.
- Redis local : `redis://localhost:6379/0` (activé dans `backend/.env` de test → mode Redis actif).
- Worker RQ lancé : `python extraction_worker.py` (arrière-plan).
- Compte QA : `qa@example.com` / `Test1234!` (voir `/app/memory/test_credentials.md`).
- Backend URL preview : `https://d2e91b73-c029-4dbb-81e6-45269ce77da7.preview.emergentagent.com` (préfixe `/api`).
- Suites de tests : `/app/backend/tests/` (dont `test_single_active_catalog.py`, `test_redis_queue.py`, `repro_*` créés durant les runs). Rapports : `/app/test_reports/iteration_6.json`, `iteration_7.json`.

> Pour repasser en comportement de PROD (in-memory + BackgroundTasks) : retirer `REDIS_URL` de l'environnement. Tout est **opt-in**.

---

## 7. Backlog / suggestions d'amélioration

### P0 — à faire côté infra (utilisateur, hors pod)
- [ ] **Modèles VPS** : `ollama pull qwen2.5:7b` + `qwen2.5vl:7b`, puis `scripts/pull-and-benchmark.sh` pour mesurer le temps réel d'extraction.
- [ ] **Env Render** : coller `docs/RENDER-ENV-A-COLLER.md` (ou s'appuyer sur les défauts code déjà en 7B).
- [ ] **Test extraction réel** : lancer `scripts/test-extraction-e2e.py` depuis Render/poste vers `ia.blueseatra.com` ; ajuster `OLLAMA_NUM_PARALLEL` selon la mesure.

### P1 — architecture / robustesse
- [ ] **Déployer** `compose.yaml` corrigé + `services/extraction/` sur le VPS.
- [ ] **File durable en prod** : provisionner Redis + un Background Worker Render (`python extraction_worker.py`), ou l'option Supabase `SKIP LOCKED`.
- [ ] **Corriger le gap Bearer Hermes** dans Caddy si Hermes est exposé (déjà corrigé dans le Caddyfile livré).
- [ ] **Aligner les timeouts** entre couches (SaaS ≥ Hermes ≥ modèle) — inutile de garder 900 s une fois les gros modèles retirés.
- [ ] **Relancer testing_agent** sur single-active / cache Redis / file RQ (validation faisant autorité).

### P2 — qualité produit & scale
- [ ] **GPU L4** (Gravelines) si besoin de synchrone rapide à 100 users ou de gros modèles (voir chiffrage).
- [ ] **Simplifier les cascades** restantes de `ai_service.py` (OCR 4 étages, timeouts ésotériques) une fois les petits modèles confirmés.
- [ ] **Contexte modèle** : passer `OLLAMA_CONTEXT_LENGTH` à 16384 pour les devis multi-pages.
- [ ] **Healthcheck Ollama** : `ollama ps` au lieu de `ollama list`.
- [ ] **Limites CPU** par conteneur (`cpus:`) pour ne pas affamer Caddy/n8n.
- [ ] **Observabilité** : journaliser le temps par étape (parse / LLM) et le modèle réellement utilisé, pour détecter tout retour aux gros modèles.
- [ ] **Vision** : ne router vers le VLM (`qwen2.5vl:7b`) QUE les vrais scans/photos (PDF sans couche texte).

### Dette / points ouverts
- [ ] **`frontend/yarn.lock`** généré dans le pod (Node 20, `--ignore-engines`) — ne pas committer tel quel si votre CI attend Node 22.
- [ ] **Deux catalogues actifs** : désormais résolu (un seul actif) — vérifier qu'aucun flux existant ne dépendait du comportement précédent.
- [ ] **`_CATALOG_CACHE` in-memory** reste utilisé si `REDIS_URL` absent ; sur plusieurs workers sans Redis, l'invalidation reste locale au process (documenté, opt-in Redis pour y remédier).
