"""Lightweight Markdown -> PDF renderer (ReportLab Platypus).

Supports: H1-H4 headings, paragraphs, bullet/numbered lists, pipe tables,
fenced code blocks (```), blockquotes, inline **bold** and `code`.

Usage:
    python make_docs_pdf.py README.md "Blueseatra - Documentation (FR)" Blueseatra_Documentation_FR.pdf
"""
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (ListFlowable, ListItem, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

PRIMARY = colors.HexColor("#1e3a5f")
ACCENT = colors.HexColor("#2563eb")
CODE_BG = colors.HexColor("#f1f5f9")
BORDER = colors.HexColor("#cbd5e1")
HEADER_BG = colors.HexColor("#1e3a5f")
ROW_ALT = colors.HexColor("#f8fafc")

styles = getSampleStyleSheet()
S = {
    "h1": ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, leading=24,
                         textColor=PRIMARY, spaceBefore=14, spaceAfter=10),
    "h2": ParagraphStyle("h2", parent=styles["Heading2"], fontSize=15, leading=19,
                         textColor=PRIMARY, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", parent=styles["Heading3"], fontSize=12.5, leading=16,
                         textColor=ACCENT, spaceBefore=9, spaceAfter=4),
    "h4": ParagraphStyle("h4", parent=styles["Heading4"], fontSize=11, leading=14,
                         textColor=ACCENT, spaceBefore=7, spaceAfter=3),
    "p": ParagraphStyle("p", parent=styles["BodyText"], fontSize=9.5, leading=14,
                        alignment=TA_LEFT, spaceAfter=5),
    "quote": ParagraphStyle("quote", parent=styles["BodyText"], fontSize=9, leading=13,
                            textColor=colors.HexColor("#475569"), leftIndent=10,
                            borderColor=ACCENT, spaceAfter=5, fontName="Helvetica-Oblique"),
    "li": ParagraphStyle("li", parent=styles["BodyText"], fontSize=9.5, leading=13, spaceAfter=2),
    "cell": ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8, leading=10.5),
    "cellh": ParagraphStyle("cellh", parent=styles["BodyText"], fontSize=8, leading=10.5,
                            textColor=colors.white, fontName="Helvetica-Bold"),
    "code": ParagraphStyle("code", parent=styles["Code"], fontSize=7.8, leading=10.5,
                           textColor=colors.HexColor("#0f172a")),
}


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t: str) -> str:
    """Apply inline markdown (escape first), then **bold** and `code`."""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font face="Courier" size="8" color="#b91c1c">\1</font>', t)
    t = re.sub(r"\[(.+?)\]\(#.*?\)", r"\1", t)  # strip internal anchor links
    return t


def make_table(rows):
    header, body = rows[0], rows[1:]
    data = [[Paragraph(inline(c), S["cellh"]) for c in header]]
    for r in body:
        data.append([Paragraph(inline(c), S["cell"]) for c in r])
    t = Table(data, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(style))
    return t


def parse(md_lines):
    flow = []
    i, n = 0, len(md_lines)
    while i < n:
        line = md_lines[i].rstrip("\n")

        # Fenced code block
        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < n and not md_lines[i].strip().startswith("```"):
                buf.append(md_lines[i].rstrip("\n"))
                i += 1
            i += 1
            code = "\n".join(buf) or " "
            pre = Preformatted(code, S["code"])
            tbl = Table([[pre]], colWidths=[170 * mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            flow.append(tbl)
            flow.append(Spacer(1, 5))
            continue

        # Pipe table
        if line.strip().startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", md_lines[i + 1]):
            rows = []
            while i < n and md_lines[i].strip().startswith("|"):
                raw = md_lines[i].strip().strip("|")
                if re.match(r"^[\s:|-]+$", raw):
                    i += 1
                    continue
                cells = [c.strip() for c in raw.split("|")]
                rows.append(cells)
                i += 1
            if rows:
                flow.append(make_table(rows))
                flow.append(Spacer(1, 6))
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            txt = inline(m.group(2))
            flow.append(Paragraph(txt, S[f"h{lvl}"]))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^\s*---+\s*$", line):
            flow.append(Spacer(1, 4))
            i += 1
            continue

        # Blockquote
        if line.strip().startswith(">"):
            buf = []
            while i < n and md_lines[i].strip().startswith(">"):
                buf.append(md_lines[i].strip()[1:].strip())
                i += 1
            flow.append(Paragraph(inline(" ".join(buf)), S["quote"]))
            flow.append(Spacer(1, 3))
            continue

        # Lists (bullet or numbered)
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            items = []
            bullet = "bullet"
            while i < n and re.match(r"^\s*([-*]|\d+\.)\s+", md_lines[i].rstrip("\n")):
                mm_ = re.match(r"^\s*([-*]|\d+\.)\s+(.*)$", md_lines[i].rstrip("\n"))
                if mm_.group(1)[0].isdigit():
                    bullet = "1"
                items.append(ListItem(Paragraph(inline(mm_.group(2)), S["li"]), leftIndent=12))
                i += 1
            flow.append(ListFlowable(items, bulletType=bullet, start="1" if bullet == "1" else None,
                                     leftIndent=14, bulletColor=ACCENT))
            flow.append(Spacer(1, 4))
            continue

        # Blank
        if not line.strip():
            i += 1
            continue

        # Paragraph
        flow.append(Paragraph(inline(line), S["p"]))
        i += 1
    return flow


def build(md_path, title, out_path):
    with open(md_path, encoding="utf-8") as f:
        lines = f.readlines()
    # Drop the first H1 (we render our own cover title)
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=16 * mm,
                            title=title, author="Blueseatra")
    story = [
        Spacer(1, 40 * mm),
        Paragraph(title, ParagraphStyle("cover", parent=styles["Title"], fontSize=26,
                                        textColor=PRIMARY, leading=30)),
        Spacer(1, 6 * mm),
        Paragraph("AI-Assisted B2B Quoting SaaS Platform", ParagraphStyle(
            "sub", parent=styles["Normal"], fontSize=12, textColor=ACCENT)),
        Spacer(1, 4 * mm),
        Paragraph("FastAPI &bull; React &bull; Supabase / PostgreSQL", ParagraphStyle(
            "sub2", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#64748b"))),
    ]
    story.append(Spacer(1, 200 * mm))
    story += parse(lines)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(20 * mm, 9 * mm, "Blueseatra - Documentation")
        canvas.drawRightString(A4[0] - 20 * mm, 9 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    print(f"PDF generated: {out_path}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
