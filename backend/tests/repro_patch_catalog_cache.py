"""Check: PATCH /catalogs/{id} (name/client_code) does not evict _CATALOG_CACHE."""
import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
s.headers.update({"Authorization": "Bearer " + s.post(
    f"{API}/auth/login", json={"email": "qa@example.com", "password": "Test1234!"},
    timeout=60).json()["token"]})

a = s.get(f"{API}/catalog/active", timeout=60).json()["catalog"]
print("active:", a["name"], a["client_code"])
cid = a["id"]
orig = a["client_code"]
print("patch:", s.patch(f"{API}/catalogs/{cid}", json={"client_code": "TESTPATCH"}, timeout=60).json())
after = s.get(f"{API}/catalog/active", timeout=60).json()["catalog"]
print("after patch (immediate):", after["client_code"])
print("RESULT:", "STALE (patch not evicted)" if after["client_code"] != "TESTPATCH" else "fresh")
print("restore:", s.patch(f"{API}/catalogs/{cid}", json={"client_code": orig}, timeout=60).status_code)
