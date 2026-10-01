"""Désignation affichée des offres fournisseurs au libellé amputé.

Cas réels relevés en production le 01/10/2026 (catalogue Rexel).
"""
import pytest

from designation_fournisseur import designation_affichee, nettoyer_ligne


@pytest.mark.parametrize("brut, marque, ref_fab, ref_frn, attendu", [
    # 45 accessoires RZB : libellé réduit aux dimensions.
    (", D 350 H 1, blanc", "RZB", "982552.002", "RZB982552.002",
     "RZB 982552.002 · D 350 H 1, blanc"),
    (", blanc", "RZB", "99050.1167", "RZB99050.1167", "RZB 99050.1167 · blanc"),
    # Daikin : premier caractère perdu, la ponctuation est retirée.
    (".ERAMIC FIBRE 6x6MM PACKING CORD", "Daikin", "5004737", "DKN5004737",
     "Daikin 5004737 · ERAMIC FIBRE 6x6MM PACKING CORD"),
    # Blm : tiret de liste en tête.
    ("- Boite de dérivation OPTIBOX 155x110x80 lisse 1/4T", "Blm", "525509", "BLI525509",
     "Blm 525509 · Boite de dérivation OPTIBOX 155x110x80 lisse 1/4T"),
])
def test_libelles_amputes(brut, marque, ref_fab, ref_frn, attendu):
    assert designation_affichee(brut, marque, ref_fab, ref_frn) == attendu


@pytest.mark.parametrize("brut", [
    "Disjoncteur Ph/N 16A à vis courbe C 4,5",
    "S200L Disjoncteur modulaire- 1P - 16A - Cbe C - 4500A/6kA (1 module)-peignable",
    "Joint plat",
    "3-WAY VALVE",
    "026816 - FAN",
    "  Espace en tête conservé",
])
def test_libelle_normal_inchange(brut):
    # Un libellé normal est rendu au caractère près, même s'il contient des
    # tirets ou des virgules plus loin.
    assert designation_affichee(brut, "ABB", "123", "X123") == brut


def test_reference_fournisseur_a_defaut_de_reference_fabricant():
    assert designation_affichee(", blanc", "RZB", None, "RZB99050.1167") == "RZB99050.1167 · blanc"


def test_pas_de_marque_en_double():
    assert designation_affichee(", blanc", "RZB", "RZB99050.1167") == "RZB99050.1167 · blanc"


def test_sans_marque_ni_reference():
    assert designation_affichee(", D 95 H 65, blanc") == "D 95 H 65, blanc"


def test_libelle_reduit_a_la_ponctuation():
    assert designation_affichee(" , ", "RZB", "982617.002") == "RZB 982617.002"
    assert designation_affichee(" - ") == "-"


def test_none():
    assert designation_affichee(None, "RZB", "1") is None


def test_nettoyer_ligne_en_place():
    ligne = {"designation": ", D 101 H 76, blanc", "marque": "RZB",
             "reference_fabricant": "982813.002", "reference_fournisseur": "RZB982813.002"}
    assert nettoyer_ligne(ligne) is ligne
    assert ligne["designation"] == "RZB 982813.002 · D 101 H 76, blanc"
    assert nettoyer_ligne({"id": 1}) == {"id": 1}
