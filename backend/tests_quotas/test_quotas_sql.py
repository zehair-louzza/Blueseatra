"""Tests d'intégration des compteurs et quotas (migration 20260925090000).

Exécutés seulement si TEST_PG_DSN pointe vers une base JETABLE contenant le
schéma `blueseatra`, la fonction `current_tenant()` et le rôle
`blueseatra_app`. Ne JAMAIS pointer TEST_PG_DSN vers Supabase.

    TEST_PG_DSN='postgresql://postgres@/qt?host=/tmp&port=55432' pytest backend/tests_quotas -q
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

DSN = os.environ.get("TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_PG_DSN non défini")

MIGRATION = (Path(__file__).resolve().parents[2]
             / "supabase/migrations/20260925090000_compteurs_quotas.sql")


def _cx(autocommit=True):
    c = psycopg2.connect(DSN, client_encoding="utf8")
    c.autocommit = autocommit
    return c


@pytest.fixture(scope="module", autouse=True)
def migration():
    assert "supabase.co" not in DSN and "pooler" not in DSN, "base jetable uniquement"
    with _cx() as c, c.cursor() as cur:
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        cur.execute(MIGRATION.read_text(encoding="utf-8"))   # idempotente
    yield


class App:
    """Connexion sous blueseatra_app avec app.tenant_id, comme le backend."""

    def __init__(self, tenant):
        self.tenant = tenant
        self.c = _cx(autocommit=False)

    def q(self, sql, params=()):
        with self.c.cursor() as cur:
            cur.execute("SET LOCAL ROLE blueseatra_app")
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (self.tenant,))
            cur.execute(sql, params)
            rows = cur.fetchall() if cur.description else None
        self.c.commit()
        return rows

    def reserver(self, demande, devis=1, pages=0, bloquer=True):
        r = self.q("SELECT blueseatra.quota_reserver(%s,%s,%s,%s,%s,%s)",
                   (self.tenant, demande, devis, pages, "test@x", bloquer))[0][0]
        return r if isinstance(r, dict) else json.loads(r)

    def soldes(self):
        rows = self.q("""
            SELECT unite, reserve, sum(quantite) FROM blueseatra.registre_consommation
            WHERE tenant_id = %s GROUP BY unite, reserve""", (self.tenant,))
        return {(u, r): int(s) for u, r, s in rows}

    def close(self):
        self.c.close()


def _nouveau(offre="decouverte", statut="essai", essai_fin="now() + interval '14 days'"):
    t = str(uuid.uuid4())
    with _cx() as c, c.cursor() as cur:
        cur.execute(f"""INSERT INTO blueseatra.abonnements (tenant_id, offre_code, statut, essai_fin_le)
                        VALUES (%s, %s, %s, {essai_fin})""", (t, offre, statut))
    return t


def _admin(sql, params=()):
    with _cx() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else None


def test_essai_cree_au_premier_usage_et_dotation_unique():
    t = str(uuid.uuid4())
    a = App(t)
    assert a.reserver("d1")["autorise"]
    assert a.reserver("d2")["autorise"]
    ab = a.q("SELECT offre_code, statut FROM blueseatra.abonnements WHERE tenant_id=%s", (t,))
    assert ab == [("decouverte", "essai")]
    dot = a.q("""SELECT unite, quantite FROM blueseatra.registre_consommation
                 WHERE tenant_id=%s AND nature='dotation' ORDER BY unite""", (t,))
    assert dot == [("devis_ia", 10), ("page_lue", 30)]
    assert a.soldes()[("devis_ia", "forfait")] == 8
    a.close()


def test_meme_demande_jamais_comptee_deux_fois():
    t = _nouveau()
    a = App(t)
    a.reserver("d1", pages=3)
    r = a.reserver("d1", pages=3)
    assert r.get("deja_compte") is True
    s = a.soldes()
    assert s[("devis_ia", "forfait")] == 9 and s[("page_lue", "forfait")] == 27
    a.close()


def test_quota_atteint_refuse_sans_rien_ecrire():
    t = _nouveau()
    a = App(t)
    for i in range(10):
        assert a.reserver(f"d{i}")["autorise"]
    avant = a.q("SELECT count(*) FROM blueseatra.registre_consommation WHERE tenant_id=%s", (t,))
    r = a.reserver("d10")
    assert r == {"autorise": False, "motif": "quota_atteint_devis_ia", "offre": "decouverte"}
    apres = a.q("SELECT count(*) FROM blueseatra.registre_consommation WHERE tenant_id=%s", (t,))
    assert avant == apres
    a.close()


def test_pages_insuffisantes_refusent_toute_la_demande():
    t = _nouveau()
    a = App(t)
    r = a.reserver("gros-scan", pages=31)
    assert r["autorise"] is False and r["motif"] == "quota_atteint_page_lue"
    assert a.soldes()[("devis_ia", "forfait")] == 10   # le devis n'a pas été compté
    a.close()


def test_mode_observation_compte_sans_bloquer():
    t = _nouveau()
    a = App(t)
    for i in range(12):
        r = a.reserver(f"d{i}", bloquer=False)
        assert r["autorise"]
    assert r["depassement"] is True
    assert a.soldes()[("devis_ia", "forfait")] == -2
    a.close()


def test_recharge_consommee_apres_le_forfait():
    t = _nouveau()
    _admin("SELECT blueseatra.quota_crediter_recharge(%s,'devis_ia',25,'plateforme','pack 25')", (t,))
    a = App(t)
    for i in range(12):
        assert a.reserver(f"d{i}")["autorise"]
    s = a.soldes()
    assert s[("devis_ia", "forfait")] == 0 and s[("devis_ia", "recharge")] == 23
    a.close()


def test_scan_partage_entre_forfait_et_recharge():
    t = _nouveau()
    _admin("SELECT blueseatra.quota_crediter_recharge(%s,'page_lue',500,'plateforme','pack 500')", (t,))
    a = App(t)
    a.reserver("d1", pages=28)
    a.reserver("d2", pages=5)       # 2 sur le forfait, 3 sur la recharge
    lignes = a.q("""SELECT reserve, quantite FROM blueseatra.registre_consommation
                    WHERE tenant_id=%s AND demande_id='d2' AND unite='page_lue' ORDER BY reserve""", (t,))
    assert lignes == [("forfait", -2), ("recharge", -3)]
    a.close()


def test_annulation_rend_les_unites_et_permet_un_nouvel_essai():
    t = _nouveau()
    a = App(t)
    a.reserver("d1", pages=4)
    assert a.q("SELECT blueseatra.quota_annuler(%s,'d1','extraction échouée')", (t,))[0][0] == 2
    assert a.q("SELECT blueseatra.quota_annuler(%s,'d1','bis')", (t,))[0][0] == 0   # idempotent
    s = a.soldes()
    assert s[("devis_ia", "forfait")] == 10 and s[("page_lue", "forfait")] == 30
    r = a.reserver("d1", pages=4)                # retraitement après échec : recompté
    assert r["autorise"] and not r.get("deja_compte")
    assert a.soldes()[("devis_ia", "forfait")] == 9
    a.close()


def test_registre_en_ajout_seul():
    t = _nouveau()
    a = App(t)
    a.reserver("d1")
    a.close()
    for sql in ("UPDATE blueseatra.registre_consommation SET quantite = 1 WHERE tenant_id = %s",
                "DELETE FROM blueseatra.registre_consommation WHERE tenant_id = %s"):
        with pytest.raises(psycopg2.Error):
            _admin(sql, (t,))                   # même le propriétaire est refusé
    with pytest.raises(psycopg2.Error):
        _admin("TRUNCATE blueseatra.registre_consommation")


def test_solde_reproductible_en_rejouant_le_registre():
    t = _nouveau()
    _admin("SELECT blueseatra.quota_crediter_recharge(%s,'devis_ia',25,'plateforme','pack')", (t,))
    a = App(t)
    for i in range(14):
        a.reserver(f"d{i}", pages=i % 3)
    a.q("SELECT blueseatra.quota_annuler(%s,'d3','échec')", (t,))
    rejoue = {}
    for u, r, q in a.q("""SELECT unite, reserve, quantite FROM blueseatra.registre_consommation
                          WHERE tenant_id=%s ORDER BY id""", (t,)):
        rejoue[(u, r)] = rejoue.get((u, r), 0) + q
    assert rejoue == a.soldes()
    assert rejoue[("devis_ia", "forfait")] + rejoue[("devis_ia", "recharge")] == 10 + 25 - 13
    a.close()


def test_isolation_entre_entreprises():
    ta, tb = _nouveau(), _nouveau()
    a, b = App(ta), App(tb)
    a.reserver("secret-a")
    assert b.q("SELECT count(*) FROM blueseatra.registre_consommation")[0][0] == 0
    assert b.q("SELECT count(*) FROM blueseatra.abonnements")[0][0] == 1
    with pytest.raises(psycopg2.Error):
        b.q("SELECT blueseatra.quota_reserver(%s,'x',1,0,'pirate',true)", (ta,))
    b.c.rollback()
    with pytest.raises(psycopg2.Error):
        b.q("SELECT blueseatra.quota_annuler(%s,'secret-a','pirate')", (ta,))
    b.c.rollback()
    a.close(), b.close()


def test_application_ne_peut_ni_recharger_ni_changer_d_offre():
    t = _nouveau()
    a = App(t)
    with pytest.raises(psycopg2.Error):
        a.q("SELECT blueseatra.quota_crediter_recharge(%s,'devis_ia',1000,'moi','gratuit')", (t,))
    a.c.rollback()
    with pytest.raises(psycopg2.Error):
        a.q("UPDATE blueseatra.abonnements SET offre_code='performance' WHERE tenant_id=%s", (t,))
    a.c.rollback()
    with pytest.raises(psycopg2.Error):
        a.q("""INSERT INTO blueseatra.registre_consommation (tenant_id, unite, quantite, nature, reserve)
               VALUES (%s, 'devis_ia', 1000, 'recharge', 'recharge')""", (str(uuid.uuid4()),))
    a.c.rollback()
    a.close()


def test_essai_termine_et_lecture_seule():
    t = _nouveau(essai_fin="now() - interval '1 day'")
    a = App(t)
    assert a.reserver("d1") == {"autorise": False, "motif": "essai_termine", "offre": "decouverte"}
    a.close()
    t2 = _nouveau(offre="pilotage", statut="lecture_seule", essai_fin="NULL")
    b = App(t2)
    assert b.reserver("d1")["motif"] == "lecture_seule"
    b.close()


def test_offres_illimitees_et_payantes():
    t = _nouveau(offre="interne", statut="actif", essai_fin="NULL")
    a = App(t)
    for i in range(30):
        assert a.reserver(f"d{i}", pages=50)["autorise"]
    assert a.q("""SELECT count(*) FROM blueseatra.registre_consommation
                  WHERE tenant_id=%s AND nature='dotation'""", (t,))[0][0] == 0
    a.close()
    t2 = _nouveau(offre="pilotage", statut="actif", essai_fin="NULL")
    b = App(t2)
    b.reserver("d1")
    assert b.soldes()[("devis_ia", "forfait")] == 249
    b.close()


def test_periode_mensuelle_glissante():
    t = _nouveau(offre="initial", statut="actif", essai_fin="NULL")
    _admin("UPDATE blueseatra.abonnements SET periode_debut = now() - interval '40 days' WHERE tenant_id=%s", (t,))
    a = App(t)
    a.reserver("d1")
    per = a.q("""SELECT DISTINCT periode_debut > now() - interval '31 days'
                 FROM blueseatra.registre_consommation WHERE tenant_id=%s""", (t,))
    assert per == [(True,)]                     # dotation du 2e mois, pas du 1er
    a.close()


def test_reservations_concurrentes_ne_depassent_jamais_le_quota():
    t = _nouveau()
    resultats = []
    verrou = threading.Lock()

    def tache(i):
        a = App(t)
        r = a.reserver(f"c{i}")
        with verrou:
            resultats.append(r["autorise"])
        a.close()

    fils = [threading.Thread(target=tache, args=(i,)) for i in range(25)]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert resultats.count(True) == 10 and resultats.count(False) == 15
    a = App(t)
    assert a.soldes()[("devis_ia", "forfait")] == 0
    a.close()
