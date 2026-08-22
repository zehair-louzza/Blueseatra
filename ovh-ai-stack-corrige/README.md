# ovh-ai-stack — version corrigée + audit

Livrable produit pour résoudre le problème « IA locale trop lente / OOM sur VPS OVH CPU » et
faire tourner le SaaS **Blueseatra** en harmonie avec l'infra.

## Ce qui est dedans

| Chemin | Rôle |
|---|---|
| `docs/AUDIT.md` | Audit complet des 2 dépôts (infra + `ai_service.py`), anomalies chiffrées, architecture cible |
| `docs/FIX-IMMEDIAT-ENV.md` | **Correctif en 5 min, sans code** : variables d'env Render → fin des 11 min |
| `docs/GPU-OVH-CHIFFRAGE.md` | Faut-il un GPU ? Grille de prix OVH + reco (L4 24 Go) |
| `compose.yaml` | Docker Compose corrigé (petits modèles chauds, service extraction, limites CPU) |
| `caddy/Caddyfile` | Reverse proxy corrigé (+ correctif Bearer Hermes) |
| `scripts/pull-models.sh` | Ne tire que les petits modèles adaptés au CPU |
| `.env.example` | Env corrigé |
| `services/extraction/` | **Service d'extraction runnable** : pdfplumber (tableaux) + LLM `format=json` |
| `services/extraction/test_extraction.py` | Test e2e (exécuté ✅ : tableau extrait, JSON structuré, 0 prix) |

## Ordre d'application conseillé

1. **Aujourd'hui (0 code)** : appliquer `docs/FIX-IMMEDIAT-ENV.md` (env Render + `ollama pull qwen2.5:7b`).
   → l'extraction passe de plusieurs minutes à quelques secondes, plus d'OOM.
2. **Cette semaine** : déployer `compose.yaml` + `services/extraction/` corrigés sur le VPS.
3. **Ensuite** : brancher la file d'attente async (n8n / Redis-RQ) pour tenir 10-100 users.
4. **Si besoin de synchrone rapide** : évaluer un GPU L4 (`docs/GPU-OVH-CHIFFRAGE.md`).

## Tester le service d'extraction en local

```bash
cd services/extraction
pip install -r requirements.txt reportlab
# démo hors VPS (clé Emergent) :
EMERGENT_LLM_KEY=... EXTRACT_PROVIDER=emergent python test_extraction.py
# prod (Ollama local) : EXTRACT_PROVIDER=ollama OLLAMA_BASE_URL=http://ollama:11434 uvicorn app:app
```

> ⚠️ `EXTRACT_PROVIDER=emergent` sort les données de l'UE (démo/dev uniquement).
> En production, **toujours** `EXTRACT_PROVIDER=ollama` (local, RGPD).

---

## Journal des changements & passation

La traçabilité complète (actions réalisées, fichiers modifiés, statut de validation, environnement de test) et le **backlog priorisé (P0/P1/P2)** sont dans **[`../HANDOFF.md`](../HANDOFF.md)**.

### Suggestions d'amélioration (résumé)
- **P0** : `ollama pull qwen2.5:7b`+`qwen2.5vl:7b` sur le VPS ; coller les env Render ; lancer `scripts/test-extraction-e2e.py` (mesure réelle) et ajuster `OLLAMA_NUM_PARALLEL`.
- **P1** : déployer `compose.yaml` + `services/extraction/` ; provisionner Redis + worker (`services/queue/`) ; corriger le Bearer Hermes si exposé ; aligner les timeouts inter-couches.
- **P2** : GPU L4 Gravelines si synchrone rapide requis ; simplifier les cascades restantes ; `OLLAMA_CONTEXT_LENGTH=16384` ; healthcheck `ollama ps` ; limites `cpus:` par conteneur ; observabilité (temps par étape + modèle réellement utilisé) ; router au VLM uniquement les vrais scans.
