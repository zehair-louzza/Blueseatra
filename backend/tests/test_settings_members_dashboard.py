"""Additional non-regression coverage (iteration 6): members invite/role,
settings/integrations PUT, company-profile PUT, catalog PATCH/deactivate/
reactivate, dashboard coherence vs /quotes, RBAC on viewer role.
Deterministic (non-AI) flows only.
"""
import uuid

import pytest
import requests

TIMEOUT = 120


# --------------------------------------------------------------------- members
class TestMembers:
    state = {}

    def test_invite_member_and_change_role(self, api, client):
        email = f"test_member_{uuid.uuid4().hex[:8]}@example.com"
        r = client.post(f"{api}/members",
                        json={"email": email, "name": "TEST Member",
                              "password": "Test1234!", "role": "viewer"},
                        timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        uid = r.json().get("user_id")
        assert uid
        TestMembers.state["user_id"] = uid
        TestMembers.state["email"] = email

        members = client.get(f"{api}/members", timeout=TIMEOUT).json()
        m = next((x for x in members if x["email"] == email), None)
        assert m, members
        assert m["role"] == "viewer" and m["name"] == "TEST Member"

        # invited member can log in
        lg = requests.post(f"{api}/auth/login",
                           json={"email": email, "password": "Test1234!"}, timeout=TIMEOUT)
        assert lg.status_code == 200, lg.text[:300]
        TestMembers.state["token"] = lg.json()["token"]

        # role change persists
        p = client.patch(f"{api}/members/{uid}", json={"role": "operator"}, timeout=TIMEOUT)
        assert p.status_code == 200, p.text[:300]
        members = client.get(f"{api}/members", timeout=TIMEOUT).json()
        assert next(x for x in members if x["email"] == email)["role"] == "operator"

    def test_invalid_role_rejected(self, api, client):
        uid = TestMembers.state.get("user_id")
        if not uid:
            pytest.skip("member not created")
        r = client.patch(f"{api}/members/{uid}", json={"role": "superadmin"}, timeout=TIMEOUT)
        assert r.status_code == 400, r.status_code

    def test_duplicate_member_rejected(self, api, client):
        email = TestMembers.state.get("email")
        if not email:
            pytest.skip("member not created")
        r = client.post(f"{api}/members",
                        json={"email": email, "name": "dup", "password": "Test1234!",
                              "role": "viewer"}, timeout=TIMEOUT)
        assert r.status_code == 400, r.status_code

    def test_patch_unknown_member_404(self, api, client):
        r = client.patch(f"{api}/members/{uuid.uuid4()}", json={"role": "viewer"}, timeout=TIMEOUT)
        assert r.status_code == 404, r.status_code

    def test_zz_viewer_rbac(self, api, client):
        """Viewer must not be able to mutate settings/quotes."""
        uid = TestMembers.state.get("user_id")
        tok = TestMembers.state.get("token")
        if not (uid and tok):
            pytest.skip("member not created")
        assert client.patch(f"{api}/members/{uid}", json={"role": "viewer"},
                            timeout=TIMEOUT).status_code == 200
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {tok}"})
        # token carries old role -> re-login to pick up viewer role
        email = TestMembers.state["email"]
        lg = requests.post(f"{api}/auth/login", json={"email": email, "password": "Test1234!"},
                           timeout=TIMEOUT)
        assert lg.status_code == 200
        s.headers.update({"Authorization": f"Bearer {lg.json()['token']}"})
        assert s.get(f"{api}/dashboard", timeout=TIMEOUT).status_code == 200
        r = s.put(f"{api}/settings/integrations", json={"ai_provider": "hermes"}, timeout=TIMEOUT)
        assert r.status_code == 403, f"viewer could update settings: {r.status_code}"
        r2 = s.post(f"{api}/members", json={"email": "x@example.com", "name": "x",
                                            "password": "Test1234!", "role": "admin"},
                    timeout=TIMEOUT)
        assert r2.status_code == 403, r2.status_code


# -------------------------------------------------------- settings / company
class TestSettingsCompanyProfile:
    def test_settings_roundtrip(self, api, client):
        before = client.get(f"{api}/settings/integrations", timeout=TIMEOUT)
        assert before.status_code == 200, before.text[:300]
        orig = before.json()["settings"]
        assert "provider_models" in before.json()

        r = client.put(f"{api}/settings/integrations",
                       json={"ai_provider": "hermes", "ai_model": "qwen2.5:14b",
                             "ai_key": "TEST_secret_key", "n8n_webhook_url": "https://example.com/hook"},
                       timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        after = client.get(f"{api}/settings/integrations", timeout=TIMEOUT).json()["settings"]
        assert after["ai_model"] == "qwen2.5:14b"
        assert after["n8n_webhook_url"] == "https://example.com/hook"
        assert after.get("ai_key_set") is True
        assert "ai_key" not in after, "raw ai_key leaked in GET response"

        # restore
        client.put(f"{api}/settings/integrations",
                   json={"ai_provider": orig.get("ai_provider") or "hermes",
                         "ai_model": orig.get("ai_model"),
                         "n8n_webhook_url": orig.get("n8n_webhook_url")}, timeout=TIMEOUT)

    def test_company_profile_roundtrip(self, api, client):
        before = client.get(f"{api}/company-profile", timeout=TIMEOUT)
        assert before.status_code == 200, before.text[:300]
        orig = before.json()
        payload = dict(orig)
        payload.pop("tenant_id", None)
        payload.pop("updated_at", None)
        payload["company_name"] = "TEST_Blueseatra SARL"
        payload["address_line1"] = "12 rue de TEST, 69000 Lyon"
        payload["siret"] = "12345678900011"
        r = client.put(f"{api}/company-profile", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        after = client.get(f"{api}/company-profile", timeout=TIMEOUT).json()
        assert after["company_name"] == "TEST_Blueseatra SARL"
        assert after["address_line1"] == "12 rue de TEST, 69000 Lyon"
        assert after["siret"] == "12345678900011"
        assert "_id" not in after
        # restore original company_name
        payload["company_name"] = orig.get("company_name") or "QA SARL"
        payload["address_line1"] = orig.get("address_line1")
        payload["siret"] = orig.get("siret")
        client.put(f"{api}/company-profile", json=payload, timeout=TIMEOUT)


# ------------------------------------------------------------------- catalogs
class TestCatalogLifecycle:
    def test_patch_deactivate_reactivate_demo(self, api, client):
        cats = client.get(f"{api}/catalogs", timeout=TIMEOUT).json()
        demo = next((c for c in cats if not c["name"].startswith("TEST_")), None)
        assert demo, cats
        cid = demo["id"]
        orig_code = demo.get("client_code")
        active_ver = demo.get("active_version_id") or sorted(
            demo["versions"], key=lambda v: v["version_number"])[-1]["id"]

        p = client.patch(f"{api}/catalogs/{cid}", json={"client_code": "TEST_CODE"}, timeout=TIMEOUT)
        assert p.status_code == 200, p.text[:300]
        cats2 = client.get(f"{api}/catalogs", timeout=TIMEOUT).json()
        assert next(c for c in cats2 if c["id"] == cid)["client_code"] == "TEST_CODE"

        d = client.post(f"{api}/catalogs/{cid}/deactivate", timeout=TIMEOUT)
        assert d.status_code == 200, d.text[:300]
        cats3 = client.get(f"{api}/catalogs", timeout=TIMEOUT).json()
        assert next(c for c in cats3 if c["id"] == cid)["active_version_id"] is None

        a = client.post(f"{api}/catalogs/{cid}/activate/{active_ver}", timeout=TIMEOUT)
        assert a.status_code == 200, a.text[:300]
        cats4 = client.get(f"{api}/catalogs", timeout=TIMEOUT).json()
        assert next(c for c in cats4 if c["id"] == cid)["active_version_id"] == active_ver
        client.patch(f"{api}/catalogs/{cid}", json={"client_code": orig_code or "N/A"}, timeout=TIMEOUT)

    def test_unknown_catalog_404(self, api, client):
        assert client.get(f"{api}/catalogs/{uuid.uuid4()}/items",
                          timeout=TIMEOUT).status_code == 404
        assert client.patch(f"{api}/catalogs/{uuid.uuid4()}", json={"name": "x"},
                            timeout=TIMEOUT).status_code == 404
        assert client.post(f"{api}/catalogs/{uuid.uuid4()}/deactivate",
                           timeout=TIMEOUT).status_code == 404

    def test_catalog_active_shape(self, api, client):
        r = client.get(f"{api}/catalog/active", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("catalog") and isinstance(d.get("items"), list) and d["items"]
        it = d["items"][0]
        assert "item_label" in it and "unit_price_ht" in it and "_id" not in it


# ------------------------------------------------------------------ dashboard
class TestDashboardCoherence:
    def test_dashboard_matches_quotes_and_requests(self, api, client):
        d = client.get(f"{api}/dashboard", timeout=TIMEOUT).json()
        quotes = client.get(f"{api}/quotes", timeout=TIMEOUT).json()
        reqs = client.get(f"{api}/requests", timeout=TIMEOUT).json()

        for key in ("kpis", "pipeline", "request_status", "monthly", "funnel",
                    "recent_requests", "recent_quotes", "top_clients"):
            assert key in d, f"missing dashboard key {key}"

        kpis = d["kpis"]
        assert kpis["requests"] == len(reqs), (kpis["requests"], len(reqs))
        assert sum(x["count"] for x in d["request_status"]) == len(reqs)
        assert sum(x["count"] for x in d["pipeline"]) == len(quotes), (d["pipeline"], len(quotes))

        by_status = {}
        for q in quotes:
            by_status[q.get("status") or "draft"] = by_status.get(q.get("status") or "draft", 0) + 1
        assert kpis["drafts"] == by_status.get("draft", 0)
        assert kpis["validated"] == by_status.get("validated", 0)
        assert kpis["sent"] == by_status.get("sent", 0)

        assert len(d["monthly"]) == 12, len(d["monthly"])
        funnel = {x["key"]: x["count"] for x in d["funnel"]}
        assert funnel["requests"] == len(reqs)
        assert funnel["drafts"] == kpis["drafts"]

        active = client.get(f"{api}/catalog/active", timeout=TIMEOUT).json()
        assert kpis["active_catalog_items"] == len(active["items"])
        assert kpis["active_catalog_name"] == active["catalog"]["name"]
