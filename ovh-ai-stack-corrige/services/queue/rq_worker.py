"""
Option A — File durable Redis + RQ (recommandée sur Render).

Déploiement Render :
  1. Ajouter un datastore Redis -> variable REDIS_URL.
  2. Créer un service "Background Worker" avec la commande :  python rq_worker.py
  3. Dans server.py, remplacer (pour le chemin standard, PAS le pdf_ocr vision) :
        background.add_task(process_request, req_id, cu.tenant_id)
     par :
        from job_queue import enqueue_request
        enqueue_request(req_id, cu.tenant_id)   # si REDIS_URL défini, sinon fallback BackgroundTasks

Le job ne transporte QUE request_id + tenant_id (jamais les octets du fichier) :
le worker relit la demande en base et appelle process_request. Le cas
'pdf_ocr' (pages rendues en mémoire, non persistées — RGPD) reste sur
BackgroundTasks en process, car ses octets ne doivent pas transiter par Redis.
"""
import os
import asyncio

# --- côté API (enqueue) ---------------------------------------------------
def get_queue():
    from redis import Redis
    from rq import Queue
    return Queue("extraction", connection=Redis.from_url(os.environ["REDIS_URL"]),
                 default_timeout=600)


def enqueue_request(request_id: str, tenant_id: str):
    """Pousse un job. À appeler depuis server.py à la place de background.add_task."""
    get_queue().enqueue("rq_worker.run_extraction", request_id, tenant_id)


# --- côté worker (Render Background Worker : `python rq_worker.py`) --------
def run_extraction(request_id: str, tenant_id: str):
    """Point d'entrée RQ (sync) : exécute la coroutine process_request.
    Importe le pipeline sans booter FastAPI (voir note d'intégration)."""
    from server import process_request  # process_request(request_id, tenant_id)
    asyncio.run(process_request(request_id, tenant_id))


if __name__ == "__main__":
    from redis import Redis
    from rq import Worker, Queue
    conn = Redis.from_url(os.environ["REDIS_URL"])
    # 1 worker = 1 inférence à la fois ; lancer N workers = N devis en parallèle
    # (garder N <= OLLAMA_NUM_PARALLEL du VPS pour ne pas saturer le CPU).
    Worker([Queue("extraction", connection=conn)], connection=conn).work()
