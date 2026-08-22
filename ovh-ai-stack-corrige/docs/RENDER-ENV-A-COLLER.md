# À coller dans les variables d'environnement Render (backend Blueseatra)

Ces variables suffisent à activer le « Correctif Express » même si le code par défaut n'est pas
redéployé. (Depuis ce livrable, les défauts du code `ai_service.py` sont DÉJÀ ces valeurs.)

```
HERMES_DEFAULT_MODEL=qwen2.5:7b
HERMES_EXTRACT_MODEL=qwen2.5:7b
HERMES_REASONING_MODEL=qwen2.5:7b
HERMES_STRUCTURING_MODEL_1=qwen2.5:7b
HERMES_STRUCTURING_MODEL_2=qwen2.5:7b
HERMES_STRUCTURING_MODEL_3=qwen2.5:7b
HERMES_STRUCTURING_MODEL_4=qwen2.5:7b
HERMES_VISION_MODEL=qwen2.5vl:7b
HERMES_ESCALATION_VISION_MODEL=qwen2.5vl:7b
OLLAMA_MAX_CONCURRENCY=2
```

Sur le VPS (une fois) :
```
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull qwen2.5vl:7b
docker compose exec ollama ollama run qwen2.5:7b "réponds juste OK"   # doit répondre en secondes
```
> ⚠️ Tirer `qwen2.5:7b` sur le VPS AVANT de basculer les variables, sinon les requêtes
> échoueront tant que le modèle n'est pas présent.
