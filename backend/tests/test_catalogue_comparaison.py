"""Ticket #86 : comparaison de versions de catalogue et seuils avant activation."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from catalogue_comparaison import comparer, controler


def art(code, label, prix, unit="u"):
    return {"item_code": code, "item_label": label, "label_norm": label.lower(), "unit_price_ht": prix, "unit": unit}


ACTIFS = [art("R1", "Dalle LED", 25), art("R2", "Câble 3G1.5", 1.2, "m"), art("R3", "Boîte de dérivation", 3)]


def test_ajouts_retraits_hausses_baisses():
    nouv = [art("R1", "Dalle LED 600", 30), art("R2", "Câble 3G1.5", 1.0, "m"), art("R4", "Interrupteur", 5)]
    c = comparer(ACTIFS, nouv)
    assert (c["ajoutes"], c["retires"], c["hausses"], c["baisses"]) == (1, 1, 1, 1)
    assert c["plus_fortes_hausses"][0]["variation_pct"] == 20.0
    assert controler(nouv, 0, 3, c)["verdict"] == "OK"


def test_codes_generes_compares_par_libelle():
    a = [art("ART-2", "Dalle LED", 25)]
    n = [art("ART-9", "Dalle LED", 25)]
    assert comparer(a, n)["inchanges"] == 1


def test_chute_de_lignes_et_prix_negatif_bloquent():
    nouv = [art("R1", "Dalle LED", -2)]
    v = controler(nouv, 0, 1, comparer(ACTIFS, nouv))
    assert v["verdict"] == "BLOQUANT"
    assert {a["code"] for a in v["alertes"]} >= {"chute_lignes", "prix_negatifs"}


def test_prix_manquants_unites_et_rejets_a_verifier():
    nouv = [art("R1", "Dalle LED", None, "zz"), art("R2", "Câble", 1.2, "m"), art("R3", "Boîte", 3)]
    v = controler(nouv, 1, 10, comparer(ACTIFS, nouv))
    assert v["verdict"] == "A_VERIFIER"
    assert {a["code"] for a in v["alertes"]} == {"prix_manquants", "unites", "rejets"}


def test_premiere_version_sans_comparaison():
    assert controler([art("R1", "Dalle", 5)], 0, 1, None)["verdict"] == "OK"
    assert controler([], 3, 3, None)["verdict"] == "BLOQUANT"


def test_prix_a_zero_compte_comme_manquant():
    nouv = [art("R1", "Dalle LED", 0), art("R2", "Câble", 1.2, "m"), art("R3", "Boîte", 3)]
    v = controler(nouv, 0, 3, None)
    assert v["sans_prix"] == 1 and "prix_manquants" in {a["code"] for a in v["alertes"]}
