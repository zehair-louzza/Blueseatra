"""Quote PDF generation using reportlab."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

NAVY = colors.HexColor("#1A2B45")
TEAL = colors.HexColor("#3F8F8A")
LIGHT = colors.HexColor("#E7F3F2")


def generate_quote_pdf(quote: dict, tenant_name: str = "Blueseatra") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading1"], textColor=NAVY, fontSize=22)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#6A7B8A"), fontSize=9)
    normal = styles["Normal"]
    elems = []

    elems.append(Paragraph(tenant_name, h))
    elems.append(Paragraph(f"Devis / Quote {quote.get('number', '')}", sub))
    elems.append(Spacer(1, 8))

    cur = quote.get("currency", "EUR")
    meta = [
        ["Client", quote.get("client") or "-", "Statut / Status", quote.get("status", "draft")],
        ["Site", quote.get("site") or "-", "Version", str(quote.get("version", 1))],
    ]
    mt = Table(meta, colWidths=[70, 180, 90, 80])
    mt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), TEAL),
        ("TEXTCOLOR", (2, 0), (2, -1), TEAL),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(mt)
    elems.append(Spacer(1, 12))

    head = ["Description", "Cat. item", "Qty", "Unit", "PU HT", "TVA%", "Total HT"]
    data = [head]
    for l in quote.get("lines", []):
        data.append([
            Paragraph(str(l.get("description") or l.get("request_label") or "-"), normal),
            l.get("matched_item_code") or "—",
            _fmt(l.get("qty")),
            l.get("unit") or "-",
            _money(l.get("unit_price_ht")),
            _fmt(l.get("vat_rate")),
            _money(l.get("line_ht")),
        ])
    t = Table(data, colWidths=[150, 70, 40, 40, 60, 45, 65], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDE3EA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 12))

    totals = [
        ["Total HT", _money(quote.get("total_ht"), cur)],
        ["TVA / VAT", _money(quote.get("total_vat"), cur)],
        ["Total TTC", _money(quote.get("total_ttc"), cur)],
    ]
    tt = Table(totals, colWidths=[120, 100], hAlign="RIGHT")
    tt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 1, NAVY),
        ("TEXTCOLOR", (0, 2), (-1, 2), NAVY),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(tt)
    elems.append(Spacer(1, 18))
    elems.append(Paragraph(
        f"Pricing source: catalog snapshot v{quote.get('pricing_snapshot', {}).get('version_number', '-')} "
        f"({quote.get('pricing_snapshot', {}).get('catalog_name', '-')}). "
        "Prices are deterministic from the active catalog; AI does not set prices.", sub))

    doc.build(elems)
    return buf.getvalue()


def _money(v, cur=""):
    if v is None:
        return "—"
    try:
        s = f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)
    return f"{s} {cur}".strip()


def _fmt(v):
    if v is None:
        return "-"
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:g}"
    except (TypeError, ValueError):
        return str(v)
