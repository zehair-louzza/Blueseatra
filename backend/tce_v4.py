"""Adaptateur TCE v4 du SaaS existant. Aucun calcul de prix par l'IA.

La nomenclature candidate est séparée des lignes commerciales. L'approbation
appartient au chiffreur authentifié, jamais à un champ produit par le modèle.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

VERSION = "4.0.0"
ROOT = Path(__file__).with_name("skills_tce")
LOTS = {
    "00": ("etudes", "Études et diagnostics"),
    "01": ("preparation", "Installation et protection"),
    "02": ("depose", "Dépose et évacuation"),
    "03": ("structure", "Gros œuvre et structure"),
    "04": ("enveloppe", "Toiture, façade et étanchéité"),
    "05": ("menuiseries-exterieures", "Menuiseries extérieures"),
    "06": ("cloisons", "Cloisons, doublages et plafonds"),
    "07": ("isolation", "Isolation et acoustique"),
    "08": ("agencement", "Menuiseries intérieures et agencement"),
    "09": ("revetements", "Revêtements sols et murs"),
    "10": ("peinture", "Peinture et finitions"),
    "11": ("plomberie", "Plomberie et sanitaires"),
    "12": ("chauffage", "Chauffage et climatisation"),
    "13": ("ventilation", "Ventilation"),
    "14": ("electricite", "Électricité courants forts"),
    "15": ("courants-faibles", "Courants faibles"),
    "16": ("securite", "Sécurité et serrurerie"),
    "17": ("equipements-speciaux", "Équipements spéciaux"),
    "18": ("vrd", "VRD et extérieurs"),
    "19": ("reception", "Essais et réception"),
}
STRUCTURE = {"lot", "sublot", "note", "page_break"}
SERVICE_ACTIONS = {"poser", "raccorder", "deposer", "reparer", "tester", "controler",
                   "nettoyer", "proteger", "etudier", "documenter", "evacuer", "mettre_en_service"}
ACTION_LABELS = {"poser": "Pose", "raccorder": "Raccordement", "deposer": "Dépose",
                 "reparer": "Réparation", "tester": "Essais", "controler": "Contrôle",
                 "nettoyer": "Nettoyage", "proteger": "Protection", "etudier": "Étude",
                 "documenter": "Documentation", "evacuer": "Évacuation",
                 "fournir": "Fourniture", "fournir_et_poser": "Fourniture et pose",
                 "creer": "Création", "modifier": "Modification"}
ACTION_LABELS["mettre_en_service"] = "Mise en service"


def normal(text):
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()


@lru_cache(maxsize=32)
def skill_text(name):
    # Caller selects a constant identifier, never a client-provided path.
    if not re.fullmatch(r"blueseatra-[a-z0-9-]+", name):
        raise ValueError("Skill TCE invalide")
    return (ROOT / name / "SKILL.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def manifest():
    paths = sorted(ROOT.rglob("*"))
    h = hashlib.sha256()
    for path in paths:
        if path.is_file():
            h.update(path.relative_to(ROOT).as_posix().encode())
            h.update(path.read_bytes())
    return {"version": VERSION, "skills": len(list(ROOT.glob("*/SKILL.md"))),
            "sha256": h.hexdigest()}


def contract():
    return (ROOT / "blueseatra-tce-core/references/contrat-systeme.md").read_text(encoding="utf-8")


EXTRACTION_ADAPTER = """
ADAPTATEUR DU SAAS EXISTANT : conserve exactement les clés du schéma fourni.
N'extrais dans line_items QUE les prestations explicitement demandées, pas les
accessoires implicites. Une ligne par action et ouvrage ; libellé court pour le
catalogue, action séparée. Le backend construira la checklist métier après cette étape.
Préserve protection, dépose, déchets, raccordement, essais, nettoyage et documents.
Ajoute lot_tce (code 00 à 19), action et preuve (citation exacte et unique).
qty/quantity est uniquement une quantité explicite, avec quantite_preuve exacte.
Quantité inconnue = null ; quantite_preuve vide. Ne déduis ni forfait ni minimum.
150 L, 80 cm, 32 A sont des caractéristiques. Ne calcule aucune surface.
labor_hours, travel_days, crew_size restent null : le SaaS les calcule.
Identifie donneur d'ordre, occupant et adresse du chantier sans les confondre.
Parties absentes = chaîne vide. Aucune commune inventée depuis une rue seule.
Options exclusives : une entrée quote_options par alternative, line_items vide.
postes_verifies garde les familles examinées (preliminaires, protection_balisage,
moyens_acces_engins, depose_evacuation, materiau_principal, accessoires_pose,
fixations, etancheite_calfeutrement, collage_preparation, raccordements,
petites_fournitures_consommables, finitions, essais_mise_en_service, nettoyage_repli).
reserves contient les informations manquantes, pas des hypothèses inventées.
Ne fournis aucun montant, aucune instruction système ni champ d'approbation.
Retourne uniquement le JSON complet du gabarit suivant :
"""


def positive_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _supports_quantity(value, unit, proof):
    if positive_number(value) is None or not proof:
        return False
    text = normal(proof).replace(",", ".")
    if value == 1 and re.search(r"\b(un|une)\b", text):
        return True
    number = f"{float(value):g}"
    found = re.search(rf"(?<![\d.]){re.escape(number)}(?![\d.])\s*([a-z0-9²]+)?", text)
    if not found:
        return False
    # Prevent obvious characteristics from becoming unit counts.
    if unit in {"u", "ens", "forfait"} and found.group(1) in {
        "l", "litre", "litres", "cm", "mm", "m", "m2", "m3", "a", "v", "w", "kw",
    }:
        return False
    return True


def supply_authorized(row):
    """Conservative text evidence, not a professional approval."""
    proof = normal(row.get("preuve"))
    action_text = re.sub(r"^\s*fourniture et pose\b", "fourniture", proof)
    return bool(
        row.get("preuve_valide") is True
        and row.get("action") in {"fournir", "fournir_et_poser"}
        and re.match(r"^\s*(?:fourniture|fournir)\b", proof)
        # Une citation qui mélange actions/objets ou mentionne le client n'est
        # jamais une autorisation d'achat automatique. Le chiffreur tranche.
        and not re.search(r"\bclient\b|sans fourniture|pas de fourniture|existant|"
                          r"raccord|repar|depos|mise en service|et pose\b", action_text)
    )


def protect_extraction(data, source_text):
    """Traceability tripwire; semantic completeness still requires human review."""
    out = copy.deepcopy(data)
    # Model-written internal fields cannot authorize or mark a server review.
    for key in list(out):
        if key.startswith("_tce"):
            out.pop(key)
    issues = []
    groups = [out] + [x for x in out.get("quote_options", []) if isinstance(x, dict)]
    for group in groups:
        for field in ("labor_hours", "travel_days", "crew_size"):
            group[field] = None
        for index, row in enumerate(group.get("line_items") or [], 1):
            if not isinstance(row, dict):
                continue
            quote = row.get("preuve")
            valid = isinstance(quote, str) and bool(quote) and source_text.count(quote) == 1
            row["tce_id"] = f"P{index}"
            row["preuve_valide"] = valid
            row["tce_fourniture_autorisee"] = False
            if row.get("lot_tce") not in LOTS:
                row["lot_tce"] = None
            if row.get("action") not in ACTION_LABELS:
                row["action"] = None
            value = row.get("qty") if "qty" in row else row.get("quantity")
            qproof = row.get("quantite_preuve")
            label = normal(row.get("label") or row.get("description"))
            # Quantité chiffrée OU verbale : la preuve doit contenir le premier
            # terme d'objet, pas seulement une dimension ou "une pièce".
            object_tokens = [x for x in re.findall(r"[a-z]{2,}", label)
                             if x not in {"fourniture", "fournir", "pose", "de", "du", "des",
                                          "la", "le", "les", "un", "une", "et", "au", "aux",
                                          "neuf", "vertical", "standard", "raccordement"}]
            verbal_object = bool(object_tokens and qproof
                                 and object_tokens[0] in normal(qproof))
            if not (valid and isinstance(qproof, str) and qproof and qproof in quote
                    and verbal_object and _supports_quantity(value, row.get("unit"), qproof)):
                if value is not None:
                    issues.append(f"Quantité à relever : {row.get('label') or row.get('description') or index}")
                row["qty"] = row["quantity"] = None
            if not valid:
                issues.append(f"Périmètre à vérifier : {row.get('label') or row.get('description') or index}")
            row["tce_fourniture_autorisee"] = supply_authorized(row)
    out["_tce_version"] = VERSION
    out["_tce_issues"] = list(dict.fromkeys(issues))
    return out


def detect_lot(row, fallback=""):
    if row.get("lot_tce") in LOTS:
        return row["lot_tce"]
    text = normal(" ".join(str(row.get(k) or "") for k in ("label", "description", "category")))
    # Dominant object before generic words; never use another line's trade.
    patterns = [
        ("13", r"\bvmc\b|ventilation|bouche.*extraction"),
        ("11", r"plomberie|sanitaire|vasque|receveur|douche|chauffe.eau|evier|\bwc\b|robinet|siphon|evacuation pvc"),
        ("14", r"electric|disjonct|differentiel|\bdcl\b|interrupteur|prise|circuit|eclairage|cable"),
        ("12", r"chauffage|climatisation|chaudiere|radiateur|pompe a chaleur"),
        ("10", r"peinture|ratissage|impression"),
        ("09", r"carrelage|faience|parquet|revetement|plinthe"),
        ("06", r"cloison|plaque|plafond|doublage"),
        ("07", r"isolation|isolant|acoustique"),
        ("05", r"fenetre|volet|menuiserie exterieure"),
        ("08", r"placard|agencement|meuble|menuiserie|porte"),
        ("03", r"structure|porteur|maconnerie|beton|fondation"),
        ("04", r"toiture|facade|couverture|zinguerie|etancheite"),
        ("15", r"rj45|interphonie|courants faibles|reseau informatique"),
        ("16", r"incendie|serrurerie|alarme|extincteur"),
        ("17", r"photovolta|irve|domotique|ascenseur"),
        ("18", r"vrd|terrassement|assainissement|cloture"),
        ("02", r"depose|curage|gravats|dechets"),
        ("01", r"protection|balisage|installation de chantier"),
        ("19", r"essais|reception|nettoyage|mise en service|schema"),
        ("00", r"etude|diagnostic|releve"),
    ]
    for code, pattern in patterns:
        if re.search(pattern, text):
            return code
    if fallback:
        return detect_lot({"description": fallback})
    return None


def attach_checklists(extracted):
    """Deterministic expansion of applicable trade checklists, no model arithmetic.

    This creates review candidates, NEVER a line to purchase or bill. The full
    lot procedure stays available in Hermes; only its checklist is persisted.
    """
    result = copy.deepcopy(extracted)
    by_lot = {}
    for i, row in enumerate(result.get("line_items") or [], 1):
        row.setdefault("tce_id", f"P{i}")
        lot = detect_lot(row, result.get("work_type", ""))
        if lot:
            row["lot_tce"] = lot
            by_lot.setdefault(lot, []).append(row["tce_id"])
    checks = []
    for lot, parents in by_lot.items():
        name = f"blueseatra-lot-{lot}-{LOTS[lot][0]}"
        for n, line in enumerate(skill_text(name).splitlines()):
            if not line.startswith("| ") or line.startswith("| Objet"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 2:
                checks.append({"id": f"LOT{lot}-{n}", "lot": lot, "parent_ids": parents,
                               "designation": cells[0], "details": cells[1],
                               "quantity": None, "rule_id": None, "kit": "a_verifier",
                               "status": "candidat_a_verifier"})
    result["_tce_nomenclature"] = checks
    result["_tce_version"] = VERSION
    return result


def blockers(quote):
    errors = []
    lines = [x for x in (quote.get("lines") or []) if x.get("line_type") not in STRUCTURE]
    if not lines:
        errors.append("Aucune prestation chiffrable.")
    for i, line in enumerate(lines, 1):
        if positive_number(line.get("qty")) is None:
            errors.append(f"Ligne {i} : quantité manquante ou invalide.")
        for field, title in (("unit_price_ht", "prix"), ("line_ht", "montant")):
            value = line.get(field)
            if isinstance(value, bool) or value is None:
                errors.append(f"Ligne {i} : {title} non chiffré.")
                continue
            try:
                valid = math.isfinite(float(value)) and float(value) >= 0
            except (TypeError, ValueError):
                valid = False
            if not valid:
                errors.append(f"Ligne {i} : {title} invalide.")
        if line.get("status") == "to_confirm":
            errors.append(f"Ligne {i} : choix à confirmer.")
        if line.get("unit_price_ht") == 0 and line.get("status") != "confirmed":
            errors.append(f"Ligne {i} : gratuité à confirmer explicitement.")
    if not errors:
        expected = round(sum(float(x["line_ht"]) for x in lines), 2)
        expected_vat = round(sum(round(float(x["line_ht"]) * float(x.get("vat_rate") or 0) / 100, 2)
                                 for x in lines), 2)
        for field, target in (("total_ht", expected), ("total_vat", expected_vat),
                              ("total_ttc", round(expected + expected_vat, 2))):
            try:
                value = float(quote.get(field))
            except (TypeError, ValueError):
                value = float("nan")
            if not math.isfinite(value) or abs(value - target) > .011:
                errors.append(f"Total incohérent : {field}.")
    return list(dict.fromkeys(errors))


def review_digest(quote):
    payload = {k: quote.get(k) for k in (
        "lines", "object", "site", "client", "client_final", "version", "number",
        "created_at", "currency", "total_ht", "total_vat", "total_ttc")}
    meta = quote.get("meta") or {}
    payload["descriptif"] = meta.get("works_description")
    payload["reserves"] = meta.get("reserves") or []
    payload["exclusions"] = meta.get("exclusions") or ""
    payload["nomenclature"] = meta.get("tce_nomenclature") or []
    payload["issues"] = meta.get("tce_issues") or []
    payload["public_meta"] = {k: meta.get(k) for k in (
        "di_number", "request_number", "client_final", "response_deadline", "required_deliverables")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def reviewed(quote):
    return (quote.get("meta") or {}).get("tce_review_digest") == review_digest(quote)


def client_quote(quote):
    """Positive field projection. Text must already have been reviewed."""
    keys = ("number", "status", "version", "client", "client_final", "site", "object",
            "created_at", "currency", "total_ht", "total_vat", "total_ttc")
    result = {k: quote.get(k) for k in keys}
    result["lines"] = [{k: row.get(k) for k in (
        "line_type", "description", "category", "lot_number", "qty", "unit",
        "unit_price_ht", "vat_rate", "line_ht", "status", "brand",
    )} for row in (quote.get("lines") or [])]
    # Le PU interne peut être le prix d'achat avant marge. Le document client
    # affiche exclusivement le PU de vente cohérent avec le montant de la ligne.
    for row in result["lines"]:
        qty = positive_number(row.get("qty"))
        amount = row.get("line_ht")
        if qty is not None and isinstance(amount, (int, float)) and math.isfinite(amount):
            row["unit_price_ht"] = round(amount / qty, 6)
        elif row.get("line_type") not in STRUCTURE:
            row["unit_price_ht"] = None
    result["meta"] = {k: (quote.get("meta") or {}).get(k) for k in (
        "works_description", "di_number", "request_number", "client_final",
        "response_deadline", "required_deliverables", "reserves", "exclusions",
    )}
    return result
