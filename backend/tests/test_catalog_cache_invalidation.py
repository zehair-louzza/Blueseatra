"""Iteration 7 - VERIFY FIX: _CATALOG_CACHE invalidation on catalog mutations.

Covers server.py _evict_catalog_cache() calls in import_catalog, activate_version,
deactivate_catalog and delete_catalog. Every assertion is IMMEDIATE (no sleep) so
any remaining 45s stale window fails the test.

Uses the shared `client` / `api` / `seeded_request` fixtures from conftest.py.
"""
import io
import uuid

import pytest

PAINT = "Peinture murale deux couches"  # label present in the demo catalog


def _csv(marker, price="99.99"):
    return (f"Famille,Article,Unit\u00e9,TVA_%,Prix_vente_HT\n"
            f"TEST,{marker},u,20,{price}\n").encode()


def _import(client, api, marker, price="99.99", activate="true", extra_rows=b""):
    payload = _csv(marker, price) + extra_rows
    r = client.post(f"{api}/catalogs/import",
                    files={"file": ("c.csv", io.BytesIO(payload), "text/csv")},
                    data={"catalog_name": marker, "activate": activate}, timeout=120)
    assert r.status_code == 200, f"import failed {r.status_code}: {r.text[:300]}"
    return r.json()


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


# --- FIX 1: import + activate is immediately visible -------------------------
def test_import_activate_evicts_cache_immediately(client, api):
    warm = client.get(f"{api}/catalog/active", timeout=60).json()
    assert warm["catalog"] is not None, "no active catalog to warm the cache with"
    old_name = warm["catalog"]["name"]

    marker = f"TEST_CACHE_{uuid.uuid4().hex[:6]}"
    body = _import(client, api, marker)
    assert body["success_rows"] == 1 and body["activated"] is True
    cid = body["catalog_id"]
    try:
        active = client.get(f"{api}/catalog/active", timeout=60).json()
        assert active["catalog"]["name"] == marker, (
            f"STALE CACHE: /catalog/active still returns {active['catalog']['name']} "
            f"(old={old_name}) instead of {marker}")
        assert active["catalog"]["id"] == cid
        assert marker in [i["item_label"] for i in active["items"]]

        srch = client.get(f"{api}/catalog/search", params={"q": marker}, timeout=60).json()
        assert len(srch["items"]) >= 1, "STALE CACHE: /catalog/search found 0 hits for the new item"
        assert srch["items"][0]["item_label"] == marker
        assert float(srch["items"][0]["unit_price_ht"]) == 99.99
    finally:
        client.delete(f"{api}/catalogs/{cid}", timeout=60)


# --- FIX 2: activate/{ver} switching version is immediately visible ----------
def test_activate_version_switch_immediate(client, api):
    marker = f"TEST_CACHE_{uuid.uuid4().hex[:6]}"
    v1 = _import(client, api, marker, price="10.00")
    cid = v1["catalog_id"]
    try:
        v2 = _import(client, api, marker, price="20.00")
        assert v2["catalog_id"] == cid, "same catalog_name should reuse the catalog"
        assert v2["version_number"] == v1["version_number"] + 1
        a2 = client.get(f"{api}/catalog/active", timeout=60).json()
        assert float(a2["items"][0]["unit_price_ht"]) == 20.00

        r = client.post(f"{api}/catalogs/{cid}/activate/{v1['version_id']}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        a1 = client.get(f"{api}/catalog/active", timeout=60).json()
        assert a1["catalog"]["active_version_id"] == v1["version_id"]
        assert float(a1["items"][0]["unit_price_ht"]) == 10.00, (
            "STALE CACHE: activate/{ver} did not invalidate the cache")
    finally:
        client.delete(f"{api}/catalogs/{cid}", timeout=60)


# --- FIX 3: deactivate is reflected immediately ------------------------------
def test_deactivate_immediate(client, api):
    marker = f"TEST_CACHE_{uuid.uuid4().hex[:6]}"
    body = _import(client, api, marker)
    cid = body["catalog_id"]
    try:
        assert client.get(f"{api}/catalog/active", timeout=60).json()["catalog"]["id"] == cid
        r = client.post(f"{api}/catalogs/{cid}/deactivate", timeout=60)
        assert r.status_code == 200, r.text[:300]
        after = client.get(f"{api}/catalog/active", timeout=60).json()
        # the deactivated catalog must no longer be served (another catalog may
        # legitimately take over as active)
        assert after["catalog"] is None or after["catalog"]["id"] != cid, (
            "STALE CACHE: deactivated catalog still served by /catalog/active")
        assert marker not in [i["item_label"] for i in after["items"]]
        srch = client.get(f"{api}/catalog/search", params={"q": marker}, timeout=60).json()
        assert srch["items"] == [], "STALE CACHE: search still returns deactivated catalog items"
    finally:
        client.delete(f"{api}/catalogs/{cid}", timeout=60)


# --- FIX 3b: deactivating the ONLY active catalog -> none immediately --------
def test_deactivate_last_active_returns_none(client, api, demo_catalog):
    """Deactivate every active catalog, then /catalog/active must be None at once."""
    cats = client.get(f"{api}/catalogs", timeout=60).json()
    touched = [c["id"] for c in cats if c.get("active_version_id")]
    for cid in touched:
        assert client.post(f"{api}/catalogs/{cid}/deactivate", timeout=60).status_code == 200
    after = client.get(f"{api}/catalog/active", timeout=60).json()
    assert after["catalog"] is None, (
        f"STALE CACHE: still serving {after['catalog']} after deactivating all catalogs")
    assert after["items"] == []
    srch = client.get(f"{api}/catalog/search", params={"q": "Peinture"}, timeout=60).json()
    assert srch["items"] == [], "STALE CACHE: search returns items with no active catalog"


# --- FIX 4: delete of the active catalog -> gone immediately -----------------
def test_delete_active_catalog_immediate(client, api):
    marker = f"TEST_CACHE_{uuid.uuid4().hex[:6]}"
    body = _import(client, api, marker)
    cid = body["catalog_id"]
    assert client.get(f"{api}/catalog/active", timeout=60).json()["catalog"]["id"] == cid

    r = client.delete(f"{api}/catalogs/{cid}", timeout=60)
    assert r.status_code == 200, r.text[:300]

    active = client.get(f"{api}/catalog/active", timeout=60).json()
    if active["catalog"] is not None:
        assert active["catalog"]["id"] != cid, "STALE CACHE: deleted catalog still served"
        assert marker not in [i["item_label"] for i in active["items"]]
    srch = client.get(f"{api}/catalog/search", params={"q": marker}, timeout=60).json()
    assert srch["items"] == [], "STALE CACHE: search still returns items of the deleted catalog"


# --- FIX 5: quote drafted right after an import uses the FRESH prices -------
def test_quote_draft_uses_fresh_prices_immediately(client, api, seeded_request):
    """Import a catalog re-pricing '<PAINT>' at 777.77 then draft IMMEDIATELY."""
    marker = f"TEST_CACHE_{uuid.uuid4().hex[:6]}"
    extra = f"TEST,{PAINT},m2,20,777.77\n".encode()
    body = _import(client, api, marker, extra_rows=extra)
    assert body["success_rows"] == 2
    cid = body["catalog_id"]
    qid = None
    try:
        r = client.post(f"{api}/quotes/draft", json={"request_id": seeded_request}, timeout=180)
        assert r.status_code == 200, f"draft failed {r.status_code}: {r.text[:300]}"
        q = r.json()
        qid = q["id"]
        assert q["pricing_snapshot"]["catalog_id"] == cid, (
            f"STALE CACHE: quote priced with catalog {q['pricing_snapshot']['catalog_id']} "
            f"instead of the just-imported {cid}")
        paint = next((l for l in q["lines"] if l.get("matched_label") == PAINT), None)
        assert paint is not None, [l.get("matched_label") for l in q["lines"]]
        assert float(paint["unit_price_ht"]) == 777.77, (
            f"STALE CACHE: line priced {paint['unit_price_ht']} instead of the new 777.77")
    finally:
        if qid:
            client.delete(f"{api}/quotes/{qid}", timeout=60)
        client.delete(f"{api}/catalogs/{cid}", timeout=60)
