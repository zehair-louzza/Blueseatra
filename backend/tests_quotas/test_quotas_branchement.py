"""Branchement des compteurs dans server.py (sans base : tout est simulé).

Vérifie ce qui est compté pour chaque type de demande, que le refus est une
402 explicite sans rien enregistrer, et qu'un échec d'extraction rend les
unités.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "x" * 64)
if "APP_ENCRYPTION_KEY" not in os.environ:
    from cryptography.fernet import Fernet
    os.environ["APP_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

server = pytest.importorskip("server")
from fastapi.testclient import TestClient  # noqa: E402

import quotas  # noqa: E402


class _Col:
    def __init__(self, store, name):
        self.store, self.name = store, name

    async def insert_one(self, doc):
        self.store.setdefault(self.name, []).append(doc)

    async def update_one(self, flt, upd, **kw):
        for d in self.store.get(self.name, []):
            if all(d.get(k) == v for k, v in flt.items()):
                d.update(upd.get("$set", {}))

    async def find_one(self, flt, *a, **kw):
        for d in self.store.get(self.name, []):
            if all(d.get(k) == v for k, v in flt.items()):
                return dict(d)
        return None

    async def count_documents(self, flt=None):
        return len(self.store.get(self.name, []))


class _DB:
    def __init__(self):
        self.store = {}

    def __getattr__(self, name):
        return _Col(self.store, name)


@pytest.fixture
def env(monkeypatch):
    fake = _DB()
    monkeypatch.setattr(server, "db", fake)
    appels = {"reserver": [], "annuler": []}

    async def reserver(demande, devis, pages, acteur):
        appels["reserver"].append((demande, devis, pages))
        if appels.get("refuser"):
            raise quotas.QuotaAtteint(appels["refuser"])
        return {"autorise": True}

    async def annuler(demande, motif):
        appels["annuler"].append((demande, motif))
        return 1

    monkeypatch.setattr(quotas, "reserver", reserver)
    monkeypatch.setattr(quotas, "annuler", annuler)
    monkeypatch.setattr(server, "_redis_sync", lambda: None)

    class _Q:
        async def put(self, item):
            appels.setdefault("file", []).append(item)

    monkeypatch.setattr(server, "_extraction_queue", _Q())
    cu = server.CurrentUser(user_id="u1", email="a@x.fr", name="A", tenant_id="t1", role="owner")
    server.app.dependency_overrides[server.get_current] = lambda: cu
    yield fake, appels, TestClient(server.app)
    server.app.dependency_overrides.clear()


def test_texte_colle_compte_un_devis_et_aucune_page(env):
    fake, appels, c = env
    r = c.post("/api/requests", data={"title": "T", "text": "Remplacer 3 prises"})
    assert r.status_code == 200
    assert appels["reserver"] == [(r.json()["id"], 1, 0)]


def test_photo_compte_une_page(env):
    fake, appels, c = env
    r = c.post("/api/requests", data={"title": "Photo"},
               files={"file": ("chantier.jpg", b"\xff\xd8\xff" + b"0" * 50, "image/jpeg")})
    assert r.status_code == 200
    assert appels["reserver"][0][1:] == (1, 1)


def test_scan_compte_ses_pages(env, monkeypatch):
    fake, appels, c = env
    monkeypatch.setattr(server.ai_service, "extract_pdf_text", lambda b: "")
    monkeypatch.setattr(server.ai_service, "pdf_needs_vision_fallback", lambda t: True)
    monkeypatch.setattr(server.ai_service, "render_pdf_pages_to_images", lambda b: [b"p1", b"p2", b"p3"])
    r = c.post("/api/requests", data={"title": "Scan"},
               files={"file": ("scan.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert r.status_code == 200
    assert appels["reserver"][0][1:] == (1, 3)


def test_pdf_avec_texte_ne_compte_aucune_page(env, monkeypatch):
    fake, appels, c = env
    monkeypatch.setattr(server.ai_service, "extract_pdf_text", lambda b: "Devis pour 12 luminaires LED")
    monkeypatch.setattr(server.ai_service, "pdf_needs_vision_fallback", lambda t: False)
    r = c.post("/api/requests", data={"title": "PDF"},
               files={"file": ("devis.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert r.status_code == 200
    assert appels["reserver"][0][1:] == (1, 0)


def test_quota_atteint_renvoie_402_et_n_enregistre_rien(env):
    fake, appels, c = env
    appels["refuser"] = "quota_atteint_devis_ia"
    r = c.post("/api/requests", data={"title": "T", "text": "Remplacer 3 prises"})
    assert r.status_code == 402
    assert r.json()["motif"] == "quota_atteint_devis_ia"
    assert "recharge" in r.json()["detail"]
    assert not fake.store.get("requests")


def test_membre_refuse_au_dela_des_sieges(env, monkeypatch):
    fake, appels, c = env

    async def siege(n):
        raise quotas.QuotaAtteint("sieges")

    monkeypatch.setattr(quotas, "verifier_siege", siege)
    r = c.post("/api/members", json={"email": "b@x.fr", "name": "B", "password": "secret12"})
    assert r.status_code == 402 and r.json()["motif"] == "sieges"


def test_echec_d_extraction_rend_les_unites(env, monkeypatch):
    fake, appels, c = env

    async def settings(tid):
        return {}

    async def boom(*a, **kw):
        raise RuntimeError("modèle indisponible")

    monkeypatch.setattr(server, "get_tenant_ai_settings", settings)
    monkeypatch.setattr(server.ai_service, "extract_from_text", boom)
    fake.store["requests"] = [{"id": "r1", "tenant_id": "t1", "raw_text": "abc", "source_type": "text"}]
    asyncio.new_event_loop().run_until_complete(server.process_request("r1", "t1"))
    assert fake.store["requests"][0]["status"] == "failed"
    assert appels["annuler"] and appels["annuler"][0][0] == "r1"
