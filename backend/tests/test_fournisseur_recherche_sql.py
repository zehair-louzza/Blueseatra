"""Comparateur de prix : appel de blueseatra.offres_candidates.

Tests sans base : on verifie le CONTRAT envoye a PostgreSQL (tenants,
termes, chemin choisi). Le comportement SQL lui-meme (isolation, injection,
exactitude) est teste sur base jetable dans
tests_security/test_offres_candidates_sql.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catalogue_commun  # noqa: E402
import fournisseur_recherche as fr  # noqa: E402

TENANT = "11111111-1111-4111-8111-111111111111"


class _Res:
    def __init__(self, lignes):
        self.lignes = lignes

    def mappings(self):
        return self

    def all(self):
        return self.lignes

    def __iter__(self):
        return iter(self.lignes)


class _Session:
    def __init__(self, candidats):
        self.candidats = candidats
        self.executed = []

    async def execute(self, sql, params=None):
        self.executed.append((str(sql), params))
        if len(self.executed) == 1:
            return _Res(self.candidats)
        if len(self.executed) == 2:   # noms des fournisseurs
            return _Res([{"tenant_id": catalogue_commun.TENANT_COMMUN, "id": "s1", "name": "Rexel"}])
        return _Res([])                 # fiches


class _Ctx:
    def __init__(self, s):
        self.s = s

    async def __aenter__(self):
        return self.s

    async def __aexit__(self, *a):
        return False


def _lancer(monkeypatch, requete, masque=False, famille=None):
    session = _Session([{"id": "o1", "tenant_id": catalogue_commun.TENANT_COMMUN,
                         "supplier_id": "s1", "price_ht": 6.83,
                         "recherche_norm": "disjoncteur 16a courbe c"}])
    monkeypatch.setattr(fr, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(fr, "tenant_session", lambda: _Ctx(session))

    async def est_masque(_s, _t):
        return masque
    monkeypatch.setattr(catalogue_commun, "est_masque", est_masque)
    return asyncio.run(fr.recherche(requete, famille=famille)), session


def test_comparateur_passe_par_la_fonction_avec_tenant_courant_et_commun(monkeypatch):
    resultat, session = _lancer(monkeypatch, "disjoncteur 16a courbe c")
    sql, params = session.executed[0]
    assert "blueseatra.offres_candidates(" in sql
    assert "ORDER BY c.price_ht ASC NULLS LAST, c.id" in sql
    assert params["tenants"] == [TENANT, catalogue_commun.TENANT_COMMUN]
    assert params["versions_actives"] is True and params["tri_prix"] is True
    assert params["limite"] == fr.PLAFOND_LIGNES
    assert params["version"] is None and params["hist"] is None
    assert params["famille"] is None
    assert "CAST(:famille AS text)" in sql
    termes = json.loads(params["termes"])
    assert termes[0] == [{"op": "like", "v": "%disjoncteur%"}]
    assert "\\b" not in params["termes"]          # limite de mot PostgreSQL : \y
    assert isinstance(resultat, dict)


def test_catalogue_commun_masque_seul_le_tenant(monkeypatch):
    _, session = _lancer(monkeypatch, "prise", masque=True)
    assert session.executed[0][1]["tenants"] == [TENANT]


def test_termes_identiques_a_conditions():
    """termes_recherche() et _conditions() doivent porter les memes motifs."""
    for q in ["disjoncteur 16a courbe c ph+n", "interrupteur differentiel 2p 40a",
              "dalle LED 600x600", "cable rigide 3g2.5", "tube alu"]:
        _, params, _ = fr._conditions(q)
        a_plat = [alt["v"] for terme in fr.termes_recherche(q) for alt in terme]
        assert sorted(a_plat) == sorted(params.values()), q


def test_motif_postgres():
    assert fr.motif_postgres(r"\bph\+n\b") == r"\yph\+n\y"
    assert fr.motif_postgres(r"(?<![2-9])1?p\+n") == r"(?<![2-9])1?p\+n"


# --- Recherche dans un catalogue (catalogue_navigation.produits) -------------

import catalogue_navigation as nav  # noqa: E402

VERSION = "22222222-2222-4222-8222-222222222222"


class _SessionPage:
    def __init__(self, page_json, fiches):
        self.page_json, self.fiches, self.executed = page_json, fiches, []

    async def execute(self, sql, params=None):
        self.executed.append((str(sql), params))
        if "catalogue_page(" in str(sql):
            return _Scalaire(self.page_json)
        return _Res(self.fiches)


class _Scalaire:
    def __init__(self, v):
        self.v = v

    def scalar(self):
        return self.v


def _produits(monkeypatch, cle, page_json, fiches, **kw):
    session = _SessionPage(page_json, fiches)
    monkeypatch.setattr(nav, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(nav, "tenant_session", lambda: _Ctx(session))

    async def resoudre(_s, tenant, c):
        p = {"tenant_id": tenant, "commun": catalogue_commun.TENANT_COMMUN, "avec_commun": True}
        if c.startswith("hist:"):
            return "o.tenant_id = :tenant_id", p
        p.update(vt=catalogue_commun.TENANT_COMMUN, version=c)
        return "o.tenant_id = :vt AND o.version_id = :version", p
    monkeypatch.setattr(nav, "_resoudre", resoudre)
    return asyncio.run(nav.produits(cle, **kw)), session


def _fiche(i, prix):
    return {"id": i, "fournisseur": "Rexel", "designation": i, "prix_net_ht": prix,
            "prix_public_ht": None, "date_prix": None}


def test_catalogue_recherche_passe_par_la_fonction(monkeypatch):
    page = json.dumps({"ids": ["o2", "o1", "o3"], "total": 1001})
    # Fiches renvoyees dans le desordre : l'ordre de la fonction fait foi.
    res, session = _produits(monkeypatch, VERSION, page,
                             [_fiche("o1", 2.0), _fiche("o3", 3.0), _fiche("o2", 1.0)],
                             q="disjoncteur 16a courbe c", famille="Distribution", page=3, taille=2)
    sql, params = session.executed[0]
    assert "blueseatra.catalogue_page(" in sql
    assert params["t"] == catalogue_commun.TENANT_COMMUN and params["v"] == VERSION
    assert params["h"] is None and params["famille"] == "Distribution"
    assert params["limite"] == 3 and params["decalage"] == 4
    assert params["plafond"] == nav.PLAFOND_COMPTE_RECHERCHE + 1
    assert "\\b" not in params["termes"]
    sql2, params2 = session.executed[1]
    assert "o.id = ANY(:ids)" in sql2 and "(o.tenant_id = :tenant_id OR o.tenant_id = :commun)" in sql2
    assert params2["ids"] == ["o2", "o1", "o3"] and params2["tenant_id"] == TENANT
    assert [l["id"] for l in res["produits"]] == ["o2", "o1"]
    assert res["page_suivante"] is True
    assert res["total"] == 1001 and res["total_plafonne"] is True


def test_catalogue_recherche_historique_et_vide(monkeypatch):
    res, session = _produits(monkeypatch, "hist:frn-1", json.dumps({"ids": [], "total": 0}), [],
                             q="prise")
    params = session.executed[0][1]
    assert params["t"] == TENANT and params["v"] is None and params["h"] == "frn-1"
    assert params["famille"] is None
    assert len(session.executed) == 1          # aucune relecture de fiches
    assert res["produits"] == [] and res["total"] == 0 and res["page_suivante"] is False


def test_catalogue_sans_mot_inchange(monkeypatch):
    res, session = _produits(monkeypatch, VERSION, None, [_fiche("o1", 1.0)])
    assert len(session.executed) == 1
    assert "catalogue_page(" not in session.executed[0][0]
    assert "ORDER BY o.raw_label, o.id" in session.executed[0][0]
    assert res["total"] is None


def test_comparateur_famille_plafond_reduit(monkeypatch):
    res, session = _lancer(monkeypatch, "led", famille="  Eclairage ")
    params = session.executed[0][1]
    assert params["famille"] == "Eclairage"
    assert params["limite"] == fr.PLAFOND_LIGNES_FAMILLE
    assert res["famille"] == "Eclairage" and res["plafond"] == fr.PLAFOND_LIGNES_FAMILLE
    _, session = _lancer(monkeypatch, "led", famille="   ")
    assert session.executed[0][1]["famille"] is None
    assert session.executed[0][1]["limite"] == fr.PLAFOND_LIGNES


def test_familles_visibles_agrege_les_catalogues(monkeypatch):
    async def fournisseurs():
        return {"fournisseurs": [{"cle": "v1", "fournisseur": "Rexel"},
                                 {"cle": "hist:x", "fournisseur": "Prolians"},
                                 {"cle": "v2", "fournisseur": "Rexel"}]}
    donnees = {"v1": [{"famille": "Eclairage", "nb": 10}, {"famille": "Cables", "nb": 4}],
               "hist:x": [{"famille": "Eclairage", "nb": 3}],
               "v2": [{"famille": "Cables", "nb": 20}]}

    async def familles(cle):
        return {"cle": cle, "familles": donnees[cle]}
    monkeypatch.setattr(nav, "fournisseurs", fournisseurs)
    monkeypatch.setattr(nav, "familles", familles)
    res = asyncio.run(nav.familles_visibles())
    assert res["familles"] == [
        {"famille": "Cables", "nb": 24, "fournisseurs": ["Rexel"]},
        {"famille": "Eclairage", "nb": 13, "fournisseurs": ["Rexel", "Prolians"]},
    ]
