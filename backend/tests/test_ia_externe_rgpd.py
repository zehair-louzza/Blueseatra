"""Appels IA hors du VPS (Mistral, OpenCode Free) : masquage RGPD obligatoire. Aucun réseau, données fictives."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

ai = pytest.importorskip("ai_service")
import masquage_rgpd as m

DEMANDE = ("Client : LUMIA\nSite : 14 rue des Peupliers, 75020 Paris\nContact : Mme Ducros 06 12 34 56 78\n"
           "Travaux suivants : remplacement de 3 spots LED.")


class _R:
    status_code = 200
    text = ""
    headers = {"content-type": "application/json"}

    def __init__(self, contenu):
        self._c = contenu

    def json(self):
        return {"choices": [{"message": {"content": self._c}}]}


def _passerelle(monkeypatch, reponse='{"client": "[client_1]", "produits": ["spot LED"]}'):
    vu = {"appels": 0}

    class _AC:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            vu["appels"] += 1
            vu["corps"] = json
            return _R(reponse)

    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "https://hermes.exemple")
    monkeypatch.setattr(ai, "IA_RUNS", False)
    monkeypatch.setattr(ai.httpx, "AsyncClient", _AC)

    async def _entites():
        return m.Entites(clients=["LUMIA"])
    monkeypatch.setattr(ai, "_entites_rgpd", _entites)
    return vu


def _texte_envoye(vu):
    return vu["corps"]["messages"][-1]["content"]


@pytest.mark.parametrize("fournisseur", ["custom:mistral", "opencode-free"])
def test_fournisseur_externe_recoit_le_texte_masque_et_la_reponse_est_restauree(monkeypatch, fournisseur):
    vu = _passerelle(monkeypatch)
    sortie = asyncio.run(ai._hermes_chat("modele", "consigne", DEMANDE, provider=fournisseur))
    envoye = _texte_envoye(vu)
    for fuite in ("LUMIA", "Peupliers", "75020", "Ducros", "06 12"):
        assert fuite not in envoye, fuite
    assert "3 spots LED" in envoye
    assert '"client": "LUMIA"' in sortie


def test_modele_local_du_vps_recoit_le_texte_intact(monkeypatch):
    vu = _passerelle(monkeypatch, reponse="ok")
    asyncio.run(ai._hermes_chat("gpt-oss:20b", "consigne", DEMANDE, provider="custom:ollama"))
    assert _texte_envoye(vu).endswith(DEMANDE)


def test_image_jamais_envoyee_a_un_fournisseur_externe(monkeypatch):
    vu = _passerelle(monkeypatch)
    with pytest.raises(m.FuitePossible):
        asyncio.run(ai._hermes_chat("modele", "consigne", "lis l'image", image_b64="QUJD", provider="opencode-free"))
    assert vu["appels"] == 0


def test_envoi_refuse_si_le_controle_trouve_une_fuite(monkeypatch):
    vu = _passerelle(monkeypatch)
    vrai_masquer = m.masquer
    appels = []

    def _masquage_defaillant(texte, entites=None):   # 1er passage raté, le contrôle utilise le vrai détecteur
        appels.append(1)
        return m.Resultat(texte, {}) if len(appels) == 1 else vrai_masquer(texte, entites)
    monkeypatch.setattr(ai.masquage_rgpd, "masquer", _masquage_defaillant)
    with pytest.raises(m.FuitePossible):
        asyncio.run(ai._hermes_chat("modele", "consigne", DEMANDE, provider="custom:mistral"))
    assert vu["appels"] == 0


def test_opencode_free_reglages_et_routage(monkeypatch):
    assert len(ai.OPENCODE_FREE_MODELES) == 13 and "big-pickle" in ai.OPENCODE_FREE_MODELES
    p, modele, _ = asyncio.run(ai.resolve_ai_config({"ai_provider": "opencode", "ai_model": "nemotron-3-ultra-free"}))
    assert (p, modele) == ("hermes", "opencode:nemotron-3-ultra-free")
    assert ai.est_externe_via_hermes(p, modele) and not ai.est_mistral_via_hermes(p, modele)
    p, modele, _ = asyncio.run(ai.resolve_ai_config({"ai_provider": "opencode", "ai_model": "modele-inconnu"}))
    assert modele == "opencode:" + ai.OPENCODE_FREE_MODELES[0]
    vu = _passerelle(monkeypatch)
    asyncio.run(ai._call_externe_via_hermes(model="opencode:big-pickle", system_prompt="s", user_message=DEMANDE))
    assert vu["corps"]["provider"] == "opencode-free" and vu["corps"]["model"] == "big-pickle"
    assert "LUMIA" not in _texte_envoye(vu)
