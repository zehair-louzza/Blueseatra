"""Unit tests around the MODIFIED parts of ai_service.py (no network needed):
pdfplumber table extraction, the vision-fallback heuristic on table-heavy PDFs,
model defaults and the Ollama concurrency semaphore.
"""
import asyncio
import io
import os
import sys

import pytest

sys.path.insert(0, "/app/backend")
import ai_service  # noqa: E402


def _table_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    data = [["Designation", "Quantite", "Unite", "Prix"],
            ["Peinture murale deux couches", "20", "m2", "12,50"],
            ["Pose placo BA13", "10", "m2", "28,00"],
            ["Main d'oeuvre qualifiee", "4", "hr", "38,50"]]
    doc.build([
        Paragraph("Demande de devis TEST - remise en etat local technique "
                  "pour le compte de la societe TEST Client SA a Paris.", styles["Normal"]),
        Table(data, style=TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black)])),
    ])
    return buf.getvalue()


class TestPdfExtraction:
    def test_table_pdf_text_and_tables(self):
        pdf = _table_pdf()
        text = ai_service.extract_pdf_text(pdf)
        assert "Peinture murale deux couches" in text
        assert "Tableaux" in text, text[:300]
        assert "| Designation | Quantite | Unite | Prix |" in text, text[-500:]
        assert "| Pose placo BA13 | 10 | m2 | 28,00 |" in text

    def test_table_pdf_not_flagged_for_vision_fallback(self):
        """Regression guard: the added markdown tables must not make a native
        text PDF look 'garbled' and divert it to the (AI) vision pipeline."""
        pdf = _table_pdf()
        text = ai_service.extract_pdf_text(pdf)
        assert ai_service.pdf_needs_vision_fallback(text) is False, \
            "table-heavy native PDF wrongly routed to vision fallback"

    def test_tables_extractor_never_raises(self):
        assert ai_service._extract_pdf_tables_markdown(b"not a pdf at all") == ""
        assert ai_service._extract_pdf_tables_markdown(b"") == ""

    def test_extract_pdf_text_on_plain_pdf(self):
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(72, 700, "Bonjour ceci est une demande de devis de test sans tableau.")
        c.save()
        text = ai_service.extract_pdf_text(buf.getvalue())
        assert "demande de devis" in text
        assert "Tableaux" not in text
        assert ai_service.pdf_needs_vision_fallback(text) is False


class TestConfigDefaults:
    def test_model_defaults(self):
        assert ai_service.HERMES_EXTRACT_MODEL
        assert ai_service.HERMES_REASONING_MODEL
        assert ai_service.HERMES_VISION_MODEL

    def test_semaphore_matches_env(self):
        expected = int(os.environ.get("OLLAMA_MAX_CONCURRENCY", "2"))
        assert isinstance(ai_service._OLLAMA_SEMAPHORE, asyncio.Semaphore)
        assert ai_service._OLLAMA_SEMAPHORE._value == ai_service._OLLAMA_MAX_CONCURRENCY
        assert ai_service._OLLAMA_MAX_CONCURRENCY >= 1
        if "OLLAMA_MAX_CONCURRENCY" in os.environ:
            assert ai_service._OLLAMA_MAX_CONCURRENCY == expected

    def test_semaphore_serializes(self):
        async def scenario():
            sem = ai_service._OLLAMA_SEMAPHORE
            limit = ai_service._OLLAMA_MAX_CONCURRENCY
            running = {"cur": 0, "max": 0}

            async def worker():
                async with sem:
                    running["cur"] += 1
                    running["max"] = max(running["max"], running["cur"])
                    await asyncio.sleep(0.05)
                    running["cur"] -= 1

            await asyncio.gather(*[worker() for _ in range(limit + 3)])
            return running["max"]

        assert asyncio.run(scenario()) <= ai_service._OLLAMA_MAX_CONCURRENCY


class TestNormalizeExtracted:
    def test_normalize_keeps_line_items(self):
        out = ai_service._normalize_extracted({
            "client_name": "ACME", "line_items": [{"description": "Peinture", "quantity": 5}]})
        assert out["line_items"][0]["label"] == "Peinture"
        assert out["line_items"][0]["qty"] == 5
        assert out["client_final"] == "ACME"
        assert out["language"] == "fr"

    def test_normalize_handles_empty(self):
        out = ai_service._normalize_extracted({})
        assert isinstance(out, dict)
        assert out.get("language") == "fr"
