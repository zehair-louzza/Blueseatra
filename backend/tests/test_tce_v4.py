"""Régressions du raccordement TCE v4 au SaaS, sans réseau ni base réelle."""
import asyncio
import copy
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://127.0.0.1:1")
import pdfplumber
import pytest

import ai_service
import matching
import pdf_service
import tce_v4 as tce
import quote_scenarios

SOURCE = "Fourniture et pose d'un chauffe-eau vertical 150 L."


def extracted():
    return {"description": SOURCE, "line_items": [{
        "label": "Chauffe-eau vertical 150 L", "qty": 1, "unit": "u",
        "action": "fournir_et_poser", "lot_tce": "11", "preuve": SOURCE,
        "quantite_preuve": "un chauffe-eau",
    }], "labor_hours": 20, "crew_size": 4, "travel_days": 3}


def quote():
    return {"status": "draft", "number": "TEST-TCE", "client": "Test", "site": "Test",
            "total_ht": 100, "total_vat": 0, "total_ttc": 100, "version": 1,
            "meta": {"tce_version": tce.VERSION, "reserves": ["Support à vérifier."],
                     "exclusions": "Évier neuf exclu."},
            "lines": [{"line_type": "material", "qty": 1, "unit": "u",
                       "description": "Fourniture et pose : chauffe-eau",
                       "unit_price_ht": 100, "line_ht": 100, "status": "confirmed",
                       "supplier": "FOURNISSEUR_INTERNE", "matched_item_code": "CODE_INTERNE"}],
            "pricing_snapshot": {"catalog_name": "CATALOGUE_SECRET"}}


def test_manifest():
    assert tce.manifest()["skills"] == 25
    assert len(tce.manifest()["sha256"]) == 64


def test_prompt_short_no_estimates():
    assert len(ai_service.EXTRACTION_SYSTEM) < 12000
    assert "minimum réaliste" not in ai_service.EXTRACTION_SYSTEM
    assert "crew_size restent null" in ai_service.EXTRACTION_SYSTEM


def test_explicit_and_capacity():
    result = tce.protect_extraction(extracted(), SOURCE)
    assert result["line_items"][0]["qty"] == 1
    assert result["labor_hours"] is None
    assert result["travel_days"] is None
    assert result["crew_size"] is None


@pytest.mark.parametrize("value,proof", [(150, "150 L"), (7, ""), (2, "un chauffe-eau"),
                                       (True, "un chauffe-eau"), (float("nan"), "un chauffe-eau")])
def test_wrong_quantities_nulled(value, proof):
    data = extracted()
    data["line_items"][0].update(qty=value, quantite_preuve=proof)
    assert tce.protect_extraction(data, SOURCE)["line_items"][0]["qty"] is None


def test_missing_quantity_not_one_even_matched():
    data = {"line_items": [{"label": "Prise 16A", "qty": None, "unit": "u"}]}
    catalog = [{"item_code": "P", "item_label": "Prise 16A", "unit": "u", "unit_price_ht": 10}]
    lines, _, _ = matching.build_quote_lines(data, catalog)
    line = next(x for x in lines if x.get("request_label") == "Prise 16A")
    assert line["qty"] is None and line["line_ht"] is None and line["status"] == "to_confirm"


def test_no_sink_purchase_for_connection():
    data = {"line_items": [{"label": "Évier", "qty": 1, "unit": "u", "action": "raccorder"}]}
    catalog = [{"item_code": "E", "item_label": "Évier", "unit": "u", "unit_price_ht": 200}]
    lines, _, _ = matching.build_quote_lines(data, catalog)
    line = next(x for x in lines if x.get("request_label") == "Évier")
    assert line["matched_item_code"] is None and line["unit_price_ht"] is None
    assert line["description"].startswith("Raccordement")


def test_checklist_kept_out_of_commercial_lines():
    original = tce.protect_extraction(extracted(), SOURCE)
    result = asyncio.run(ai_service.expand_work_into_materials(original, {}))
    assert len(result["line_items"]) == 1
    checks = result["_tce_nomenclature"]
    assert any("siphon" in c["details"].lower() for c in checks)
    assert any("évacuation" in c["details"].lower() for c in checks)
    assert all(c["quantity"] is None and c["rule_id"] is None for c in checks)
    assert {c["lot"] for c in checks} == {"11"}


def test_mixed_lots_do_not_share_global_category():
    rows = [{"line_type": "material", "description": "Vasque", "qty": None},
            {"line_type": "material", "description": "Prises électriques", "qty": None},
            {"line_type": "material", "description": "VMC", "qty": None}]
    lots = [x["description"] for x in matching.wrap_in_lots(rows) if x["line_type"] == "lot"]
    assert set(lots) == {"Plomberie et sanitaires", "Électricité courants forts", "Ventilation"}


@pytest.mark.parametrize("field,value", [("qty", None), ("qty", 0), ("qty", -1),
                                       ("unit_price_ht", None), ("line_ht", None),
                                       ("unit_price_ht", float("inf"))])
def test_publication_blockers(field, value):
    q = quote()
    q["lines"][0][field] = value
    assert tce.blockers(q)


def test_price_zero_requires_human_confirmation():
    q = quote()
    q["lines"][0].update(unit_price_ht=0, line_ht=0, status="proposed")
    q["total_ht"] = q["total_ttc"] = 0
    assert tce.blockers(q)
    q["lines"][0]["status"] = "confirmed"
    assert not tce.blockers(q)


def test_review_invalidated_by_changes():
    q = quote()
    q["meta"]["tce_review_digest"] = tce.review_digest(q)
    assert tce.reviewed(q)
    q["lines"][0]["qty"] = 2
    assert not tce.reviewed(q)


def test_client_projection_hides_internal_fields():
    text = json.dumps(tce.client_quote(quote()), ensure_ascii=False)
    for secret in ("FOURNISSEUR_INTERNE", "CODE_INTERNE", "CATALOGUE_SECRET", "tce_review_digest"):
        assert secret not in text
    assert "Support à vérifier" in text and "Évier neuf exclu" in text


def test_client_unit_price_is_sale_price_not_purchase():
    q = quote()
    q["lines"][0].update(qty=2, unit_price_ht=100, margin=20, line_ht=240)
    row = tce.client_quote(q)["lines"][0]
    assert row["unit_price_ht"] == 120
    assert "margin" not in row


def pdf_text(q):
    content = pdf_service.generate_quote_pdf(q, "Entreprise Test", {})
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_incomplete_pdf_no_acceptance_no_hidden_data():
    q = quote()
    q["lines"][0]["line_ht"] = None
    text = pdf_text(q)
    assert "BROUILLON NON CONTRACTUEL" in text
    assert "Bon pour accord" not in text and "Net à payer" not in text
    assert "FOURNISSEUR_INTERNE" not in text and "CODE_INTERNE" not in text
    assert "Source tarifaire" not in text and "293 B" not in text
    assert "Support à vérifier" in text and "Évier neuf exclu" in text


def test_final_pdf_incomplete_refused():
    q = quote()
    q.update(status="validated")
    q["lines"][0]["qty"] = None
    with pytest.raises(ValueError):
        pdf_text(q)


def test_complete_pdf_shows_only_complete_total():
    q = quote()
    q["status"] = "validated"
    text = pdf_text(q)
    assert "Net à payer" in text and "Bon pour accord" in text


def test_fallback_does_not_add_purchase():
    data = {"_tce_version": tce.VERSION, "line_items": [
        {"label": "évier existant", "action": "raccorder", "qty": 1}]}
    text = matching.build_works_description(data)
    assert "Raccordement" in text and "Fourniture" not in text


def test_variant_proofs_and_quantities_independent():
    data = {"quote_options": [
        {"line_items": [{"description": "Chauffe-eau", "quantity": 1, "unit": "u",
                         "preuve": SOURCE, "quantite_preuve": "un chauffe-eau"}]},
        {"line_items": [{"description": "Vasque", "quantity": 9, "unit": "u"}]},
    ]}
    out = tce.protect_extraction(data, SOURCE)
    assert out["quote_options"][0]["line_items"][0]["quantity"] == 1
    assert out["quote_options"][1]["line_items"][0]["quantity"] is None


def test_variant_fallback_never_invents_one():
    scenarios = quote_scenarios.split_quote_scenarios(
        {"_tce_version": tce.VERSION}, "soit pose évier ou soit pose lavabo")
    assert len(scenarios) == 2
    assert all(s["line_items"][0]["quantity"] is None for s in scenarios)


def test_wrong_object_and_action_do_not_authorize_purchase():
    source = "raccorder deux éviers existants dans une pièce"
    data = {"line_items": [{"label": "Évier neuf", "action": "fournir_et_poser",
                           "qty": 1, "unit": "u", "preuve": source,
                           "quantite_preuve": "une pièce"}]}
    row = tce.protect_extraction(data, source)["line_items"][0]
    assert row["qty"] is None
    assert row["tce_fourniture_autorisee"] is False


@pytest.mark.parametrize("source,qproof", [
    ("Fourniture de 3 siphons et raccordement de 2 éviers", "3 siphons"),
    ("Pose de 2 éviers, fourniture assurée directement par le client", "2 éviers"),
])
def test_mixed_supply_or_client_supply_never_auto_buys(source, qproof):
    data = {"line_items": [{"label": "Évier", "action": "fournir_et_poser",
                           "qty": 3, "unit": "u", "preuve": source, "quantite_preuve": qproof}]}
    row = tce.protect_extraction(data, source)["line_items"][0]
    assert not row["tce_fourniture_autorisee"]
    assert row["qty"] is None


@pytest.mark.parametrize("action", [None, "raccorder", "poser", "mettre_en_service"])
def test_ambiguous_or_service_action_not_purchase(action):
    data = {"_tce_version": tce.VERSION, "line_items": [
        {"label": "Évier", "qty": 1, "unit": "u", "action": action}]}
    catalog = [{"item_code": "E", "item_label": "Évier", "unit": "u", "unit_price_ht": 200}]
    lines, _, _ = matching.build_quote_lines(data, catalog)
    row = next(x for x in lines if x.get("request_label") == "Évier")
    assert row["unit_price_ht"] is None


@pytest.mark.parametrize("field", ["client_final", "total_ttc", "currency", "created_at"])
def test_review_covers_public_fields(field):
    q = quote()
    q["meta"]["tce_review_digest"] = tce.review_digest(q)
    q[field] = "changed"
    assert not tce.reviewed(q)


def test_ttc_total_tamper_blocked():
    q = quote()
    q["total_ttc"] = 999
    assert tce.blockers(q)


def test_rematch_selects_original_variant():
    data = {"quote_options": [
        {"label": "A", "line_items": [{"label": "Évier"}]},
        {"label": "B", "line_items": [{"label": "Vasque"}]},
    ]}
    result = quote_scenarios.scenario_for_quote(data, "", {"option_count": 2, "option_label": "B"})
    assert result["line_items"] == [{"label": "Vasque"}]
    with pytest.raises(ValueError):
        quote_scenarios.scenario_for_quote(data, "", {"option_count": 2, "option_label": "C"})


def test_v4_description_never_uses_unreviewed_ai_prose(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("No AI prose before review")
    monkeypatch.setattr(ai_service, "generate_ai_works_narrative", forbidden)
    data = tce.protect_extraction(extracted(), SOURCE)
    result = asyncio.run(ai_service.build_works_description_ai(data, {}))
    assert "Chauffe-eau" in result and "Fourniture et pose" in result


def test_atomic_approval_and_send(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    import quote_approval
    from models_sql import Quote
    from pg_adapter import _to_dict
    q = quote()
    row = Quote(**{**q, "id": "Q1", "tenant_id": "T1"})
    session = SimpleNamespace(saved=[], commits=0)
    async def execute(stmt):
        sql = str(stmt)
        assert "FOR UPDATE" in sql and "tenant_id" in sql
        return SimpleNamespace(scalar_one_or_none=lambda: row)
    async def commit():
        session.commits += 1
    session.execute, session.commit, session.add = execute, commit, session.saved.append
    @asynccontextmanager
    async def factory():
        yield session
    monkeypatch.setattr(quote_approval, "tenant_session", factory)
    digest = tce.review_digest(_to_dict(Quote, row))
    result = asyncio.run(quote_approval.transition("T1", "Q1", "reviewer", "validated", digest, True))
    assert result["status"] == "validated" and row.status == "validated"
    assert session.commits == 1 and len(session.saved) == 1
    assert session.saved[0].snapshot["meta"]["tce_reviewed_by"] == "reviewer"
    assert asyncio.run(quote_approval.transition("T1", "Q1", "reviewer", "sent"))["status"] == "sent"


def test_stale_approval_never_commits(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    import quote_approval
    from fastapi import HTTPException
    from models_sql import Quote
    row = Quote(**{**quote(), "id": "Q1", "tenant_id": "T1"})
    async def execute(stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: row)
    session = SimpleNamespace(execute=execute)
    @asynccontextmanager
    async def factory():
        yield session
    monkeypatch.setattr(quote_approval, "tenant_session", factory)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(quote_approval.transition("T1", "Q1", "reviewer", "validated", "old-digest", True))
    assert exc.value.status_code == 409
    assert row.status == "draft"


def test_delayed_edit_after_validation_is_rejected(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    import server
    q = quote()
    q.update(id="Q1", tenant_id="T1")
    captured = {}
    async def read(*args, **kwargs):
        return copy.deepcopy(q)  # request read the draft before another validation
    async def update(flt, change):
        captured.update(flt)
        return SimpleNamespace(matched_count=0)  # row is now validated/sent
    fake = SimpleNamespace(quotes=SimpleNamespace(find_one=read, update_one=update))
    monkeypatch.setattr(server, "db", fake)
    actor = SimpleNamespace(tenant_id="T1", email="test-only")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.update_quote("Q1", {}, actor))
    assert exc.value.status_code == 409
    assert captured == {"id": "Q1", "tenant_id": "T1", "status": "draft", "version": 1}
