# File d'attente async — encaisser 10-100 devis en parallèle

## Ce qui existe déjà dans Blueseatra
`server.py` utilise `BackgroundTasks` : `create_request` renvoie tout de suite `status:"received"`,
un worker de fond fait `received → processing → needs_review/done/failed`, le front interroge
`GET /requests/{id}`. C'est déjà un modèle « brouillon en préparation » asynchrone.

**Limites pour 10-100 users** : les `BackgroundTasks` tournent DANS le process web (pas de
durabilité si le process redémarre, pas de limite globale de charge, concurrence avec les requêtes
HTTP).

## Correctif déjà appliqué (code)
`ai_service.py` : ajout d'un `asyncio.Semaphore` (`OLLAMA_MAX_CONCURRENCY`, défaut 2) qui **borne
les appels Ollama simultanés par process**. Au-delà, les extractions attendent leur tour au lieu de
saturer le CPU du VPS et de provoquer des timeouts en cascade. → aligner sur `OLLAMA_NUM_PARALLEL`.

## Étape suivante : une vraie file durable (choisir UNE option)

### Option A — Redis + RQ (recommandé, dans l'écosystème Render)
1. Render : ajouter un **Redis** (addon) + un service **Background Worker** (même image que le backend).
2. `create_request` fait `queue.enqueue(process_request, req_id, tenant_id)` au lieu de
   `background.add_task(...)`.
3. Le worker consomme la file ; le front continue de poller `GET /requests/{id}`.
4. Bénéfices : durabilité (survit à un redéploiement), débit lissé, `--workers N` réglable,
   retries et *dead-letter* natifs.

```python
# worker.py (Render Background Worker)
from redis import Redis
from rq import Worker, Queue
if __name__ == "__main__":
    Worker([Queue("extraction", connection=Redis.from_url(os.environ["REDIS_URL"]))]).work()
```

### Option B — n8n (déjà dans la stack OVH)
- Webhook n8n `POST /intake` reçoit email/fichier → écrit une ligne `requests(status=received)`
  dans Supabase → appelle le service d'extraction → met à jour le statut.
- n8n gère la concurrence (nœud « Split in Batches » + limite) et les relances.
- Avantage : aucun composant Render en plus ; l'intake email est déjà son rôle (ADR).

### Option C — file portée par Supabase (zéro infra en plus)
- Table `jobs(status, payload, locked_at)` + un worker qui `SELECT ... FOR UPDATE SKIP LOCKED`.
- Simple, durable, pas de Redis. Idéal si vous voulez rester minimal.

## Règle d'or de dimensionnement
Un VPS **CPU** ne fait pas 100 inférences en parallèle. La file **lisse** la charge :
- `OLLAMA_NUM_PARALLEL=2` + `OLLAMA_MAX_CONCURRENCY=2` → ~1 doc / 20-60 s ;
- 100 demandes arrivées d'un coup → toutes acceptées instantanément (`received`), traitées en file,
  l'utilisateur voit « brouillon en préparation » puis le résultat.
Pour du **synchrone rapide** à cette échelle → GPU (voir `GPU-OVH-CHIFFRAGE.md`).
