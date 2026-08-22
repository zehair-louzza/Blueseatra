import json
import os
import re
import subprocess
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing from env and /app/frontend/.env")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

backend_env = dotenv_values("/app/backend/.env")
DATABASE_URL = backend_env.get("DATABASE_URL")


@pytest.fixture(scope="session")
def api():
    return API


@pytest.fixture(scope="session")
def test_credentials():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("Missing /app/memory/test_credentials.md")
    content = p.read_text(encoding="utf-8")
    email = re.search(r"(?im)^\s*[-*]?\s*Email\s*:\s*`?([^`\s]+)", content)
    pwd = re.search(r"(?im)^\s*[-*]?\s*Mot de passe\s*:\s*`?([^`\s]+)", content)
    if not email or not pwd:
        pytest.skip("No credentials found in test_credentials.md")
    return {"email": email.group(1), "password": pwd.group(1)}


@pytest.fixture(scope="session")
def auth_token(test_credentials):
    r = requests.post(f"{API}/auth/login", json=test_credentials, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:400]}")
    token = r.json().get("token")
    if not token:
        pytest.fail("Login response has no token")
    return token


@pytest.fixture(scope="session")
def client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    return s


def psql(sql: str):
    """Run SQL against the local PostgreSQL used by the backend (seeding only)."""
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not configured")
    res = subprocess.run(["psql", DATABASE_URL, "-v", "ON_ERROR_STOP=1", "-c", sql],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        pytest.fail(f"psql seeding failed: {res.stderr[:400]}")
    return res.stdout


EXTRACTED_SEED = {
    "language": "fr",
    "confidence": 0.92,
    "client_name": "TEST_Client SA",
    "donneur_d_ordre": "TEST_Client SA",
    "description": "TEST_Remise en etat local technique",
    "intervention_address": "12 rue de Test, 75000 Paris",
    "line_items": [
        {"label": "Peinture murale deux couches", "qty": 20, "unit": "m2"},
        {"label": "Pose placo BA13", "qty": 10, "unit": "m2"},
        {"label": "Main d'oeuvre qualifiee", "qty": 4, "unit": "hr"},
        {"label": "Article totalement inconnu XYZ123", "qty": 2},
    ],
}


@pytest.fixture(scope="session")
def seeded_request(client):
    """Create a request via the API, then seed AI-extracted content directly in DB.

    The AI extraction (Ollama) is unreachable in this environment, so the
    background task will mark the request 'failed'. Seeding lets us test the
    DETERMINISTIC quote flows that depend on `extracted`.
    """
    title = f"TEST_seed_{uuid.uuid4().hex[:8]}"
    r = client.post(f"{API}/requests",
                    data={"title": title, "text": "TEST peinture 20 m2 et placo 10 m2"},
                    timeout=120)
    assert r.status_code == 200, r.text[:400]
    rid = r.json()["id"]
    # Wait for the background AI extraction to settle (it fails: Ollama/Hermes
    # unreachable) BEFORE seeding, otherwise it overwrites our seeded payload.
    import time
    for _ in range(30):
        st = psql(f"SELECT status FROM requests WHERE id='{rid}';")
        if "processing" not in st and "received" not in st:
            break
        time.sleep(2)
    payload = json.dumps(EXTRACTED_SEED).replace("'", "''")
    psql(f"UPDATE requests SET status='done', extracted='{payload}'::jsonb, "
         f"language='fr', confidence=0.92, error=NULL WHERE id='{rid}';")
    yield rid
    psql(f"DELETE FROM quotes WHERE request_id='{rid}';")
    psql(f"DELETE FROM requests WHERE id='{rid}';")


@pytest.fixture(scope="session")
def demo_catalog_active(client):
    """Wait until the ACTIVE catalog served by the API is the demo one.

    NOTE (iteration 7): server.py still caches the active catalog per tenant for
    45s (_CATALOG_CACHE) but now evicts it on import/activate/deactivate/delete
    (_evict_catalog_cache), so this normally resolves on the first attempt. The
    retry loop is kept as a safety net (PATCH /catalogs/{id} is still not evicted).
    """
    import time
    deadline = time.time() + 75
    while time.time() < deadline:
        r = client.get(f"{API}/catalog/search", params={"q": "Peinture murale"}, timeout=60)
        if r.status_code == 200 and r.json().get("items"):
            return True
        time.sleep(5)
    pytest.fail("Demo catalog never became active/visible via /catalog/search "
                "(stale _CATALOG_CACHE?)")
