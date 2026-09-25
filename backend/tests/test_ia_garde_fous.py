"""Ticket #88 : schéma strict, aucun prix venu de l'IA, coupure d'urgence, journal par appel."""
import asyncio, logging, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import ia_garde_fous as g


def test_prix_tva_et_marges_de_l_ia_sont_retires_et_signales():
    out = g.valider_extraction({
        "client_final": "Carrefour", "urgency": "URGENT !", "confidence": "85",
        "line_items": [{"label": "Dalle LED", "qty": "6", "unit_price_ht": 25, "tva": 20,
                        "details": {"prix": 12}}],
        "total_ht": 150, "_structuring_engine": "qwen",
    })
    ligne = out["line_items"][0]
    assert "unit_price_ht" not in ligne and "tva" not in ligne and "prix" not in ligne["details"]
    assert "total_ht" not in out and out["_structuring_engine"] == "qwen"
    assert ligne["qty"] == 6.0 and out["urgency"] == "urgent" and out["confidence"] == 0.85
    assert any("prix ignoré" in a for a in out["_anomalies_schema"])


def test_types_incoherents_convertis_sans_planter():
    out = g.valider_extraction({"line_items": ["texte libre", {"label": None, "qty": "-3", "included_items": "vis, chevilles"}],
                                "labor_hours": "", "quote_options": "aucune", "urgency": None})
    assert len(out["line_items"]) == 1
    li = out["line_items"][0]
    assert li["label"] == "" and li["qty"] is None and li["included_items"] == ["vis", "chevilles"]
    assert out["labor_hours"] is None and out["quote_options"] == [] and out["urgency"] == "normal"


def test_sortie_non_objet_refusee():
    with pytest.raises(ValueError):
        g.valider_extraction(["pas", "un", "objet"])


def test_coupure_arret_et_repli(monkeypatch):
    monkeypatch.delenv("BLUESEATRA_IA_COUPURE", raising=False)
    assert g.appliquer_coupure("hermes", "qwen", "") == ("hermes", "qwen", "")
    monkeypatch.setenv("BLUESEATRA_IA_COUPURE", "arret")
    with pytest.raises(g.IACoupee):
        g.appliquer_coupure("hermes", "qwen", "")
    monkeypatch.setenv("BLUESEATRA_IA_COUPURE", "repli")
    with pytest.raises(g.IACoupee):            # repli demandé mais non configuré : refus explicite
        g.appliquer_coupure("hermes", "qwen", "")
    monkeypatch.setenv("BLUESEATRA_IA_REPLI_PROVIDER", "openai")
    monkeypatch.setenv("BLUESEATRA_IA_REPLI_MODEL", "gpt-4o-mini")
    assert g.appliquer_coupure("hermes", "qwen", "k")[:2] == ("openai", "gpt-4o-mini")


def test_journal_par_appel_sans_contenu(caplog):
    @g.journaliser("hermes")
    async def appel(model, system_prompt, user_message, role=None):
        return "réponse"
    with caplog.at_level(logging.INFO, logger="blueseatra.ia"):
        asyncio.run(appel(model="qwen2.5:7b", system_prompt="S", user_message="donnée client secrète", role="extract"))
    msg = caplog.records[-1].getMessage()
    assert "modele=qwen2.5:7b" in msg and "succes=True" in msg and "role=extract" in msg
    assert "secrète" not in msg


def test_extraction_coupee_echoue_proprement(monkeypatch):
    monkeypatch.setenv("BLUESEATRA_IA_COUPURE", "arret")
    ai = pytest.importorskip("ai_service")
    with pytest.raises(g.IACoupee):
        asyncio.run(ai.extract_request_data("Remplacer 6 dalles LED", {}, from_file=True))
