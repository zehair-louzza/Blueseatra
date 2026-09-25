"""Ticket #90 : signature du webhook, encodage Stripe, correspondance des statuts."""
import hashlib, hmac, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
fs = pytest.importorskip("facturation_stripe")


def _signer(corps: bytes, secret: str, t: int) -> str:
    return f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.".encode() + corps, hashlib.sha256).hexdigest()


def test_signature_valide_invalide_et_expiree():
    corps = json.dumps({"id": "evt_1", "type": "invoice.paid"}).encode()
    t = int(time.time())
    assert fs.verifier_signature(corps, _signer(corps, "whsec_x", t), "whsec_x")["id"] == "evt_1"
    for entete, secret in ((_signer(corps, "autre", t), "whsec_x"), ("t=1", "whsec_x"), ("", "whsec_x"), (_signer(corps, "whsec_x", t), "")):
        with pytest.raises(ValueError):
            fs.verifier_signature(corps, entete, secret)
    with pytest.raises(ValueError):
        fs.verifier_signature(corps, _signer(corps, "whsec_x", t - 3600), "whsec_x")
    with pytest.raises(ValueError):   # corps modifié après signature
        fs.verifier_signature(corps + b" ", _signer(corps, "whsec_x", t), "whsec_x")


def test_encodage_formulaire_imbrique():
    d = fs._aplatir({"line_items": [{"price": "p1", "quantity": 1}], "metadata": {"tenant_id": "t"}, "tax_id_collection": {"enabled": True}})
    assert ("line_items[0][price]", "p1") in d and ("metadata[tenant_id]", "t") in d and ("tax_id_collection[enabled]", "true") in d


def test_statuts_et_grille():
    assert fs.STATUTS["active"] == "actif" and fs.STATUTS["past_due"] == "actif" and fs.STATUTS["unpaid"] == "lecture_seule"
    assert fs.lookup_offre("pilotage", "annuel") == "pilotage_annuel"
    assert fs.RECHARGES["recharge_pages_500"] == ("page_lue", 500)


def test_cle_live_refusee_sans_bascule(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_x")
    monkeypatch.delenv("BLUESEATRA_STRIPE_LIVE", raising=False)
    with pytest.raises(Exception):
        fs._cle()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    assert fs._cle() == "sk_test_x" and fs.mode_test()
