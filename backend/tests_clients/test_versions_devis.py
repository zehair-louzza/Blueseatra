"""Ticket #85 : comparaison des versions d'un devis (fonctions pures)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from quote_versions_diff import comparer, resume_version  # noqa: E402


def devis(lignes, **kw):
    base = {"client": "FONCIA", "site": "Versailles", "object": "Dalles LED", "client_final": "Carrefour",
            "total_ht": sum(l.get("line_ht") or 0 for l in lignes), "total_vat": 0, "total_ttc": 0}
    base.update(kw)
    base["lines"] = lignes
    return base


L_MO = {"line_type": "labour", "description": "Main d'oeuvre pose", "qty": 6, "unit": "h", "unit_price_ht": 42, "line_ht": 252}
L_DEP = {"line_type": "travel", "description": "Déplacement", "qty": 1, "unit": "j", "unit_price_ht": 40, "line_ht": 40}
L_LOT = {"line_type": "lot", "description": "Électricité", "lot_number": "1"}


def test_versions_identiques():
    r = comparer(devis([L_LOT, L_MO, L_DEP]), devis([L_LOT, L_MO, L_DEP]))
    assert r["identique"] and not r["modifiees"]


def test_ligne_modifiee_ajoutee_supprimee_et_totaux():
    mo2 = {**L_MO, "qty": 8, "line_ht": 336}
    ajout = {"line_type": "material", "description": "Dalle LED 600x600", "matched_item_code": "LED-60",
             "qty": 6, "unit": "u", "unit_price_ht": 25, "line_ht": 150}
    r = comparer(devis([L_LOT, L_MO, L_DEP]), devis([L_LOT, mo2, ajout]))
    assert [m["description"] for m in r["modifiees"]] == ["Main d'oeuvre pose"]
    assert r["modifiees"][0]["champs"]["qty"] == {"avant": 6, "apres": 8}
    assert [a["code"] for a in r["ajoutees"]] == ["LED-60"]
    assert [s["description"] for s in r["supprimees"]] == ["Déplacement"]
    assert r["totaux"]["total_ht"]["ecart"] == 336 + 150 - 292
    assert not r["identique"]


def test_accents_et_casse_ne_creent_pas_de_fausse_difference():
    r = comparer(devis([L_DEP]), devis([{**L_DEP, "description": "deplacement "}]))
    assert r["identique"]


def test_entete_et_doublons_conserves():
    r = comparer(devis([L_MO]), devis([L_MO, dict(L_MO)], client="CITYA"))
    assert r["entete"]["client"] == {"avant": "FONCIA", "apres": "CITYA"}
    assert len(r["ajoutees"]) == 1


def test_resume_ignore_lots_et_notes():
    assert resume_version(devis([L_LOT, L_MO, {"line_type": "note", "description": "x"}]))["lignes"] == 1
