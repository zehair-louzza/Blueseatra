# Changelog

## 2026-08-25/26 — Gestion des membres, affichage suggestion catalogue, file d'extraction séquentielle

PR #60 à #64 sur `main`.

### Documentation (PR #60)
- README/CHANGELOG mis à jour avec les rôles IA par clé dédiée (voir entrée précédente) et le correctif Gemma frontend.

### Correctif affichage suggestion catalogue (PR #61)
- Bug réel signalé par l'utilisateur : une ligne à correspondance ambiguë (`status="to_confirm"`, score 45-89) ne recevait volontairement aucun prix automatique (comportement voulu de `matching.py` — jamais de prix sur une correspondance incertaine), mais le frontend n'affichait alors **rien du tout**, laissant croire que l'IA n'avait pas cherché dans le catalogue alors que l'article y était bien présent.
- `QuoteEditor.js` affiche désormais l'indice de suggestion (`suggested_item_code` / `suggested_label`, déjà calculé par le backend mais jamais rendu) sur chaque ligne `to_confirm`, avec un texte explicite invitant à confirmer via « Ajouter depuis le catalogue ».

### Gestion des membres (PR #62, #63)
- `DELETE /api/members/{user_id}` : retire un membre du tenant. Refuse de retirer le dernier `owner` ou de se retirer soi-même.
- `PATCH /api/members/{user_id}` étendu : accepte désormais `name` (renommer un membre) et `password` — ce dernier **réservé au rôle owner** (403 pour un admin), pour que le changement de mot de passe d'un membre ne soit possible que depuis le compte owner.
- Page Membres (`Members.js`) : édition inline du nom (crayon), bouton Supprimer avec confirmation, bouton «clé» (changement de mot de passe) visible uniquement pour le rôle owner.

### File d'extraction séquentielle (PR #64)
- Bug de production confirmé le 25/08 : 5 demandes créées à ~2 min d'intervalle sont restées bloquées sur `processing` pendant 80+ minutes ; le VPS était en réalité inactif (0 % CPU) au moment du contrôle — contention CPU entre extractions concurrentes, puis perte des tâches en mémoire lors d'un redéploiement Render.
- Nouvelle file FIFO in-process (`asyncio.Queue` + une tâche de fond persistante) : une seule extraction IA à la fois, dans l'ordre d'arrivée. Nouveau statut `queued` avec position réelle exposée par l'API et affichée clairement dans le SaaS (« En file d'attente (position N) »).
- Filet de sécurité au démarrage (`_requeue_stuck_on_startup`) : toute demande encore `queued`/`processing` au redémarrage du service est remise en file automatiquement — a réparé seul les 5 demandes bloquées en production.
- Détail complet et alternatives écartées : [`docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md`](./docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md).

## 2026-08-25 — Rôles IA isolés (describe) + garde-fous hallucination + correctif Gemma frontend

PR #55 à #59 sur `main`.

### Rôles IA par clé dédiée (`ai_service.py`)
- Nouveau rôle `describe`, strictement confiné aux champs **Description des travaux** et **Étapes à suivre** — ne touche jamais au calcul, aux quantités, aux prix ni à la décomposition matériaux. Modèle : `HERMES_DESCRIPTION_MODEL` (défaut `glm-4.7-flash:Q3_K_M`), `force_think=False` (mesuré ~28-54 s contre >200 s en mode réflexion sur ce rôle).
- `HERMES_REASONING_MODEL` (rôle `reason`) reste `gpt-oss:20b` après un essai réel de `glm-4.7-flash` comme modèle principal Hermes, reverté (préfill trop lent avec le prompt système complet de Hermes, >200 s pour 34 % d'un prompt de 15k tokens).
- Journalisation du rôle + modèle réellement utilisés à chaque appel (`logger.info("ai_role_resolved ...")`, `ai_call_attempt`/`ai_call_success`/`ai_call_failed`) — aucune journalisation de ce type n'existait avant.

### Garde-fous anti-hallucination (rôle `describe`)
- Rejet automatique si le modèle ajoute une étape de dépose/retrait sur une installation explicitement neuve, ou invente une exclusion non fournie — 2 hallucinations réelles trouvées et corrigées (repli sur le gabarit déterministe existant).
- Règles des 12 skills devis (jusque-là jamais lues par le pipeline SaaS — FastAPI appelle Ollama directement, pas la passerelle Hermes) activées dans les prompts système réels (`EXTRACTION_SYSTEM`, `EXPAND_SYSTEM`, `DESCRIPTION_SYSTEM`), avec défense anti-injection de prompt sur le contenu de document non fiable.

### Frontend
- Le panneau « Extraction IA » affichait en dur « lu directement par **Gemma** » sur le chemin de secours vision, alors que `gemma4:26b` a été retiré du VPS le 23/08. Le backend exposait déjà `_ocr_engine` dynamiquement — seul le libellé frontend (`i18n.js`, `req.ocr_fallback_note`) n'avait pas suivi. Corrigé pour interpoler `{{engine}}`.

## 2026-08-15 — OVH + MCP + devis

Tout est sur `main` (PR #1 à #9). Smoke : ce commit.

### IA locale (OVH)
- Hermes / Ollama derrière Caddy (`HERMES_BASE_URL=https://ia.blueseatra.com`, `HERMES_API_KEY`)
- `extract_from_text` / `extract_from_image` / PDF / DOCX
- Modèles UI = ceux du VPS : `hermes-3`, `qwen3.6:27b`, `qwen2.5:14b`
- Mapping `client_name` / `location` → champs écran devis

### Devis
- Rapprochement catalogue (`description` + pluriels → Spot LED encastré)
- Marge % : `HT = qté × PU × (1 + marge/100)`
- Catalogue slim + cache 45 s + `GET /catalog/search`
- pandas chargé seulement à l’import CSV (boot Render plus court)

### MCP Perplexity Computer
- `POST /mcp` (Streamable HTTP)
- `MCP_TENANT_ID` = ANELEC Test `9171d808-f7ee-4d51-92f6-db60d93d8ecc`
- Outils : list_requests, get_request, list_quotes, search_catalog

### Infra
- Pooler Supabase : `prepared_statement_cache_size` et `statement_cache_size` à 0

### Hostinger (manuel)
Rebuild frontend pour voir marge / picker en direct :

```bash
cd frontend && yarn build
```

Uploader le contenu de `frontend/build/` vers `public_html/`.
