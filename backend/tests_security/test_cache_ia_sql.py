"""Cache IA (migration 20261006220000) : isolation par entreprise (RLS), idempotence, expiration.

Exécuté seulement si TEST_PG_DSN pointe vers une base JETABLE (schéma `blueseatra`, `current_tenant()`,
rôle `blueseatra_app`). Ne JAMAIS pointer TEST_PG_DSN vers Supabase.
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
MIGRATION = Path(__file__).resolve().parents[2] / "supabase/migrations/20261006220000_cache_ia.sql"
CLE = "a" * 64


def _cx():
    c = psycopg2.connect(DSN, client_encoding="utf8")
    c.autocommit = True
    return c


@pytest.fixture(scope="module", autouse=True)
def migration():
    assert "supabase.co" not in DSN and "pooler" not in DSN, "base jetable uniquement"
    with _cx() as c, c.cursor() as cur:
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        cur.execute(MIGRATION.read_text(encoding="utf-8"))   # idempotente
    yield


def _app(tenant, sql, params=()):
    """Exécute `sql` sous blueseatra_app avec app.tenant_id, comme le backend."""
    c = psycopg2.connect(DSN, client_encoding="utf8")
    try:
        with c.cursor() as cur:
            cur.execute("SET LOCAL ROLE blueseatra_app")
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            cur.execute(sql, params)
            rows = cur.fetchall() if cur.description else None
            n = cur.rowcount
        c.commit()
        return rows, n
    finally:
        c.close()


def _ecrire(tenant, cle=CLE, resultat=None):
    return _app(tenant, """INSERT INTO blueseatra.cache_ia (tenant_id, cle, source, resultat)
                           VALUES (%s, %s, 'texte', %s::jsonb)
                           ON CONFLICT (tenant_id, cle) DO UPDATE SET resultat = EXCLUDED.resultat""",
                (tenant, cle, json.dumps(resultat or {"confidence": 0.9})))


def test_chaque_entreprise_ne_voit_que_son_cache():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    _ecrire(a, resultat={"client": "A"})
    assert _app(a, "SELECT resultat->>'client' FROM blueseatra.cache_ia WHERE cle = %s", (CLE,))[0] == [("A",)]
    assert _app(b, "SELECT 1 FROM blueseatra.cache_ia WHERE cle = %s", (CLE,))[0] == []
    # B ne peut ni lire, ni modifier, ni supprimer la ligne de A
    assert _app(b, "UPDATE blueseatra.cache_ia SET resultat = '{}'::jsonb WHERE cle = %s", (CLE,))[1] == 0
    assert _app(b, "DELETE FROM blueseatra.cache_ia WHERE cle = %s", (CLE,))[1] == 0
    assert _app(a, "SELECT count(*) FROM blueseatra.cache_ia WHERE cle = %s", (CLE,))[0] == [(1,)]


def test_une_entreprise_ne_peut_pas_ecrire_pour_une_autre():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        _app(a, """INSERT INTO blueseatra.cache_ia (tenant_id, cle, source, resultat)
                   VALUES (%s, %s, 'texte', '{}'::jsonb)""", (b, "b" * 64))


def test_ecrire_deux_fois_remplace_sans_doublon():
    t = str(uuid.uuid4())
    _ecrire(t, resultat={"v": 1})
    _ecrire(t, resultat={"v": 2})
    assert _app(t, "SELECT count(*), max((resultat->>'v')::int) FROM blueseatra.cache_ia")[0] == [(1, 2)]


def test_entree_perimee_ignoree_par_la_requete_de_lecture():
    t = str(uuid.uuid4())
    _ecrire(t)
    with _cx() as c, c.cursor() as cur:
        cur.execute("UPDATE blueseatra.cache_ia SET cree_le = now() - interval '31 days' WHERE tenant_id = %s", (t,))
    lecture = """UPDATE blueseatra.cache_ia SET reutilisations = reutilisations + 1
                 WHERE tenant_id = %s AND cle = %s AND cree_le > now() - make_interval(days => 30) RETURNING resultat"""
    assert _app(t, lecture, (t, CLE))[0] == []
    _ecrire(t)  # le même contenu se réécrit
    with _cx() as c, c.cursor() as cur:
        cur.execute("UPDATE blueseatra.cache_ia SET cree_le = now() - interval '2 days' WHERE tenant_id = %s", (t,))
    assert len(_app(t, lecture, (t, CLE))[0]) == 1
