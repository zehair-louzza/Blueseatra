"""Explainable, scored matching engine + deterministic quote calculation.
Pricing ALWAYS comes from the catalog. AI never sets the price.
"""
import math
import re
import unicodedata
from collections import OrderedDict
from rapidfuzz import fuzz

UNIT_COMPAT = {
    "m2": {"m2"}, "ml": {"ml"}, "hr": {"hr"}, "u": {"u", "ens"}, "ens": {"ens", "u"},
}
SCORE_THRESHOLD = 45

# Phrases d'action a retirer avant le rapprochement catalogue : on ne matche
# jamais une phrase entiere, seulement l'article/la designation (voir skill
# rapprochement-catalogue-sans-prix). Ex. "le remplacement total de la pompe
# de relevage" -> "pompe de relevage".
_ACTION_PREFIX = re.compile(
    r"^(?:le |la |les |l['’])?"
    r"(?:remplacement(?: total| partiel)?|pose|d[ée]pose|installation|"
    r"r[ée]paration|changement|fourniture(?: et pose)?|mise en place|"
    r"entretien|nettoyage|v[ée]rification|contr[ôo]le|maintenance|"
    r"intervention sur|d[ée]montage|montage)\s+"
    r"(?:de |du |de la |des |d['’])?",
    re.I,
)
_LEADING_ARTICLE = re.compile(r"^(?:le |la |les |l['’]|du |de la |des |de )", re.I)
# Tarifs ANELEC imposés (devis type DEV-2026-0477 / 0525)
LABOR_RATE_HT = 42.0
TRAVEL_RATE_HT = 40.0


def clean_text(s: str) -> str:
    """Turn literal \\n / \\r into real line breaks and tidy spaces."""
    if s is None:
        return ""
    t = str(s).replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\\n", "\n").replace("\\r", "")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def short_title(s: str, limit: int = 120) -> str:
    t = clean_text(s).split("\n")[0].strip()
    for sep in (". ", " : ", " — ", " - "):
        head = t.split(sep, 1)[0].strip()
        if 24 <= len(head) < len(t):
            t = head
            break
    if len(t) > limit:
        t = t[: limit - 1].rsplit(" ", 1)[0] + "\u2026"
    return t


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


def article_only(text: str) -> str:
    """Retire le verbe d'action, garde uniquement le nom de l'article pour
    le rapprochement catalogue. Ne modifie jamais la description affichee
    sur le devis, seulement la chaine utilisee pour chercher dans le
    catalogue."""
    s = clean_text(text or "")
    prev = None
    while prev != s:
        prev = s
        s = _ACTION_PREFIX.sub("", s).strip()
    s = _LEADING_ARTICLE.sub("", s).strip()
    return s or clean_text(text or "")


def match_line(line: dict, catalog: list) -> dict | None:
    raw_full = clean_text(_line_text(line))
    # Un paragraphe de demande n'est pas un article catalogue.
    if len(raw_full) > 100 or raw_full.count("\n") >= 1 or len(raw_full.split()) > 18:
        return {"item": None, "score": 0, "reasons": ["texte_trop_long"], "status": "to_confirm"}
    raw = article_only(raw_full)
    best = None
    label_norm = _match_query(raw)
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
    exact = any(r.startswith("exact_label") for r in best["reasons"])
    strong_fuzzy = any(r.startswith("label_fuzzy_8") or r.startswith("label_fuzzy_9") or r.startswith("label_fuzzy_100") for r in best["reasons"])
    if best["score"] >= 90 and (exact or strong_fuzzy):
        best["status"] = "matched"
    elif best["score"] >= SCORE_THRESHOLD:
        best["status"] = "proposed"
    else:
        best["status"] = "to_confirm"
    return best


def _ensure_line_items(extracted: dict) -> list:
    items = list(extracted.get("line_items") or [])
    if items:
        return items
    desc = (extracted.get("description") or extracted.get("work_type") or "").strip()
    return [{"description": desc or "Prestation selon demande", "quantity": 1, "unit": "u"}]


def _empty_rubric(line_type: str, description: str, qty, unit: str, reasons: list) -> dict:
    return {
        "line_type": line_type,
        "request_label": description,
        "description": description,
        "category": "deplacement" if line_type == "travel" else ("main_oeuvre" if line_type == "labor" else None),
        "matched_item_code": None,
        "matched_label": None,
        "qty": qty,
        "unit": unit,
        "unit_price_ht": None,
        "vat_rate": None,
        "line_ht": None,
        "status": "to_confirm",
        "score": 0,
        "reasons": reasons,
    }


def build_quote_lines(extracted: dict, catalog: list):
    lines = []
    total_ht = 0.0
    total_vat = 0.0
    for li in _ensure_line_items(extracted):
        m = match_line(li, catalog)
        try:
            qty = float(li.get("qty") or li.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1.0
        # rich description: label + dimensions / specs / location
        extra = [str(li.get(k)) for k in ("dimensions", "specs", "location") if li.get(k)]
        desc = clean_text(li.get("label") or li.get("description") or "")
        if extra:
            sep = " \u00b7 "
            desc = desc + " (" + sep.join(extra) + ")"
        if m and m["status"] == "matched":
            item = m["item"]
            eff_qty = max(qty, float(item.get("min_qty") or 0))
            unit_price = float(item.get("unit_price_ht") or 0)
            vat_rate = None  # TVA toujours vide (consigne ANELEC)
            margin = item.get("margin") or 0
            line_ht = line_amount_ht(eff_qty, unit_price, margin)
            line_vat = 0.0
            total_ht += line_ht or 0
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
                "vat_rate": None,
                "line_ht": line_ht,
                "status": m["status"],
                "score": m["score"],
                "reasons": m["reasons"],
            })
        else:
            # Regle catalogue : sans correspondance sure, AUCUN prix n'est applique.
            # Un match flou (status "proposed") reste une suggestion humaine.
            suggestion = m["item"] if (m and m.get("item") and m.get("status") == "proposed") else None
            lines.append({
                "line_type": "material",
                "request_label": li.get("label"),
                "description": desc,
                "category": li.get("category") or extracted.get("work_type"),
                "matched_item_code": None,
                "matched_label": None,
                "suggested_item_code": suggestion.get("item_code") if suggestion else None,
                "suggested_label": suggestion.get("item_label") if suggestion else None,
                "qty": qty,
                "unit": li.get("unit"),
                "unit_price_ht": None,
                "vat_rate": None,
                "line_ht": None,
                "status": "to_confirm",
                "score": m["score"] if m else 0,
                "reasons": (m["reasons"] if m else []) + (["suggestion_" + suggestion.get("item_code", "")] if suggestion else ["hors_catalogue"]),
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
    vat_rate = None
    margin = item.get("margin") or 0
    line_ht = line_amount_ht(qty, unit_price, margin) or 0
    line_vat = 0.0
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


def estimate_chantier(extracted: dict, material_lines: list | None = None) -> dict:
    """Heures-homme, effectif et jours de deplacement (barème expert, pas de prix)."""
    blob = normalize(
        " ".join([
            extracted.get("description") or "",
            extracted.get("work_type") or "",
            " ".join(
                (l.get("description") or l.get("label") or "")
                for l in (extracted.get("line_items") or []) + (material_lines or [])
            ),
        ])
    )

    def _qty_for(*needles):
        total = 0.0
        pool = extracted.get("line_items") or []
        if not pool:
            pool = [
                l for l in (material_lines or [])
                if l.get("line_type") not in ("note", "page_break", "lot", "sublot", "labor", "travel")
            ]
        for src in pool:
            txt = normalize(src.get("description") or src.get("label") or "")
            if any(n in txt for n in needles):
                try:
                    total += float(src.get("qty") or src.get("quantity") or 1)
                except (TypeError, ValueError):
                    total += 1
        return total

    hours = 0.0
    notes = []
    try:
        if extracted.get("labor_hours"):
            hours = float(extracted["labor_hours"])
            notes.append("heures_ia")
    except (TypeError, ValueError):
        hours = 0.0

    if hours <= 0:
        # Barèmes pose (h-h) — voir skill estimation-chantier.md
        n_spot = _qty_for("spot", "encastr")
        n_dalle = _qty_for("dalle led", "dalle 600")
        n_ballon = _qty_for("ballon", "ecs", "chauffe-eau", "chauffe eau")
        n_flex = _qty_for("flexible")
        n_vanne = _qty_for("vanne")
        n_vitrine = _qty_for("vitrine", "volige", "profil u")
        if n_spot:
            hours += n_spot * 0.45
            notes.append(f"spots_{n_spot:g}")
        if n_dalle:
            hours += n_dalle * 0.70
            notes.append(f"dalles_{n_dalle:g}")
        if n_ballon:
            hours += max(n_ballon, 1) * 4.50
            notes.append("ballon_ecs")
        if n_flex:
            hours += n_flex * 0.25
        if n_vanne:
            hours += n_vanne * 0.40
        if n_vitrine or any(k in blob for k in ("vitrine", "volige", "amovible")):
            hours += 6.0 if not n_vitrine else max(n_vitrine, 1) * 2.0
            notes.append("protection_vitrine")
        if any(k in blob for k in ("peinture", "enduit")):
            hours = max(hours, 7.0)
            notes.append("peinture_jour")
        if hours <= 0:
            # fallback: 0,45 h / article + chantier, min 2 h
            n_art = 0.0
            for l in material_lines or []:
                if l.get("line_type") in ("note", "page_break", "lot", "sublot", "labor", "travel"):
                    continue
                try:
                    n_art += float(l.get("qty") or 1)
                except (TypeError, ValueError):
                    n_art += 1
            hours = max(2.0, n_art * 0.45)
            notes.append("fallback_articles")
        hours += 1.25  # install 0,75 + repli 0,50
        notes.append("install_repli")

    hours = max(2.0, float(math.ceil(hours)))
    crew = 2 if hours >= 6 else 1
    try:
        if extracted.get("crew_size"):
            crew = max(1, int(extracted["crew_size"]))
    except (TypeError, ValueError):
        pass
    days = max(1, math.ceil(hours / (7.0 * crew)))
    try:
        travel_days = int(extracted["travel_days"]) if extracted.get("travel_days") else days
    except (TypeError, ValueError):
        travel_days = days
    travel_days = max(1, travel_days)
    return {
        "labor_hours": hours,
        "travel_days": travel_days,
        "crew": crew,
        "notes": notes,
    }


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

    est = estimate_chantier(extracted, existing)
    hours = est["labor_hours"]
    travel_days = est["travel_days"]

    extras_buf = []
    if "DEP-001" not in codes and "deplacement" not in texts and "d\u00e9placement" not in texts:
        dep = _find_item(catalog, "DEP-001", "deplacement technicien", "deplacement")
        if dep:
            row, ht, vat = _append_priced(
                dep, travel_days, "travel",
                f"Deplacement technicien — {travel_days:g} jour(s), heures 8h-18h",
                ["auto_travel", "tarif_40", "estime", f"{travel_days:g}_j"],
            )
            row["unit_price_ht"] = TRAVEL_RATE_HT
            row["unit"] = "j"
            row["vat_rate"] = None
            row["line_ht"] = line_amount_ht(travel_days, TRAVEL_RATE_HT, 0) or 0
            extras_buf.append((row, row["line_ht"], 0.0))
        else:
            fake = {"item_code": "DEP-001", "item_label": "Deplacement technicien",
                    "category": "deplacement", "unit": "j", "unit_price_ht": TRAVEL_RATE_HT}
            row, _, _ = _append_priced(fake, travel_days, "travel",
                f"Deplacement technicien — {travel_days:g} jour(s), heures 8h-18h",
                ["auto_travel", "tarif_40", "estime"])
            row["unit_price_ht"] = TRAVEL_RATE_HT
            row["unit"] = "j"
            row["vat_rate"] = None
            row["line_ht"] = line_amount_ht(travel_days, TRAVEL_RATE_HT, 0) or 0
            extras_buf.append((row, row["line_ht"], 0.0))

    if "MO-001" not in codes and "main d'oeuvre" not in texts and "main d oeuvre" not in texts:
        mo = _find_item(catalog, "MO-001", "main d oeuvre", "main_oeuvre")
        if mo:
            row, ht, vat = _append_priced(
                mo, hours, "labor",
                f"Main d'oeuvre pose — {hours:g} h ({est['crew']} pers.), heures 7h-18h",
                ["auto_labor", "estime", f"{hours:g}_h", f"{est['crew']}_pers"],
            )
            row["unit_price_ht"] = LABOR_RATE_HT
            row["vat_rate"] = None
            row["line_ht"] = line_amount_ht(hours, LABOR_RATE_HT, 0) or 0
            extras_buf.append((row, row["line_ht"], 0.0))
        else:
            fake = {"item_code": "MO-001", "item_label": "Main d'oeuvre qualifiee",
                    "category": "main_oeuvre", "unit": "hr", "unit_price_ht": LABOR_RATE_HT}
            row, _, _ = _append_priced(fake, hours, "labor",
                "Main d'oeuvre — heures normales 7h-18h", ["auto_labor", "tarif_42"])
            row["unit_price_ht"] = LABOR_RATE_HT
            row["vat_rate"] = None
            row["line_ht"] = line_amount_ht(hours, LABOR_RATE_HT, 0) or 0
            extras_buf.append((row, row["line_ht"], 0.0))

    for row, ht, vat in extras_buf:
        extra.append(row)
        extra_ht += ht
        extra_vat += vat
    return extra, extra_ht, extra_vat


def build_works_description(extracted: dict, chantier: dict | None = None) -> str:
    """Descriptif client : périmètre, phases, logique MO et déplacement."""
    desc = short_title(extracted.get("description") or extracted.get("option_label") or "", 280)
    site = clean_text(
        extracted.get("intervention_address")
        or extracted.get("location")
        or extracted.get("intervention_site")
        or ""
    )
    site_one = site.split("\n")[0].strip()
    items = extracted.get("line_items") or []
    labels = []
    for i in items:
        lab = clean_text(i.get("label") or i.get("description") or "")
        if lab and lab not in labels:
            labels.append(lab)
    idx = extracted.get("quote_option_index")
    cnt = extracted.get("quote_option_count") or 1
    title = extracted.get("option_label") or desc or "Travaux selon demande"
    head = f"Option {idx}/{cnt} — {title}." if cnt and int(cnt) > 1 else (title if title.endswith(".") else f"{title}.")
    fourn = ("Fournitures / pièces de cette option : " + ", ".join(labels) + ".") if labels else ""
    site_bit = f" Intervention prévue à {site_one}." if site_one else ""
    est = chantier or estimate_chantier(extracted, [])
    hours = est.get("labor_hours") or extracted.get("labor_hours") or 2
    days = est.get("travel_days") or extracted.get("travel_days") or 1
    crew = est.get("crew") or extracted.get("crew_size") or 1
    excl = clean_text(extracted.get("option_excludes") or "")
    hors = f" Hors périmètre de cette option : {excl}." if excl else ""
    return (
        f"{head} {fourn}{site_bit}{hors}\n\n"
        "Déroulement :\n"
        "1. Déplacement du (des) technicien(s) en heures normales 8h-18h.\n"
        "2. Installation, sécurisation de la zone, dépose si nécessaire.\n"
        "3. Fourniture et pose des articles de cette option uniquement.\n"
        "4. Essais, nettoyage et repli de chantier.\n\n"
        f"Déplacement : {days:g} jour(s) de présence sur site = {days:g} forfait(s) "
        f"déplacement (tarif catalogue / 40 € HT par jour par défaut). "
        "Un jour de travaux = un déplacement, sauf consigne contraire.\n\n"
        f"Main-d'œuvre : {hours:g} heure(s)-homme, {crew:g} personne(s), "
        f"plafond 7 h/personne/jour (tarif catalogue / 42 € HT/h par défaut). "
        "Les heures couvrent pose, essais et repli. Estimation si le métré n'est pas mesuré.\n\n"
        "Toute contrainte non visible au métré pourra faire l'objet d'une adaptation après accord."
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
