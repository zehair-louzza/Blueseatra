"""Tests de blueseatra.vocabulaire_recalculer / vocabulaire_suggestions
(migration 20261002040000_vocabulaire_recherche).

Les deux fonctions sont SECURITY DEFINER : elles lisent sans la RLS. On
verifie sur une base JETABLE, sous le role blueseatra_app, qu'une entreprise
ne voit jamais les mots d'une autre, que les prefixes saisis ne peuvent pas
modifier la requete, et que les comptes sont justes.

    TEST_PG_DSN='postgresql://postgres@/ci?host=/tmp&port=55432' \\
        pytest backend/tests_security/test_vocabulaire_sql.py -q
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

DSN = os.environ.get("TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_PG_DSN non défini")

RACINE = Path(__file__).resolve().parents[2]
MIGRATION = RACINE / "supabase/migrations/20261002040000_vocabulaire_recherche.sql"

COMMUN = "00000000-0000-4000-8000-000000000c0d"
A = "aaaaaaaa-0000-4000-8000-00000000000a"
B = "bbbbbbbb-0000-4000-8000-00000000000b"

AMORCE = f"""
CREATE SCHEMA IF NOT EXISTS blueseatra;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app') THEN
    CREATE ROLE blueseatra_app NOLOGIN;
  END IF;
END $$;
GRANT USAGE ON SCHEMA blueseatra TO blueseatra_app;
CREATE OR REPLACE FUNCTION blueseatra.current_tenant() RETURNS text
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.tenant_id', true), '') $$;
CREATE OR REPLACE FUNCTION blueseatra.tenant_catalogue_commun() RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT '{COMMUN}'::text $$;
GRANT EXECUTE ON FUNCTION blueseatra.current_tenant(), blueseatra.tenant_catalogue_commun()
  TO blueseatra_app;

DROP TABLE IF EXISTS blueseatra.vocabulaire_recherche;
DROP TABLE IF EXISTS blueseatra.supplier_offers, blueseatra.catalogs;
CREATE TABLE blueseatra.catalogs (
    id varchar PRIMARY KEY, tenant_id varchar NOT NULL, active_version_id varchar);
CREATE TABLE blueseatra.supplier_offers (
    id varchar PRIMARY KEY, tenant_id varchar NOT NULL, supplier_id varchar,
    catalog_id varchar, version_id varchar, is_active boolean NOT NULL DEFAULT true,
    price_ht double precision, recherche_norm text);
CREATE INDEX idx_test_tv ON blueseatra.supplier_offers (tenant_id, version_id);
"""

OFFRES = [
    ("c1", COMMUN, "rexel", "cat-c", "ver-c", "disjoncteur 16a courbe c ph+n"),
    ("c2", COMMUN, "rexel", "cat-c", "ver-c", "disjoncteur 20a courbe c disjoncteur"),
    ("c3", COMMUN, "rexel", "cat-c", "ver-c", "interrupteur differentiel 40a 30ma"),
    ("c4", COMMUN, "rexel", "cat-c", "ver-c", "prise 2p+t 16a 3664385 a9f74216"),
    ("p1", COMMUN, "prolians", "cat-p", "ver-p", "disjoncteur 2a courbe d"),
    ("a1", A, "maison", "cat-a", "ver-a", "disjoncteurmaison interne"),
    ("a2", A, "histo", None, None, "disjonctionhisto ancien"),
    ("b1", B, "concurrent", "cat-b", "ver-b", "disjoncteursecret confidentiel"),
]


def _cx():
    c = psycopg2.connect(DSN, client_encoding="utf8")
    c.autocommit = True
    return c


@pytest.fixture(scope="module", autouse=True)
def base():
    assert "supabase.co" not in DSN and "pooler" not in DSN, "base jetable uniquement"
    with _cx() as c, c.cursor() as cur:
        cur.execute(AMORCE)
        cur.executemany("INSERT INTO blueseatra.catalogs VALUES (%s,%s,%s)",
                        [("cat-c", COMMUN, "ver-c"), ("cat-p", COMMUN, "ver-p"),
                         ("cat-a", A, "ver-a"), ("cat-b", B, "ver-b")])
        cur.executemany("INSERT INTO blueseatra.supplier_offers "
                        "(id, tenant_id, supplier_id, catalog_id, version_id, recherche_norm) "
                        "VALUES (%s,%s,%s,%s,%s,%s)", OFFRES)
        sql = MIGRATION.read_text(encoding="utf-8")
        cur.execute(sql)
        cur.execute(sql)                                   # idempotente
        for t, s in [(COMMUN, "ver-c"), (COMMUN, "ver-p"), (A, "ver-a"),
                     (A, "hist:histo"), (B, "ver-b")]:
            cur.execute("SELECT blueseatra.vocabulaire_recalculer(%s, %s)", (t, s))
    yield


def _app(tenant, sql, params=()):
    with _cx() as c, c.cursor() as cur:
        cur.execute("SET ROLE blueseatra_app")
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant,))
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else None


def _sugg(tenant, tenants, sources, prefixe, limite=8):
    return _app(tenant, "SELECT mot, nb_offres FROM blueseatra.vocabulaire_suggestions(%s, %s, %s, %s)",
                (tenants, sources, prefixe, limite))


SOURCES_A = ["ver-c", "ver-p", "ver-a", "hist:histo", "ver-b"]


def test_comptes_par_offre_et_tri_par_frequence():
    lignes = _sugg(A, [A, COMMUN], SOURCES_A, "disj")
    d = dict(lignes)
    # « disjoncteur » apparait 2 fois dans c2 : compte UNE offre.
    assert d["disjoncteur"] == 3
    assert lignes[0][0] == "disjoncteur"                  # le plus frequent d'abord
    assert "disjoncteurmaison" in d and "disjonctionhisto" in d


def test_jamais_les_mots_d_une_autre_entreprise():
    mots = {m for m, _ in _sugg(A, [A, COMMUN], SOURCES_A, "disj")}
    assert "disjoncteursecret" not in mots
    assert _sugg(A, [B], SOURCES_A, "disj") == []
    assert _sugg(A, [A, B], SOURCES_A, "disj") == []
    assert _sugg(A, [A, COMMUN, B], SOURCES_A, "disj") == []


def test_sans_tenant_courant_rien():
    with _cx() as c, c.cursor() as cur:
        cur.execute("SET ROLE blueseatra_app")
        cur.execute("SELECT count(*) FROM blueseatra.vocabulaire_suggestions(%s, %s, 'disj', 8)",
                    ([COMMUN], SOURCES_A))
        # Le catalogue commun reste lisible ; l'entreprise A, non.
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM blueseatra.vocabulaire_suggestions(%s, %s, 'disj', 8)",
                    ([A], SOURCES_A))
        assert cur.fetchone()[0] == 0


def test_filtre_par_sources():
    mots = dict(_sugg(A, [A, COMMUN], ["ver-p"], "disj"))
    assert mots == {"disjoncteur": 1}


@pytest.mark.parametrize("prefixe", ["d", "", "DISJ", "di%", "dis_", "disj' OR 1=1 --", "x" * 41, None])
def test_prefixes_refuses(prefixe):
    assert _sugg(A, [A, COMMUN], SOURCES_A, prefixe) == []


def test_mots_sans_lettre_exclus():
    mots = {m for m, _ in _sugg(A, [A, COMMUN], SOURCES_A, "36")}
    assert mots == set()                                  # 3664385 : que des chiffres
    assert "16a" in {m for m, _ in _sugg(A, [A, COMMUN], SOURCES_A, "16")}


def test_limite_bornee():
    assert len(_sugg(A, [A, COMMUN], SOURCES_A, "di", 500)) <= 20


def test_ecriture_directe_refusee():
    with pytest.raises(psycopg2.Error):
        _app(A, "INSERT INTO blueseatra.vocabulaire_recherche VALUES (%s, 'x', 'y', 1)", (A,))


def test_recalcul_pour_un_autre_tenant_refuse():
    with pytest.raises(psycopg2.Error):
        _app(A, "SELECT blueseatra.vocabulaire_recalculer(%s, 'ver-b')", (B,))


def test_recalcul_sans_tenant_refuse_au_role_applicatif():
    with _cx() as c, c.cursor() as cur:
        cur.execute("SET ROLE blueseatra_app")
        with pytest.raises(psycopg2.Error):
            cur.execute("SELECT blueseatra.vocabulaire_recalculer(%s, 'ver-c')", (COMMUN,))


def test_recalcul_idempotent():
    with _cx() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM blueseatra.vocabulaire_recherche")
        avant = cur.fetchone()[0]
        cur.execute("SELECT blueseatra.vocabulaire_recalculer(%s, 'ver-c')", (COMMUN,))
        cur.execute("SELECT count(*) FROM blueseatra.vocabulaire_recherche")
        assert cur.fetchone()[0] == avant


def test_lecture_directe_sous_rls():
    assert _app(A, "SELECT count(*) FROM blueseatra.vocabulaire_recherche WHERE tenant_id = %s", (B,)) == [(0,)]
    assert _app(A, "SELECT count(*) FROM blueseatra.vocabulaire_recherche WHERE tenant_id = %s", (A,))[0][0] > 0
