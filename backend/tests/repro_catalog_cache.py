"""Reproduction: server.py _CATALOG_CACHE (45s TTL) is never invalidated on
catalog import/activate/deactivate/delete -> /catalog/active, /catalog/search
and /quotes/draft pricing can serve a stale catalog for up to 45 seconds.
"""
import io
import time
import uuid

import requests
from dotenv import dotenv_values

BASE = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
tok = s.post(f"{BASE}/auth/login",
             json={"email": "qa@example.com", "password": "Test1234!"}, timeout=60).json()["token"]
s.headers.update({"Authorization": f"Bearer {tok}"})

# warm the cache with the currently active (demo) catalog
warm = s.get(f"{BASE}/catalog/active", timeout=60).json()
print("before  :", warm["catalog"]["name"], len(warm["items"]), "items")

marker = f"TEST_CACHE_{uuid.uuid4().hex[:6]}"
csv = (f"Famille,Article,Unité,TVA_%,Prix_vente_HT\nTEST,{marker},u,20,99.99\n").encode()
r = s.post(f"{BASE}/catalogs/import",
           files={"file": ("c.csv", io.BytesIO(csv), "text/csv")},
           data={"catalog_name": marker, "activate": "true"}, timeout=120)
print("import  :", r.status_code, r.json())
cid = r.json()["catalog_id"]

imm = s.get(f"{BASE}/catalog/active", timeout=60).json()
print("t+0s    :", imm["catalog"]["name"], len(imm["items"]), "items")
stale = imm["catalog"]["name"] != marker

srch = s.get(f"{BASE}/catalog/search", params={"q": marker}, timeout=60).json()
print("search  :", len(srch["items"]), "hits for the new item")

time.sleep(50)
late = s.get(f"{BASE}/catalog/active", timeout=60).json()
print("t+50s   :", late["catalog"]["name"], len(late["items"]), "items")

print("RESULT  :", "STALE CACHE BUG REPRODUCED" if stale and late["catalog"]["name"] == marker
      else "no staleness observed")

# cleanup: delete test catalog and reactivate demo
print("delete  :", s.delete(f"{BASE}/catalogs/{cid}", timeout=60).status_code)
cats = s.get(f"{BASE}/catalogs", timeout=60).json()
demo = next(c for c in cats if not c["name"].startswith("TEST_"))
ver = sorted(demo["versions"], key=lambda v: v["version_number"])[-1]["id"]
print("reactiv :", s.post(f"{BASE}/catalogs/{demo['id']}/activate/{ver}", timeout=60).status_code)
