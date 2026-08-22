"""Iteration 8 - ITEM 1: invariant "UN SEUL CATALOGUE ACTIF par tenant".

Covers server.py _deactivate_other_catalogs() called from import_catalog
(activate=true) and activate_version(). Also re-checks Redis-backed cache
invalidation for PATCH /catalogs/{id} (iteration-7 residual gap).
All assertions are IMMEDIATE (no sleep) so any stale cache window fails.
"""
import io
import uuid

import pytest


def _csv(marker, price="99.99"):
    return (f"Famille,Article,Unit\u00e9,TVA_%,Prix_vente_HT\n"
            f"TEST,{marker},u,20,{price}\n").encode()


def _import(client, api, marker, price="99.99", activate="true", name=None):
    r = client.post(f"{api}/catalogs/import",
                    files={"file": ("c.csv", io.BytesIO(_csv(marker, price)), "text/csv")},
                    data={"catalog_name": name or marker, "activate": activate}, timeout=120)
    assert r.status_code == 200, f"import failed {r.status_code}: {r.text[:300]}"
    return r.json()


def _catalogs(client, api):
    r = client.get(f"{api}/catalogs", timeout=60)
    assert r.status_code == 200, r.text[:300]
    return {c["id"]: c for c in r.json()}


def _active_ids(client, api):
    return sorted(cid for cid, c in _catalogs(client, api).items() if c.get("active_version_id"))


@pytest.fixture(scope="module")
def demo_catalog(client, api):
    cats = client.get(f"{api}/catalogs", timeout=60).json()
    demo = next((c for c in cats if not c["name"].startswith("TEST_")), None)
    assert demo, "no demo catalog present"
    return demo


@pytest.fixture(autouse=True)
def restore_demo(client, api, demo_catalog):
    """Re-activate the demo catalog after each test so later suites are unaffected."""
    yield
    cats = client.get(f"{api}/catalogs", timeout=60).json()
    demo = next((c for c in cats if c["id"] == demo_catalog["id"]), None)
    if demo and demo.get("versions"):
        ver = sorted(demo["versions"], key=lambda v: v["version_number"])[-1]["id"]
        client.post(f"{api}/catalogs/{demo_catalog['id']}/activate/{ver}", timeout=60)


# --- ITEM 1a: import+activate B deactivates A --------------------------------
def test_import_activate_deactivates_other_catalogs(client, api):
    ma = f"TEST_ONE_A_{uuid.uuid4().hex[:6]}"
    mb = f"TEST_ONE_B_{uuid.uuid4().hex[:6]}"
    a = _import(client, api, ma, price="11.00")
    cid_a = a["catalog_id"]
    cid_b = None
    try:
        assert a["activated"] is True
        cats = _catalogs(client, api)
        assert cats[cid_a]["active_version_id"] == a["version_id"]
        assert _active_ids(client, api) == [cid_a], (
            "importing+activating A must leave A as the ONLY active catalog")
        assert client.get(f"{api}/catalog/active", timeout=60).json()["catalog"]["id"] == cid_a

        b = _import(client, api, mb, price="22.00")
        cid_b = b["catalog_id"]
        assert b["activated"] is True
        cats = _catalogs(client, api)
        assert cats[cid_b]["active_version_id"] == b["version_id"], "B should be active"
        assert cats[cid_a]["active_version_id"] is None, (
            f"INVARIANT BROKEN: catalog A still active "
            f"(active_version_id={cats[cid_a]['active_version_id']}) after activating B")
        assert _active_ids(client, api) == [cid_b]

        # /catalog/active must reflect the LAST activated one, immediately
        act = client.get(f"{api}/catalog/active", timeout=60).json()
        assert act["catalog"]["id"] == cid_b
        assert [i["item_label"] for i in act["items"]] == [mb]
        assert float(act["items"][0]["unit_price_ht"]) == 22.00
        # A's items must not be served anymore
        assert client.get(f"{api}/catalog/search", params={"q": ma}, timeout=60).json()["items"] == []
    finally:
        client.delete(f"{api}/catalogs/{cid_a}", timeout=60)
        if cid_b:
            client.delete(f"{api}/catalogs/{cid_b}", timeout=60)


# --- ITEM 1b: POST /catalogs/{id}/activate/{ver} keeps a single active -------
def test_activate_endpoint_keeps_single_active(client, api):
    ma = f"TEST_ONE_A_{uuid.uuid4().hex[:6]}"
    mb = f"TEST_ONE_B_{uuid.uuid4().hex[:6]}"
    a = _import(client, api, ma, price="11.00", activate="false")
    b = _import(client, api, mb, price="22.00", activate="false")
    cid_a, cid_b = a["catalog_id"], b["catalog_id"]
    try:
        assert a["activated"] is False and b["activated"] is False
        # activate A explicitly
        r = client.post(f"{api}/catalogs/{cid_a}/activate/{a['version_id']}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert _active_ids(client, api) == [cid_a], "only A must be active"
        assert client.get(f"{api}/catalog/active", timeout=60).json()["catalog"]["id"] == cid_a

        # activate B -> A must be deactivated automatically
        r = client.post(f"{api}/catalogs/{cid_b}/activate/{b['version_id']}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        cats = _catalogs(client, api)
        assert cats[cid_a]["active_version_id"] is None, "INVARIANT BROKEN: A still active"
        assert cats[cid_b]["active_version_id"] == b["version_id"]
        assert _active_ids(client, api) == [cid_b]
        act = client.get(f"{api}/catalog/active", timeout=60).json()
        assert act["catalog"]["id"] == cid_b
        assert float(act["items"][0]["unit_price_ht"]) == 22.00

        # re-activate A -> B must be deactivated (symmetry)
        r = client.post(f"{api}/catalogs/{cid_a}/activate/{a['version_id']}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert _active_ids(client, api) == [cid_a]
        act = client.get(f"{api}/catalog/active", timeout=60).json()
        assert act["catalog"]["id"] == cid_a
        assert float(act["items"][0]["unit_price_ht"]) == 11.00
    finally:
        client.delete(f"{api}/catalogs/{cid_a}", timeout=60)
        client.delete(f"{api}/catalogs/{cid_b}", timeout=60)


# --- ITEM 1c: versions of the deactivated catalog are archived ---------------
def test_other_catalog_versions_archived(client, api):
    ma = f"TEST_ONE_A_{uuid.uuid4().hex[:6]}"
    mb = f"TEST_ONE_B_{uuid.uuid4().hex[:6]}"
    a = _import(client, api, ma)
    cid_a = a["catalog_id"]
    b = _import(client, api, mb)
    cid_b = b["catalog_id"]
    try:
        cats = _catalogs(client, api)
        a_vers = cats[cid_a].get("versions") or []
        assert a_vers, "catalog A should still expose its versions"
        assert all(v["status"] == "archived" for v in a_vers), (
            f"deactivated catalog A keeps a non-archived version: "
            f"{[(v['version_number'], v['status']) for v in a_vers]}")
        b_active = [v for v in (cats[cid_b].get("versions") or []) if v["status"] == "active"]
        assert len(b_active) == 1 and b_active[0]["id"] == b["version_id"]
    finally:
        client.delete(f"{api}/catalogs/{cid_a}", timeout=60)
        client.delete(f"{api}/catalogs/{cid_b}", timeout=60)


# --- ITEM 1d: demo catalog is deactivated too (no privileged catalog) --------
def test_demo_catalog_deactivated_when_other_activated(client, api, demo_catalog):
    marker = f"TEST_ONE_C_{uuid.uuid4().hex[:6]}"
    # ensure demo is the active one first
    ver = sorted(demo_catalog["versions"], key=lambda v: v["version_number"])[-1]["id"]
    client.post(f"{api}/catalogs/{demo_catalog['id']}/activate/{ver}", timeout=60)
    assert _active_ids(client, api) == [demo_catalog["id"]]

    body = _import(client, api, marker)
    cid = body["catalog_id"]
    try:
        cats = _catalogs(client, api)
        assert cats[demo_catalog["id"]]["active_version_id"] is None, (
            "INVARIANT BROKEN: demo catalog still active after activating another catalog")
        assert _active_ids(client, api) == [cid]
        # demo items must no longer be searchable
        srch = client.get(f"{api}/catalog/search", params={"q": "Peinture murale"}, timeout=60).json()
        assert srch["items"] == [], "demo items still served though its catalog is deactivated"
    finally:
        client.delete(f"{api}/catalogs/{cid}", timeout=60)


# --- ITEM 2 residual: PATCH /catalogs/{id} must evict the (Redis) cache -----
def test_patch_catalog_evicts_cache_immediately(client, api):
    marker = f"TEST_ONE_P_{uuid.uuid4().hex[:6]}"
    body = _import(client, api, marker)
    cid = body["catalog_id"]
    try:
        warm = client.get(f"{api}/catalog/active", timeout=60).json()
        assert warm["catalog"]["id"] == cid
        new_name = marker + "_RENAMED"
        r = client.patch(f"{api}/catalogs/{cid}",
                         json={"client_code": "TESTPATCH", "name": new_name}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        after = client.get(f"{api}/catalog/active", timeout=60).json()
        assert after["catalog"]["client_code"] == "TESTPATCH", (
            f"STALE CACHE after PATCH: client_code={after['catalog']['client_code']}")
        assert after["catalog"]["name"] == new_name, (
            f"STALE CACHE after PATCH: name={after['catalog']['name']}")
    finally:
        client.delete(f"{api}/catalogs/{cid}", timeout=60)


# --- ITEM 1e: the invariant is TENANT-SCOPED (no cross-tenant deactivation) --
def test_single_active_invariant_is_tenant_scoped(client, api, demo_catalog):
    """Activating a catalog in tenant B must NOT deactivate tenant A's catalog."""
    import requests as rq
    # ensure tenant A (qa@) has exactly one active catalog
    ver = sorted(demo_catalog["versions"], key=lambda v: v["version_number"])[-1]["id"]
    client.post(f"{api}/catalogs/{demo_catalog['id']}/activate/{ver}", timeout=60)
    a_active_before = _active_ids(client, api)
    assert a_active_before == [demo_catalog["id"]]

    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_tenant_{suffix}@example.com"
    s = rq.post(f"{api}/auth/signup", json={
        "email": email, "password": "Test1234!", "name": "TEST Tenant",
        "company": f"TEST_CO_{suffix}"}, timeout=60)
    assert s.status_code == 200, s.text[:300]
    other = rq.Session()
    other.headers.update({"Authorization": f"Bearer {s.json()['token']}"})
    marker = f"TEST_ONE_T_{suffix}"
    b = _import(other, api, marker)
    try:
        # tenant B has exactly one active catalog (its own new one)
        assert _active_ids(other, api) == [b["catalog_id"]]
        # tenant A untouched
        assert _active_ids(client, api) == a_active_before, (
            "CROSS-TENANT LEAK: activating a catalog in tenant B deactivated tenant A's catalog")
        assert client.get(f"{api}/catalog/active", timeout=60).json()["catalog"]["id"] == demo_catalog["id"]
        # and tenant B cannot see tenant A's catalog
        assert b["catalog_id"] not in _catalogs(client, api)
    finally:
        for cid in list(_catalogs(other, api)):
            other.delete(f"{api}/catalogs/{cid}", timeout=60)
        from conftest import psql
        psql(f"DELETE FROM audit_logs WHERE tenant_id IN (SELECT id FROM tenants WHERE name='TEST_CO_{suffix}');")
        psql(f"DELETE FROM tenant_users WHERE user_id IN (SELECT id FROM users WHERE email='{email.lower()}');")
        psql(f"DELETE FROM users WHERE email='{email.lower()}';")
        psql(f"DELETE FROM tenants WHERE name='TEST_CO_{suffix}';")
