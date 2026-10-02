"""Journal d'audit en ajout seul (migration 20261002040000). Base JETABLE uniquement.

    TEST_PG_DSN='postgresql://postgres@/qt?host=/tmp&port=55432' pytest backend/tests_security/test_journal_audit_ajout_seul_sql.py -q
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
             / "supabase/migrations/20261002040000_journal_audit_ajout_seul.sql")


def _cx():
    c = psycopg2.connect(DSN, client_encoding="utf8")
    c.autocommit = True
    return c


@pytest.fixture(scope="module", autouse=True)
def migration():
    assert "supabase" not in DSN, "base jetable uniquement"
    with _cx() as c, c.cursor() as cur:
        # Table et droits tels qu'avant le correctif (GRANT global de l'étape 4).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS blueseatra.audit_logs (
                id varchar(36) PRIMARY KEY, tenant_id varchar(36), actor varchar,
                action varchar, target varchar, meta jsonb, created_at varchar);
            ALTER TABLE blueseatra.audit_logs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS audit_tenant_test ON blueseatra.audit_logs;
            CREATE POLICY audit_tenant_test ON blueseatra.audit_logs FOR ALL TO blueseatra_app
                USING (tenant_id = blueseatra.current_tenant())
                WITH CHECK (tenant_id = blueseatra.current_tenant());
            GRANT SELECT, INSERT, UPDATE, DELETE ON blueseatra.audit_logs TO blueseatra_app;
        """)
        sql = MIGRATION.read_text(encoding="utf-8")
        cur.execute(sql)
        cur.execute(sql)   # idempotente


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


def ligne(tenant):
    lid = str(uuid.uuid4())
    app(tenant, "INSERT INTO blueseatra.audit_logs (id, tenant_id, actor, action) VALUES (%s,%s,'test','quote.validate')",
        (lid, tenant))
    return lid


def test_insertion_et_lecture_restent_possibles():
    t = str(uuid.uuid4())
    lid = ligne(t)
    assert app(t, "SELECT id FROM blueseatra.audit_logs WHERE id=%s", (lid,)) == [(lid,)]


@pytest.mark.parametrize("sql", [
    "UPDATE blueseatra.audit_logs SET action='falsifie' WHERE id=%s",
    "DELETE FROM blueseatra.audit_logs WHERE id=%s",
])
def test_role_applicatif_ne_peut_ni_modifier_ni_supprimer(sql):
    t = str(uuid.uuid4())
    lid = ligne(t)
    with pytest.raises(psycopg2.Error) as e:
        app(t, sql, (lid,))
    assert e.value.pgcode == "42501"   # insufficient_privilege
    assert app(t, "SELECT action FROM blueseatra.audit_logs WHERE id=%s", (lid,)) == [("quote.validate",)]


def test_role_applicatif_ne_peut_pas_contourner_par_le_reglage_de_maintenance():
    t = str(uuid.uuid4())
    lid = ligne(t)
    with pytest.raises(psycopg2.Error):
        app(t, "SELECT set_config('blueseatra.maintenance_audit','on',true); "
               "DELETE FROM blueseatra.audit_logs WHERE id=%s", (lid,))
    assert app(t, "SELECT count(*) FROM blueseatra.audit_logs WHERE id=%s", (lid,)) == [(1,)]


@pytest.mark.parametrize("sql", [
    "UPDATE blueseatra.audit_logs SET action='falsifie' WHERE id=%s",
    "DELETE FROM blueseatra.audit_logs WHERE id=%s",
])
def test_meme_un_administrateur_est_refuse_sans_maintenance(sql):
    t = str(uuid.uuid4())
    lid = ligne(t)
    with _cx() as c, c.cursor() as cur:
        with pytest.raises(psycopg2.Error) as e:
            cur.execute(sql, (lid,))
        assert e.value.pgcode == "42501"


def test_truncate_refuse():
    with _cx() as c, c.cursor() as cur:
        with pytest.raises(psycopg2.Error) as e:
            cur.execute("TRUNCATE blueseatra.audit_logs")
        assert e.value.pgcode == "42501"


def test_maintenance_explicite_par_un_administrateur():
    t = str(uuid.uuid4())
    lid = ligne(t)
    c = psycopg2.connect(DSN, client_encoding="utf8")
    try:
        with c.cursor() as cur:
            cur.execute("SET LOCAL blueseatra.maintenance_audit = 'on'")
            cur.execute("DELETE FROM blueseatra.audit_logs WHERE id=%s", (lid,))
            assert cur.rowcount == 1
        c.commit()
    finally:
        c.close()
    # Le réglage est local à la transaction : la protection revient aussitôt.
    lid2 = ligne(t)
    with _cx() as c2, c2.cursor() as cur:
        with pytest.raises(psycopg2.Error):
            cur.execute("DELETE FROM blueseatra.audit_logs WHERE id=%s", (lid2,))


def test_droits_du_role_applicatif():
    with _cx() as c, c.cursor() as cur:
        cur.execute("""SELECT privilege_type FROM information_schema.role_table_grants
                       WHERE table_schema='blueseatra' AND table_name='audit_logs'
                         AND grantee='blueseatra_app' ORDER BY 1""")
        assert [r[0] for r in cur.fetchall()] == ["INSERT", "SELECT"]
