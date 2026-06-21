"""
Blueseatra Core POC (isolated)
Proves the hardest, most failure-prone parts before building the full app:
  1. Multilingual AI extraction: raw text / image / PDF -> structured business JSON (any language)
  2. CSV pricing catalog ingestion + normalization
  3. Explainable matching engine (request line items -> catalog pricing items)
  4. Deterministic quote calculation (HT / VAT / TTC) -- AI NEVER sets price

Run: cd /app/backend && python poc_core.py
"""
import os
import io
import json
import base64
import asyncio
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from rapidfuzz import fuzz

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from PIL import Image, ImageDraw, ImageFont

import pdfplumber

from emergentintegrations.llm.chat import (
    LlmChat, UserMessage, ImageContent, TextDelta, StreamDone,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.4"

TMP = Path("/tmp/blueseatra_poc")
TMP.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Sample CSV pricing catalog (official Blueseatra template)
# ---------------------------------------------------------------------------
SAMPLE_CSV = """client_code,item_code,item_label,category,unit,unit_price_ht,currency,vat_rate,min_qty,is_active,notes
ACME,DEP-001,Deplacement technicien,deplacement,u,45.00,EUR,20,1,true,Forfait deplacement
ACME,MO-001,Main d'oeuvre qualifiee,main_oeuvre,hr,38.50,EUR,20,1,true,Taux horaire
ACME,PEINT-001,Peinture murale deux couches,peinture,m2,12.50,EUR,10,5,true,Inclut sous-couche
ACME,PROT-001,Protection chantier,protection,ens,85.00,EUR,20,1,true,Baches et adhesifs
ACME,PLACO-001,Pose placo BA13,placo,m2,28.00,EUR,10,2,true,Hors finition
ACME,FIBRE-001,Tirage fibre optique,fibre,ml,6.20,EUR,20,1,true,Par metre lineaire
ACME,MAINT-001,Maintenance porte automatique,maintenance,u,150.00,EUR,20,1,true,Intervention standard
ACME,CONSO-001,Consommables divers,consommables,ens,25.00,EUR,20,1,true,Visserie joints etc
"""


def build_catalog():
    df = pd.read_csv(io.StringIO(SAMPLE_CSV))
    items = []
    for _, r in df.iterrows():
        items.append({
            "item_code": str(r["item_code"]).strip(),
            "item_label": str(r["item_label"]).strip(),
            "label_norm": normalize(str(r["item_label"])),
            "category": str(r["category"]).strip().lower(),
            "unit": str(r["unit"]).strip().lower(),
            "unit_price_ht": float(r["unit_price_ht"]),
            "currency": str(r["currency"]).strip(),
            "vat_rate": float(r["vat_rate"]),
            "min_qty": float(r["min_qty"]),
            "is_active": str(r["is_active"]).strip().lower() in ("true", "1", "yes"),
        })
    return [i for i in items if i["is_active"]]


def normalize(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


# ---------------------------------------------------------------------------
# 2. Generate REAL test inputs (PDF + image) and a foreign-language raw text
# ---------------------------------------------------------------------------
def make_test_pdf() -> Path:
    p = TMP / "demande_fr.pdf"
    c = pdf_canvas.Canvas(str(p), pagesize=A4)
    text = c.beginText(50, 800)
    lines = [
        "Societe BatiPro - Demande de devis",
        "Client: ACME Industries / Site: Entrepot Nord, Lyon",
        "",
        "Bonjour,",
        "Nous souhaitons un devis pour les travaux suivants :",
        "- Peinture des murs de l'entrepot, surface environ 120 m2, deux couches.",
        "- Pose de cloison placo BA13 sur 35 m2.",
        "- Tirage de fibre optique sur 80 metres lineaires.",
        "- Prevoir le deplacement du technicien et la protection du chantier.",
        "Intervention urgente souhaitee avant fin du mois.",
        "Cordialement, Jean Dupont",
    ]
    for ln in lines:
        text.textLine(ln)
    c.drawText(text)
    c.showPage()
    c.save()
    return p


def make_test_image() -> Path:
    """English-language work request rendered as a document photo (real text features)."""
    p = TMP / "request_en.png"
    img = Image.new("RGB", (1000, 700), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        fontb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
        fontb = ImageFont.load_default()
    d.text((40, 30), "WORK REQUEST - ACME Industries", fill="black", font=fontb)
    body = [
        "Client: ACME / Site: Warehouse South, Manchester",
        "",
        "Please quote the following maintenance work:",
        "- Repaint office walls, about 60 square meters, two coats.",
        "- Maintenance of one automatic door (standard service).",
        "- Skilled labour estimated at 8 hours.",
        "- Include technician travel and miscellaneous consumables.",
        "",
        "Priority: normal. Contact: John Smith",
    ]
    y = 90
    for ln in body:
        d.text((40, y), ln, fill="black", font=font)
        y += 36
    # add a border rectangle for extra visual features
    d.rectangle([15, 15, 985, 685], outline="black", width=3)
    img.save(p)
    return p


SPANISH_TEXT = (
    "Solicitud de presupuesto - Cliente ACME, sede de Madrid. "
    "Necesitamos pintar las paredes de la oficina, aproximadamente 45 metros cuadrados, dos capas. "
    "Tambien requerimos tirar 50 metros lineales de fibra optica y prever el desplazamiento del tecnico. "
    "Urgencia: alta. Atentamente, Maria Garcia."
)


# ---------------------------------------------------------------------------
# 3. Text extraction helpers
# ---------------------------------------------------------------------------
def extract_pdf_text(path: Path) -> str:
    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out).strip()


def image_to_b64(path: Path) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# 4. AI multilingual extraction -> strict JSON
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM = """You are Blueseatra's document understanding engine for a B2B quoting platform.
Extract a structured business request from the provided content, which may be in ANY language.
Return ONLY valid minified JSON (no markdown, no commentary) with EXACTLY this schema:
{
 "language": "ISO 639-1 code of the source content",
 "client": "string or null",
 "site": "string or null",
 "description": "short summary in the source language",
 "urgency": "low|normal|high",
 "constraints": ["string", ...],
 "keywords": ["string", ...],
 "line_items": [
   {"label": "string", "category": "string or null", "qty": number, "unit": "hr|m2|ml|u|ens or null", "dimensions": "string or null", "notes": "string or null"}
 ],
 "confidence": number between 0 and 1
}
Rules: Never invent prices. Infer qty/unit only when clearly stated; otherwise qty=1 and unit=null.
Categories should be lowercase business families (e.g. peinture, placo, fibre, maintenance, deplacement, main_oeuvre, protection, consommables)."""


async def ai_extract(content_text: str = None, image_b64: str = None, label: str = ""):
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"poc-extract-{label}",
        system_message=EXTRACTION_SYSTEM,
    ).with_model(DEFAULT_PROVIDER, DEFAULT_MODEL)

    if image_b64:
        msg = UserMessage(
            text="Extract the structured request JSON from this document image.",
            file_contents=[ImageContent(image_base64=image_b64)],
        )
    else:
        msg = UserMessage(text=f"Extract the structured request JSON from this content:\n\n{content_text}")

    buf = []
    async for ev in chat.stream_message(msg):
        if isinstance(ev, TextDelta):
            buf.append(ev.content)
        elif isinstance(ev, StreamDone):
            break
    raw = "".join(buf).strip()
    # strip code fences if any
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()
    return json.loads(raw)


# ---------------------------------------------------------------------------
# 5. Matching engine (explainable, scored)
# ---------------------------------------------------------------------------
UNIT_COMPAT = {
    "m2": {"m2"}, "ml": {"ml"}, "hr": {"hr"}, "u": {"u", "ens"}, "ens": {"ens", "u"},
}
SCORE_THRESHOLD = 45


def match_line(line, catalog):
    best = None
    label_norm = normalize(line.get("label", ""))
    req_cat = (line.get("category") or "").lower()
    req_unit = (line.get("unit") or "").lower()
    for item in catalog:
        score = 0
        reasons = []
        # exact label
        if label_norm and label_norm == item["label_norm"]:
            score += 70
            reasons.append("exact_label(+70)")
        else:
            fz = fuzz.token_set_ratio(label_norm, item["label_norm"])
            sem = int(fz * 0.5)  # up to +50
            if fz >= 60:
                score += sem
                reasons.append(f"label_fuzzy_{fz}(+{sem})")
        # category
        if req_cat and req_cat == item["category"]:
            score += 40
            reasons.append("same_category(+40)")
        # unit compat
        if req_unit and item["unit"] in UNIT_COMPAT.get(req_unit, {req_unit}):
            score += 20
            reasons.append("unit_compatible(+20)")
        if best is None or score > best["score"]:
            best = {"item": item, "score": score, "reasons": reasons}
    if best and best["score"] >= SCORE_THRESHOLD:
        best["status"] = "matched" if best["score"] >= 90 else "proposed"
    elif best:
        best["status"] = "to_confirm"
    return best


def build_quote(extracted, catalog):
    lines = []
    total_ht = 0.0
    total_vat = 0.0
    for li in extracted.get("line_items", []):
        m = match_line(li, catalog)
        qty = float(li.get("qty") or 1)
        if m and m["status"] in ("matched", "proposed"):
            item = m["item"]
            eff_qty = max(qty, item["min_qty"])
            line_ht = round(eff_qty * item["unit_price_ht"], 2)
            line_vat = round(line_ht * item["vat_rate"] / 100, 2)
            total_ht += line_ht
            total_vat += line_vat
            lines.append({
                "request_label": li.get("label"),
                "matched_item": item["item_code"],
                "matched_label": item["item_label"],
                "qty": eff_qty, "unit": item["unit"],
                "unit_price_ht": item["unit_price_ht"],
                "line_ht": line_ht, "vat_rate": item["vat_rate"],
                "status": m["status"], "score": m["score"], "reasons": m["reasons"],
            })
        else:
            lines.append({
                "request_label": li.get("label"),
                "matched_item": None, "qty": qty, "unit": li.get("unit"),
                "line_ht": None, "status": "to_confirm",
                "score": m["score"] if m else 0,
                "reasons": m["reasons"] if m else ["no_candidate"],
            })
    return {
        "lines": lines,
        "total_ht": round(total_ht, 2),
        "total_vat": round(total_vat, 2),
        "total_ttc": round(total_ht + total_vat, 2),
        "currency": catalog[0]["currency"] if catalog else "EUR",
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def main():
    print("=" * 70)
    print("BLUESEATRA CORE POC")
    print("=" * 70)
    assert EMERGENT_LLM_KEY, "EMERGENT_LLM_KEY missing"

    catalog = build_catalog()
    print(f"[catalog] loaded {len(catalog)} active pricing items")

    pdf_path = make_test_pdf()
    img_path = make_test_image()
    pdf_text = extract_pdf_text(pdf_path)
    print(f"[pdf] extracted {len(pdf_text)} chars from PDF")

    results = {}

    # Case 1: French PDF text
    print("\n--- CASE 1: French PDF ---")
    ex1 = await ai_extract(content_text=pdf_text, label="pdf")
    print("language:", ex1.get("language"), "| items:", len(ex1.get("line_items", [])), "| conf:", ex1.get("confidence"))
    q1 = build_quote(ex1, catalog)
    print(f"quote: HT={q1['total_ht']} VAT={q1['total_vat']} TTC={q1['total_ttc']} {q1['currency']}")
    results["pdf_fr"] = (ex1, q1)

    # Case 2: English image
    print("\n--- CASE 2: English image (vision) ---")
    ex2 = await ai_extract(image_b64=image_to_b64(img_path), label="img")
    print("language:", ex2.get("language"), "| items:", len(ex2.get("line_items", [])), "| conf:", ex2.get("confidence"))
    q2 = build_quote(ex2, catalog)
    print(f"quote: HT={q2['total_ht']} VAT={q2['total_vat']} TTC={q2['total_ttc']} {q2['currency']}")
    results["image_en"] = (ex2, q2)

    # Case 3: Spanish raw text
    print("\n--- CASE 3: Spanish raw text ---")
    ex3 = await ai_extract(content_text=SPANISH_TEXT, label="es")
    print("language:", ex3.get("language"), "| items:", len(ex3.get("line_items", [])), "| conf:", ex3.get("confidence"))
    q3 = build_quote(ex3, catalog)
    print(f"quote: HT={q3['total_ht']} VAT={q3['total_vat']} TTC={q3['total_ttc']} {q3['currency']}")
    results["text_es"] = (ex3, q3)

    # Validation
    print("\n" + "=" * 70)
    print("VALIDATION")
    print("=" * 70)
    ok = True
    for name, (ex, q) in results.items():
        has_items = len(ex.get("line_items", [])) > 0
        has_lang = bool(ex.get("language"))
        matched = sum(1 for l in q["lines"] if l["status"] in ("matched", "proposed"))
        priced = q["total_ttc"] > 0
        status = "PASS" if (has_items and has_lang and matched > 0 and priced) else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"[{status}] {name}: lang={ex.get('language')} items={len(ex.get('line_items', []))} matched={matched}/{len(q['lines'])} ttc={q['total_ttc']}")

    print("\nSample detailed quote lines (CASE 1 French PDF):")
    print(json.dumps(results["pdf_fr"][1]["lines"], ensure_ascii=False, indent=2))

    print("\nOVERALL:", "SUCCESS ✅" if ok else "FAILURE ❌")
    return ok


if __name__ == "__main__":
    asyncio.run(main())
