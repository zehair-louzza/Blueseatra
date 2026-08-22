# AUDIT ovh-ai-stack + Blueseatra — anomalies & architecture cible

> Analyse des DEUX dépôts qui doivent tourner en harmonie :
> - `ovh-ai-stack` : l'infra (Ollama, Hermes, n8n, Caddy sur VPS OVH Roubaix)
> - `Blueseatra` : le SaaS (FastAPI/React/Supabase) — module d'intégration `backend/ai_service.py`
>
> **Matériel confirmé** (dans les SKILL.md + `ai_service.py`) : **CPU seul, 8 vCPU, 22 Go RAM, swap 4 Go, aucun GPU.**
> **Cible** : 10-100 utilisateurs simultanés ; extraction fiable de PDF (surtout tableaux).

---

## 0. Cause racine unique

Tout part d'un seul choix : faire tourner des **modèles de 17-18 Go en mode raisonnement sur un
VPS CPU de 22 Go**. Vos propres mesures le prouvent : `gemma4:26b` = **80 s à 11 min** par
extraction, `Phi-4-reasoning-vision-15B` = **12,5 min/page**, `598 Mo de RAM libres` avec un seul
modèle chargé.

Pour compenser, deux couches ont accumulé des rustines qui aggravent le problème :
- **Infra** : `OLLAMA_KEEP_ALIVE=0` (recharge 18 Go à chaque requête), `mem_limit=18g` (OOM),
  `MAX_LOADED_MODELS=1` (thrashing entre slots).
- **SaaS (`ai_service.py`)** : une **cascade de structuration à 4 modèles lents** (qwen3:14b →
  deepseek-r1:14b → gemma4:26b → qwen3.6:27b, jusqu'à **900 s par étage**), une **cascade OCR à
  4 étages**, une **escalade Phi-4-15B** cassée, et un **mode raisonnement forcé** (`think=True`)
  qui génère des milliers de tokens de réflexion.

**Aucun réglage ne rend ce dimensionnement compatible avec 10-100 users.** La solution :
petit modèle rapide + parsing déterministe des tableaux + traitement asynchrone.
**80 % du gain s'obtient SANS toucher au code** (voir `FIX-IMMEDIAT-ENV.md`).

---

## 1. Anomalies — dépôt `ovh-ai-stack` (infra)

| # | Gravité | Fichier | Anomalie | Correctif |
|---|---|---|---|---|
| I1 | 🔴 | compose.yaml | Modèles 17-18 Go sur CPU 22 Go → OOM + 80 s-11 min/doc | Modèles 7B (`compose.yaml` corrigé) |
| I2 | 🔴 | compose.yaml | `OLLAMA_KEEP_ALIVE=0` recharge 18 Go à chaque requête | `30m` (petits modèles restent chauds) |
| I3 | 🔴 | compose.yaml | `mem_limit:18g` pour un modèle 18 Go → rien pour le KV-cache | `14g` + `cpus:"6"` |
| I4 | 🟠 | compose.yaml | `MAX_LOADED_MODELS=1` + Hermes route chaque slot ailleurs → thrashing | `2`, 2 petits modèles coexistent |
| I5 | 🟠 | compose.yaml | Aucun étage de parsing PDF/tableaux (le besoin n°1) | service `extraction` (pdfplumber) |
| I6 | 🟠 | Hermes | Couche agent sur-dimensionnée pour un flux déterministe | profil `hermes` optionnel |
| I7 | 🟡 | Caddyfile | Hermes exige `Bearer` (ADR-004) mais Caddy n'injecte que `X-Api-Key` → 401 | `header_up Authorization "Bearer ..."` |
| I8 | 🟡 | compose.yaml | `OLLAMA_CONTEXT_LENGTH=8192` trop court (devis multi-pages) → troncature | `16384` |
| I9 | 🟡 | compose.yaml | Pas de limite CPU → Ollama affame Caddy/n8n | `cpus:` par service |
| I10 | 🟡 | compose.yaml | healthcheck `ollama list` ne teste pas la disponibilité | `ollama ps` |
| I11 | ⚪ | compose.yaml | `n8n depends_on ollama` inutile | retiré |

## 2. Anomalies — `Blueseatra/backend/ai_service.py` (intégration OVH)

| # | Gravité | Ligne(s) | Anomalie | Correctif |
|---|---|---|---|---|
| S1 | 🔴 | 56-86 | Cascade structuration = qwen3:14b → deepseek-r1:14b → gemma4:26b → qwen3.6:27b, **900 s/étage** → un doc peut monopoliser le worker >30 min | env `HERMES_STRUCTURING_MODEL_*=qwen2.5:7b` |
| S2 | 🔴 | 351-355, 449-451 | `_wants_think` force `think=True` sur `qwen3*`/`gemma4*` → milliers de tokens de réflexion = les 11 min | passer aux modèles `qwen2.5:7b` (→ `_wants_think`=False, pas de code à changer) |
| S3 | 🔴 | 220-221 | Escalade `Phi-4-reasoning-vision-15B` documentée cassée (« 12,5 min/page, paraphrase ») mais branchée | env `HERMES_ESCALATION_VISION_MODEL=qwen2.5vl:7b` |
| S4 | 🟠 | 57 | `deepseek-r1:14b` (modèle de *raisonnement*) dans la chaîne d'*extraction* → lent et bavard | retirer de la cascade |
| S5 | 🟠 | 23,25,36 | Défauts `gemma4:26b` pour raisonnement/vision | env `HERMES_REASONING_MODEL` / `HERMES_VISION_MODEL` |
| S6 | 🟡 | 494 | `current_timeout=900s` pour les modèles « think » → un appel peut geler 15 min | disparaît avec les modèles non-think |
| S7 | 🟡 | 193-213 | Cascade OCR 4 étages + timeout ésotérique (1.2× durée de l'étape suivante) | simplifier : 1 VLM (`qwen2.5vl:7b`) |
| S8 | ⚪ | 486-511 | Traces d'un « enregistrement DNS A parasite » sur `HERMES_BASE_URL` | vérifier le DNS `ia.` |

> Point positif : le SaaS a déjà identifié de **bons petits modèles** (`qwen2.5vl:7b`,
> `PaddleOCR-VL-0.9B`, `LightOnOCR-1b`). Il faut juste **retirer les gros modèles du chemin chaud**.

---

## 3. Architecture cible

```
                    Internet  80/443
                       ▼
                 Caddy (TLS + X-Api-Key)
       ┌───────────────┼─────────────────────────┐
       ▼               ▼                          ▼
    n8n:5678     extraction:8000              ollama:11434
   (intake mail) (FastAPI worker)             (LLM local)
                   1) parse pdfplumber  ── tableaux/texte déterministes (pas de LLM)
                   2) qwen2.5:7b format=json ── structuration
                   3) qwen2.5vl:7b ── SI image seulement
                       ▼
                 JSON structuré (sans prix)  ─►  FastAPI Blueseatra (seul moteur de prix)  ─►  Supabase
```

Principes :
1. **Parsing déterministe d'abord.** pdfplumber lit la structure des tableaux (testé : 4/4 lignes,
   0 prix reporté). Le LLM ne fait que structurer un texte déjà propre.
2. **Petits modèles chauds.** `qwen2.5:7b` (~5 Go) + `qwen2.5vl:7b` (~6 Go) tiennent ensemble dans
   22 Go → pas de rechargement, `NUM_PARALLEL≥2`.
3. **Asynchrone obligatoire.** Un seul VPS CPU ne fait pas 100 inférences en parallèle. File
   d'attente (n8n / Redis-RQ / table Supabase + worker) + UI « brouillon en préparation ».
4. **Hermes hors chemin critique.** Le flux est déterministe ; l'orchestration multi-agents
   n'apporte rien ici et aggrave le thrashing.

**Concurrence réaliste** : `NUM_PARALLEL=2`, modèle 7B → ~1 doc / 20-60 s. Pour 10-100 users,
la file lisse la charge. Si vous voulez du **synchrone rapide** ou garder les gros modèles,
→ **GPU OVH** (voir `GPU-OVH-CHIFFRAGE.md`).

---

## 4. Choix de modèles (CPU)

| Rôle | Recommandation | Empreinte |
|---|---|---|
| Parsing PDF + tableaux | pdfplumber (défaut) / Docling (scans complexes) | lib CPU |
| Structuration texte → JSON | **`qwen2.5:7b`** (`format=json`) | ~4,7 Go |
| Vision (photo, PDF illisible) | **`qwen2.5vl:7b`** | ~6 Go |
| OCR spécialisé (déjà en place) | `PaddleOCR-VL-0.9B`, `LightOnOCR-1b` | < 2 Go |
| Premium (gemma4:26b, qwen3.6:27b, Phi-4-15B) | **GPU uniquement / batch nocturne** | 17-30 Go |

---

## 5. Preuve : le pipeline recommandé fonctionne

`services/extraction/test_extraction.py` (exécuté) génère un devis PDF avec tableau puis :
- pdfplumber extrait **les 4 lignes** du tableau avec leur structure ;
- le LLM renvoie 4 items structurés + parties (donneur d'ordre, client, site) ;
- **aucun prix** (294, 680, 672, 24,50, 42,00) ne fuit dans la sortie (assertions OK).

Voir aussi : `FIX-IMMEDIAT-ENV.md` (correctifs sans code) et `GPU-OVH-CHIFFRAGE.md`.
