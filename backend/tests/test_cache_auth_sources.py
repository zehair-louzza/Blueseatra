"""Caches courts de get_current et des sources de chiffrage (02/10/2026)."""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt  # noqa: E402

import server  # noqa: E402
import catalogue_chiffrage as cc  # noqa: E402

TENANT_A = "11111111-1111-4111-8111-111111111111"
TENANT_B = "22222222-2222-4222-8222-222222222222"


class _Col:
    def __init__(self, lignes, appels, nom):
        self.lignes, self.appels, self.nom = lignes, appels, nom

    async def find_one(self, flt, projection=None):
        self.appels.append(self.nom)
        return next((l for l in self.lignes if all(l.get(k) == v for k, v in flt.items())), None)


class _Db:
    def __init__(self, users, tus):
        self.appels = []
        self.users = _Col(users, self.appels, "users")
        self.tenant_users = _Col(tus, self.appels, "tenant_users")


class _Creds:
    def __init__(self, t):
        self.credentials = t


def _jeton(user, tenant):
    return _Creds(jwt.encode({"user_id": user, "tenant_id": tenant}, server.JWT_SECRET, algorithm=server.JWT_ALGO))


@pytest.fixture
def base(monkeypatch):
    db = _Db([{"id": "u1", "email": "a@exemple.fr", "name": "A"}],
             [{"tenant_id": TENANT_A, "user_id": "u1", "role": "admin"}])
    monkeypatch.setattr(server, "db", db)
    server.invalider_auth()
    yield db
    server.invalider_auth()


def _courant(creds):
    return asyncio.run(server.get_current(creds))


def test_deuxieme_requete_sans_lecture_en_base(base):
    cu = _courant(_jeton("u1", TENANT_A))
    assert cu.role == "admin" and base.appels == ["users", "tenant_users"]
    cu2 = _courant(_jeton("u1", TENANT_A))
    assert cu2.role == "admin" and cu2.tenant_id == TENANT_A
    assert base.appels == ["users", "tenant_users"]          # aucune relecture


def test_refus_jamais_mis_en_cache(base):
    from fastapi import HTTPException
    for _ in range(2):
        with pytest.raises(HTTPException) as e:
            _courant(_jeton("u1", TENANT_B))
        assert e.value.status_code == 403
    assert base.appels.count("tenant_users") == 2


def test_jeton_invalide_toujours_refuse(base):
    from fastapi import HTTPException
    _courant(_jeton("u1", TENANT_A))
    with pytest.raises(HTTPException) as e:
        asyncio.run(server.get_current(_Creds("pas-un-jwt")))
    assert e.value.status_code == 401


def test_invalidation_apres_retrait_du_membre(base):
    from fastapi import HTTPException
    _courant(_jeton("u1", TENANT_A))
    base.tenant_users.lignes.clear()                 # membre retiré
    server.invalider_auth(user_id="u1", tenant_id=TENANT_A)
    with pytest.raises(HTTPException) as e:
        _courant(_jeton("u1", TENANT_A))
    assert e.value.status_code == 403


def test_changement_de_role_pris_en_compte(base):
    _courant(_jeton("u1", TENANT_A))
    base.tenant_users.lignes[0]["role"] = "viewer"
    server.invalider_auth(user_id="u1")
    assert _courant(_jeton("u1", TENANT_A)).role == "viewer"


def test_expiration(base, monkeypatch):
    _courant(_jeton("u1", TENANT_A))
    t = server.time.monotonic()
    monkeypatch.setattr(server.time, "monotonic", lambda: t + server._AUTH_TTL_S + 1)
    _courant(_jeton("u1", TENANT_A))
    assert base.appels.count("users") == 2


def test_le_tenant_courant_est_publie_meme_depuis_le_cache(base):
    """tenant_session() lit ce contexte : il doit etre pose aussi sur un succes en cache."""
    from database import get_current_tenant, set_current_tenant

    async def scenario():
        await server.get_current(_jeton("u1", TENANT_A))      # remplit le cache
        set_current_tenant(None)
        await server.get_current(_jeton("u1", TENANT_A))      # servi par le cache
        return get_current_tenant()
    assert asyncio.run(scenario()) == TENANT_A
    assert base.appels == ["users", "tenant_users"]


# --- sources de chiffrage ------------------------------------------------------

def test_sources_en_cache_et_invalidation(monkeypatch):
    appels = []

    async def etats(tenant):
        appels.append(("etats", tenant))
        return {"v1": True, "v2": False, "v3": True}

    async def fournisseurs():
        appels.append(("fournisseurs",))
        return {"fournisseurs": [{"cle": "v1", "catalogue_commun": True}, {"cle": "v2"}]}

    monkeypatch.setattr(cc, "_etats_tenant", etats)
    monkeypatch.setattr(cc.catalogue_navigation, "fournisseurs", fournisseurs)
    cc.invalider_sources()
    cles, vis = asyncio.run(cc._sources_recherche(TENANT_A))
    assert cles == ["v1"] and set(vis) == {"v1", "v2"}       # v3 actif mais plus visible
    asyncio.run(cc._sources_recherche(TENANT_A))
    assert len(appels) == 2                                   # 2e appel : cache
    asyncio.run(cc._sources_recherche(TENANT_B))
    assert len(appels) == 4                                   # autre entreprise : relu
    cc.invalider_sources(TENANT_A)
    asyncio.run(cc._sources_recherche(TENANT_A))
    assert len(appels) == 6
    cc.invalider_sources()


def test_masquage_du_catalogue_commun_vide_le_cache(monkeypatch):
    import catalogue_commun
    cc._cache_sources["x"] = (10**12, ["v1"], {})
    catalogue_commun._invalider_sources(None)
    assert cc._cache_sources == {}
