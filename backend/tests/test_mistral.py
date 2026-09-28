"""Ticket #88 : fournisseur Mistral (remplace Cerebras). Aucun appel réseau."""
import asyncio, logging, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
ai = pytest.importorskip("ai_service")
import ia_garde_fous as g


class _Rep:
    def __init__(self, code, corps): self.status_code, self._c, self.text = code, corps, str(corps)
    def json(self): return self._c


def test_resolution_cle_entreprise_puis_plateforme(monkeypatch):
    monkeypatch.setattr(ai, "MISTRAL_API_KEY", "cle-plateforme")
    p, m, k = asyncio.run(ai.resolve_ai_config({"ai_provider": "mistral", "ai_model": "mistral-small-latest", "ai_key": "cle-entreprise"}))
    assert (p, m, k) == ("mistral", "mistral-small-latest", "cle-entreprise")
    p, m, k = asyncio.run(ai.resolve_ai_config({"ai_provider": "mistral", "ai_model": "hermes-3"}))
    assert m == ai.MISTRAL_DEFAULT_MODEL and k == "cle-plateforme"


def test_appel_json_image_et_cle_absente_des_journaux(monkeypatch, caplog):
    vu = {}
    class _C:
        def __init__(self, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, headers=None, json=None):
            vu.update(url=url, auth=headers["Authorization"], corps=json)
            return _Rep(200, {"choices": [{"message": {"content": '{"description": "ok"}'}}]})
    monkeypatch.setattr(ai.httpx, "Client", _C)
    caplog.set_level(logging.INFO)
    sortie = asyncio.run(ai._call_mistral(api_key="mstrl_CLE_SECRETE", model="mistral-medium-latest",
                                          system_prompt="sys", user_message="demande", image_b64="QUJD"))
    assert sortie == '{"description": "ok"}'
    assert vu["url"].endswith("/v1/chat/completions") and vu["auth"] == "Bearer mstrl_CLE_SECRETE"
    assert vu["corps"]["response_format"] == {"type": "json_object"}
    assert vu["corps"]["messages"][1]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")
    assert "mstrl_CLE_SECRETE" not in caplog.text and "fournisseur=mistral modele=mistral-medium-latest" in caplog.text


def test_cle_manquante_et_refus():
    with pytest.raises(RuntimeError):
        asyncio.run(ai._call_mistral(api_key="", model="m", system_prompt="s", user_message="u"))
    assert ai.tester_mistral("")["ok"] is False


def test_prix_renvoye_par_mistral_retire():
    r = g.valider_extraction({"description": "x", "line_items": [{"label": "pompe", "qty": 1, "unit": "u", "prix": 120}]})
    assert "prix" not in r["line_items"][0]
