"""Iteration 8 probe (manual): prove POST /requests -> Redis queue -> RQ worker -> DB.

Observes the RQ 'extraction' queue length right after the POST and the final
status/error of the request. Ollama unreachable => needs_review/failed expected.
Run: cd /app/backend && python tests/probe_queue_flow.py
"""
import os
import time
import uuid

import redis
import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
REDIS_URL = os.environ.get("REDIS_URL") or dotenv_values("/app/backend/.env")["REDIS_URL"]


def main():
    conn = redis.from_url(REDIS_URL)
    from rq import Queue
    q = Queue("extraction", connection=conn)
    tok = requests.post(f"{API}/auth/login",
                        json={"email": "qa@example.com", "password": "Test1234!"},
                        timeout=60).json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})

    title = f"TEST_QFLOW_{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    r = s.post(f"{API}/requests", data={"title": title, "text": "TEST peinture 20 m2"}, timeout=120)
    dt = time.time() - t0
    print(f"POST /requests -> {r.status_code} in {dt:.2f}s body={r.text[:120]}")
    rid = r.json()["id"]
    print("queue length just after POST:", len(q), "| started/finished registries:",
          q.started_job_registry.count, q.finished_job_registry.count)
    job_ids = q.job_ids
    print("queued job ids:", job_ids)

    seen = []
    for _ in range(50):
        g = s.get(f"{API}/requests/{rid}", timeout=60).json()
        st = g.get("status")
        if not seen or seen[-1] != st:
            seen.append(st)
        if st in ("done", "needs_review", "failed"):
            print("status timeline:", seen, "| final:", st, "| error:", str(g.get("error"))[:160])
            print("extracted present:", bool(g.get("extracted")))
            break
        time.sleep(2)
    else:
        print("STUCK, timeline:", seen)
    print("cleanup:", s.delete(f"{API}/requests/{rid}", timeout=60).status_code)
    print("failed job registry count:", q.failed_job_registry.count)


main()
