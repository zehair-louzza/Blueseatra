"""Classement par pertinence (pertinence.py) et son application au comparateur.

Cas réel remonté par l'utilisateur (02/10/2026) : « porte-coupe-feu »
affichait d'abord un panneau PVC 1,80 €, un judas et une gâche — le tri au
prix. Les blocs-portes (150 à 255 €) doivent passer devant : un produit EST
ce que sa désignation annonce en premier, un accessoire le mentionne en fin
de libellé.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comparateur_produits as cp
import pertinence


def _o(i, f, prix, desig, pert=None):
    l = {"id": i, "fournisseur": f, "prix_net_ht": prix, "prix_unite_base_ht": prix,
         "designation": desig}
    if pert is not None:
        l["_pertinence"] = pert
    return l


# --- score ----------------------------------------------------------------------

def test_score_porte_coupe_feu_les_portes_dabord():
    q = "porte-coupe-feu"
    porte = pertinence.score("bloc porte coupe feu ei30 rive droite", q)
    porte2 = pertinence.score("bloc porte prepeint coupe feu 1 point ei30", q)
    panneau = pertinence.score("panneau pvc porte coupe feu l 200mm", q)
    gache = pertinence.score("gache peripherique pour portes coupe feu grise", q)
    judas = pertinence.score("judas optique coupe feu pour epaisseur de porte", q)
    assert porte > porte2 > panneau > 0
    assert panneau > gache and panneau > judas and gache > 0 and judas > 0


def test_score_pluriel_et_requete_vide():
    assert pertinence.score("portes coupe feu", "porte coupe feu") > 0
    assert pertinence.score("bloc porte coupe feu", "") == 0.0
    assert pertinence.score("", "porte") == 0.0


def test_score_mots_absents_nivelle():
    # Mots introuvables : meme score pour tous, le prix reprend la main.
    assert pertinence.score("aaa bbb", "zzz") == pertinence.score("bbb aaa ccc", "zzz")


def test_normalise():
    assert pertinence.normalise("Bloc-Porte COUPE-FEU 2,5 mm²") == "bloc porte coupe feu 2.5 mm2"


# --- application au comparateur --------------------------------------------------

def test_meilleurs_par_fournisseur_prend_le_plus_pertinent():
    lignes = [
        _o("r1", "Rexel", 1.80, "panneau pvc porte coupe feu", pert=0.78),
        _o("r2", "Rexel", 42.0, "bloc porte coupe feu ei30", pert=1.08),
        _o("p1", "Point.P", 242.14, "bloc porte coupe feu ei30 rive droite", pert=1.08),
        _o("a1", "AFDB", 11.91, "gache pour portes coupe feu", pert=0.38),
    ]
    m = cp.meilleurs_par_fournisseur(lignes)
    # Rexel garde sa porte (la plus pertinente), pas son panneau a 1,80 €.
    assert [(x["fournisseur"], x["id"]) for x in m] == [("Rexel", "r2"), ("Point.P", "p1"), ("AFDB", "a1")]
    assert m[0]["pertinence"] == 1.08


def test_meilleurs_par_fournisseur_sans_score_inchange():
    lignes = [
        _o("r1", "Rexel", 1.80, "panneau"),
        _o("r2", "Rexel", 42.0, "porte"),
        _o("p1", "Point.P", 242.14, "porte"),
    ]
    m = cp.meilleurs_par_fournisseur(lignes)
    assert [(x["fournisseur"], x["id"]) for x in m] == [("Rexel", "r1"), ("Point.P", "p1")]


def test_cle_recherche_pertinence_puis_prix():
    lignes = [
        _o("a", "Rexel", 50.0, "bloc porte coupe feu", pert=1.08),
        _o("b", "Rexel", 10.0, "gache pour porte coupe feu", pert=0.38),
        _o("c", "Rexel", 20.0, "bloc porte coupe feu autre", pert=1.08),
    ]
    # A pertinence egale (a et c), le moins cher d'abord : c (20 €) avant a.
    assert [l["id"] for l in sorted(lignes, key=cp.cle_recherche)] == ["c", "a", "b"]
