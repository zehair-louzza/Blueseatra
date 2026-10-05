"""Entrée modèle dédoublonnée sans effacer une information source unique."""
import asyncio
import json

import pytest
import ai_service as ai

NATIVE = (
    "Client : Démonstration\nDésignation Unité Qté P.U. HT Total HT\n"
    "Fourniture et pose de prises u 14 10,00 € 140,00 €\n"
    "Pose de douche u 1 100,00 € 100,00 €\n"
    "Peinture exclue. Accès à confirmer."
)
TABLE = (
    "\n\n=== Tableaux détectés ===\n[Tableau p.1.1]\n"
    "| Désignation | Unité | Qté | P.U. HT | Total HT |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| Fourniture et pose de prises | u | 14 | 10,00 € | 140,00 € |\n"
    "| Pose de douche | u | 1 | 100,00 € | 100,00 € |"
)


def test_verified_duplicate_tables_removed_but_native_kept():
    assert ai._deduplicate_pdf_tables(NATIVE + TABLE) == NATIVE


def test_unique_table_cell_never_removed():
    text = NATIVE + TABLE.replace("Pose de douche", "Pose de lavabo")
    assert ai._deduplicate_pdf_tables(text) == text


def test_unknown_text_in_appended_section_is_preserved():
    text = NATIVE + TABLE + "\nRaccordement gaz explicitement exclu."
    assert ai._deduplicate_pdf_tables(text) == text


def test_no_marker_or_empty_table_is_unchanged():
    assert ai._deduplicate_pdf_tables(NATIVE) == NATIVE
    text = NATIVE + "\n=== Tableaux détectés ===\n"
    assert ai._deduplicate_pdf_tables(text) == text


def test_prompt_contains_real_taxonomy_and_precise_actions():
    assert "14=Électricité courants forts" in ai.EXTRACTION_SYSTEM
    assert "11=Plomberie et sanitaires" in ai.EXTRACTION_SYSTEM
    assert "13=Ventilation" in ai.EXTRACTION_SYSTEM
    assert "numéros de lots du document" in ai.EXTRACTION_SYSTEM
    assert "Pose" in ai.EXTRACTION_SYSTEM and "poser" in ai.EXTRACTION_SYSTEM


def test_short_table_proofs_only_with_verified_backend_binding(monkeypatch):
    seen = {}

    async def fake(**kwargs):
        seen.update(kwargs)
        return json.dumps({"confidence": 0.5, "line_items": [{
            "label": "Fourniture et pose de prises", "qty": None,
            "unit": "", "preuve": "", "quantite_preuve": "",
            "action": "poser", "lot_tce": "00",
        }]}), "GPT-OSS-20B"

    monkeypatch.setattr(ai, "_call_structuring_cascade", fake)
    result = asyncio.run(ai.extract_request_data(
        NATIVE + TABLE, {"ai_provider": "hermes", "ai_model": "gpt-oss:20b"}, from_file=True,
    ))
    row = result["line_items"][0]
    assert "TABLEAUX SOURCE IDENTIFIÉS" in seen["system_prompt"]
    assert row["qty"] == 14 and row["unit"] == "u"
    assert row["lot_tce"] == "14" and row["action"] == "fournir_et_poser"
    assert row["preuve"] in (NATIVE + TABLE) and row["preuve_valide"]
    assert result["_input_preparation"]["duplicate_tables_removed"]
    assert not result["_input_preparation"]["truncated"]
    import matching
    lines, _, _ = matching.build_quote_lines(result, [])
    material = next(line for line in lines if line.get("tce_id") == row["tce_id"])
    assert material["tce_source_row_id"] == row["tce_source_row_id"]
    assert material["tce_source_designation"] == "Fourniture et pose de prises"
    assert material["tce_correction"]["approbation"] is False


@pytest.mark.parametrize("engine,truncated", [
    ("GPT-OSS-20B", False), ("GPT-OSS-20B (compact)", True),
])
def test_warning_only_if_the_used_stage_really_truncated(monkeypatch, engine, truncated):
    seen = {}

    async def fake(**kwargs):
        seen.update(kwargs)
        return json.dumps({"line_items": [], "confidence": 0.5}), engine

    monkeypatch.setattr(ai, "_call_structuring_cascade", fake)
    monkeypatch.setattr(ai, "EXTRACTION_DOC_MAX", 9000)
    monkeypatch.setattr(ai, "EXTRACTION_DOC_COMPACT_MAX", 3000)
    result = asyncio.run(ai.extract_request_data(
        "Demande sans prix. " * 200,
        {"ai_provider": "hermes", "ai_model": "gpt-oss:20b"}, from_file=True,
    ))
    assert bool(result["_input_preparation"]["truncated"]) is truncated
    assert any("Document long" in x for x in result["_tce_issues"]) is truncated
    assert "TABLEAUX SOURCE IDENTIFIÉS" not in seen["system_prompt"]
