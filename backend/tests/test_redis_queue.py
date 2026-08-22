"""Iteration 8 - ITEM 4 (informational): durable Redis+RQ extraction queue.

REDIS_URL is set in this pod and an RQ worker (extraction_worker.py) is running.
POST /requests must return {status: received} immediately (job enqueued, not
in-process) and the request must reach a TERMINAL state (done / needs_review /
failed) - never stay stuck in received/processing. Ollama is unreachable here so
`failed` is the EXPECTED outcome; that is not asserted as a bug.
"""
import os
import time
import uuid

import pytest
from dotenv import dotenv_values

TERMINAL = {"done", "needs_review", "failed"}
REDIS_URL = os.environ.get("REDIS_URL") or dotenv_values("/app/backend/.env").get("REDIS_URL")


def test_redis_reachable():
    if not REDIS_URL:
        pytest.skip("REDIS_URL not configured -> in-process fallback")
    import redis
    assert redis.from_url(REDIS_URL).ping() is True


def test_rq_worker_present():
    if not REDIS_URL:
        pytest.skip("REDIS_URL not configured")
    import redis
    from rq import Worker
    conn = redis.from_url(REDIS_URL)
    workers = Worker.all(connection=conn)
    names = [w.name for w in workers]
    assert any("extraction" in q.name for w in workers for q in w.queues), (
        f"no RQ worker listening on the 'extraction' queue (workers={names})")


def test_create_request_enqueues_and_reaches_terminal_state(client, api):
    title = f"TEST_RQ_{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    r = client.post(f"{api}/requests",
                    data={"title": title, "text": "TEST peinture 20 m2 et placo BA13 10 m2"},
                    timeout=120)
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    assert body["status"] == "received", body
    rid = body["id"]
    try:
        # The API must not block on the AI call when the job is queued.
        assert elapsed < 20, f"POST /requests took {elapsed:.1f}s (job not really enqueued?)"

        status = None
        deadline = time.time() + 150
        while time.time() < deadline:
            g = client.get(f"{api}/requests/{rid}", timeout=60)
            assert g.status_code == 200, g.text[:300]
            status = g.json()["status"]
            if status in TERMINAL:
                break
            time.sleep(3)
        assert status in TERMINAL, (
            f"request stuck in '{status}' after 150s -> queue/worker not consuming jobs")
    finally:
        client.delete(f"{api}/requests/{rid}", timeout=60)


# --- ITEM 2: the catalog cache really lives in Redis (shared across workers) --
def test_catalog_cache_uses_redis_and_is_evicted(client, api):
    """The cached active catalog must be a Redis key (cross-worker/pod) and any
    mutation must DELETE it, not just the local process dict."""
    if not REDIS_URL:
        pytest.skip("REDIS_URL not configured")
    import io
    import redis
    conn = redis.from_url(REDIS_URL, decode_responses=True)
    prefix = "blueseatra:catalog_active:"

    for k in conn.scan_iter(prefix + "*"):
        conn.delete(k)
    # warm the cache through the public API
    assert client.get(f"{api}/catalog/active", timeout=60).status_code == 200
    keys = list(conn.scan_iter(prefix + "*"))
    assert keys, "no Redis cache key created -> cache is still process-local in-memory"
    ttl = conn.ttl(keys[0])
    assert 0 < ttl <= 45, f"unexpected TTL {ttl}s on {keys[0]}"

    marker = f"TEST_RQ_CACHE_{uuid.uuid4().hex[:6]}"
    csv = (f"Famille,Article,Unit\u00e9,TVA_%,Prix_vente_HT\nTEST,{marker},u,20,5.55\n").encode()
    r = client.post(f"{api}/catalogs/import",
                    files={"file": ("c.csv", io.BytesIO(csv), "text/csv")},
                    data={"catalog_name": marker, "activate": "true"}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    cid = r.json()["catalog_id"]
    try:
        assert not list(conn.scan_iter(prefix + "*")), (
            "Redis cache key NOT deleted after import+activate -> stale prices across workers")
        fresh = client.get(f"{api}/catalog/active", timeout=60).json()
        assert fresh["catalog"]["id"] == cid
        assert float(fresh["items"][0]["unit_price_ht"]) == 5.55
    finally:
        client.delete(f"{api}/catalogs/{cid}", timeout=60)
        cats = client.get(f"{api}/catalogs", timeout=60).json()
        demo = next((c for c in cats if not c["name"].startswith("TEST_")), None)
        if demo and demo.get("versions"):
            ver = sorted(demo["versions"], key=lambda v: v["version_number"])[-1]["id"]
            client.post(f"{api}/catalogs/{demo['id']}/activate/{ver}", timeout=60)
