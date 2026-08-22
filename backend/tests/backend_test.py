"""Non-regression suite for Blueseatra deterministic (non-AI) business flows.

Scope (per review request): auth, catalogs + CSV import, quotes (deterministic
catalog matching via matching.py), dashboard/audit/members, requests CRUD.
AI extraction failures (Ollama unreachable) are EXPECTED and not asserted.
"""
import io
import json
import uuid

import pytest
import requests

TIMEOUT = 120


# ---------------------------------------------------------------- health / auth
class TestHealthAuth:
    def test_root_and_health(self, api):
        r = requests.get(f"{api}/", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        h = requests.get(f"{api}/health", timeout=TIMEOUT)
        assert h.status_code == 200, h.text[:300]

    def test_login_success(self, api, test_credentials):
        r = requests.post(f"{api}/auth/login", json=test_credentials, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d.get("token"), str) and len(d["token"]) > 20
        assert d["user"]["email"] == test_credentials["email"]
        assert d["tenant"]["id"] and d["tenant"]["role"] in ("owner", "admin", "operator", "viewer")

    def test_login_wrong_password(self, api, test_credentials):
        r = requests.post(f"{api}/auth/login",
                          json={"email": test_credentials["email"], "password": "WrongPass!1"},
                          timeout=TIMEOUT)
        assert r.status_code == 401, r.text[:300]

    def test_login_unknown_email(self, api):
        r = requests.post(f"{api}/auth/login",
                          json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com", "password": "x"},
                          timeout=TIMEOUT)
        assert r.status_code == 401, r.text[:300]

    def test_me(self, api, client, test_credentials):
        r = client.get(f"{api}/auth/me", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["user"]["email"] == test_credentials["email"]
        assert d.get("tenant") or d.get("tenants")

    def test_me_without_token(self, api):
        r = requests.get(f"{api}/auth/me", timeout=TIMEOUT)
        assert r.status_code in (401, 403), r.status_code

    def test_signup_creates_user_tenant_and_demo_catalog(self, api):
        email = f"TEST_signup_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{api}/auth/signup",
                          json={"email": email, "password": "Test1234!", "name": "TEST Signup",
                                "company": "TEST_Co"},
                          timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("token")
        assert d["tenant"]["name"] == "TEST_Co"
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {d['token']}"})
        cats = s.get(f"{api}/catalogs", timeout=TIMEOUT)
        assert cats.status_code == 200, cats.text[:300]
        assert len(cats.json()) >= 1, "demo catalog not seeded on signup"
        active = s.get(f"{api}/catalog/active", timeout=TIMEOUT)
        assert active.status_code == 200
        assert len(active.json().get("items") or []) > 0, "demo catalog has no items"
        # duplicate signup rejected
        dup = requests.post(f"{api}/auth/signup",
                            json={"email": email, "password": "Test1234!", "name": "x", "company": "y"},
                            timeout=TIMEOUT)
        assert dup.status_code == 400, dup.status_code


# -------------------------------------------------------------------- catalogs
class TestCatalogs:
    imported_catalog = {}

    def test_list_catalogs(self, api, client):
        r = client.get(f"{api}/catalogs", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        cats = r.json()
        assert isinstance(cats, list) and len(cats) >= 1
        for c in cats:
            assert "_id" not in c
            assert isinstance(c.get("versions"), list)

    def test_template_csv(self, api, client):
        r = client.get(f"{api}/catalog-template.csv", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:200]
        assert "text/csv" in r.headers.get("content-type", "")
        assert "Article" in r.text and "Prix_vente_HT" in r.text

    def test_import_preview(self, api, client):
        tpl = client.get(f"{api}/catalog-template.csv", timeout=TIMEOUT).content
        files = {"file": ("tpl.csv", io.BytesIO(tpl), "text/csv")}
        r = client.post(f"{api}/catalogs/import/preview", files=files, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["total_rows"] == 1
        assert "Article" in d["columns"]
        assert d["suggested_mapping"].get("item_label") == "Article"
        assert any(f["key"] == "item_label" for f in d["standard_fields"])

    def test_import_activate_and_items(self, api, client):
        csv_bytes = (
            "Famille,Article,Unité,Marque,Référence,Fournisseur_principal,TVA_%,Marge_%,"
            "Prix_achat_HT,Prix_vente_HT,Délai\n"
            "TEST,TEST_Article Alpha,u,MarqueA,REF-A,FourniA,20,10,8.00,10.50,2 j\n"
            "TEST,TEST_Article Beta,m2,MarqueB,REF-B,FourniB,10,15,4,5.75,3 j\n"
        ).encode()
        name = f"TEST_Catalogue_{uuid.uuid4().hex[:6]}"
        files = {"file": ("import.csv", io.BytesIO(csv_bytes), "text/csv")}
        r = client.post(f"{api}/catalogs/import", files=files,
                        data={"catalog_name": name, "activate": "false"}, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d.get("success_rows") == 2 and d.get("error_rows") == 0, d
        assert d.get("activated") is False, d
        cat_id = d.get("catalog_id")
        ver_id = d.get("version_id")
        assert cat_id and ver_id
        TestCatalogs.imported_catalog = {"id": cat_id, "version_id": ver_id, "name": name}

        act = client.post(f"{api}/catalogs/{cat_id}/activate/{ver_id}", timeout=TIMEOUT)
        assert act.status_code == 200, act.text[:300]

        items = client.get(f"{api}/catalogs/{cat_id}/items", timeout=TIMEOUT)
        assert items.status_code == 200, items.text[:300]
        di = items.json()
        assert di["catalog"]["active_version_id"] == ver_id
        assert len(di["items"]) == 2, di["items"]
        labels = sorted(i["item_label"] for i in di["items"])
        assert labels == ["TEST_Article Alpha", "TEST_Article Beta"], labels
        alpha = next(i for i in di["items"] if i["item_label"] == "TEST_Article Alpha")
        assert float(alpha["unit_price_ht"]) == 10.5
        assert alpha["unit"] == "u"
        assert "_id" not in alpha

    def test_catalog_search(self, api, client):
        r = client.get(f"{api}/catalog/search", params={"q": "TEST_Article"}, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["catalog"] is not None
        assert len(d["items"]) >= 2, d
        empty = client.get(f"{api}/catalog/search", params={"q": "zzzz_no_match_zzzz"}, timeout=TIMEOUT)
        assert empty.status_code == 200 and empty.json()["items"] == []

    def test_import_bad_file_rejected(self, api, client):
        files = {"file": ("bad.csv", io.BytesIO(b"\x00\x01binary"), "text/csv")}
        r = client.post(f"{api}/catalogs/import", files=files,
                        data={"catalog_name": "TEST_bad", "activate": "false"}, timeout=TIMEOUT)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"

    def test_zz_reactivate_demo_and_cleanup(self, api, client):
        """Re-activate the demo catalog (needed by quote tests) and delete TEST catalog."""
        cats = client.get(f"{api}/catalogs", timeout=TIMEOUT).json()
        demo = next((c for c in cats if not c["name"].startswith("TEST_")), None)
        assert demo, "no demo catalog found"
        vers = sorted(demo["versions"], key=lambda v: v["version_number"], reverse=True)
        assert vers, "demo catalog has no version"
        act = client.post(f"{api}/catalogs/{demo['id']}/activate/{vers[0]['id']}", timeout=TIMEOUT)
        assert act.status_code == 200, act.text[:300]
        info = TestCatalogs.imported_catalog
        if info.get("id"):
            dele = client.delete(f"{api}/catalogs/{info['id']}", timeout=TIMEOUT)
            assert dele.status_code == 200, dele.text[:300]
            gone = client.get(f"{api}/catalogs/{info['id']}/items", timeout=TIMEOUT)
            assert gone.status_code == 404


# -------------------------------------------------------------- requests CRUD
class TestRequestsCrud:
    def test_create_list_get_patch_delete(self, api, client):
        title = f"TEST_req_{uuid.uuid4().hex[:6]}"
        r = client.post(f"{api}/requests",
                        data={"title": title, "text": "Besoin de peinture 20 m2 et placo 10 m2"},
                        timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["status"] == "received"
        rid = d["id"]

        lst = client.get(f"{api}/requests", timeout=TIMEOUT)
        assert lst.status_code == 200
        assert any(x["id"] == rid for x in lst.json())
        assert all("file_b64" not in x and "_id" not in x for x in lst.json())

        one = client.get(f"{api}/requests/{rid}", timeout=TIMEOUT)
        assert one.status_code == 200
        assert one.json()["title"] == title

        pat = client.patch(f"{api}/requests/{rid}", json={"title": title + "_edited"}, timeout=TIMEOUT)
        assert pat.status_code == 200, pat.text[:300]
        assert pat.json()["title"] == title + "_edited"
        assert client.get(f"{api}/requests/{rid}", timeout=TIMEOUT).json()["title"] == title + "_edited"

        dele = client.delete(f"{api}/requests/{rid}", timeout=TIMEOUT)
        assert dele.status_code == 200, dele.text[:300]
        assert client.get(f"{api}/requests/{rid}", timeout=TIMEOUT).status_code == 404

    def test_create_without_content_rejected(self, api, client):
        r = client.post(f"{api}/requests", data={"title": "TEST_empty", "text": "   "}, timeout=TIMEOUT)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:300]}"

    def test_get_unknown_request_404(self, api, client):
        r = client.get(f"{api}/requests/{uuid.uuid4()}", timeout=TIMEOUT)
        assert r.status_code == 404


# ------------------------------------------------------------------- quotes
class TestQuotes:
    state = {}

    def test_draft_deterministic_matching(self, api, client, seeded_request, demo_catalog_active):
        r = client.post(f"{api}/quotes/draft", json={"request_id": seeded_request}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        q = r.json()
        assert q["status"] == "draft"
        assert q["number"].startswith("BS-")
        assert q["pricing_snapshot"]["catalog_id"]
        lines = q["lines"]
        assert len(lines) >= 3, lines
        matched = [l for l in lines if l.get("matched_label")]
        assert any(l["matched_label"] == "Peinture murale deux couches" for l in matched), \
            [l.get("matched_label") for l in lines]
        paint = next(l for l in lines if l.get("matched_label") == "Peinture murale deux couches")
        assert float(paint["unit_price_ht"]) == 12.5
        assert float(paint["qty"]) == 20
        # unknown item must not be silently priced
        unknown = [l for l in lines if "inconnu" in (l.get("description") or "").lower()]
        assert unknown, "unknown item line missing"
        assert unknown[0].get("status") != "matched"
        assert q["total_ht"] > 0
        assert round(q["total_ht"] + q["total_vat"], 2) == q["total_ttc"]
        TestQuotes.state["id"] = q["id"]

    def test_draft_unknown_request_404(self, api, client):
        r = client.post(f"{api}/quotes/draft", json={"request_id": str(uuid.uuid4())}, timeout=TIMEOUT)
        assert r.status_code == 404

    def test_list_and_get(self, api, client):
        qid = TestQuotes.state["id"]
        lst = client.get(f"{api}/quotes", timeout=TIMEOUT)
        assert lst.status_code == 200
        assert any(x["id"] == qid for x in lst.json())
        one = client.get(f"{api}/quotes/{qid}", timeout=TIMEOUT)
        assert one.status_code == 200
        assert one.json()["id"] == qid and "_id" not in one.json()

    def test_patch_recomputes_totals(self, api, client):
        qid = TestQuotes.state["id"]
        body = {
            "client": "TEST_Client Edited",
            "lines": [
                {"line_type": "material", "description": "TEST ligne A", "qty": 3,
                 "unit_price_ht": 100, "vat_rate": 20, "unit": "u"},
                {"line_type": "material", "description": "TEST ligne B", "qty": 2,
                 "unit_price_ht": 50, "vat_rate": 10, "unit": "u"},
                {"line_type": "note", "description": "TEST note"},
            ],
        }
        r = client.patch(f"{api}/quotes/{qid}", json=body, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["total_ht"] == 400.0, d["total_ht"]
        assert d["total_vat"] == 70.0, d["total_vat"]
        assert d["total_ttc"] == 470.0, d["total_ttc"]
        assert d["client"] == "TEST_Client Edited"
        note = [l for l in d["lines"] if l["line_type"] == "note"][0]
        assert note["line_ht"] is None
        # persistence
        g = client.get(f"{api}/quotes/{qid}", timeout=TIMEOUT).json()
        assert g["total_ttc"] == 470.0 and g["client"] == "TEST_Client Edited"
        assert len(g["lines"]) == 3

    def test_pdf(self, api, client):
        qid = TestQuotes.state["id"]
        r = client.get(f"{api}/quotes/{qid}/pdf", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF", r.content[:20]
        assert len(r.content) > 1000

    def test_status_transitions(self, api, client):
        qid = TestQuotes.state["id"]
        v = client.post(f"{api}/quotes/{qid}/validate", timeout=TIMEOUT)
        assert v.status_code == 200, v.text[:300]
        assert client.get(f"{api}/quotes/{qid}", timeout=TIMEOUT).json()["status"] == "validated"

        # edit must be blocked once validated
        blocked = client.patch(f"{api}/quotes/{qid}", json={"client": "X"}, timeout=TIMEOUT)
        assert blocked.status_code == 400, blocked.status_code

        s = client.post(f"{api}/quotes/{qid}/send", timeout=TIMEOUT)
        assert s.status_code == 200 and s.json()["status"] == "sent"
        assert client.get(f"{api}/quotes/{qid}", timeout=TIMEOUT).json()["status"] == "sent"

        ro = client.post(f"{api}/quotes/{qid}/reopen", timeout=TIMEOUT)
        assert ro.status_code == 200, ro.text[:300]
        assert client.get(f"{api}/quotes/{qid}", timeout=TIMEOUT).json()["status"] == "draft"

    def test_duplicate(self, api, client):
        qid = TestQuotes.state["id"]
        r = client.post(f"{api}/quotes/{qid}/duplicate", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        clone = r.json()
        assert clone["id"] != qid and clone["status"] == "draft"
        assert clone["number"].startswith("BS-")
        assert len(clone["lines"]) == 3
        got = client.get(f"{api}/quotes/{clone['id']}", timeout=TIMEOUT)
        assert got.status_code == 200
        dele = client.delete(f"{api}/quotes/{clone['id']}", timeout=TIMEOUT)
        assert dele.status_code == 200
        assert client.get(f"{api}/quotes/{clone['id']}", timeout=TIMEOUT).status_code == 404

    def test_rematch_restores_catalog_prices(self, api, client):
        qid = TestQuotes.state["id"]
        r = client.post(f"{api}/quotes/{qid}/rematch", timeout=300)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert any(l.get("matched_label") == "Peinture murale deux couches" for l in d["lines"]), \
            [l.get("matched_label") for l in d["lines"]]
        assert d["total_ht"] > 0
        assert round(d["total_ht"] + (d["total_vat"] or 0), 2) == d["total_ttc"]

    def test_zz_cleanup_quote(self, api, client):
        qid = TestQuotes.state.get("id")
        if qid:
            r = client.delete(f"{api}/quotes/{qid}", timeout=TIMEOUT)
            assert r.status_code == 200, r.text[:300]


# ---------------------------------------------------- dashboard / audit / members
class TestDashboardAuditMembers:
    def test_dashboard(self, api, client):
        r = client.get(f"{api}/dashboard", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert isinstance(d, dict) and d, "empty dashboard payload"
        assert json.dumps(d)  # serializable, no ObjectId leaks
        assert "_id" not in json.dumps(d)

    def test_audit(self, api, client):
        r = client.get(f"{api}/audit", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        logs = r.json()
        assert isinstance(logs, list) and len(logs) > 0
        assert all("_id" not in x for x in logs)
        assert any(x.get("action") for x in logs)

    def test_members(self, api, client, test_credentials):
        r = client.get(f"{api}/members", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        members = r.json()
        assert isinstance(members, list) and len(members) >= 1
        assert any(m.get("email") == test_credentials["email"] for m in members)

    def test_settings_and_company_profile(self, api, client):
        s = client.get(f"{api}/settings/integrations", timeout=TIMEOUT)
        assert s.status_code == 200, s.text[:300]
        assert "ai_key" not in s.json() or s.json().get("ai_key") in (None, "")
        p = client.get(f"{api}/company-profile", timeout=TIMEOUT)
        assert p.status_code == 200, p.text[:300]
