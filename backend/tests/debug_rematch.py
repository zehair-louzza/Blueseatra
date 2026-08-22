import json
import subprocess
import uuid

import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = dotenv_values("/app/backend/.env")["DATABASE_URL"]

EX = {
    "language": "fr", "confidence": 0.92, "client_name": "TEST_Client SA",
    "donneur_d_ordre": "TEST_Client SA", "description": "TEST_Remise en etat local technique",
    "intervention_address": "12 rue de Test",
    "line_items": [
        {"label": "Peinture murale deux couches", "qty": 20, "unit": "m2"},
        {"label": "Pose placo BA13", "qty": 10, "unit": "m2"},
        {"label": "Main d'oeuvre qualifiee", "qty": 4, "unit": "hr"},
        {"label": "Article totalement inconnu XYZ123", "qty": 2},
    ],
}

s = requests.Session()
tok = requests.post(f"{API}/auth/login", json={"email": "qa@example.com", "password": "Test1234!"}, timeout=60).json()["token"]
s.headers.update({"Authorization": f"Bearer {tok}"})

r = s.post(f"{API}/requests", data={"title": f"TEST_dbg_{uuid.uuid4().hex[:6]}", "text": "peinture"}, timeout=120)
rid = r.json()["id"]
subprocess.run(["psql", DB, "-c", f"UPDATE requests SET status='done', extracted='{json.dumps(EX).replace(chr(39), chr(39) * 2)}'::jsonb WHERE id='{rid}';"], check=True, capture_output=True)

d = s.post(f"{API}/quotes/draft", json={"request_id": rid}, timeout=180)
print("draft", d.status_code)
q = d.json()
qid = q["id"]
for l in q["lines"]:
    print(" DRAFT", l.get("line_type"), l.get("status"), l.get("matched_label"), l.get("unit_price_ht"), l.get("qty"))
print("totals", q["total_ht"], q["total_vat"], q["total_ttc"])

rm = s.post(f"{API}/quotes/{qid}/rematch", timeout=300)
print("rematch(no edit)", rm.status_code, rm.text[:200] if rm.status_code != 200 else "")
if rm.status_code == 200:
    for l in rm.json()["lines"]:
        print(" REMATCH", l.get("line_type"), l.get("status"), l.get("matched_label"), l.get("unit_price_ht"))

# now patch with custom lines then rematch
p = s.patch(f"{API}/quotes/{qid}", json={"lines": [
    {"line_type": "material", "description": "TEST ligne A", "qty": 3, "unit_price_ht": 100, "vat_rate": 20, "unit": "u"},
    {"line_type": "material", "description": "TEST ligne B", "qty": 2, "unit_price_ht": 50, "vat_rate": 10, "unit": "u"},
    {"line_type": "note", "description": "TEST note"},
]}, timeout=120)
print("patch", p.status_code, p.json().get("total_ht"), p.json().get("total_vat"))
rm2 = s.post(f"{API}/quotes/{qid}/rematch", timeout=300)
print("rematch(after edit)", rm2.status_code, rm2.text[:300])

s.delete(f"{API}/quotes/{qid}", timeout=60)
subprocess.run(["psql", DB, "-c", f"DELETE FROM requests WHERE id='{rid}';"], capture_output=True)
