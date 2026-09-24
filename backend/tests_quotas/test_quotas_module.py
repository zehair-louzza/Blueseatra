"""Test de bout en bout de quotas.py sur le vrai chemin database.py.

Même base jetable que test_quotas_sql.py, mais via tenant_session() sous
le rôle blueseatra_app (DATABASE_URL_APP), exactement comme en production.

    TEST_PG_URL='postgresql://postgres@localhost:55432/qt' \
    TEST_PG_URL_APP='postgresql://blueseatra_app@localhost:55432/qt' \
    pytest backend/tests_quotas -q
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

URL = os.environ.get("TEST_PG_URL")
URL_APP = os.environ.get("TEST_PG_URL_APP")
pytestmark = pytest.mark.skipif(not (URL and URL_APP), reason="TEST_PG_URL(_APP) non définis")


@pytest.fixture(scope="module")
def q():
    assert "supabase" not in URL and "supabase" not in URL_APP, "base jetable uniquement"
    os.environ["DATABASE_URL"] = URL
    os.environ["DATABASE_URL_APP"] = URL_APP
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    for m in ("database", "quotas"):
        sys.modules.pop(m, None)
    import database  # noqa: F401
    import quotas
    return quotas


_BOUCLE = asyncio.new_event_loop()


def _run(coro):
    return _BOUCLE.run_until_complete(coro)   # une seule boucle : le pool y est attaché


def test_parcours_complet(q, monkeypatch):
    from database import tenant_context
    t = str(uuid.uuid4())

    async def scenario():
        async with tenant_context(t):
            e0 = await q.etat(nb_membres=1)
            assert e0["disponible"] and e0["offre"]["code"] == "decouverte"
            assert e0["statut"] == "essai" and e0["jauges"]["devis_ia"]["restant"] == 10
            await q.reserver("d1", 1, q.pages_a_compter("pdf_ocr", 4), "a@x")
            await q.reserver("d2", 1, q.pages_a_compter("pdf", 0), "a@x")
            e1 = await q.etat(nb_membres=1)
            assert e1["jauges"]["devis_ia"] == {"inclus": 10, "utilise": 2, "recharge_restante": 0, "restant": 8}
            assert e1["jauges"]["page_lue"]["restant"] == 26
            assert await q.annuler("d1", "échec") == 2
            e2 = await q.etat(nb_membres=1)
            assert e2["jauges"]["devis_ia"]["restant"] == 9 and e2["jauges"]["page_lue"]["restant"] == 30
            h = await q.historique(50, 0)
            assert {l["nature"] for l in h} == {"dotation", "consommation", "annulation"}

            monkeypatch.setenv("BLUESEATRA_QUOTAS_APPLIQUES", "1")
            for i in range(9):
                await q.reserver(f"x{i}", 1, 0, "a@x")
            with pytest.raises(q.QuotaAtteint) as exc:
                await q.reserver("trop", 1, 0, "a@x")
            assert exc.value.motif == "quota_atteint_devis_ia"
            assert "recharge" in str(exc.value)
            with pytest.raises(q.QuotaAtteint):
                await q.verifier_siege(1)          # Découverte : 1 siège, déjà pris
            monkeypatch.setenv("BLUESEATRA_QUOTAS_APPLIQUES", "0")
            r = await q.reserver("observe", 1, 0, "a@x")
            assert r["autorise"] and r["depassement"]

    _run(scenario())


def test_une_entreprise_ne_voit_pas_l_autre(q):
    from database import tenant_context
    ta, tb = str(uuid.uuid4()), str(uuid.uuid4())

    async def scenario():
        async with tenant_context(ta):
            await q.reserver("secret", 1, 3, "a@x")
        async with tenant_context(tb):
            assert await q.historique(50, 0) == []
            e = await q.etat(nb_membres=1)
            assert e["jauges"]["devis_ia"]["utilise"] == 0

    _run(scenario())
