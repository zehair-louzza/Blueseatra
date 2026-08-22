"""
Worker de la file Supabase (Option C) — Render Background Worker : `python supabase_worker.py`.
Boucle : réclame un job (claim_next_job / SKIP LOCKED) -> process_request -> statut.
Ne transporte pas d'octets de fichier : relit la demande en base par request_id.
"""
import os
import time
import asyncio

POLL_SECONDS = float(os.environ.get("QUEUE_POLL_SECONDS", "2"))


async def _handle(job, process_request, db):
    try:
        await process_request(job["request_id"], job["tenant_id"])
        status = "done"
    except Exception as exc:  # échec VISIBLE, jamais silencieux
        status = "failed"
        print(f"job {job['id']} failed: {type(exc).__name__}: {exc}")
    await db.execute(
        "update extraction_jobs set status=$1, updated_at=now() where id=$2",
        status, job["id"])


async def main():
    # Importer le pipeline + l'accès DB de l'app (adapter à votre pg_adapter).
    from server import process_request
    from pg_adapter import PGDatabase
    db = PGDatabase()
    print("supabase_worker démarré")
    while True:
        row = await db.fetchrow("select * from claim_next_job()")
        if not row or not row.get("id"):
            time.sleep(POLL_SECONDS)
            continue
        await _handle(row, process_request, db)


if __name__ == "__main__":
    asyncio.run(main())
