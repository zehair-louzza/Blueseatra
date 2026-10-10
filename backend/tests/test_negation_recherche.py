# -*- coding: utf-8 -*-
"""Exclusion par négation : une désignation qui NIE un terme de la requête
(« porte multi-usage non coupe-feu » pour « porte coupe feu ») est un faux
positif du filtre de mots, pas un résultat moins pertinent — elle est
exclue, avec compte et motifs affichés. Voir negation_recherche.py.

Tests sans base de données (module autonome).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from negation_recherche import negation_presente, exclure


def l(norm, designation=""):
    return {"recherche_norm": norm, "designation": designation or norm}


# ---------------------------------------------------------------- présence
def test_non_coupe_feu_exclu():
    assert negation_presente(
        "porte metallique multi usage twin non coupe feu ral 9010",
        "porte coupe feu") == "non coupe feu"


def test_vrai_bloc_porte_garde():
    assert negation_presente(
        "bloc porte coupe feu ei30 rive droite prepeint huisserie serrure",
        "porte coupe feu") is None


def test_negation_hors_requete_garde():
    # « non isole » ne nie aucun mot demandé : la porte reste candidate.
    assert negation_presente(
        "porte coupe feu ei30 non isole", "porte coupe feu") is None


def test_negation_mot_unique_avec_non():
    assert negation_presente("coffret non blinde", "coffret blinde") == "non blinde"


def test_sans_un_seul_mot_garde():
    # « vis sans fin » : composé légitime, jamais une négation de « vis ».
    assert negation_presente("vis sans fin inox", "vis inox") is None


def test_sans_deux_mots_exclu():
    assert negation_presente(
        "gaine plastique sans gaine technique", "gaine technique") == "sans gaine technique"


def test_plus_long_motif_d_abord():
    # « non coupe feu » (2 mots) rapporté, pas « non coupe ».
    assert negation_presente("x non coupe feu y", "porte coupe feu") == "non coupe feu"


def test_requete_vide_ou_texte_vide():
    assert negation_presente("non coupe feu", "") is None
    assert negation_presente("", "porte coupe feu") is None


# ------------------------------------------------------------------- exclure
def test_exclure_portes_twin_non_coupe_feu():
    lignes = [
        l("porte metallique multi usage twin non coupe feu ral 9010",
          "Porte métallique multi-usage TWIN non coupe-feu blanc RAL 9010"),
        l("bloc porte coupe feu ei30", "Bloc-porte coupe-feu EI30"),
        l("porte coupe feu demi heure reversible", "Porte coupe-feu 1/2 h réversible"),
    ]
    retenues, rapport = exclure(lignes, "porte coupe feu")
    assert [x["recherche_norm"] for x in retenues] == [
        "bloc porte coupe feu ei30", "porte coupe feu demi heure reversible"]
    assert rapport["nombre"] == 1
    assert rapport["motifs"] == ["non coupe feu"]
    assert "TWIN" in rapport["exemples"][0]


def test_exclure_aucune_negation_rapport_none():
    lignes = [l("bloc porte coupe feu ei30")]
    retenues, rapport = exclure(lignes, "porte coupe feu")
    assert len(retenues) == 1
    assert rapport is None


def test_exclure_plusieurs_motifs_et_exemples_plafonnes():
    lignes = [
        l("porte a non coupe feu 1"), l("porte b non coupe feu 2"), l("porte c non coupe feu 3"),
        l("porte d non coupe feu 4"), l("gaine sans gaine technique"),
        l("porte coupe feu ei30"),
    ]
    _, rapport = exclure(lignes, "porte coupe feu gaine technique")
    assert rapport["nombre"] == 5
    assert len(rapport["exemples"]) == 3


def test_exclure_ligne_sans_texte_gardee():
    lignes = [{"recherche_norm": None, "designation": None}]
    retenues, rapport = exclure(lignes, "porte coupe feu")
    assert len(retenues) == 1
    assert rapport is None


def test_exclure_requete_vide_tout_garde():
    lignes = [l("porte non coupe feu")]
    retenues, rapport = exclure(lignes, "  ")
    assert len(retenues) == 1
    assert rapport is None


def test_porte_seule_ne_exclut_pas_porte_non_coupe_feu():
    # Pour « porte », une porte non coupe-feu EST une porte.
    assert negation_presente("porte non coupe feu", "porte") is None
