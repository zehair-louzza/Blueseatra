"""Quote PDF generation — professional French "devis / facture pro forma" layout.

Mirrors the customer template:
  - Two-column header: company (left) + client (right)
  - Document title + number + validity + date
  - Centered bold reference line
  - Line items table: N | Designation | Qte | PU | TVA | Total, grouped by category (green section bars)
  - Totals block with TVA breakdown by rate + "Net a payer"
  - Payment terms block + client acceptance box
  - Legal footer with SIRET / TVA / capital / IBAN + "Page x/y" on every page
"""
import io
from collections import defaultdict, OrderedDict

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Table, TableStyle, Paragraph, Spacer,
    KeepTogether, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

NAVY = colors.HexColor("#1A2B45")
GREEN = colors.HexColor("#D8EBE3")        # light muted green section bars
GREEN_LINE = colors.HexColor("#3F8F8A")
GREY = colors.HexColor("#6A7B8A")
BORDER = colors.HexColor("#DDE3EA")

styles = getSampleStyleSheet()
S = {
    "company": ParagraphStyle("company", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, textColor=NAVY, leading=17),
    "subtitle": ParagraphStyle("subtitle", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=8.5, textColor=GREEN_LINE, leading=11),
    "small": ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#2C3E50"), leading=12),
    "small_r": ParagraphStyle("small_r", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#2C3E50"), leading=12, alignment=TA_RIGHT),
    "client_name": ParagraphStyle("client_name", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, textColor=NAVY, leading=13),
    "title": ParagraphStyle("title", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16, textColor=NAVY, leading=18),
    "label": ParagraphStyle("label", parent=styles["Normal"], fontSize=9, textColor=GREY, leading=12),
    "ref": ParagraphStyle("ref", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, leading=14, alignment=TA_CENTER),
    "section": ParagraphStyle("section", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, textColor=NAVY, leading=12),
    "cell": ParagraphStyle("cell", parent=styles["Normal"], fontSize=8.5, leading=11),
    "cell_b": ParagraphStyle("cell_b", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11),
    "th": ParagraphStyle("th", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.white, leading=11),
    "th_r": ParagraphStyle("th_r", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.white, leading=11, alignment=TA_RIGHT),
    "code": ParagraphStyle("code", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=7, textColor=GREY, leading=9),
    "pay": ParagraphStyle("pay", parent=styles["Normal"], fontSize=9, leading=14),
    "accept": ParagraphStyle("accept", parent=styles["Normal"], fontSize=9, leading=13),
    "net_lbl": ParagraphStyle("net_lbl", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, leading=14),
    "net_val": ParagraphStyle("net_val", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, textColor=NAVY, leading=16, alignment=TA_RIGHT),
}


def _money(v, cur="EUR"):
    if v is None:
        return "\u2014"
    try:
        s = f"{float(v):,.2f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(v)
    sym = "\u20ac" if cur in ("EUR", "\u20ac") else cur
    return f"{s} {sym}"


def _fmt(v):
    if v is None:
        return "-"
    try:
        f = float(v)
        if f.is_integer():
            return str(int(f))
        return f"{f:g}".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


class _NumberedCanvas(pdfcanvas.Canvas):
    """Adds 'Page x/y' + legal footer on every page (two-pass)."""
    footer_text = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        w, _ = A4
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.5)
        self.line(18 * mm, 16 * mm, w - 18 * mm, 16 * mm)
        self.setFont("Helvetica", 6.5)
        self.setFillColor(GREY)
        lines = (self.footer_text or "").split("\n")
        y = 13 * mm
        for ln in lines[:2]:
            self.drawCentredString(w / 2, y, ln.strip())
            y -= 3.4 * mm
        self.setFont("Helvetica", 7)
        self.drawRightString(w - 18 * mm, 13 * mm, f"Page {self._pageNumber}/{total}")


def _profile(profile, tenant_name):
    p = dict(profile or {})
    p.setdefault("company_name", tenant_name or "Blueseatra")
    return p


def generate_quote_pdf(quote: dict, tenant_name: str = "Blueseatra", profile: dict = None) -> bytes:
    p = _profile(profile, tenant_name)
    cur = quote.get("currency", "EUR")
    buf = io.BytesIO()

    legal_bits = []
    if p.get("siret"):
        legal_bits.append(f"SIRET : {p['siret']}")
    if p.get("tva_intra"):
        legal_bits.append(f"TVA intra. : {p['tva_intra']}")
    if p.get("capital"):
        legal_bits.append(f"Capital : {p['capital']}")
    if p.get("ape"):
        legal_bits.append(f"Code APE : {p['ape']}")
    if p.get("assurance"):
        legal_bits.append(f"Assurance : {p['assurance']}")
    if p.get("iban"):
        legal_bits.append(f"IBAN : {p['iban']}")
    addr_bits = [b for b in [p.get("company_name"), p.get("address_line1"), p.get("address_line2"), p.get("country")] if b]
    contact_bits = [b for b in [(f"T\u00e9l : {p['phone']}" if p.get("phone") else None), p.get("email")] if b]
    footer_line1 = " \u2014 ".join(addr_bits + contact_bits)
    footer_line2 = " \u2014 ".join(legal_bits)
    _NumberedCanvas.footer_text = (footer_line1 + "\n" + footer_line2).strip()

    doc = BaseDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=22 * mm,
                          leftMargin=18 * mm, rightMargin=18 * mm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame])])

    e = []

    # ---- Header: two columns -------------------------------------------------
    left = [Paragraph(p.get("company_name", ""), S["company"])]
    if p.get("subtitle"):
        left.append(Paragraph(p["subtitle"], S["subtitle"]))
    left.append(Spacer(1, 4))
    for k in ["address_line1", "address_line2", "country"]:
        if p.get(k):
            left.append(Paragraph(p[k], S["small"]))
    if p.get("phone"):
        left.append(Paragraph(f"T\u00e9l : {p['phone']}", S["small"]))
    if p.get("email"):
        left.append(Paragraph(p["email"], S["small"]))

    right = [Paragraph("DESTINATAIRE", S["label"]),
             Paragraph(quote.get("client") or "\u2014", S["client_name"])]
    if quote.get("site"):
        right.append(Paragraph(quote["site"], S["small"]))

    header = Table([[left, right]], colWidths=[doc.width * 0.58, doc.width * 0.42])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    e.append(header)
    e.append(Spacer(1, 14))

    # ---- Title block: number / validity (left) + date (right) ----------------
    is_proforma = quote.get("doc_type", "proforma") == "proforma"
    title_txt = "DEVIS \u2013 FACTURE PRO FORMA" if is_proforma else "DEVIS"
    validity = p.get("validity") or "3 mois"
    date_str = (quote.get("created_at") or "")[:10]
    if date_str:
        y, m, d = (date_str.split("-") + ["", "", ""])[:3]
        date_str = f"{d}/{m}/{y}" if y else date_str
    tl = [Paragraph(title_txt, S["title"]),
          Paragraph(f"N\u00b0 {quote.get('number', '')}", S["label"]),
          Paragraph(f"Valable {validity}", S["label"])]
    tr = [Paragraph(f"En date du {date_str}" if date_str else "", S["small_r"])]
    title_tbl = Table([[tl, tr]], colWidths=[doc.width * 0.6, doc.width * 0.4])
    title_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    e.append(title_tbl)
    e.append(Spacer(1, 8))

    # ---- Reference line (centered, bold) -------------------------------------
    ref = quote.get("object") or " \u2013 ".join([b for b in [quote.get("client"), quote.get("site")] if b])
    if ref:
        e.append(Table([[Paragraph(ref, S["ref"])]], colWidths=[doc.width],
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F8F7")),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LINEABOVE", (0, 0), (-1, 0), 1, GREEN_LINE),
                           ("LINEBELOW", (0, 0), (-1, 0), 1, GREEN_LINE),
                       ])))
        e.append(Spacer(1, 8))

    # ---- Reference metadata (request N / DI / client final / deadline) -------
    meta = quote.get("meta") or {}
    chips = []
    if meta.get("request_number"):
        chips.append(("R\u00e9f. demande", str(meta["request_number"])))
    if meta.get("di_number"):
        chips.append(("N\u00b0 dossier DI", str(meta["di_number"])))
    if meta.get("client_final") or quote.get("client_final"):
        chips.append(("Client final", str(meta.get("client_final") or quote.get("client_final"))))
    if meta.get("response_deadline"):
        chips.append(("R\u00e9ponse avant", str(meta["response_deadline"])))
    if chips:
        cells = [Paragraph(f"<font color='#6A7B8A'>{k} :</font> <b>{v}</b>", S["small"]) for k, v in chips]
        # pad to a row layout (max 4 columns)
        meta_tbl = Table([cells], colWidths=[doc.width / len(cells)] * len(cells))
        meta_tbl.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        e.append(meta_tbl)
    e.append(Spacer(1, 6))

    # ---- Line items table: line types, sections, notes, page breaks ----------
    col_w = [22, doc.width - 22 - 40 - 64 - 38 - 72, 40, 64, 38, 72]

    def _header():
        return [Paragraph("N\u00b0", S["th"]), Paragraph("D\u00e9signation", S["th"]),
                Paragraph("Qt\u00e9", S["th_r"]), Paragraph("PU HT", S["th_r"]),
                Paragraph("TVA", S["th_r"]), Paragraph("Total HT", S["th_r"])]

    def _base_style():
        return [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
            ("TOPPADDING", (0, 1), (-1, -1), 5), ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]

    def _section_label(l):
        lt = l.get("line_type")
        if lt == "labor":
            return "MAIN-D'\u0152UVRE"
        if lt == "material":
            return "MAT\u00c9RIAUX & FOURNITURES"
        cat = l.get("category")
        return str(cat).replace("_", " ").upper() if cat else "PRESTATIONS"

    # split into page chunks on page_break lines
    chunks = [[]]
    for l in quote.get("lines", []):
        if l.get("line_type") == "page_break":
            chunks.append([])
        else:
            chunks[-1].append(l)
    chunks = [c for c in chunks if c]

    n = 1
    for ci, chunk in enumerate(chunks):
        data = [_header()]
        style_cmds = _base_style()
        row_idx = 1
        last_section = None
        for l in chunk:
            if l.get("line_type") == "note":
                data.append([Paragraph("<i>" + (l.get("description") or "") + "</i>", S["cell"]), "", "", "", "", ""])
                style_cmds += [
                    ("SPAN", (0, row_idx), (-1, row_idx)),
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#F7FAF9")),
                ]
                row_idx += 1
                continue
            sec = _section_label(l)
            if sec != last_section:
                data.append([Paragraph(sec, S["section"]), "", "", "", "", ""])
                style_cmds += [
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), GREEN),
                    ("SPAN", (0, row_idx), (-1, row_idx)),
                ]
                row_idx += 1
                last_section = sec
            desig = [Paragraph(str(l.get("description") or l.get("request_label") or "\u2014"), S["cell"])]
            sub = []
            if l.get("matched_item_code"):
                sub.append(f"R\u00e9f. {l['matched_item_code']}")
            if l.get("brand"):
                sub.append(str(l["brand"]))
            if l.get("supplier"):
                sub.append(f"Fourn. {l['supplier']}")
            if sub:
                desig.append(Paragraph(" \u00b7 ".join(sub), S["code"]))
            data.append([
                Paragraph(str(n), S["cell"]), desig,
                Paragraph(_fmt(l.get("qty")) + (f" {l.get('unit')}" if l.get("unit") else ""), S["cell"]),
                Paragraph(_money(l.get("unit_price_ht"), cur) if l.get("unit_price_ht") is not None else "\u2014", S["cell"]),
                Paragraph(f"{_fmt(l.get('vat_rate'))} %" if l.get("vat_rate") is not None else "\u2014", S["cell"]),
                Paragraph(_money(l.get("line_ht"), cur) if l.get("line_ht") is not None else "\u00e0 confirmer", S["cell"]),
            ])
            row_idx += 1
            n += 1
        items = Table(data, colWidths=col_w, repeatRows=1)
        items.setStyle(TableStyle(style_cmds))
        e.append(items)
        if ci < len(chunks) - 1:
            e.append(PageBreak())
    e.append(Spacer(1, 12))

    # ---- TVA breakdown + totals (right aligned) ------------------------------
    vat_by_rate = defaultdict(float)
    for l in quote.get("lines", []):
        if l.get("line_ht") is not None and l.get("vat_rate") is not None and l.get("status") in ("matched", "proposed", "confirmed"):
            vat_by_rate[float(l["vat_rate"])] += round(float(l["line_ht"]) * float(l["vat_rate"]) / 100, 2)

    trows = [["Total HT", _money(quote.get("total_ht"), cur)]]
    for rate in sorted(vat_by_rate.keys()):
        trows.append([f"TVA {(_fmt(rate))} %", _money(round(vat_by_rate[rate], 2), cur)])
    if not vat_by_rate:
        trows.append(["TVA", _money(quote.get("total_vat"), cur)])
    trows.append(["Total TTC", _money(quote.get("total_ttc"), cur)])

    totals = Table([[r[0], r[1]] for r in trows], colWidths=[doc.width * 0.22, doc.width * 0.18])
    totals.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2C3E50")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    net = Table([[Paragraph("Net \u00e0 payer", S["net_lbl"]), Paragraph(_money(quote.get("total_ttc"), cur), S["net_val"])]],
                colWidths=[doc.width * 0.22, doc.width * 0.18])
    net.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, GREEN_LINE),
    ]))
    totals_wrap = Table([[totals], [Spacer(1, 4)], [net]], colWidths=[doc.width * 0.4])
    totals_wrap.hAlign = "RIGHT"
    e.append(totals_wrap)
    e.append(Spacer(1, 14))

    # ---- Required deliverables (from the incoming request) -------------------
    deliverables = (quote.get("meta") or {}).get("required_deliverables") or []
    if deliverables:
        e.append(Paragraph("<b>D\u00e9tails fournis dans ce devis</b>", S["pay"]))
        for d in deliverables[:8]:
            e.append(Paragraph("&ndash;&nbsp;" + str(d), S["small"]))
        e.append(Spacer(1, 10))

    # ---- Payment terms + acceptance ------------------------------------------
    pay_terms = p.get("payment_terms") or "\u2022 30 % \u00e0 la signature du devis\n\u2022 40 % en cours de travaux\n\u2022 30 % \u00e0 la livraison"
    pay_block = [Paragraph("<b>Modalit\u00e9s de paiement</b>", S["pay"])]
    for ln in pay_terms.split("\n"):
        ln = ln.strip().lstrip("\u2022").strip()
        if ln:
            pay_block.append(Paragraph("&ndash;&nbsp;" + ln, S["pay"]))

    accept_text = p.get("acceptance_text") or "\u00ab Devis re\u00e7u avant l\u2019ex\u00e9cution des travaux. Bon pour accord. \u00bb"
    accept_block = [
        Paragraph("<b>Le client</b>", S["accept"]),
        Paragraph("<i>Mention dat\u00e9e et sign\u00e9e :</i>", S["accept"]),
        Spacer(1, 4),
        Paragraph(accept_text, S["accept"]),
        Spacer(1, 24),
    ]
    bottom = Table([[pay_block, accept_block]], colWidths=[doc.width * 0.5, doc.width * 0.5])
    bottom.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("BOX", (1, 0), (1, 0), 0.6, BORDER),
        ("TOPPADDING", (1, 0), (1, 0), 8), ("BOTTOMPADDING", (1, 0), (1, 0), 8),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    e.append(KeepTogether(bottom))
    e.append(Spacer(1, 6))
    # ---- TVA legal mention (auto-liquidation / franchise 293B) ---------------
    if p.get("tva_intra"):
        tva_mention = (f"TVA intracommunautaire : {p['tva_intra']}. "
                       "TVA due par le preneur assujetti \u2014 auto-liquidation en application de "
                       "l\u2019article 242 nonies A, I-13 de l\u2019annexe II au CGI.")
    else:
        tva_mention = "TVA non applicable, selon l\u2019article 293 B du CGI."
    e.append(Paragraph(f"<font size=7.5 color='#2C3E50'>{tva_mention}</font>", S["small"]))
    e.append(Spacer(1, 3))
    e.append(Paragraph(
        f"<font size=7 color='#6A7B8A'>Source tarifaire : {quote.get('pricing_snapshot', {}).get('catalog_name', '-')} "
        f"v{quote.get('pricing_snapshot', {}).get('version_number', '-')}. "
        "Prix issus du catalogue actif. Document pro forma sans valeur comptable.</font>", S["small"]))

    doc.build(e, canvasmaker=_NumberedCanvas)
    return buf.getvalue()
