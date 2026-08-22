# Chiffrage GPU OVH — faut-il passer au GPU ?

> Prix OVHcloud Public Cloud GPU, datacenter **Gravelines (GRA11, France → RGPD OK)**,
> facturation **horaire à l'usage** (source : ovhcloud.com/public-cloud/prices, août 2026).
> USD ; ~×0,92 pour l'EUR. 1 mois ≈ 730 h.

## 1. La question à trancher AVANT de payer un GPU

Avec l'architecture recommandée (**parsing déterministe + `qwen2.5:7b` + file async**), un VPS
**CPU** traite un devis en quelques secondes et absorbe 10-100 users via la file. **Vous n'avez
probablement pas besoin de GPU.**

Le GPU devient utile seulement si vous voulez **l'un** de ces points :
- réponses **synchrones** (pas de file) sous forte charge ;
- garder de **gros modèles** (gemma4:26b, qwen3.6:27b, un reasoner) dans le chemin chaud ;
- **vision lourde** en volume (beaucoup de scans/photos par heure).

## 2. Grille de prix (1 GPU sauf mention)

| Instance | GPU | VRAM | Prix/h (USD) | ~ /mois 24/7 (USD) | ~ /mois (EUR) |
|---|---|---|---|---|---|
| **l4-90** | 1× L4 | 24 Go | **$1,00** | **~$730** | **~€680** |
| l40s-90 | 1× L40S | 48 Go | $1,80 | ~$1 314 | ~€1 210 |
| a100-180 | 1× A100 | 80 Go | $3,07 | ~$2 241 | ~€2 060 |
| h100-380 | 1× H100 | 80 Go | $2,99 | ~$2 183 | ~€2 010 |

> Éteindre la nuit/week-end (facturation horaire) : un L4 utilisé ~12 h/jour ouvré ≈ **~$260/mois**.

## 3. Recommandation : **NVIDIA L4 24 Go (`l4-90`)**

C'est le meilleur rapport efficacité/prix pour Blueseatra :
- **24 Go de VRAM** : fait tourner `gemma3:27b`/`qwen` 32B en Q4 (~17-20 Go) **entièrement sur GPU**.
- **Débit** : ~30-60 tok/s sur un 27B Q4 (vs ~2-5 tok/s en CPU) → extraction de tableau en
  **quelques secondes**, y compris en mode raisonnement.
- **Concurrence réelle** avec un serveur d'inférence à batching (vLLM, ou Ollama `NUM_PARALLEL`).
- **Gravelines (France)** → souveraineté RGPD conservée, cohérent avec ADR-001.
- **~€680/mois** 24/7, ou **~€260/mois** en extinction nocturne.

Montez en A100/L40S 48-80 Go **seulement** si vous servez plusieurs gros modèles en parallèle ou
de très longs contextes — inutile pour l'extraction de devis.

## 4. Moteur d'inférence sur GPU

- **Ollama** (simple, déjà en place) : parfait pour démarrer, `OLLAMA_NUM_PARALLEL=4-8` sur L4.
- **vLLM** (recommandé à charge élevée) : batching continu, bien meilleur débit multi-utilisateurs,
  API OpenAine-compatible → aucun changement côté FastAPI. À privilégier si vous visez les 100 users
  en synchrone.

## 5. Décision en une ligne

| Situation | Reste sur CPU ? | GPU ? |
|---|---|---|
| Extraction async + modèles 7B (recommandé) | ✅ oui, VPS actuel suffit | non nécessaire |
| Vous voulez du synchrone rapide à 50-100 users | non | **L4 `l4-90` + vLLM** |
| Vous tenez absolument à gemma4:26b/qwen3.6:27b en direct | impossible | **L4 minimum**, A100 si plusieurs modèles |

> Piste hybride économique : garder le **VPS CPU** pour le parsing/OCR déterministe + les petits
> modèles, et n'allumer un **L4 à l'heure** que pour les rares documents « premium » ou les pics.
