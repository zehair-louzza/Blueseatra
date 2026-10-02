"""Suggestions de mots pendant la frappe (suggestions_mots.py) — tests unitaires."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catalogue_chiffrage
import suggestions_mots
import vocabulaire_btp
from catalogue_commun import TENANT_COMMUN


TENANT = "11111111-1111-4111-8111-111111111111"


class _Resultat:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return self._lignes


class _Session:
    def __init__(self, lignes):
        self._lignes = lignes
        self.executees = []

    async def execute(self, sql, params=None):
        self.executees.append(params)
        return _Resultat(self._lignes)


class _Ctx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *a):
        return False


def _patch(monkeypatch, lignes, visibles=None):
    async def faux_sources_recherche(t):
        return (["v1", "v2"], {"v1": {"cle": "v1"}, "v2": {"cle": "v2"}})

    async def faux_visibles(t):
        return visibles if visibles is not None else ["v1", "v2"]

    monkeypatch.setattr(suggestions_mots, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(catalogue_chiffrage, "_sources_recherche", faux_sources_recherche)
    monkeypatch.setattr(catalogue_chiffrage, "sources_visibles", faux_visibles)
    catalogue_chiffrage.invalider_sources()
    catalogue_chiffrage._cache_visibles.clear()

    sessions = []

    def session():
        s = _Ctx(_Session(lignes))
        sessions.append(s.session)
        return s

    monkeypatch.setattr(suggestions_mots, "tenant_session", session)
    return sessions


def test_decoupe_debut_et_prefixe():
    assert suggestions_mots.decoupe("disj") == ("", "disj")           # un seul mot : rien avant
    assert suggestions_mots.decoupe("disjoncteur 16a cou") == ("disjoncteur 16a", "cou")
    assert suggestions_mots.decoupe("cable ") == ("cable", "")          # espace : mot complet
    assert suggestions_mots.decoupe("Disj 2,5") == ("disj", "2.5")        # debut = avant le dernier mot
    assert suggestions_mots.decoupe("") == ("", "")


def test_suggestions_triees_par_frequence_avec_comptes(monkeypatch):
    sessions = _patch(monkeypatch, [("disjoncteur", 221), ("disj", 9), ("disjonct", 3)])
    r = asyncio.run(suggestions_mots.suggerer("disj"))
    assert r["prefixe"] == "disj"
    mots = [s["mot"] for s in r["suggestions"]]
    assert mots[:3] == ["disjoncteur", "disj", "disjonct"]              # par frequence decroissante
    assert r["suggestions"][0]["nb_offres"] == 221
    # Tenants et sources passes a la fonction SQL : entreprise + commun, sources actives.
    p = sessions[0].executees[0]
    assert p["tenants"] == [TENANT, TENANT_COMMUN]
    assert p["sources"] == ["v1", "v2"]
    assert p["prefixe"] == "disj"


def test_catalogue_interne_compte_par_article(monkeypatch):
    _patch(monkeypatch, [("disjoncteur", 2)])
    r = asyncio.run(suggestions_mots.suggerer(
        "disj", designations_internes=["Disjoncteur interne A", "disjoncteur interne B", "prise"]))
    d = {s["mot"]: s["nb_offres"] for s in r["suggestions"]}
    assert d["disjoncteur"] == 4                                        # 2 fournisseurs + 2 internes
    assert "disjoncteurmaison" not in d


def test_portee_comparateur_prend_toutes_les_sources_visibles(monkeypatch):
    sessions = _patch(monkeypatch, [("prise", 12)], visibles=["v1", "v2", "v9"])
    r = asyncio.run(suggestions_mots.suggerer("pri", portee="comparateur"))
    assert sessions[0].executees[0]["sources"] == ["v1", "v2", "v9"]


def test_synonymes_du_vocabulaire(monkeypatch):
    _patch(monkeypatch, [("tetrapolaire", 5)])
    r = asyncio.run(suggestions_mots.suggerer("tetra"))
    s = {x["mot"]: x for x in r["suggestions"]}
    assert "tetrapolaire" in s
    assert "4P" in (s["tetrapolaire"]["synonymes"] or [])              # synonymes affiches tels quels


def test_termes_du_metier_proposes_sans_compte(monkeypatch):
    _patch(monkeypatch, [])                                             # rien cote fournisseurs
    r = asyncio.run(suggestions_mots.suggerer("ph"))
    mots = {s["mot"] for s in r["suggestions"]}
    assert "ph+n" in mots                                               # vocabulaire_btp.LIBELLES
    sans_compte = [s for s in r["suggestions"] if s["nb_offres"] is None]
    assert sans_compte and all(s["synonymes"] is None or isinstance(s["synonymes"], list)
                               for s in sans_compte)


def test_prefixe_invalide_aucune_suggestion(monkeypatch):
    sessions = _patch(monkeypatch, [("disjoncteur", 2)])
    for q in ("d", "a" * 41, "cable ", ""):                           # apres normalisation
        r = asyncio.run(suggestions_mots.suggerer(q))
        assert r["suggestions"] == [], q
    assert sessions == []                                              # la base n'a pas ete appelee


def test_erreur_fournisseurs_n_empeche_pas_les_suggestions_internes(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(suggestions_mots, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(suggestions_mots, "_mots_fournisseurs", boom)
    r = asyncio.run(suggestions_mots.suggerer("disj", designations_internes=["disjoncteur interne"]))
    assert [s["mot"] for s in r["suggestions"]] == ["disjoncteur"]


def test_sans_tenant_aucun_appel_fournisseur(monkeypatch):
    sessions = _patch(monkeypatch, [("disjoncteur", 2)])
    import suggestions_mots as sm
    vrai = sm.get_current_tenant
    monkeypatch.setattr(sm, "get_current_tenant", lambda: None)
    r = asyncio.run(sm.suggerer("disj"))
    monkeypatch.setattr(sm, "get_current_tenant", vrai)
    assert sessions == []
    assert r["suggestions"] == []