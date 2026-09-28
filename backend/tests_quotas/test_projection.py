"""Ticket #89 : projection de consommation (fonction pure)."""
import os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
pytest.importorskip("sqlalchemy")
from quotas import projeter  # noqa: E402

D = datetime(2026, 9, 1, tzinfo=timezone.utc)
F = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_rythme_et_projection_lineaires():
    p = projeter(20, 60, 0, D, F, maintenant=D + timedelta(days=10))
    assert p["rythme_par_jour"] == 2.0 and p["projection_fin_periode"] == 60
    assert p["epuisement_prevu_le"] is None          # épuisement le 01/10, pas avant la fin


def test_epuisement_avant_la_fin_de_periode():
    p = projeter(30, 60, 0, D, F, maintenant=D + timedelta(days=10))
    assert p["epuisement_prevu_le"].startswith("2026-09-21")


def test_recharges_repoussent_l_epuisement_et_illimite_sans_date():
    assert projeter(30, 60, 100, D, F, maintenant=D + timedelta(days=10))["epuisement_prevu_le"] is None
    assert projeter(500, None, 0, D, F, maintenant=D + timedelta(days=10))["epuisement_prevu_le"] is None


def test_premier_jour_pas_d_extrapolation_excessive():
    p = projeter(3, 60, 0, D, F, maintenant=D + timedelta(hours=2))
    assert p["rythme_par_jour"] == 3.0 and p["projection_fin_periode"] == 90
