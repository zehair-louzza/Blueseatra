"""
Test e2e du pipeline d'extraction : génère un PDF de devis avec TABLEAU,
puis vérifie parsing déterministe (pdfplumber) + structuration LLM.
Lancé une fois via `python test_extraction.py` — pas de serveur long.
"""
import os
import io
import asyncio
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

import extract_core


def make_sample_pdf() -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("DEMANDE DE DEVIS — Réf. DI 2026-0451 (URGENT)", styles["Title"]),
        Paragraph("Donneur d'ordre : SCI Les Tilleuls — Client : Boulangerie Maison Petit — "
                  "Site d'intervention : 14 rue des Arts, 59000 Lille", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Prestations demandées :", styles["Heading2"]),
    ]
    data = [
        ["Désignation", "Qté", "Unité", "P.U. HT (€)", "Total HT (€)"],
        ["Pose de spots LED encastrés 230V", "12", "u", "24,50", "294,00"],
        ["Remplacement tableau électrique", "1", "ens", "680,00", "680,00"],
        ["Câble R2V 3G2.5", "80", "ml", "1,90", "152,00"],
        ["Main d'oeuvre électricien", "16", "h", "42,00", "672,00"],
    ]
    t = Table(data, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


async def main():
    pdf = make_sample_pdf()
    print(f"PDF généré : {len(pdf)} octets")

    # 1) Étape déterministe seule (aucun LLM) — le cœur de la valeur pour les tableaux.
    parsed = extract_core.parse_pdf(pdf)
    print(f"\n[1] Parsing déterministe : {parsed['text_len']} car., tableaux détectés = {parsed['has_tables']}")
    assert parsed["has_tables"], "ÉCHEC : le tableau n'a pas été extrait par pdfplumber"
    assert "spots LED" in parsed["markdown"], "ÉCHEC : contenu tableau manquant"
    print("    -> Tableau extrait avec structure. Extrait markdown :")
    print("    " + parsed["markdown"][:300].replace("\n", "\n    "))

    # 2) Pipeline complet parse -> LLM (provider démo = Emergent, hors VPS).
    provider = os.environ.get("EXTRACT_PROVIDER", "emergent")
    print(f"\n[2] Structuration LLM (provider={provider}, modèle={os.environ.get('DEMO_MODEL','gpt-5.4')})...")
    result = await extract_core.extract(pdf, provider=provider)
    items = result.get("requested_items", [])
    parties = result.get("parties", {})
    print(f"    -> {len(items)} lignes structurées ; donneur d'ordre = {parties.get('donneur_ordre')}")
    for it in items:
        print(f"       - {it.get('designation')} | {it.get('quantite')} {it.get('unite')} | {it.get('confiance')}")

    # Contrôles clés : items extraits ET aucun prix reporté.
    assert len(items) >= 3, f"ÉCHEC : trop peu d'items ({len(items)})"
    blob = json.dumps(result, ensure_ascii=False)
    for price_token in ("294", "680", "672", "24,50", "42,00"):
        assert price_token not in blob, f"ÉCHEC : un prix ({price_token}) a fuité dans la sortie"
    assert result.get("pricing_prohibited") is True
    print("\n✅ TEST OK : tableau extrait de façon déterministe, JSON structuré, AUCUN prix reporté.")


if __name__ == "__main__":
    import json
    asyncio.run(main())
