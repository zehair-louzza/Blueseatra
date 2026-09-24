"""Migration du module Clients : isolation, archivage sans suppression,
journal en ajout seul, contraintes. Base JETABLE uniquement.

    TEST_PG_DSN='postgresql://postgres@/qt?host=/tmp&port=55432' pytest backend/tests_clients -q
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")
DSN = os.environ.get("TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_PG_DSN non défini")
MIGRATION = (Path(__file__).resolve().parents[2]
             / "supabase/migrations/20260926090000_module_clients.sql")


def _cx():
    c = psycopg2.connect(DSN, client_encoding="utf8")
    c.autocommit = True
    return c


@pytest.fixture(scope="module", autouse=True)
def migration():
    assert "supabase" not in DSN, "base jetable uniquement"
    with _cx() as c, c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS blueseatra.requests (id varchar(36) PRIMARY KEY, tenant_id varchar(36));
                       CREATE TABLE IF NOT EXISTS blueseatra.quotes (id varchar(36) PRIMARY KEY, tenant_id varchar(36));""")
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        cur.execute(MIGRATION.read_text(encoding="utf-8"))


def app(tenant, sql, params=()):
    c = psycopg2.connect(DSN, client_encoding="utf8")
    try:
        with c.cursor() as cur:
            cur.execute("SET LOCAL ROLE blueseatra_app")
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            cur.execute(sql, params)
            rows = cur.fetchall() if cur.description else None
        c.commit()
        return rows
    finally:
        c.close()


def nouveau_client(tenant, nom="SCI Les Tilleuls", siret=None):
    cid = str(uuid.uuid4())
    app(tenant, "INSERT INTO blueseatra.clients (id, tenant_id, raison_sociale, siret) VALUES (%s,%s,%s,%s)",
        (cid, tenant, nom, siret))
    return cid


def test_une_entreprise_ne_voit_jamais_les_clients_d_une_autre():
    ta, tb = str(uuid.uuid4()), str(uuid.uuid4())
    nouveau_client(ta, "Client secret A")
    assert app(tb, "SELECT count(*) FROM blueseatra.clients")[0][0] == 0
    with pytest.raises(psycopg2.Error):
        nouveau_client_autre = str(uuid.uuid4())
        app(tb, "INSERT INTO blueseatra.clients (id, tenant_id, raison_sociale) VALUES (%s,%s,'x')",
            (nouveau_client_autre, ta))


def test_suppression_impossible_archivage_possible():
    t = str(uuid.uuid4())
    cid = nouveau_client(t)
    with pytest.raises(psycopg2.Error):
        app(t, "DELETE FROM blueseatra.clients WHERE id = %s", (cid,))
    app(t, "UPDATE blueseatra.clients SET archive_le = now() WHERE id = %s", (cid,))
    assert app(t, "SELECT archive_le IS NOT NULL FROM blueseatra.clients WHERE id = %s", (cid,)) == [(True,)]


def test_siret_valide_et_unique_par_entreprise():
    t = str(uuid.uuid4())
    nouveau_client(t, siret="12345678900011")
    with pytest.raises(psycopg2.Error):
        nouveau_client(t, "Doublon", siret="12345678900011")
    with pytest.raises(psycopg2.Error):
        nouveau_client(t, "Mauvais", siret="123")
    nouveau_client(str(uuid.uuid4()), "Même SIRET ailleurs", siret="12345678900011")   # autre entreprise : permis


def test_un_seul_contact_principal():
    t = str(uuid.uuid4())
    cid = nouveau_client(t)
    sql = "INSERT INTO blueseatra.contacts (id, tenant_id, client_id, nom, principal) VALUES (%s,%s,%s,%s,true)"
    app(t, sql, (str(uuid.uuid4()), t, cid, "Martin"))
    with pytest.raises(psycopg2.Error):
        app(t, sql, (str(uuid.uuid4()), t, cid, "Durand"))


def test_journal_des_echanges_en_ajout_seul():
    t = str(uuid.uuid4())
    cid = nouveau_client(t)
    app(t, "INSERT INTO blueseatra.echanges_clients (tenant_id, client_id, type, resume) VALUES (%s,%s,'appel','RDV fixé')",
        (t, cid))
    for sql in ("UPDATE blueseatra.echanges_clients SET resume = 'x' WHERE client_id = %s",
                "DELETE FROM blueseatra.echanges_clients WHERE client_id = %s"):
        with pytest.raises(psycopg2.Error):
            app(t, sql, (cid,))
    with _cx() as c, c.cursor() as cur, pytest.raises(psycopg2.Error):
        cur.execute("UPDATE blueseatra.echanges_clients SET resume = 'x' WHERE client_id = %s", (cid,))


def test_une_relance_par_rang_sauf_annulee():
    t = str(uuid.uuid4())
    sql = """INSERT INTO blueseatra.relances (id, tenant_id, devis_id, rang, echeance, canal, raison, statut)
             VALUES (%s,%s,'q1',1, now(), 'email', 'relance 1', %s)"""
    app(t, sql, (str(uuid.uuid4()), t, "annulee"))
    app(t, sql, (str(uuid.uuid4()), t, "prevue"))
    with pytest.raises(psycopg2.Error):
        app(t, sql, (str(uuid.uuid4()), t, "prevue"))


def test_issue_du_devis_controlee():
    t = str(uuid.uuid4())
    with _cx() as c, c.cursor() as cur:
        cur.execute("INSERT INTO blueseatra.quotes (id, tenant_id, issue) VALUES (%s,%s,'accepte')", (str(uuid.uuid4()), t))
        with pytest.raises(psycopg2.Error):
            cur.execute("INSERT INTO blueseatra.quotes (id, tenant_id, issue) VALUES (%s,%s,'gagne')", (str(uuid.uuid4()), t))
