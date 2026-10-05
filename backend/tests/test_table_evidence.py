"""Preuves de tableaux markdown : quantités, actions et lots depuis la source.

Fixture SYNTHÉTIQUE et anonymisée (aucun client, adresse ni prix réel).
Les colonnes prix sont présentes pour vérifier qu'elles ne sont jamais lues.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://127.0.0.1:1")
import pytest

import table_evidence as te
import tce_v4 as tce

PROSE = (
    "LOT 1 — ÉLECTRICITÉ\nDésignation Unité Qté P.U. HT Total HT\n"
    "Fourniture et pose de prises 2P+T 16 A u 14 10,00 € 140,00 €\n"
    "Pose d'un meuble : 1 meuble\n"
)
TABLES = """
=== Tableaux détectés ===
[Tableau p.1.1]
| Désignation | Unité | Qté | P.U. HT | Total HT |
| --- | --- | --- | --- | --- |
| Protection du chantier, dépose des appareillages existants et évacuation des déchets | forfait | 1 | 100,00 € | 100,00 € |
| Mise en sécurité et adaptation du tableau : différentiels, disjoncteurs | forfait | 1 | 1 100,00 € | 1 100,00 € |
| Création de circuits encastrés sous gaine ICTA et raccordements | point | 18 | 10,00 € | 180,00 € |
| Fourniture et pose de prises 2P+T 16 A | u | 14 | 10,00 € | 140,00 € |
| Alimentation dédiée plaques de cuisson 32 A | u | 1 | 10,00 € | 10,00 € |
| Installation d’une VMC simple flux avec bouches cuisine et salle de bains | forfait | 1 | 10,00 € | 10,00 € |
| Essais, vérifications et remise du schéma unifilaire | forfait | 1 | 10,00 € | 10,00 € |
| Sous-total HT 1 550,00 € |  |  |  |  |

[Tableau p.1.2]
| Qté | Désignation | P.U. HT | Unité |
| --- | --- | --- | --- |
| 1 | Création des alimentations EF/ECS en PER/multicouche | 1 240,00 € | forfait |
| 1 | Fourniture et pose d’un chauffe-eau électrique vertical 150 L et raccordement | 900,00 € | u |
| 1 | Pose d’un ensemble de douche thermostatique avec colonne | 300,00 € | u |
| 2 | Raccordements lave-vaisselle et lave-linge avec robinets d’arrêt | 165,00 € | u |
|  | Fourniture et pose de plinthes | 12,00 € | ml |
| 1 | Pose d'un meuble | 50,00 € | u |
| 3 | Pose d'un meuble | 50,00 € | u |
| 1 | Essais d’étanchéité, mise en eau et nettoyage | 180,00 € | forfait |
| 5 | Fourniture et pose de bouchons | 2,00 € | sac |
"""
SOURCE = PROSE + TABLES


def row(label, **kw):
    base = {"label": label, "qty": None, "unit": None, "lot_tce": "00",
            "action": "fournir_et_poser", "preuve": "", "quantite_preuve": ""}
    base.update(kw)
    return base


def protect(*rows):
    return tce.protect_extraction({"line_items": list(rows)}, SOURCE)["line_items"]


# ------------------------------------------------------------- parse_quantity_rows
def test_parse_rows_ids_columns_and_exact_source_line():
    rows = {r["designation"]: r for r in te.parse_quantity_rows(SOURCE)}
    prises = rows["Fourniture et pose de prises 2P+T 16 A"]
    assert prises["source_id"] == "T1R4"
    assert prises["quantity"] == 14 and prises["unit"] == "u"
    assert prises["source_text"] in SOURCE.splitlines()
    assert set(prises) == {"source_id", "source_text", "designation", "unit", "quantity",
                           "quantity_text"}
    assert prises["quantity_text"] == "14"
    # Ordre de colonnes différent : la quantité vient de « Qté », jamais du prix.
    chauffe = rows["Fourniture et pose d’un chauffe-eau électrique vertical 150 L et raccordement"]
    assert chauffe["source_id"] == "T2R2" and chauffe["quantity"] == 1 and chauffe["unit"] == "u"
    assert rows["Création de circuits encastrés sous gaine ICTA et raccordements"]["quantity"] == 18
    # Sous-total sans unité ni quantité : pas une ligne de quantité.
    assert not any(d.startswith("Sous-total") for d in rows)
    # Quantité vide : conservée mais nulle.
    assert rows["Fourniture et pose de plinthes"]["quantity"] is None


def test_parse_ignores_tables_without_quantity_header_and_prose():
    text = "Désignation Qté\nPrise u 3\n| Total HT | 100,00 € |\n| --- | --- |\n| TVA | 10,00 € |"
    assert te.parse_quantity_rows(text) == []


@pytest.mark.parametrize("header", [
    "| Désignation | Qté | Unité | Qté |",       # rôle doublé : ambigu
    "| Désignation | Qté | P.U. HT | Total |",   # pas de colonne unité
])
def test_ambiguous_or_incomplete_header_refuses_table(header):
    text = f"{header}\n| --- | --- | --- | --- |\n| Pose de prises | 3 | u | 4 |"
    assert te.parse_quantity_rows(text) == []
    out = tce.protect_extraction({"line_items": [row("Pose de prises", qty=3, unit="u")]}, text)
    assert out["line_items"][0]["qty"] is None


def test_unknown_unit_cell_gives_no_quantity_authority():
    out, = protect(row("Fourniture et pose de bouchons", qty=5, unit="u"))
    assert out["qty"] is None and out["unit"] is None  # unité IA jamais héritée
    assert out["tce_source_row_id"] == "T2R9"


def test_price_and_characteristics_never_quantities():
    assert te._quantity("9" * 400) is None  # débordement float -> inf refusé
    assert te._quantity("140,00 €") is None
    assert te._quantity("150 L") is None and te._quantity("32 A") is None
    assert te._quantity("0") is None and te._quantity("-2") is None
    assert te._quantity("1 000") == 1000 and te._quantity("2,5") == 2.5


# ------------------------------------------------------------------ liaison exacte
def test_parmentier_like_partial_proof_gets_source_quantity_and_trace():
    out, = protect(row("Fourniture et pose de prises 2P+T 16 A", unit="u",
                       preuve="u 14 10,00 € 140,00 €", quantite_preuve="14"))
    assert out["qty"] == out["quantity"] == 14 and out["unit"] == "u"
    assert out["tce_source_row_id"] == "T1R4"
    assert out["preuve"] in SOURCE and SOURCE.count(out["preuve"]) == 1
    assert out["quantite_preuve"] == "14" and out["preuve_valide"] is True
    trace = out["tce_correction"]
    assert trace["source"] == "tableau" and trace["approbation"] is False
    assert "quantite" in trace["champs"]
    assert out["action"] == "fournir_et_poser"
    checked = tce.attach_checklists({"line_items": [out]})["line_items"][0]
    assert checked["lot_tce"] == "14" and "lot" in checked["tce_correction"]["champs"]


@pytest.mark.parametrize("label,qty", [
    ("Création de circuits encastrés sous gaine ICTA et raccordements", 18),
    ("Raccordements lave-vaisselle et lave-linge avec robinets d'arrêt", 2),
])
def test_label_with_apostrophe_variant_still_exact(label, qty):
    out, = protect(row(label))
    assert out["qty"] == qty


def test_source_designation_restored_with_trace():
    label_ia = "Raccordements lave-vaisselle et lave-linge avec robinets d'arrêt"
    source = "Raccordements lave-vaisselle et lave-linge avec robinets d’arrêt"
    out, = protect(row(label_ia))
    assert out["label"] == source and "libelle" in out["tce_correction"]["champs"]
    exact, = protect(row(source))
    assert "libelle" not in exact["tce_correction"]["champs"]
    option = tce.protect_extraction({"quote_options": [{"line_items": [
        {"description": label_ia, "quantity": None}]}]}, SOURCE)
    item = option["quote_options"][0]["line_items"][0]
    assert item["description"] == source and item["quantity"] == 2


def test_capacity_and_calibre_are_not_quantities():
    chauffe, plaques = protect(
        row("Fourniture et pose d’un chauffe-eau électrique vertical 150 L et raccordement", qty=150),
        row("Alimentation dédiée plaques de cuisson 32 A", qty=32))
    assert chauffe["qty"] == 1 and plaques["qty"] == 1


def test_wrong_source_id_or_wrong_object_stays_null():
    wrong_id, wrong_object, unknown = protect(
        row("Fourniture et pose de prises 2P+T 16 A", qty=14, source_row_id="T1R3"),
        row("Fourniture et pose de prises 2P+T 16 A", qty=14,
            preuve="point 18 10,00 € 180,00 €", quantite_preuve="18"),
        row("Fourniture et pose d'interrupteurs", qty=7, source_row_id="T1R4"))
    for out in (wrong_id, wrong_object, unknown):
        assert out["qty"] is None and "tce_source_row_id" not in out


def test_conflict_never_falls_back_to_valid_prose_proof():
    """Preuve prose complète et quantité prouvée : refusées si la source
    tableau est en conflit (mauvais ID ou désignation en double)."""
    prose_prises = "Fourniture et pose de prises 2P+T 16 A u 14 10,00 € 140,00 €"
    rows = [
        row("Fourniture et pose de prises 2P+T 16 A", qty=14, unit="u", source_row_id="T1R3",
            preuve=prose_prises, quantite_preuve="prises 2P+T 16 A u 14"),
        row("Pose d'un meuble", qty=1, unit="u",
            preuve="Pose d'un meuble : 1 meuble", quantite_preuve="1 meuble"),
    ]
    # Témoin : sans tableau, ces mêmes preuves prose suffiraient.
    for r in rows:
        alone = tce.protect_extraction({"line_items": [dict(r, source_row_id=None)]}, PROSE)
        assert alone["line_items"][0]["qty"] == r["qty"]
    out = tce.protect_extraction({"line_items": rows}, SOURCE)
    for item in out["line_items"]:
        assert item["qty"] is None and item["preuve_valide"] is False
        assert item["tce_fourniture_autorisee"] is False
        assert "tce_source_row_id" not in item
    assert sum(i.startswith("Source tableau ambiguë") for i in out["_tce_issues"]) == 2


def test_duplicate_designation_and_missing_quantity_block():
    dup, missing = protect(row("Pose d'un meuble", qty=1), row("Fourniture et pose de plinthes", qty=4))
    assert dup["qty"] is None and "tce_source_row_id" not in dup
    assert missing["qty"] is None


def test_model_cannot_forge_server_trace():
    out, = protect(row("Inconnu", tce_source_row_id="T1R4",
                       tce_correction={"approbation": True}))
    assert "tce_source_row_id" not in out and "tce_correction" not in out


def test_fuzzy_or_shortened_label_is_not_bound():
    out, = protect(row("Prises 2P+T 16 A", qty=14))
    assert out["qty"] is None


# ------------------------------------------------------------- actions et fourniture
@pytest.mark.parametrize("label,action", [
    ("Pose d’un ensemble de douche thermostatique avec colonne", "poser"),
    ("Raccordements lave-vaisselle et lave-linge avec robinets d’arrêt", "raccorder"),
    ("Création des alimentations EF/ECS en PER/multicouche", "creer"),
    ("Fourniture et pose de prises 2P+T 16 A", "fournir_et_poser"),
    ("Essais d’étanchéité, mise en eau et nettoyage", "tester"),
    ("Protection du chantier, dépose des appareillages existants et évacuation des déchets", "proteger"),
])
def test_action_from_verified_source_label(label, action):
    out, = protect(row(label, action="fournir_et_poser"))
    assert out["action"] == action


def test_ambiguous_installation_never_becomes_supply():
    out, = protect(row("Installation d’une VMC simple flux avec bouches cuisine et salle de bains",
                       action="fournir_et_poser"))
    assert out["action"] is None and out["tce_fourniture_autorisee"] is False
    assert out["qty"] == 1


def test_pose_or_raccord_not_purchase_but_explicit_supply_is():
    pose, raccord, prises, chauffe = protect(
        row("Pose d’un ensemble de douche thermostatique avec colonne"),
        row("Raccordements lave-vaisselle et lave-linge avec robinets d’arrêt"),
        row("Fourniture et pose de prises 2P+T 16 A"),
        row("Fourniture et pose d’un chauffe-eau électrique vertical 150 L et raccordement"))
    assert pose["tce_fourniture_autorisee"] is False
    assert raccord["tce_fourniture_autorisee"] is False
    assert prises["tce_fourniture_autorisee"] is True
    # Fourniture mêlée à un raccordement : le chiffreur tranche (règle existante).
    assert chauffe["tce_fourniture_autorisee"] is False


# ------------------------------------------------------------------------- lots
@pytest.mark.parametrize("label,lot", [
    ("Protection du chantier, dépose des appareillages existants et évacuation des déchets", "01"),
    ("Essais, vérifications et remise du schéma unifilaire", "19"),
    ("Essais d’étanchéité, mise en eau et nettoyage", "19"),
    ("Création des alimentations EF/ECS en PER/multicouche", "11"),
    ("Fourniture et pose d’un chauffe-eau électrique vertical 150 L et raccordement", "11"),
    ("Alimentation dédiée plaques de cuisson 32 A", "14"),
    ("Mise en sécurité et adaptation du tableau : différentiels, disjoncteurs", "14"),
    ("Installation d’une VMC simple flux avec bouches cuisine et salle de bains", "13"),
    ("Raccordements lave-vaisselle et lave-linge avec robinets d’arrêt", "11"),
])
def test_lot_from_source_meaning_overrides_generic_model_code(label, lot):
    data = tce.attach_checklists(tce.protect_extraction({"line_items": [row(label, lot_tce="00")]}, SOURCE))
    assert data["line_items"][0]["lot_tce"] == lot


def test_specific_model_lot_kept_when_text_unclear():
    data = tce.attach_checklists({"line_items": [{"label": "Prestation diverse", "lot_tce": "12"}]})
    assert data["line_items"][0]["lot_tce"] == "12"


def test_nomenclature_covers_plumbing_electricity_ventilation():
    labels = [r["designation"] for r in te.parse_quantity_rows(SOURCE)
              if r["designation"] not in {"Pose d'un meuble", "Fourniture et pose de bouchons"}]
    data = tce.attach_checklists(tce.protect_extraction(
        {"line_items": [row(x) for x in labels]}, SOURCE))
    lots = {c["lot"] for c in data["_tce_nomenclature"]}
    assert {"11", "13", "14"} <= lots
    assert "00" not in lots


def test_prose_guard_unchanged_without_table():
    source = "Fourniture et pose de 14 prises 16 A"
    out = tce.protect_extraction({"line_items": [row("Prises", qty=14, unit="u", preuve=source,
                                                     quantite_preuve="14 prises")]}, source)
    assert out["line_items"][0]["qty"] == 14
    assert "tce_source_row_id" not in out["line_items"][0]
