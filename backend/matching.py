"""Explainable, scored matching engine + deterministic quote calculation.
Pricing ALWAYS comes from the catalog. AI never sets the price.
"""
import unicodedata
from collections import OrderedDict
from rapidfuzz import fuzz

UNIT_COMPAT = {
    "m2": {"m2"}, "ml": {"ml"}, "hr": {"hr"}, "u": {"u", "ens"}, "ens": {"ens", "u"},
}
SCORE_THRESHOLD = 45
# Tarifs ANELEC imposés (devis type DEV-2026-0477 / 0525)
LABOR_RATE_HT = 42.0
TRAVEL_RATE_HT = 40.0


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
                "line_type": "material",
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
                "line_type": "material",
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
    extra, extra_ht, extra_vat = _auto_labor_and_travel(extracted, catalog, lines)
    # Ordre ANELEC / Tolteck : déplacement, main-d'œuvre, puis fournitures
    lines = extra + lines
    total_ht += extra_ht
    total_vat += extra_vat
    return wrap_in_lots(lines), round(total_ht, 2), round(total_vat, 2)


def _find_item(catalog: list, *codes_or_needles: str):
    needles = [normalize(c) for c in codes_or_needles if c]
    for item in catalog:
        code = normalize(item.get("item_code") or "")
        label = normalize(item.get("item_label") or "")
        cat = normalize(item.get("category") or "")
        if code in needles or any(n and n in label for n in needles) or any(n and n == cat for n in needles):
            if item.get("is_active") is False:
                continue
            return item
    return None


def _append_priced(item: dict, qty: float, line_type: str, description: str, reasons: list):
    unit_price = float(item.get("unit_price_ht") or 0)
    vat_rate = float(item.get("vat_rate") or 20)
    margin = item.get("margin") or 0
    line_ht = line_amount_ht(qty, unit_price, margin) or 0
    line_vat = round(line_ht * vat_rate / 100, 2)
    return {
        "line_type": line_type,
        "request_label": description,
        "description": description,
        "category": item.get("category"),
        "matched_item_code": item.get("item_code"),
        "matched_label": item.get("item_label"),
        "qty": qty,
        "unit": item.get("unit"),
        "unit_price_ht": unit_price,
        "margin": margin,
        "vat_rate": vat_rate,
        "line_ht": line_ht,
        "status": "proposed",
        "score": 80,
        "reasons": reasons,
    }, line_ht, line_vat


def _auto_labor_and_travel(extracted: dict, catalog: list, existing: list):
    """Tolteck-style completeness: fourniture + main-d'oeuvre + deplacement."""
    extra = []
    extra_ht = 0.0
    extra_vat = 0.0
    codes = {(l.get("matched_item_code") or "") for l in existing}
    texts = " ".join((l.get("description") or "") for l in existing).lower()

    units = 0.0
    for l in existing:
        if l.get("line_type") in ("note", "page_break", "labor", "travel", "lot", "sublot"):
            continue
        try:
            units += float(l.get("qty") or 0)
        except (TypeError, ValueError):
            units += 1
    if units <= 0:
        units = 1.0

    extras_buf = []
    if "DEP-001" not in codes and "deplacement" not in texts and "d\u00e9placement" not in texts:
        dep = _find_item(catalog, "DEP-001", "deplacement technicien", "deplacement") or {
            "item_code": "DEP-001", "item_label": "Deplacement technicien",
            "category": "deplacement", "unit": "u", "unit_price_ht": TRAVEL_RATE_HT, "vat_rate": 20,
        }
        row, ht, vat = _append_priced(
            dep, 1.0, "travel",
            "Deplacement en Ile-de-France — heures normales 8h-18h",
            ["auto_travel", "tarif_40"],
        )
        row["unit_price_ht"] = TRAVEL_RATE_HT
        row["line_ht"] = line_amount_ht(1.0, TRAVEL_RATE_HT, 0) or 0
        ht = row["line_ht"]
        vat = round(ht * float(row.get("vat_rate") or 20) / 100, 2)
        extras_buf.append((row, ht, vat))

    if "MO-001" not in codes and "main d'oeuvre" not in texts and "main d oeuvre" not in texts:
        mo = _find_item(catalog, "MO-001", "main d oeuvre", "main_oeuvre") or {
            "item_code": "MO-001", "item_label": "Main d'oeuvre qualifiee",
            "category": "main_oeuvre", "unit": "hr", "unit_price_ht": LABOR_RATE_HT, "vat_rate": 20,
        }
        if mo:
            hours = max(1.0, round(units * 0.4 * 4) / 4)  # 0.4 h / u, min 1 h, pas de 0.25
            row, ht, vat = _append_priced(
                mo, hours, "labor",
                "Main d'oeuvre — heures normales 7h-18h",
                ["auto_labor", f"{units:g}_unites", "tarif_42"],
            )
            row["unit_price_ht"] = LABOR_RATE_HT
            row["line_ht"] = line_amount_ht(hours, LABOR_RATE_HT, 0) or 0
            ht = row["line_ht"]
            vat = round(ht * float(row.get("vat_rate") or 20) / 100, 2)
            extras_buf.append((row, ht, vat))

    for row, ht, vat in extras_buf:
        extra.append(row)
        extra_ht += ht
        extra_vat += vat
    return extra, extra_ht, extra_vat


def build_works_description(extracted: dict) -> str:
    """Bloc obligatoire 'Description / Deroulement des travaux' (modele ANELEC)."""
    desc = (extracted.get("description") or "").strip()
    site = (
        extracted.get("intervention_address")
        or extracted.get("location")
        or extracted.get("intervention_site")
        or ""
    ).strip()
    items = extracted.get("line_items") or []
    labels = []
    for i in items:
        t = (i.get("label") or i.get("description") or "").strip()
        if t and t not in labels:
            labels.append(t)
    core = desc or (", ".join(labels) if labels else "Travaux selon demande client")
    if core and not core.endswith("."):
        core += "."
    site_bit = f" Intervention prévue à {site}." if site else ""
    return (
        f"{core}{site_bit}\n\n"
        "Les travaux seront exécutés en phases successives : déplacement du technicien "
        "en Île-de-France (heures normales 8h-18h), installation et sécurisation de la "
        "zone d'intervention, fourniture et pose ou remplacement des articles listés, "
        "puis nettoyage de fin de chantier.\n\n"
        "Toute contrainte technique non visible lors du métré initial pourra faire "
        "l'objet d'une adaptation complémentaire après accord du client."
    )


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


TCE_LOT_RULES = [
    (("gros oeuvre", "maconnerie"), "Gros \u0153uvre \u2014 Ma\u00e7onnerie"),
    (("platrerie", "cloison", "faux plafond"), "Pl\u00e2trerie \u2014 Cloisons \u2014 Faux plafonds"),
    (("electricite", "cfo", "cfa", "eclairage", "led", "spot"), "\u00c9lectricit\u00e9 \u2014 Courants forts et faibles"),
    (("plomberie", "sanitaire"), "Plomberie \u2014 Sanitaires"),
    (("cvc", "chauffage", "ventilation", "clim"), "CVC \u2014 Chauffage, Ventilation, Climatisation"),
    (("sol", "carrelage", "parquet", "revetement souple"), "Rev\u00eatements de sols"),
    (("peinture", "enduit", "mural"), "Rev\u00eatements muraux \u2014 Peinture"),
    (("serrurerie", "metallerie"), "Serrurerie \u2014 M\u00e9tallerie"),
    (("maintenance",), "Maintenance multitechnique"),
]


def _tce_lot_name(category: str | None, description: str = "") -> str:
    blob = normalize(f"{category or ''} {description or ''}")
    for needles, title in TCE_LOT_RULES:
        if any(n in blob for n in needles):
            return title
    return "Fournitures et pose"


def _struct_line(line_type: str, number: str, title: str) -> dict:
    return {
        "line_type": line_type,
        "description": title,
        "lot_number": str(number),
        "category": None,
        "qty": None,
        "unit": None,
        "unit_price_ht": None,
        "vat_rate": None,
        "line_ht": None,
        "status": line_type,
        "score": 0,
        "reasons": ["structure"],
    }


def wrap_in_lots(lines: list) -> list:
    """Tolteck-style lots / sous-lots autour des lignes g\u00e9n\u00e9r\u00e9es."""
    if any(l.get("line_type") in ("lot", "sublot") for l in lines):
        return lines
    travel, labor, materials = [], [], []
    for l in lines:
        lt = l.get("line_type")
        if lt == "travel":
            travel.append(l)
        elif lt == "labor":
            labor.append(l)
        elif lt not in ("note", "page_break"):
            materials.append(l)
        else:
            materials.append(l)

    out = []
    lot_n = 1
    if travel or labor:
        out.append(_struct_line("lot", lot_n, "Installation de chantier / Pr\u00e9liminaires"))
        sub = 1
        if travel:
            out.append(_struct_line("sublot", f"{lot_n}.{sub}", "D\u00e9placement"))
            out.extend(travel)
            sub += 1
        if labor:
            out.append(_struct_line("sublot", f"{lot_n}.{sub}", "Main-d'\u0153uvre"))
            out.extend(labor)
        lot_n += 1

    groups = OrderedDict()
    leftovers = []
    for l in materials:
        if l.get("line_type") in ("note", "page_break"):
            leftovers.append(l)
            continue
        name = _tce_lot_name(l.get("category"), l.get("description") or l.get("request_label") or "")
        groups.setdefault(name, []).append(l)
    for name, items in groups.items():
        out.append(_struct_line("lot", lot_n, name))
        out.append(_struct_line("sublot", f"{lot_n}.1", "Fournitures"))
        out.extend(items)
        lot_n += 1
    out.extend(leftovers)
    return out or lines


def group_subtotal(lines: list, start: int, stop_types: tuple) -> float:
    total = 0.0
    for l in lines[start + 1:]:
        if l.get("line_type") in stop_types:
            break
        if l.get("line_ht") is not None:
            try:
                total += float(l["line_ht"])
            except (TypeError, ValueError):
                pass
    return round(total, 2)


def recompute_totals(lines: list):
    total_ht = 0.0
    total_vat = 0.0
    for l in lines:
        if l.get("line_ht") is not None:
            ht = float(l["line_ht"])
            total_ht += ht
            total_vat += round(ht * float(l.get("vat_rate") or 0) / 100, 2)
    return round(total_ht, 2), round(total_vat, 2), round(total_ht + total_vat, 2)
