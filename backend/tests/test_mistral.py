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
    monkeypatch.setattr(ai, "IA_VIA_HERMES", False)   # ancien chemin direct (retour arrière)
    monkeypatch.setattr(ai, "MASQUAGE_RGPD", False)   # image : seulement sans masquage (voir test_ia_externe_rgpd)
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


def test_cle_manquante_et_refus(monkeypatch):
    monkeypatch.setattr(ai, "IA_VIA_HERMES", False)
    with pytest.raises(RuntimeError):
        asyncio.run(ai._call_mistral(api_key="", model="m", system_prompt="s", user_message="u"))
    assert ai.tester_mistral("")["ok"] is False


def test_prix_renvoye_par_mistral_retire():
    r = g.valider_extraction({"description": "x", "line_items": [{"label": "pompe", "qty": 1, "unit": "u", "prix": 120}]})
    assert "prix" not in r["line_items"][0]


def test_mistral_via_hermes_envoie_provider_et_modele(monkeypatch):
    vu = {}
    class _R:
        status_code = 200
        text = ""
        headers = {"content-type": "application/json"}
        def json(self): return {"choices": [{"message": {"content": '{"ok": true}'}}]}
    class _AC:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            vu.update(url=url, corps=json); return _R()
    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "https://hermes.exemple")
    monkeypatch.setattr(ai.httpx, "AsyncClient", _AC)
    assert ai.est_mistral_via_hermes("hermes", "mistral:mistral-small-latest")
    assert not ai.est_mistral_via_hermes("hermes", "qwen2.5:7b")
    p, m, _ = asyncio.run(ai.resolve_ai_config({"ai_provider": "hermes", "ai_model": "mistral:mistral-small-latest"}))
    assert (p, m) == ("hermes", "mistral:mistral-small-latest")
    asyncio.run(ai._call_mistral_via_hermes(model=m, system_prompt="s", user_message="u"))
    assert vu["url"] == "https://hermes.exemple/v1/chat/completions"
    assert vu["corps"]["provider"] == "custom:mistral" and vu["corps"]["model"] == "mistral-small-latest"


def test_mistral_via_hermes_sans_passerelle_ni_cle(monkeypatch):
    monkeypatch.setattr(ai, "IA_VIA_HERMES", False)
    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "")
    monkeypatch.setattr(ai, "MISTRAL_API_KEY", "")
    with pytest.raises(RuntimeError):
        asyncio.run(ai._call_mistral_via_hermes(model="mistral:x", system_prompt="s", user_message="u"))
def test_mistral_429_relance_puis_succes(monkeypatch):
    monkeypatch.setattr(ai, "IA_VIA_HERMES", False)
    appels = []
    class _C:
        def __init__(self, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, headers=None, json=None):
            appels.append(1)
            if len(appels) < 3:
                r = _Rep(429, {"message": "Rate limit exceeded"}); r.headers = {"retry-after": "0"}; return r
            r = _Rep(200, {"choices": [{"message": {"content": "{}"}}]}); r.headers = {}; return r
    async def _sans_attente(_): return None
    monkeypatch.setattr(ai.httpx, "Client", _C)
    monkeypatch.setattr(ai.asyncio, "sleep", _sans_attente)
    assert asyncio.run(ai._call_mistral(api_key="k", model="m", system_prompt="s", user_message="u")) == "{}"
    assert len(appels) == 3


def test_image_lue_en_local_meme_avec_mistral(monkeypatch):
    vu = {}
    async def _local(**kw):
        vu.update(kw); return '{"description": "x", "line_items": []}'
    async def _interdit(**kw):
        raise AssertionError("une image ne doit jamais partir vers Mistral")
    async def _ctx(_t): return ""
    monkeypatch.setattr(ai, "_call_hermes_ollama", _local)
    monkeypatch.setattr(ai, "_call_mistral", _interdit)
    monkeypatch.setattr(ai, "_web_context_sans_prix", _ctx)
    asyncio.run(ai.extract_request_data("", {"ai_provider": "mistral", "ai_model": "mistral-small-latest", "ai_key": "k"},
                                        image_bytes=b"\x89PNG"))
    assert vu["model"] == ai.HERMES_VISION_MODEL and vu["image_b64"]


class _AC:
    """Faux client asynchrone : enregistre chaque appel à la passerelle."""
    appels = []
    def __init__(self, **kw): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, json=None, headers=None):
        _AC.appels.append({"url": url, "corps": json, "entetes": headers})
        class _R:
            status_code = 200
            text = "{}"
            headers = {"content-type": "application/json"}
            def json(self_inner): return {"choices": [{"message": {"content": "Texte lu sur la page, assez long pour passer."}}]}
        return _R()


def test_tout_passe_par_hermes_aucun_appel_ollama(monkeypatch):
    _AC.appels = []
    monkeypatch.setattr(ai, "IA_VIA_HERMES", True)
    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "https://hermes.exemple")
    monkeypatch.setattr(ai.httpx, "AsyncClient", _AC)
    # OCR PaddleOCR, modèle local de raisonnement, Mistral : tous vers Hermès
    asyncio.run(ai._call_ocr_model(b"\x89PNG", ai.HERMES_OCR_MODEL, timeout=5))
    asyncio.run(ai._call_hermes_ollama("qwen2.5:7b", "sys", "demande", role="extract"))
    asyncio.run(ai._call_mistral(api_key="", model="mistral-small-latest", system_prompt="s", user_message="u"))
    urls = {a["url"] for a in _AC.appels}
    assert urls == {"https://hermes.exemple/v1/chat/completions"}
    fournisseurs = [a["corps"]["provider"] for a in _AC.appels]
    assert fournisseurs == ["custom:ollama", "custom:ollama", "custom:mistral"]
    ocr = _AC.appels[0]["corps"]
    assert ocr["model"] == ai.HERMES_OCR_MODEL and ocr["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert all(a["entetes"]["X-Hermes-Session-Id"] for a in _AC.appels)


def test_sans_passerelle_erreur_claire_et_pas_de_repli_ollama(monkeypatch):
    monkeypatch.setattr(ai, "IA_VIA_HERMES", True)
    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "")
    with pytest.raises(ai.HermesIndisponible):
        asyncio.run(ai._call_hermes_ollama("qwen2.5:7b", "sys", "demande"))
