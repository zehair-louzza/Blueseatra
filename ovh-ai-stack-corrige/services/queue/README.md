# File durable — comment brancher (item « File Durable »)

Objectif : encaisser un **pic de 100 devis** sans saturer le VPS CPU. Trois pièces :
1. **Accepter** la demande instantanément (statut `received`) — déjà le cas dans Blueseatra.
2. **Mettre en file** un job (durable) au lieu d'un `BackgroundTasks` en process.
3. **Drainer** la file avec un worker à **concurrence bornée** (≤ `OLLAMA_NUM_PARALLEL`).

> Le limiteur `_OLLAMA_SEMAPHORE` (déjà ajouté à `ai_service.py`) protège le CPU même sans file.
> La file ajoute la **durabilité** (survit à un redéploiement) et le lissage des pics.

## Preuve de mécanique (testée ici)
`queue_demo.py` simule 100 demandes simultanées : toutes acceptées en < 1 ms, puis drainées sans
jamais dépasser la concurrence cible. Lancer : `python queue_demo.py`.

## Option A — Redis + RQ (recommandé sur Render)
Fichier `rq_worker.py`.
1. Render → ajouter **Redis** (→ `REDIS_URL`).
2. Render → nouveau **Background Worker**, commande : `python rq_worker.py`.
3. `server.py`, dans `create_request`, chemin standard (pas `pdf_ocr`) :
   ```python
   if os.environ.get("REDIS_URL"):
       from job_queue import enqueue_request
       enqueue_request(req_id, cu.tenant_id)
   else:
       background.add_task(process_request, req_id, cu.tenant_id)   # comportement actuel
   ```
4. Nombre de workers ≤ `OLLAMA_NUM_PARALLEL` du VPS (sinon on sature le CPU).

## Option B — n8n (déjà dans la stack OVH, aucun composant Render en plus)
- Webhook n8n `POST /intake` → insert `requests(status='received')` dans Supabase → appelle le
  service d'extraction → met à jour le statut. Concurrence via le nœud « Split in Batches ».

## Option C — Supabase `SKIP LOCKED` (zéro infra en plus)
Fichiers `supabase_queue.sql` (table + `claim_next_job()`) et `supabase_worker.py`.
1. Exécuter `supabase_queue.sql` sur la base.
2. `create_request` insère une ligne `extraction_jobs(status='queued')` au lieu du BackgroundTasks.
3. Render → Background Worker : `python supabase_worker.py` (lancer 1 à N instances).

## Règle de dimensionnement
Un VPS CPU ne fait pas 100 inférences en parallèle : la file **accepte tout de suite** et **traite
au rythme du CPU** (~1 doc / 20-60 s avec `qwen2.5:7b`). Pour du synchrone rapide à 100 users →
GPU L4 (`docs/GPU-OVH-CHIFFRAGE.md`).
