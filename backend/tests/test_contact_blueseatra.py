"""Adresse de contact citée par l'API quand l'utilisateur doit écrire à Blueseatra."""
import importlib

import contact_blueseatra
import quotas


def test_adresse_par_defaut_dans_le_message_espace_suspendu():
    assert contact_blueseatra.CONTACT_EMAIL == "contact@blueseatra.com"
    assert "contact@blueseatra.com" in quotas.MESSAGES["suspendu"]


def test_paiement_non_active_donne_l_adresse(monkeypatch):
    import pytest
    from fastapi import HTTPException
    import facturation_stripe
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(HTTPException) as e:
        facturation_stripe._cle()
    assert e.value.status_code == 503 and "contact@blueseatra.com" in e.value.detail


def test_adresse_modifiable_par_variable(monkeypatch):
    monkeypatch.setenv("BLUESEATRA_CONTACT_EMAIL", "bonjour@exemple-fictif.fr")
    try:
        assert importlib.reload(contact_blueseatra).CONTACT_EMAIL == "bonjour@exemple-fictif.fr"
    finally:
        monkeypatch.delenv("BLUESEATRA_CONTACT_EMAIL")
        importlib.reload(contact_blueseatra)
