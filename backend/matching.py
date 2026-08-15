"""Explainable, scored matching engine + deterministic quote calculation.
Pricing ALWAYS comes from the catalog. AI never sets the price.
"""
import unicodedata
from rapidfuzz import fuzz

UNIT_COMPAT = {
    "m2": {"m2"}, "ml": {"ml"}, "hr": {"hr"}, "u": {"u", "ens"}, "ens": {"ens", "u"},
}
SCORE_THRESHOLD = 45


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def _line_text(line: dict) -> str:
    return line.get("label") or line.get("description") or line.get("request_label") or ""


def _match_query(text: str) -> str:
    """Drop verbs/qty so 'remplacement de 3 spots LED' matches 'Spot LED encastré'."""
    s = normalize(text)
    for junk in (
        "remplacement de", "remplacement d", "fourniture et pose de",
        "fourniture et pose", "pose de", "pose d", "fourniture de",
    ):
        s = s.replace(junk, " ")
    keep = []
    for tok in s.split():
        if tok in {"de", "d", "un", "une", "le", "la", "les", "des"} or tok.isdigit():
            continue
        if tok.endswith("s") and len(tok) > 3:
            tok = tok[:-1]
        keep.append(tok)
    return " ".join(keep)


def match_line(line: dict, catalog: list) -> dict | None:
    best = None
    label_norm = _match_query(_line_text(line))
    req_cat = (line.get("category") or line.get("work_type") or "").lower()
    req_unit = (line.get("unit") or "").lower()
    for item in catalog:
        score = 0
        reasons = []
        item_label_norm = item.get("label_norm") or normalize(item.get("item_label", ""))
        if label_norm and label_norm == item_label_norm:
            score += 70
            reasons.append("exact_label(+70)")
        else:
            fz = fuzz.token_set_ratio(label_norm, item_label_norm)
            if fz >= 50:
                sem = int(fz * 0.6)
                score += sem
                reasons.append(f"label_fuzzy_{int(fz)}(+{sem})")
            req_tokens = set(label_norm.split())
            item_tokens = set(item_label_norm.split())
            overlap = req_tokens & item_tokens
            if overlap:
                bonus = min(30, 10 * len(overlap))
                score += bonus
                reasons.append(f"token_overlap_{'+'.join(sorted(overlap))}(+{bonus})")
        if req_cat and req_cat == (item.get("category") or "").lower():
            score += 40
            reasons.append("same_category(+40)")
        if req_unit and item.get("unit") in UNIT_COMPAT.get(req_unit, {req_unit}):
            score += 20
            reasons.append("unit_compatible(+20)")
        if best is None or score > best["score"]:
            best = {"item": item, "score": score, "reasons": reasons}
    if not best:
        return None
    if best["score"] >= 90:
        best["status"] = "matched"
    elif best["score"] >= SCORE_THRESHOLD:
        best["status"] = "proposed"
    else:
        best["status"] = "to_confirm"
    return best


def build_quote_lines(extracted: dict, catalog: list):
    lines = []
    total_ht = 0.0
    total_vat = 0.0
    for li in extracted.get("line_items", []) or []:
        m = match_line(li, catalog)
        try:
            qty = float(li.get("qty") or li.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1.0
        # rich description: label + dimensions / specs / location
        extra = [str(li.get(k)) for k in ("dimensions", "specs", "location") if li.get(k)]
        desc = li.get("label") or li.get("description") or ""
        if extra:
            sep = " \u00b7 "
            desc = desc + " (" + sep.join(extra) + ")"
        if m and m["status"] in ("matched", "proposed"):
            item = m["item"]
            eff_qty = max(qty, float(item.get("min_qty") or 0))
            unit_price = float(item.get("unit_price_ht") or 0)
            vat_rate = float(item.get("vat_rate") or 0)
            margin = item.get("margin") or 0
            line_ht = line_amount_ht(eff_qty, unit_price, margin)
            line_vat = round((line_ht or 0) * vat_rate / 100, 2)
            total_ht += line_ht or 0
            total_vat += line_vat
            lines.append({
                "request_label": li.get("label"),
                "description": desc,
                "category": item.get("category") or li.get("category"),
                "matched_item_code": item.get("item_code"),
                "matched_label": item.get("item_label"),
                "qty": eff_qty,
                "unit": item.get("unit"),
                "unit_price_ht": unit_price,
                "margin": margin,
                "vat_rate": vat_rate,
                "line_ht": line_ht,
                "status": m["status"],
                "score": m["score"],
                "reasons": m["reasons"],
            })
        else:
            lines.append({
                "request_label": li.get("label"),
                "description": desc,
                "category": li.get("category"),
                "matched_item_code": None,
                "matched_label": None,
                "qty": qty,
                "unit": li.get("unit"),
                "unit_price_ht": None,
                "vat_rate": None,
                "line_ht": None,
                "status": "to_confirm",
                "score": m["score"] if m else 0,
                "reasons": m["reasons"] if m else ["no_candidate"],
            })
    return lines, round(total_ht, 2), round(total_vat, 2)


def line_amount_ht(qty, unit_price_ht, margin=None) -> float | None:
    """HT = qté × PU × (1 + marge%). Marge interne, masquée sur le PDF."""
    try:
        q = float(qty)
        p = float(unit_price_ht)
    except (TypeError, ValueError):
        return None
    try:
        m = float(margin or 0)
    except (TypeError, ValueError):
        m = 0.0
    return round(q * p * (1 + m / 100.0), 2)


def recompute_totals(lines: list):
    total_ht = 0.0
    total_vat = 0.0
    for l in lines:
        if l.get("line_ht") is not None:
            ht = float(l["line_ht"])
            total_ht += ht
            total_vat += round(ht * float(l.get("vat_rate") or 0) / 100, 2)
    return round(total_ht, 2), round(total_vat, 2), round(total_ht + total_vat, 2)
