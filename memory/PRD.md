# PRD — Audit & optimisation IA locale VPS OVH (Blueseatra / ovh-ai-stack)

## Problème initial (utilisateur)
Faire tourner l'IA locale sur un VPS OVH (Roubaix) pour le SaaS Blueseatra (demande → devis
TCE, extraction PDF surtout tableaux). Symptômes : lenteur (jusqu'à 11 min/doc), OOM, timeouts,
mauvais choix de modèles. Cible : 10-100 utilisateurs simultanés. Moteur : Ollama (+ Hermes, n8n, Caddy).

## Matériel
VPS OVH **CPU seul, 8 vCPU, 22 Go RAM, swap 4 Go, aucun GPU**.

## Cause racine
Modèles 17-18 Go (`gemma4:26b`, `qwen3.6:27b`, `Phi-4-reasoning-vision-15B`) en mode raisonnement
sur CPU 22 Go → OOM + 80 s-11 min/doc. Rustines aggravantes : `OLLAMA_KEEP_ALIVE=0`, cascades de
4 modèles à 900 s/étage dans `ai_service.py`, `think=True` forcé.

## Décision d'architecture
1. Parsing déterministe des tableaux (pdfplumber) AVANT le LLM.
2. Petits modèles chauds : `qwen2.5:7b` (texte→JSON), `qwen2.5vl:7b` (vision).
3. Traitement asynchrone (file) pour 10-100 users.
4. Hermes hors chemin critique (profil optionnel).
5. GPU (L4 24 Go Gravelines) uniquement si synchrone rapide / gros modèles requis.

## Livré (2026-06)
- `/app/ovh-ai-stack-corrige/` : infra corrigée (compose, Caddyfile, hermes config, pull-models, .env),
  service d'extraction runnable (pdfplumber + LLM `format=json`), et docs :
  - `docs/AUDIT.md` (anomalies infra I1-I11 + SaaS S1-S8, architecture cible)
  - `docs/FIX-IMMEDIAT-ENV.md` (correctif sans code via env Render)
  - `docs/GPU-OVH-CHIFFRAGE.md` (prix OVH + reco L4)
- Test e2e exécuté ✅ : tableau extrait, JSON structuré, aucun prix reporté.

## Statut
- Audit + architecture + chiffrage GPU : FAIT.
- Service d'extraction de référence : FAIT + testé (exécution directe).
- Correctifs appliqués au code `backend/ai_service.py` (validés à l'import + test tableau isolé) :
  - défauts modèles → qwen2.5:7b / qwen2.5vl:7b (fini gemma4:26b / qwen3.6:27b / deepseek-r1 / Phi-4-15B) ;
  - `extract_pdf_text` injecte désormais les tableaux via pdfplumber (structure préservée) ;
  - limiteur de concurrence `_OLLAMA_SEMAPHORE` (OLLAMA_MAX_CONCURRENCY, défaut 2).
- SaaS non bootable dans le pod : dépendances venv incomplètes (rapidfuzz/sqlalchemy installés) +
  `backend/.env` absent (JWT_SECRET + Supabase requis) → config utilisateur, hors périmètre.
- Docs ajoutées : FILE-ATTENTE-ASYNC.md, RENDER-ENV-A-COLLER.md.

## Backlog / prochaines étapes
- P0 : appliquer FIX-IMMEDIAT-ENV.md sur Render, `ollama pull qwen2.5:7b` + `qwen2.5vl:7b` (script `scripts/pull-and-benchmark.sh`).
- P1 : déployer compose + service extraction corrigés sur le VPS.
- P1 : file durable — livrée en 3 options (RQ `services/queue/rq_worker.py`, Supabase SKIP LOCKED `supabase_queue.sql`+`supabase_worker.py`, n8n) ; démo `queue_demo.py` testée (pic 100 devis, concurrence bornée à 2). Reste : provisionner Redis/worker sur Render OU exécuter le SQL Supabase + wiring `create_request`.
- P2 : évaluer GPU L4 si synchrone rapide requis ; simplifier les cascades de `ai_service.py`.

## Limite d'environnement (rappel)
Le SaaS Blueseatra ne démarre pas dans le pod (venv incomplet + `backend/.env` absent : JWT_SECRET + Supabase). Le testing_agent n'est donc pas exécutable ; validations faites par exécution directe isolée (import ai_service, extraction tableau pdfplumber, démo file).
