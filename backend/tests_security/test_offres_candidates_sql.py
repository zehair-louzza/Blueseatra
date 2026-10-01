"""Tests de blueseatra.offres_candidates et blueseatra.catalogue_page
(migrations 20261001180000 et 20261001190000).

La fonction est SECURITY DEFINER : elle lit supplier_offers SANS la RLS.
Ces tests verifient donc, sur une base JETABLE avec de vraies politiques
RLS et le role blueseatra_app, qu'elle ne renvoie jamais les offres d'une
autre entreprise, qu'aucun texte saisi ne peut modifier sa requete, et que
ses deux chemins (index trigramme, index par prix) donnent exactement les
memes lignes que la requete de reference.

Executes seulement si TEST_PG_DSN pointe vers une base JETABLE. Ne JAMAIS
pointer TEST_PG_DSN vers Supabase.

    TEST_PG_DSN='postgresql://postgres@/ci?host=/tmp&port=55432' \\
        pytest backend/tests_security/test_offres_candidates_sql.py -q
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

DSN = os.environ.get("TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_PG_DSN non défini")

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = [RACINE / "supabase/migrations/20261001180000_recherche_offres_sous_rls.sql",
              RACINE / "supabase/migrations/20261001190000_recherche_dans_catalogue.sql"]

COMMUN = "00000000-0000-4000-8000-000000000c0d"
A = "aaaaaaaa-0000-4000-8000-00000000000a"   # entreprise testee
B = "bbbbbbbb-0000-4000-8000-00000000000b"   # autre entreprise

# Schema minimal, fidele a la production pour les colonnes et politiques
# utilisees par la fonction (RLS activee, non forcee, proprietaire postgres).
AMORCE = f"""
CREATE EXTENSION IF NOT EXISTS pg_trgm;
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

DROP TABLE IF EXISTS blueseatra.supplier_offers, blueseatra.catalogs;
CREATE TABLE blueseatra.catalogs (
    id varchar PRIMARY KEY, tenant_id varchar NOT NULL, active_version_id varchar);
CREATE TABLE blueseatra.supplier_offers (
    id varchar PRIMARY KEY, tenant_id varchar NOT NULL, supplier_id varchar,
    catalog_id varchar, version_id varchar, is_active boolean NOT NULL DEFAULT true,
    price_ht double precision, recherche_norm text, raw_row jsonb);
CREATE INDEX idx_test_trgm ON blueseatra.supplier_offers
    USING gin (recherche_norm gin_trgm_ops);
CREATE INDEX idx_test_prix ON blueseatra.supplier_offers
    (tenant_id, price_ht, id) INCLUDE (recherche_norm, version_id, catalog_id, is_active);
ALTER TABLE blueseatra.supplier_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE blueseatra.catalogs ENABLE ROW LEVEL SECURITY;
CREATE POLICY supplier_offers_all ON blueseatra.supplier_offers TO blueseatra_app
    USING (tenant_id = blueseatra.current_tenant());
CREATE POLICY lecture_catalogue_commun ON blueseatra.supplier_offers FOR SELECT TO blueseatra_app
    USING (tenant_id = blueseatra.tenant_catalogue_commun());
CREATE POLICY catalogs_all ON blueseatra.catalogs TO blueseatra_app
    USING (tenant_id = blueseatra.current_tenant());
CREATE POLICY lecture_catalogue_commun ON blueseatra.catalogs FOR SELECT TO blueseatra_app
    USING (tenant_id = blueseatra.tenant_catalogue_commun());
GRANT SELECT ON blueseatra.supplier_offers, blueseatra.catalogs TO blueseatra_app;
"""


def _famille(offre):
    """Une prise sur dix en Eclairage, le reste en Appareillage."""
    i = offre[0]
    if i.startswith("c-prise-") and int(i.rsplit("-", 1)[1]) % 10 == 0:
        return "Eclairage"
    return "Distribution" if "dj" in i else "Appareillage"


def _cx():
    c = psycopg2.connect(DSN, client_encoding="utf8")
    c.autocommit = True
    return c


def _offres():
    """Jeu de donnees : 4 000 prises chez le commun (chemin 'index par prix'),
    quelques disjoncteurs, une ancienne version inactive, et des offres
    d'une autre entreprise B qui ne doivent JAMAIS sortir pour A."""
    lignes = []
    for i in range(4000):
        lignes.append((f"c-prise-{i}", COMMUN, "rexel", "cat-c", "ver-c2", True,
                       float(1 + (i * 7) % 997) / 10, f"prise 2p+t {i} blanc"))
    lignes += [
        ("c-dj-1", COMMUN, "rexel", "cat-c", "ver-c2", True, 6.83, "disjoncteur 16a courbe c ph+n"),
        ("c-dj-2", COMMUN, "rexel", "cat-c", "ver-c2", True, 8.10, "disjoncteur 16a cbe c 1p+n"),
        ("c-dj-3", COMMUN, "rexel", "cat-c", "ver-c2", True, 9.00, "disjoncteur 16a courbe d"),
        # Ancienne version (non active) : invisible pour le comparateur.
        ("c-old-1", COMMUN, "rexel", "cat-c", "ver-c1", True, 0.01, "prise ancienne version"),
        # Offre desactivee : invisible partout.
        ("c-off-1", COMMUN, "rexel", "cat-c", "ver-c2", False, 0.02, "prise desactivee"),
        ("a-prise-1", A, "maison", None, None, True, 0.50, "prise interne a"),
        ("a-hist-1", A, "histo", None, None, True, 3.00, "prise historique a"),
        ("b-prise-1", B, "concurrent", "cat-b", "ver-b1", True, 0.03, "prise secrete b"),
        ("b-prise-2", B, "concurrent", None, None, True, 0.04, "prise secrete b2"),
    ]
    return lignes


@pytest.fixture(scope="module", autouse=True)
def base():
    assert "supabase.co" not in DSN and "pooler" not in DSN, "base jetable uniquement"
    with _cx() as c, c.cursor() as cur:
        cur.execute(AMORCE)
        cur.executemany("INSERT INTO blueseatra.catalogs VALUES (%s,%s,%s)",
                        [("cat-c", COMMUN, "ver-c2"), ("cat-b", B, "ver-b1")])
        cur.executemany("INSERT INTO blueseatra.supplier_offers VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        [(*o, json.dumps({"famille": _famille(o)})) for o in _offres()])
        cur.execute("ANALYZE blueseatra.supplier_offers")
        for migration in MIGRATIONS:
            sql = migration.read_text(encoding="utf-8")
            cur.execute(sql)
            cur.execute(sql)   # idempotente
    yield


def _app(tenant, sql, params=()):
    """Sous blueseatra_app avec app.tenant_id, comme le backend."""
    c = psycopg2.connect(DSN, client_encoding="utf8")
    try:
        with c.cursor() as cur:
            cur.execute("SET LOCAL ROLE blueseatra_app")
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        c.rollback()
        c.close()


def _candidats(tenant, tenants, termes, limite=200, version=None, hist=None,
               actives=False, tri=False):
    return _app(tenant, """
        SELECT id, tenant_id, price_ht FROM blueseatra.offres_candidates(
            %s::text[], %s::jsonb, %s, %s, %s, %s, %s)""",
        (tenants, json.dumps(termes), limite, version, hist, actives, tri))


def _like(*mots):
    return [[{"op": "like", "v": f"%{m}%"}] for m in mots]


# --- Cloisonnement ---------------------------------------------------------

def test_jamais_les_offres_d_une_autre_entreprise():
    ids = {r[0] for r in _candidats(A, [A, COMMUN], _like("prise"), 5000)}
    assert ids and not any(i.startswith("b-") for i in ids)


def test_tenant_etranger_demande_explicitement_rien():
    assert _candidats(A, [B], _like("prise")) == []
    assert _candidats(A, [A, B], _like("prise")) == []
    assert _candidats(A, [COMMUN, B], _like("prise")) == []


def test_sans_tenant_courant_seul_le_commun_et_rien_d_autre():
    # Sans app.tenant_id, current_tenant() est NULL : A est refuse.
    assert _candidats("", [A], _like("prise")) == []
    assert _candidats("", [A, COMMUN], _like("prise")) == []


def test_parametres_invalides_rien():
    assert _candidats(A, [], _like("prise")) == []
    assert _candidats(A, [A, COMMUN, COMMUN], _like("prise")) == []
    assert _candidats(A, [COMMUN], []) == []
    assert _candidats(A, [COMMUN], [[{"op": "sql", "v": "1=1"}]]) == []
    assert _candidats(A, [COMMUN], [[{"op": "like", "v": ""}]]) == []
    assert _candidats(A, [COMMUN], [[{"op": "like"}]]) == []


def test_injection_sans_effet():
    for v in ["%' OR 1=1 --%", "%'); DROP TABLE blueseatra.catalogs; --%",
              "%\\'%", "%$fonction$%"]:
        assert _candidats(A, [COMMUN], [[{"op": "like", "v": v}]]) == []
    assert _app(A, "SELECT count(*) FROM blueseatra.catalogs")[0][0] == 1  # commun visible, table intacte


def test_droit_execute_reserve_a_blueseatra_app():
    with _cx() as c, c.cursor() as cur:
        cur.execute("""
            SELECT p.prosecdef, p.proconfig, has_function_privilege('public',
                   p.oid, 'EXECUTE')
              FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'blueseatra' AND p.proname = 'offres_candidates'""")
        secdef, config, public = cur.fetchone()
    assert secdef is True
    assert config == ["search_path=\"\""] or config == ['search_path=""']
    assert public is False
    with _cx() as c, c.cursor() as cur:
        cur.execute("""
            SELECT p.proname, p.prosecdef, has_function_privilege('public', p.oid, 'EXECUTE'),
                   has_function_privilege('blueseatra_app', p.oid, 'EXECUTE')
              FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'blueseatra'
               AND p.proname IN ('catalogue_page', 'recherche_conditions')""")
        droits = {r[0]: r[1:] for r in cur.fetchall()}
    assert droits["catalogue_page"] == (True, False, True)
    # Fonction interne : ni SECURITY DEFINER, ni appelable par l'application.
    assert droits["recherche_conditions"] == (False, False, False)


# --- Exactitude ------------------------------------------------------------

REFERENCE = """
    SELECT o.id FROM blueseatra.supplier_offers o
     WHERE o.tenant_id = ANY (%s) AND o.is_active
       AND (o.catalog_id IS NULL
            OR o.version_id IN (SELECT c.active_version_id FROM blueseatra.catalogs c
                                 WHERE c.tenant_id = ANY (%s) AND c.active_version_id IS NOT NULL)
            OR o.catalog_id NOT IN (SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = ANY (%s)))
       AND {cond}
     ORDER BY o.price_ht ASC NULLS LAST, o.id LIMIT %s
"""


def _reference(tenants, cond, params, limite):
    with _cx() as c, c.cursor() as cur:   # postgres, hors RLS : la verite
        cur.execute(REFERENCE.format(cond=cond), (tenants, tenants, tenants, *params, limite))
        return [r[0] for r in cur.fetchall()]


@pytest.mark.parametrize("limite", [50, 3500])
def test_comparateur_terme_courant_index_par_prix(limite):
    # 4 000 correspondances > seuil 3 000 : chemin "index par prix".
    obtenus = [r[0] for r in _candidats(A, [A, COMMUN], _like("prise"), limite,
                                        actives=True, tri=True)]
    attendus = _reference([A, COMMUN], "o.recherche_norm LIKE %s", ["%prise%"], limite)
    assert obtenus == attendus
    assert "c-old-1" not in obtenus and "c-off-1" not in obtenus


def test_comparateur_terme_rare_trigramme():
    obtenus = [r[0] for r in _candidats(A, [A, COMMUN], _like("disjoncteur", "16a"), 5000,
                                        actives=True, tri=True)]
    assert obtenus == ["c-dj-1", "c-dj-2", "c-dj-3"]


def test_selecteur_par_version_et_par_historique():
    v = {r[0] for r in _candidats(A, [COMMUN], _like("prise"), 10000, version="ver-c1")}
    assert v == {"c-old-1"}
    h = {r[0] for r in _candidats(A, [A], _like("prise"), 200, hist="histo")}
    assert h == {"a-hist-1"}


# --- Expressions regulieres du vocabulaire ---------------------------------

def test_limite_de_mot_traduite_pour_postgresql():
    """\\b vaut RETOUR ARRIERE en PostgreSQL : "courbe c" ne trouvait rien.

    Motifs ecrits en dur (ce job n'installe que pytest et psycopg2) ; la
    traduction elle-meme (motif_postgres) est testee dans
    tests/test_fournisseur_recherche_sql.py.
    """
    def termes(limite_de_mot):
        motif = rf"{limite_de_mot}(?:courbe|cbe|crb) ?c{limite_de_mot}"
        return _like("disjoncteur", "16a") + [[{"op": "regex", "v": motif}]]

    avant = _candidats(A, [A, COMMUN], termes("\\b"), 5000, actives=True, tri=True)
    assert avant == []                          # le bug, documente
    ids = [r[0] for r in _candidats(A, [A, COMMUN], termes("\\y"), 5000, actives=True, tri=True)]
    assert ids == ["c-dj-1", "c-dj-2"]          # pas la courbe D


def test_selecteur_lit_les_fiches_sous_rls():
    """Le second temps (relecture par id) reste soumis a la RLS."""
    lignes = _app(A, """
        WITH sel AS MATERIALIZED (
            SELECT c.id FROM blueseatra.offres_candidates(
                ARRAY[%s]::text[], %s::jsonb, 200, NULL, NULL, false, false) c)
        SELECT o.id FROM sel JOIN blueseatra.supplier_offers o ON o.id = sel.id
         WHERE (o.tenant_id = %s OR o.tenant_id = %s)""",
        (A, json.dumps(_like("prise")), A, COMMUN))
    assert {r[0] for r in lignes} == {"a-prise-1", "a-hist-1"}


# --- Recherche dans un catalogue (catalogue_page) ----------------------------

def _page(tenant, p_tenant, termes, version=None, hist=None, famille=None,
          limite=51, decalage=0, plafond=1001):
    r = _app(tenant, """SELECT blueseatra.catalogue_page(%s, %s, %s, %s::jsonb, %s, %s, %s, %s)""",
             (p_tenant, version, hist, json.dumps(termes), famille, limite, decalage, plafond))[0][0]
    return r if isinstance(r, dict) else json.loads(r)


def _ref_page(cond, params, version, famille=None, limite=51, decalage=0):
    fam = " AND o.raw_row->>'famille' = %s" if famille else ""
    with _cx() as c, c.cursor() as cur:
        cur.execute(f"""SELECT o.id FROM blueseatra.supplier_offers o
                         WHERE o.tenant_id = %s AND o.version_id = %s AND o.is_active
                           AND {cond}{fam}
                         ORDER BY o.price_ht ASC NULLS LAST, o.id LIMIT %s OFFSET %s""",
                    (COMMUN, version, *params, *([famille] if famille else []), limite, decalage))
        return [r[0] for r in cur.fetchall()]


def test_page_autre_entreprise_rien():
    assert _page(A, B, _like("prise"), version="ver-b1") == {"ids": [], "total": 0}
    assert _page(A, B, _like("prise"), hist="concurrent") == {"ids": [], "total": 0}
    assert _page("", A, _like("prise"), hist="histo") == {"ids": [], "total": 0}


def test_page_exige_une_portee_precise():
    assert _page(A, COMMUN, _like("prise")) == {"ids": [], "total": 0}           # ni version ni hist
    assert _page(A, COMMUN, _like("prise"), version="ver-c2", hist="x") == {"ids": [], "total": 0}
    assert _page(A, COMMUN, [[{"op": "sql", "v": "1=1"}]], version="ver-c2") == {"ids": [], "total": 0}


@pytest.mark.parametrize("plafond,decalage", [(1001, 0), (1001, 950), (5000, 100)])
def test_page_identique_a_la_reference(plafond, decalage):
    # plafond 1001 < 4000 prises : chemin « index par prix » ; 5000 : trigramme.
    r = _page(A, COMMUN, _like("prise"), version="ver-c2", decalage=decalage, plafond=plafond)
    assert r["total"] == min(plafond, 4000)
    assert r["ids"] == _ref_page("o.recherche_norm LIKE %s", ["%prise%"], "ver-c2", decalage=decalage)
    assert "c-off-1" not in r["ids"] and "c-old-1" not in r["ids"]


def test_page_avec_famille_les_deux_chemins():
    attendu = _ref_page("o.recherche_norm LIKE %s", ["%prise%"], "ver-c2", famille="Eclairage")
    assert len(attendu) == 51
    for plafond in (101, 1001):   # 400 prises en Eclairage : >= plafond, puis < plafond
        r = _page(A, COMMUN, _like("prise"), version="ver-c2", famille="Eclairage", plafond=plafond)
        assert r["ids"] == attendu and r["total"] == min(plafond, 400)


def test_page_historique_et_terme_rare():
    assert _page(A, A, _like("prise"), hist="histo") == {"ids": ["a-hist-1"], "total": 1}
    r = _page(A, COMMUN, _like("disjoncteur", "16a"), version="ver-c2")
    assert r == {"ids": ["c-dj-1", "c-dj-2", "c-dj-3"], "total": 3}
    assert _page(A, COMMUN, _like("introuvable"), version="ver-c2") == {"ids": [], "total": 0}


def test_page_bornes():
    r = _page(A, COMMUN, _like("prise"), version="ver-c2", limite=10 ** 6, decalage=-5, plafond=10 ** 9)
    assert len(r["ids"]) == 201 and r["total"] == 4000   # limite <= 201, decalage >= 0
