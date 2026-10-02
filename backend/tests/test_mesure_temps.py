"""En-tête Server-Timing : compteurs SQL et connexions par requête (mesure_temps.py)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

import mesure_temps as mt  # noqa: E402


def _moteur():
    m = create_engine("sqlite://")
    mt.brancher(m)
    mt.brancher(m)                      # idempotent : pas de double comptage
    return m


def test_compte_requetes_connexions_et_emprunts():
    moteur = _moteur()
    m, jeton = mt.demarrer()
    try:
        with moteur.connect() as c:
            c.execute(text("select 1"))
            c.execute(text("select 2"))
        with moteur.connect() as c:
            c.execute(text("select 3"))
    finally:
        mt.terminer(jeton)
    assert m.n_sql == 3 and m.ms_sql >= 0
    assert m.n_emprunts == 2
    assert m.n_connexions >= 1


def test_hors_requete_rien_n_est_compte():
    moteur = _moteur()
    with moteur.connect() as c:
        c.execute(text("select 1"))
    assert mt.courante() is None


def test_requetes_isolees_entre_mesures():
    moteur = _moteur()
    a, ja = mt.demarrer()
    with moteur.connect() as c:
        c.execute(text("select 1"))
    mt.terminer(ja)
    b, jb = mt.demarrer()
    mt.terminer(jb)
    assert a.n_sql == 1 and b.n_sql == 0


def test_entete():
    m = mt.Mesure()
    m.n_sql, m.ms_sql, m.n_connexions, m.n_emprunts = 5, 120.44, 1, 5
    e = mt.entete(m, 916.21)
    assert e.startswith("app;dur=916.2, sql;dur=120.4;desc=\"5 requetes\"")
    assert "1 nouvelles / 5 emprunts" in e


def test_intergiciel_pose_l_entete():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import observabilite

    app = FastAPI()
    moteur = _moteur()

    @app.get("/api/essai")
    def essai():
        with moteur.connect() as c:
            c.execute(text("select 1"))
        return {"ok": True}

    app.middleware("http")(observabilite.intergiciel)
    r = TestClient(app).get("/api/essai")
    assert r.status_code == 200
    st = r.headers["server-timing"]
    assert st.startswith("app;dur=") and "1 requetes" in st and "1 emprunts" in st
    assert r.headers["x-request-id"]
