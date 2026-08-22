# Correctif immédiat SANS toucher au code (`ai_service.py` est piloté par env)

`backend/ai_service.py` lit presque tous ses modèles depuis des variables d'environnement.
En les changeant sur **Render** (backend Blueseatra), vous supprimez ~80 % de la lenteur
**sans déployer une seule ligne de code**.

## Pourquoi ça marche

- La fonction `_wants_think(model)` (ligne ~351) n'active le mode raisonnement (`think=True`,
  qui génère des milliers de tokens = les 11 min) **que si le nom commence par `qwen3` ou
  `gemma4`**. En basculant les modèles vers `qwen2.5:7b`, `_wants_think` renvoie **False** →
  plus d'explosion de tokens, et le timeout passe de 900 s à 180 s (ligne ~494) automatiquement.
- La cascade essaie les modèles dans l'ordre : mettre un modèle **rapide en tête** fait que
  99 % des requêtes se résolvent au premier étage.

## Variables à définir sur Render

```bash
# Modèle par défaut (extraction texte collé, générationlégère)
HERMES_DEFAULT_MODEL=qwen2.5:7b
HERMES_EXTRACT_MODEL=qwen2.5:7b

# Raisonnement / fichiers importés : NE PLUS pointer gemma4:26b (11 min sur CPU)
HERMES_REASONING_MODEL=qwen2.5:7b

# Cascade de structuration : petit modèle partout (fini qwen3/deepseek-r1/gemma4/qwen3.6)
HERMES_STRUCTURING_MODEL_1=qwen2.5:7b
HERMES_STRUCTURING_MODEL_2=qwen2.5:7b
HERMES_STRUCTURING_MODEL_3=qwen2.5:7b
HERMES_STRUCTURING_MODEL_4=qwen2.5:7b

# Vision : un VLM léger comme PRIMAIRE (au lieu de gemma4:26b)
HERMES_VISION_MODEL=qwen2.5vl:7b

# Escalade vision : ne plus utiliser Phi-4-15B (12,5 min/page, paraphrase)
HERMES_ESCALATION_VISION_MODEL=qwen2.5vl:7b
```

> Gardez les OCR spécialisés déjà en place (`HERMES_OCR_MODEL=…PaddleOCR-VL-1.6-0.9B`,
> `HERMES_OCR_SECONDARY_MODEL=…LightOnOCR-2:1b`) : ils sont petits et rapides.

## Côté VPS (une fois)

```bash
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull qwen2.5vl:7b
# contrôle vitesse (doit répondre en secondes)
docker compose exec ollama ollama run qwen2.5:7b "réponds juste OK"
```

Et dans `.env` du VPS : `HERMES_MODEL=qwen2.5:7b` puis `docker compose up -d`.

## Timeout côté appelant (SaaS)

L'incident `LOT_20_LA_SABLIERE` venait d'un timeout httpx de 180 s qui coupait Gemma en plein
raisonnement puis basculait sur un extracteur dégradé (confiance 45 %, champs vides). Avec
`qwen2.5:7b` (réponses en quelques secondes), le timeout de 180 s devient **largement suffisant** —
mais assurez-vous que le timeout HTTP du SaaS est **≥** au plus grand timeout d'étage côté OVH,
jamais l'inverse.

## Gain attendu

- Extraction d'un devis texte/tableau : **de plusieurs minutes à quelques secondes**.
- Plus d'OOM (5 Go chargés au lieu de 18 Go, ~14 Go de marge).
- Le mode raisonnement lourd n'est plus jamais déclenché involontairement.

Ensuite seulement, passez à la refonte structurelle (service d'extraction + file async) décrite
dans `AUDIT.md`.
