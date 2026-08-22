"""
Démo runnable de la file durable à concurrence bornée — prouve qu'un PIC de
100 devis est accepté instantanément puis traité sans jamais saturer le CPU.

Simule le comportement cible (indépendant de Supabase/Redis pour être testable
ici) : N requêtes arrivent d'un coup -> toutes passent en 'received' tout de
suite ; un worker les traite avec au plus MAX_CONCURRENCY inférences en
parallèle ; statut received -> processing -> done.
"""
import asyncio
import time

MAX_CONCURRENCY = 2          # aligné sur OLLAMA_NUM_PARALLEL / OLLAMA_MAX_CONCURRENCY
SIM_INFERENCE_SECONDS = 0.03  # extraction simulée (le vrai temps dépend du VPS)

_live = 0
_peak = 0
_sem = asyncio.Semaphore(MAX_CONCURRENCY)


async def _extract(job, store):
    """Traitement d'un job : borné par le sémaphore (jamais > MAX_CONCURRENCY)."""
    global _live, _peak
    async with _sem:
        _live += 1
        _peak = max(_peak, _live)
        store[job]["status"] = "processing"
        await asyncio.sleep(SIM_INFERENCE_SECONDS)  # = appel Ollama réel en prod
        store[job]["status"] = "done"
        _live -= 1


async def main(n=100):
    store = {}

    # 1) PIC : 100 demandes arrivent simultanément -> acceptées instantanément.
    t0 = time.perf_counter()
    for i in range(n):
        store[f"req-{i}"] = {"status": "received"}
    accept_ms = (time.perf_counter() - t0) * 1000
    assert all(v["status"] == "received" for v in store.values())
    print(f"[1] {n} devis acceptés en {accept_ms:.1f} ms (statut 'received' immédiat)")

    # 2) Le worker draine la file à concurrence bornée.
    t0 = time.perf_counter()
    await asyncio.gather(*(_extract(j, store) for j in store))
    drain_s = time.perf_counter() - t0

    done = sum(1 for v in store.values() if v["status"] == "done")
    print(f"[2] {done}/{n} traités en {drain_s:.2f} s | concurrence max observée = {_peak}")

    assert done == n, "ÉCHEC : tous les jobs ne sont pas traités"
    assert _peak <= MAX_CONCURRENCY, f"ÉCHEC : concurrence dépassée ({_peak} > {MAX_CONCURRENCY})"
    print(f"\n✅ Pic de {n} devis encaissé sans dépasser {MAX_CONCURRENCY} inférences simultanées.")
    print("   En prod : remplacer _extract par process_request (RQ ou worker Supabase).")


if __name__ == "__main__":
    asyncio.run(main())
