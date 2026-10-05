"""Synchronise mécaniquement les contrats historiques avec l'adaptateur TCE v4.

Les schémas et les deux constantes de prompts sont dérivés, pas modifiés à la main.
Ne touche ni au moteur tarifaire, ni à l'authentification, ni aux secrets.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
schema_path = ROOT / "backend/schemas_ia/extraire_demande_travaux.json"
schema = json.loads(schema_path.read_text(encoding="utf-8"))
p = schema["properties"]
for key in ("labor_hours", "travel_days", "crew_size"):
    p[key]["description"] = "Toujours null côté IA ; calcul et validation par le SaaS."
p["line_items"]["description"] = (
    "Prestations explicitement demandées uniquement, avec preuve exacte, action et lot. "
    "Accessoires implicites dans la nomenclature candidate séparée du backend."
)
groups = [p, p["quote_options"]["items"]["properties"]]
for group in groups:
    for key in ("labor_hours", "travel_days", "crew_size"):
        group[key]["description"] = "Toujours null côté IA ; calcul par le SaaS."
    row = group["line_items"]["items"]
    rp = row["properties"]
    qty_key = "qty" if "qty" in rp else "quantity"
    rp[qty_key]["description"] = "Quantité explicitement écrite et prouvée, sinon null. Aucun minimum ni calcul."
    rp["notes"]["description"] = "Information à relever ou réserve explicite. Aucune hypothèse inventée."
    for key, definition in {
        "action": {"type": ["string", "null"], "enum": [
            "fournir", "poser", "fournir_et_poser", "deposer", "creer", "modifier",
            "reparer", "raccorder", "tester", "mettre_en_service", "nettoyer",
            "proteger", "etudier", "controler", "evacuer", "documenter", None,
        ]},
        "lot_tce": {"type": ["string", "null"], "enum": [f"{i:02}" for i in range(20)] + [None]},
        "preuve": {"type": "string", "description": "Citation exacte unique de la prestation, sans reformulation."},
        "quantite_preuve": {"type": "string", "description": "Citation exacte justifiant la quantité ; vide si inconnue."},
    }.items():
        rp[key] = definition
        # Additive contract for stored legacy extractions; prompt requires these
        # fields and the backend nulls quantities if the proof is missing.
schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

source_path = ROOT / "backend/ai_service.py"
source = source_path.read_text(encoding="utf-8")
lines = source.splitlines(keepends=True)
replacements = {
    "EXTRACTION_SYSTEM": (
        "EXTRACTION_SYSTEM = tce_v4.contract() + tce_v4.EXTRACTION_ADAPTER + _SCHEMA_EXTRACTION_TXT\n"
    ),
    "EXPAND_SYSTEM": (
        'EXPAND_SYSTEM = tce_v4.contract() + "\\nNomenclature : candidats seulement, quantity=null, '
        'rule_id=null sans règle approuvée. Ne remplace jamais les prestations extraites.\\n"\n'
    ),
}
for node in sorted(ast.parse(source).body, key=lambda n: n.lineno, reverse=True):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        name = node.targets[0].id
        if name in replacements:
            lines[node.lineno - 1:node.end_lineno] = [replacements[name]]
source_path.write_text("".join(lines), encoding="utf-8")
print("Contrats TCE synchronisés (schéma historique + deux prompts).")
