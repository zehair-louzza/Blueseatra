"""Iteration 8 probe (NOT part of the suite): behaviour when Redis is DOWN.

Redis is opt-in via REDIS_URL. This probe checks whether the app degrades
gracefully (in-memory fallback) or hard-fails (500) when Redis becomes
unreachable while REDIS_URL is still set. Restores Redis at the end.
Run manually: python tests/probe_redis_down.py
"""
import subprocess
import time

import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def main():
    tok = requests.post(f"{API}/auth/login",
                        json={"email": "qa@example.com", "password": "Test1234!"},
                        timeout=60).json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    print("baseline /catalog/active:", s.get(f"{API}/catalog/active", timeout=60).status_code)

    subprocess.run(["redis-cli", "shutdown", "nosave"], capture_output=True)
    time.sleep(1)
    print("redis ping after shutdown:",
          subprocess.run(["redis-cli", "ping"], capture_output=True, text=True).stdout.strip() or "DOWN")
    try:
        r = s.get(f"{API}/catalog/active", timeout=60)
        print("GET /catalog/active with Redis DOWN ->", r.status_code, r.text[:200])
        r = s.post(f"{API}/requests", data={"title": "TEST_redis_down", "text": "TEST peinture 5 m2"},
                   timeout=60)
        print("POST /requests with Redis DOWN ->", r.status_code, r.text[:200])
        rid = r.json().get("id") if r.status_code == 200 else None
        r2 = s.post(f"{API}/quotes/draft", json={"request_id": "nope"}, timeout=60)
        print("POST /quotes/draft (unknown req) with Redis DOWN ->", r2.status_code, r2.text[:120])
    finally:
        subprocess.Popen(["redis-server", "--daemonize", "yes", "--port", "6379"])
        time.sleep(2)
        print("redis ping after restart:",
              subprocess.run(["redis-cli", "ping"], capture_output=True, text=True).stdout.strip())
        print("recovery /catalog/active:", s.get(f"{API}/catalog/active", timeout=60).status_code)
        if rid:
            print("cleanup request:", s.delete(f"{API}/requests/{rid}", timeout=60).status_code)


main()
