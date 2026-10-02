"""Suggestions de mots pendant la frappe (suggestions_mots.py) — tests unitaires.

Composition de mots (02/10/2026) : « porte c » propose le groupe
« porte coupe feu » ; « porte » + espace propose les groupes qui continuent.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catalogue_chiffrage
import suggestions_mots
from catalogue_commun import TENANT_COMMUN


TENANT = "11111111-1111-4111-8111-111111111111"


class _Resultat:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return self._lignes


class _Session:
    """Renvoie les lignes selon le prefixe demande : simule la fonction SQL."""

    def __init__(self, table):
        self.table = table
        self.executees = []

    async def execute(self, sql, params=None):
        self.executees.append(params)
        pref = (params or {}).get("prefixe")
        return _Resultat(self.table.get(pref, []))


class _Ctx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *a):
        return False


def _patch(monkeypatch, table, visibles=None):
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
        s = _Ctx(_Session(table))
        sessions.append(s.session)
        return s

    monkeypatch.setattr(suggestions_mots, "tenant_session", session)
    return sessions


TABLE = {
    "disj": [("disjoncteur", 221), ("disj", 9), ("disjonct", 3), ("porte coupe", 4)],
    "porte c": [("porte coupe feu", 9)],
    "porte ": [("porte coupe feu", 9), ("porte interieure", 2)],
    "c": [],
}


def test_decoupe_debut_et_prefixe():
    assert suggestions_mots.decoupe("disjoncteur 16a cou") == ("disjoncteur 16a", "cou")
    assert suggestions_mots.decoupe("cable ") == ("cable", "")


def test_mot_partiel_mots_isoles_tries(monkeypatch):
    sessions = _patch(monkeypatch, TABLE)
    r = asyncio.run(suggestions_mots.suggerer("disj"))
    mots = [s["mot"] for s in r["suggestions"]]
    assert mots[:3] == ["disjoncteur", "disj", "disjonct"]          # par frequence decroissante
    assert r["suggestions"][0]["nb_offres"] == 221
    assert all(s["remplace"] == 1 for s in r["suggestions"])        # mots isoles
    # « porte coupe » (groupe) revient par l'appel isoles : filtre, on ne
    # garde que les mots isoles pour le prefixe partiel.
    assert "porte coupe" not in mots
    p = sessions[0].executees[0]
    assert p["tenants"] == [TENANT, TENANT_COMMUN]
    assert p["prefixe"] == "disj"


def test_deux_mots_propose_le_groupe(monkeypatch):
    sessions = _patch(monkeypatch, TABLE)
    r = asyncio.run(suggestions_mots.suggerer("porte c"))
    assert [s["mot"] for s in r["suggestions"]] == ["porte coupe feu"]
    assert r["suggestions"][0]["remplace"] == 3                       # remplace 3 mots tapes
    assert r["suggestions"][0]["nb_offres"] == 9
    assert [p["prefixe"] for s in sessions for p in s.executees] == ["porte c"]


def test_mot_complet_propose_les_groupes_qui_continuent(monkeypatch):
    sessions = _patch(monkeypatch, TABLE)
    r = asyncio.run(suggestions_mots.suggerer("porte "))
    assert [s["mot"] for s in r["suggestions"]] == ["porte coupe feu", "porte interieure"]
    assert [p["prefixe"] for s in sessions for p in s.executees] == ["porte "]


def test_catalogue_interne_complete_les_mots_isoles(monkeypatch):
    _patch(monkeypatch, TABLE)
    r = asyncio.run(suggestions_mots.suggerer(
        "disj", designations_internes=["Disjoncteur interne A", "disjoncteur interne B", "prise"]))
    d = {s["mot"]: s["nb_offres"] for s in r["suggestions"]}
    assert d["disjoncteur"] == 223                                   # 221 + 2 internes


def test_portee_comparateur_prend_toutes_les_sources_visibles(monkeypatch):
    sessions = _patch(monkeypatch, TABLE, visibles=["v1", "v2", "v9"])
    asyncio.run(suggestions_mots.suggerer("disj", portee="comparateur"))
    assert sessions[0].executees[0]["sources"] == ["v1", "v2", "v9"]


def test_synonymes_du_vocabulaire(monkeypatch):
    _patch(monkeypatch, {"tetra": [("tetrapolaire", 5)]})
    r = asyncio.run(suggestions_mots.suggerer("tetra"))
    s = {x["mot"]: x for x in r["suggestions"]}
    assert "tetrapolaire" in s
    assert "4P" in (s["tetrapolaire"]["synonymes"] or [])


def test_termes_du_metier_proposes_sans_compte(monkeypatch):
    _patch(monkeypatch, {"ph": []})
    r = asyncio.run(suggestions_mots.suggerer("ph"))
    mots = {s["mot"] for s in r["suggestions"]}
    assert "ph+n" in mots


def test_prefixe_trop_court_aucune_suggestion(monkeypatch):
    sessions = _patch(monkeypatch, TABLE)
    for q in ("d", "a" * 41, ""):
        r = asyncio.run(suggestions_mots.suggerer(q))
        assert r["suggestions"] == [], q
    assert sessions == []                                            # la base n'a pas ete appelee


def test_erreur_fournisseurs_n_empeche_pas_les_suggestions_internes(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(suggestions_mots, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(suggestions_mots, "_mots_fournisseurs", boom)
    r = asyncio.run(suggestions_mots.suggerer("disj", designations_internes=["disjoncteur interne"]))
    assert [s["mot"] for s in r["suggestions"]] == ["disjoncteur"]


def test_sans_tenant_aucun_appel_fournisseur(monkeypatch):
    sessions = _patch(monkeypatch, TABLE)
    monkeypatch.setattr(suggestions_mots, "get_current_tenant", lambda: None)
    r = asyncio.run(suggestions_mots.suggerer("disj"))
    assert sessions == []
    assert r["suggestions"] == []
