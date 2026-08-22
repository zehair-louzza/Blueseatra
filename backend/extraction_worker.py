"""Worker RQ de la file d'extraction (item « File Durable »).

Déploiement (ex. Render Background Worker) :
    python extraction_worker.py
Prérequis : REDIS_URL défini (même Redis que le backend), et le même code/env.

Le job ne transporte que (request_id, tenant_id) — jamais d'octets de fichier
(RGPD). run_extraction relit la demande en base et lance le pipeline existant.
Le cas 'pdf_ocr' (pages rendues en mémoire) reste traité en tâche de fond
in-process côté API et n'est jamais mis en file.
"""
import asyncio


def run_extraction(request_id, tenant_id):
    """Point d'entrée exécuté par le worker RQ (référencé par 'extraction_worker.run_extraction')."""
    from server import process_request  # import paresseux (charge l'app + l'env)
    asyncio.run(process_request(request_id, tenant_id))


if __name__ == "__main__":
    import os
    from redis import from_url
    from rq import Queue, Worker
    conn = from_url(os.environ["REDIS_URL"])
    # 1 worker = 1 extraction à la fois. Lancer N workers <= OLLAMA_NUM_PARALLEL.
    Worker([Queue("extraction", connection=conn)], connection=conn).work()
