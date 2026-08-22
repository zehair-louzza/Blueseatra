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
- NON APPLIQUÉ automatiquement au SaaS live Blueseatra (Supabase externe, non bootable ici) :
  les correctifs `ai_service.py` sont fournis en env-vars + module de référence, à appliquer par l'utilisateur.

## Backlog / prochaines étapes
- P0 : appliquer FIX-IMMEDIAT-ENV.md sur Render, `ollama pull qwen2.5:7b` + `qwen2.5vl:7b`.
- P1 : déployer compose + service extraction corrigés sur le VPS.
- P1 : brancher file d'attente async (n8n / Redis-RQ) pour la concurrence 10-100.
- P2 : évaluer GPU L4 si synchrone rapide requis ; simplifier les cascades de `ai_service.py`.
