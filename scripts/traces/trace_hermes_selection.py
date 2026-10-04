# -*- coding: utf-8 -*-
"""Trace réelle : le VRAI moteur de matching sur le VRAI catalogue de l'entreprise.
Demande : « Remplacement du chauffe-eau électrique 100 L de la cuisine »
Hermes (role=reason) produit les line_items comme EXPAND_SYSTEM l'exige.
"""
import json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'backend'))
import matching as match_engine

# ── Articles RÉELS du catalogue de l'entreprise (tenant 9171d808, pricing_items) ──
catalog = [
    # (code, label, category, unit, prix HT, marge)
    ("PLB-037", "Chauffe-eau electrique 100 L", "04 plomberie sanitaire", "u", 373.05),
    ("PLB-038", "Groupe de securite chauffe-eau", "04 plomberie sanitaire", "u", 13.35),
    ("PLB-019", "Flexible sanitaire ACS 50 cm", "04 plomberie sanitaire", "u", 2.59),
    ("MTC-014", "Anticalcaire chauffe-eau", "16 maintenance", "u", 60.50),
    ("PLB-032", "Abattant WC double", "04 plomberie sanitaire", "u", 34.05),
]
items = []
for code, label, cat, unit, price in catalog:
    items.append({
        "item_code": code, "item_label": label,
        "label_norm": match_engine.normalize(label),
        "category": cat, "unit": unit, "unit_price_ht": price,
        "currency": "EUR", "vat_rate": None, "min_qty": 1,
        "is_active": True, "notes": "",
    })

# ── Sortie d'Hermes (gpt-oss:20b, prompt EXPAND_SYSTEM, SANS prix) ──
extracted = {
    "description": "Remplacement du chauffe-eau electrique 100 L de la cuisine",
    "work_type": "plomberie sanitaire",
    "intervention_site": "Cuisine",
    "line_items": [
        {"description": "chauffe-eau electrique 100 l", "quantity": 1, "unit": "u",
         "category": "plomberie sanitaire", "line_type_hint": "main_work", "included_items": [], "notes": None},
        {"description": "groupe de securite chauffe-eau", "quantity": 1, "unit": "u",
         "category": "plomberie sanitaire", "line_type_hint": "installation_supplies", "included_items": [], "notes": None},
        {"description": "flexible sanitaire acs 50 cm", "quantity": 2, "unit": "u",
         "category": "plomberie sanitaire", "line_type_hint": "installation_supplies", "included_items": [], "notes": None},
        {"description": "Fournitures de pose et consommables : visserie, joints d'etancheite, mastic — forfait",
         "quantity": 1, "unit": "forfait", "category": "plomberie sanitaire",
         "line_type_hint": "consumable", "included_items": [], "notes": None},
        {"description": "protection sol et evacuation de l'ancien appareil", "quantity": 1, "unit": "forfait",
         "category": "plomberie sanitaire", "line_type_hint": "protection", "included_items": [], "notes": None},
    ],
}

print("=" * 78)
print("ÉTAPE 1 — match_line() sur chaque ligne Hermes (scoring réel, seuil 45/90)")
print("=" * 78)
for li in extracted["line_items"]:
    m = match_engine.match_line(li, items)
    if m is None:
        print(f"  {li['description'][:45]:<47} → aucun résultat")
        continue
    print(f"  {li['description'][:45]:<47}")
    print(f"      → best: {m['item']['item_code']} « {m['item']['item_label']} »")
    print(f"      score={m['score']}  status={m['status']}")
    for r in m["reasons"]:
        print(f"      raison: {r}")

print()
print("=" * 78)
print("ÉTAPE 2 — build_quote_lines() : CE QUE FAIT server.py LIGNE 1800")
print("=" * 78)
lines, total_ht, total_vat = match_engine.build_quote_lines(dict(extracted), items)
for l in lines:
    typ = (l.get("line_type") or "?").replace("_", " ")
    if l.get("status") == "matched":
        print(f"  [{l['status']:>10}] {typ:<22} {l.get('matched_item_code')} « {l.get('matched_label')} »")
        print(f"              qté {l.get('qty')} {l.get('unit')} × {l.get('unit_price_ht')} € → {l.get('line_ht')} € HT"
              f"   (score {l.get('score')})")
    else:
        sug = f"  suggestion: {l.get('suggested_item_code')} « {l.get('suggested_label')} »" if l.get("suggested_item_code") else ""
        print(f"  [{l.get('status') or l.get('rubrique') or '—':>10}] {typ:<22} {l.get('description') or l.get('request_label','')[:60]}"
              f"{sug}")
print()
print(f"  TOTAL DEVIS : {total_ht} € HT (TVA devis = {total_vat} €)")

print()
print("=" * 78)
print("ÉTAPE 3 — wrap_in_lots() : structure TCE finale (lots ANELEC)")
print("=" * 78)
lots = match_engine.wrap_in_lots(lines)
def walk(node, depth=0):
    if isinstance(node, dict):
        label = node.get("title") or node.get("description") or node.get("label") or ""
        ht = node.get("line_ht") or node.get("subtotal_ht")
        price = f" — {ht} € HT" if ht is not None else ""
        print("  " * depth + f"• {label[:70]}{price}")
        for k in ("lines", "items", "children"):
            for c in (node.get(k) or []):
                walk(c, depth + 1)
for lot in lots:
    walk(lot)

print()
print("=" * 78)
print("ÉTAPE 4 — estimate_chantier() : main-d'œuvre/déplacement (barème, pas l'IA)")
print("=" * 78)
chantier = match_engine.estimate_chantier(extracted)
print(json.dumps(chantier, indent=2, ensure_ascii=False, default=str)[:900])
