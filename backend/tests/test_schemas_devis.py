"""Schémas JSON des fonctions extraire_demande_travaux / decrire_demande_travaux (29/09/2026)."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
jsonschema = pytest.importorskip("jsonschema")
ai = pytest.importorskip("ai_service")
import ia_garde_fous as g

LIGNE = {"label": "nacelle ciseaux 8 m", "qty": 2, "unit": "j", "line_type_hint": "main_work",
         "famille_poste": "moyens_acces_engins", "included_items": [], "notes": "hauteur 6 m"}


def _extraction_exemple():
    return {"donneur_d_ordre": "Foncia", "donneur_email": "", "donneur_address": "", "client_name": "Picard",
            "client_final": "Picard", "client_email": "", "client_phone": "", "client_address": "",
            "location": "12 rue X 78150 Le Chesnay", "work_type": "electricite", "description": "Remplacement de spots",
            "urgency": "normal", "requested_date": None, "di_number": "", "language": "fr", "confidence": 0.8,
            "labor_hours": 4, "travel_days": 1, "crew_size": 2, "line_items": [LIGNE], "quote_options": [],
            "moyens_acces_engins": ["nacelle ciseaux 8 m (hauteur 6 m)"], "reserves": ["Confirmer la hauteur"],
            "postes_verifies": ["preliminaires", "moyens_acces_engins"]}


def test_schemas_charges_valides_et_dans_la_consigne():
    jsonschema.Draft202012Validator.check_schema(ai.SCHEMA_EXTRACTION)
    jsonschema.Draft202012Validator.check_schema(ai.SCHEMA_DESCRIPTIF)
    assert '"postes_verifies"' in ai.EXTRACTION_SYSTEM and "famille_poste" in ai.EXTRACTION_SYSTEM
    for champ in ("preliminaires", "etapes", "controles_fin_travaux"):
        assert champ in ai.SCHEMA_DESCRIPTIF["required"] and champ in ai.DESCRIPTION_SYSTEM


def test_exemple_conforme_passe_les_garde_fous_et_le_moteur():
    ex = _extraction_exemple()
    jsonschema.validate(ex, ai.SCHEMA_EXTRACTION)
    r = g.valider_extraction(dict(ex))
    assert r["reserves"] == ["Confirmer la hauteur"] and r["line_items"][0]["famille_poste"] == "moyens_acces_engins"


def test_schema_transmis_a_ollama(monkeypatch):
    vu = {}
    async def _chat(model, sp, um, **kw):
        vu.update(kw); return "{}"
    monkeypatch.setattr(ai, "IA_VIA_HERMES", True)
    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "https://hermes.exemple")
    monkeypatch.setattr(ai, "_hermes_chat", _chat)
    asyncio.run(ai._call_hermes_ollama("qwen2.5:7b", "s", "u", json_schema=ai.SCHEMA_EXTRACTION))
    assert vu["json_schema"] is ai.SCHEMA_EXTRACTION


def test_descriptif_avec_preliminaires_et_controles(monkeypatch):
    async def _faux(*a, **k):
        return json.dumps({"description": "Remplacement des luminaires du plateau.",
                           "preliminaires": ["Consigner le circuit concerné au tableau."],
                           "etapes": ["Baliser la zone.", "Déposer les spots existants.", "Poser les spots LED."],
                           "controles_fin_travaux": ["Vérifier le fonctionnement de chaque spot."]})
    async def _ctx(_t): return ""
    monkeypatch.setattr(ai, "_call_describe", _faux)
    monkeypatch.setattr(ai, "_web_context_sans_prix", _ctx)
    texte = asyncio.run(ai.build_works_description_ai({"description": "Remplacement de spots", "line_items": [LIGNE]},
                                                      {"ai_provider": "hermes"}))
    assert "Préliminaires :\n- Consigner" in texte and "Contrôles de fin de travaux :\n- Vérifier" in texte
    assert texte.index("Préliminaires") < texte.index("Déroulement") < texte.index("Contrôles")


def test_hermes_occupe_429_attend_puis_reussit(monkeypatch):
    import httpx
    reponses = [httpx.Response(429, json={"error": {"message": "Too many concurrent runs (max 1)"}}),
                httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": 1}"}}]})]
    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return reponses.pop(0)
    attentes = []
    async def _dormir(s): attentes.append(s)
    monkeypatch.setattr(ai.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(ai.asyncio, "sleep", _dormir)
    monkeypatch.setattr(ai, "HERMES_GATEWAY_URL", "https://hermes.exemple")
    monkeypatch.setattr(ai, "HERMES_ATTENTES_429", (10, 30))
    assert asyncio.run(ai._hermes_chat("qwen2.5:7b", "s", "u")) == '{"ok": 1}'
    assert attentes == [10]
