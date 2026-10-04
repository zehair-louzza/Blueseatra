# -*- coding: utf-8 -*-
"""Rapprochement fournisseur par ligne de devis (04/10/2026).

Constat réel du devis BS-2026-0055 : les libellés de prestation de 10 mots
(« fourniture et pose de prises 2p+t 16 a, gamme blanche standard ») ne
matchent AUCUNE désignation catalogue (recherche AND-tous-les-mots), donc
toutes les lignes restaient « à confirmer » sans prix alors que le catalogue
Rexel vend des prises 2P+T.

Correctifs testés ici :
- requete_materielle() : extrait la requête ARTICLE du libellé de prestation
- _enrichit_lignes_fournisseurs() : attache meilleure offre (appliquée,
  prix figé) + alternatives par ligne
- _applique_offre_ligne() : changement d'offre = prix refigé, preuve mise à jour

Tests sans base de données.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8000")

import catalogue_chiffrage as cc  # noqa: E402
import negation_recherche  # noqa: E402
import server  # noqa: E402


# ----------------------------------------------------------- requête matériau
def test_requete_materielle_prises():
    q = cc.requete_materielle(
        "fourniture et pose de prises 2p+t 16 a, gamme blanche standard")
    assert q == "prise 2p+t 16 a"


def test_requete_materielle_chauffe_eau():
    q = cc.requete_materielle(
        "fourniture et pose d'un chauffe-eau electric vertical 150 l, "
        "groupe de securite et raccordement")
    assert q == "chauffe eau electric vertical 150 l"


def test_requete_materielle_interrupteurs():
    q = cc.requete_materielle("fourniture et pose d'interrupteurs simples et va-et-vient")
    assert "interrupteur" in q
    assert "fourniture" not in q and "pose" not in q


def test_requete_materielle_libelle_deja_article():
    # Un libellé déjà article ne doit pas être cassé.
    assert cc.requete_materielle("prise 2p+t 16 a") == "prise 2p+t 16 a"


def test_requete_materielle_vide():
    assert cc.requete_materielle("") == ""
    assert cc.requete_materielle(None) == ""


def test_requete_materielle_pluriel_singulier():
    q = cc.requete_materielle("fourniture de disjoncteurs differentiels 40a")
    assert q == "disjoncteur differentiel 40a"


# -------------------------------------------------- enrichissement des lignes
def _offre(fid, prix, designation="Prise 2P+T 16A", ident=None):
    return {"id": ident or f"o-{fid}", "fournisseur": fid,
            "designation": designation, "marque": "LEGRAND",
            "reference_fournisseur": f"ref-{fid}",
            "prix_net_ht": prix, "prix_public_ht": prix * 1.5,
            "unite_vente": "u", "url_produit": f"https://ex.fr/{fid}"}


def test_enrichit_ligne_sans_prix_avec_meilleure_offre():
    lignes = [
        {"line_type": "lot", "number": "2", "title": "Électricité"},
        {"line_type": "sublot", "number": "2.1", "title": "Fournitures"},
        {"line_type": "main_work", "request_label": "fourniture et pose de prises 2p+t 16 a, gamme blanche standard",
         "description": "prises", "qty": 14, "unit": "u",
         "unit_price_ht": None, "line_ht": None, "status": "to_confirm", "reasons": []},
        {"line_type": "labor", "request_label": "Main d'oeuvre", "qty": 11,
         "unit_price_ht": 42.0, "line_ht": 462.0, "status": "proposed"},
    ]
    offres = {"fourniture et pose de prises 2p+t 16 a, gamme blanche standard":
              [_offre("Rexel", 6.42), _offre("YESSS", 5.10)]}
    server._enrichit_lignes_fournisseurs(lignes, offres)
    ligne = lignes[2]
    assert ligne["unit_price_ht"] == 6.42          # meilleure offre appliquée
    assert ligne["line_ht"] == round(6.42 * 14, 2)  # 14 prises
    assert ligne["chosen_offer"]["fournisseur"] == "Rexel"
    assert ligne["status"] == "proposed"
    assert len(ligne["alternatives"]) == 2
    assert lignes[1]["line_type"] == "sublot"       # structure intacte
    assert "chosen_offer" not in lignes[3]           # main-d'œuvre jamais touchée


def test_enrichit_ligne_deja_pricee_par_candidat_interne_pas_touchee():
    lignes = [{"line_type": "main_work", "request_label": "prise 2p+t",
               "qty": 1, "unit_price_ht": 8.5, "line_ht": 8.5,
               "status": "matched", "matched_item_code": "ELE-001"}]
    server._enrichit_lignes_fournisseurs(lignes, {"prise 2p+t": [_offre("Rexel", 6.42)]})
    assert lignes[0]["unit_price_ht"] == 8.5        # prix interne conservé
    assert "chosen_offer" not in lignes[0]
    # mais les alternatives sont proposées pour un changement manuel
    assert len(lignes[0]["alternatives"]) == 1


def test_enrichit_sans_offres_ligne_intacte():
    lignes = [{"line_type": "main_work", "request_label": "monopole inconnu",
               "qty": 1, "unit_price_ht": None, "line_ht": None, "status": "to_confirm"}]
    server._enrichit_lignes_fournisseurs(lignes, {})
    assert "chosen_offer" not in lignes[0]
    assert "alternatives" not in lignes[0]


def test_applique_offre_refigure_prix_et_preuve():
    ligne = {"qty": 3, "unit": "u", "unit_price_ht": None, "line_ht": None,
             "status": "to_confirm", "reasons": []}
    server._applique_offre_ligne(ligne, _offre("LPB", 12.5, "Chauffe-eau 150L"))
    assert ligne["unit_price_ht"] == 12.5
    assert ligne["line_ht"] == 37.5
    assert ligne["chosen_offer"]["choisie_le"]      # horodatage de la sélection
    # changement d'offre : prix REFIGÉ, ancienne preuve remplacée
    server._applique_offre_ligne(ligne, _offre("Rexel", 9.9, "Chauffe-eau 150L"))
    assert ligne["unit_price_ht"] == 9.9
    assert ligne["line_ht"] == 29.7
    assert ligne["chosen_offer"]["fournisseur"] == "Rexel"
    motifs = [r for r in ligne["reasons"] if r.startswith("offre_fournisseur:")]
    assert len(motifs) == 1                          # pas de doublon de motif


def test_resume_offre_champs_utiles():
    r = server._resume_offre(_offre("Rexel", 6.42))
    assert r["id"] == "o-Rexel"
    assert r["fournisseur"] == "Rexel"
    assert r["designation"] == "Prise 2P+T 16A"
    assert r["prix_net_ht"] == 6.42


# --------------------------------------- règles pertinence sur le rapprochement
def _offre_p(pertinence, fid, prix):
    return {"id": f"o-{fid}", "fournisseur": fid, "designation": f"article {fid}",
            "prix_net_ht": prix, "pertinence": pertinence}


def test_garde_alternatives_retire_les_accessoires():
    offres = [
        _offre_p(1.958, "LPB", 370.72),     # vraie porte
        _offre_p(1.200, "Prolians", 409.0),  # vraie porte
        _offre_p(0.783, "Rexel", 1.80),      # panneau PVC : accessoire
        _offre_p(0.617, "YESSS", 302.59),    # déclencheur : accessoire
    ]
    gardees = server._garde_alternatives(offres)
    assert {o["fournisseur"] for o in gardees} == {"LPB", "Prolians"}


def test_garde_alternatives_sans_pertinences_tout_garde():
    offres = [{"fournisseur": "A", "pertinence": None}, {"fournisseur": "B", "pertinence": None}]
    assert len(server._garde_alternatives(offres)) == 2


def test_garde_alternatives_leader_toujours_garde():
    # Même si tout est faible (que des accessoires), le leader reste
    # proposé : c'est la meilleure offre disponible, l'humain décide.
    offres = [_offre_p(0.40, "A", 10.0), _offre_p(0.10, "B", 5.0)]
    gardees = server._garde_alternatives(offres)
    assert gardees and gardees[0]["fournisseur"] == "A"


def test_resume_offre_porte_la_pertinence():
    # _resume_offre reçoit la forme BRUTE de la recherche (_pertinence)
    r = server._resume_offre({"id": "o-R", "fournisseur": "Rexel", "prix_net_ht": 6.42,
                              "_pertinence": 1.5})
    assert r["pertinence"] == 1.5


def test_en_article_porte_la_pertinence():
    art = cc._en_article({"id": "x1", "designation": "Prise", "fournisseur": "Rexel",
                          "prix_net_ht": 5.0, "_pertinence": 1.234})
    assert art["_pertinence"] == 1.234


def test_negation_exclue_du_rapprochement_par_ligne():
    """La règle pertinence 2/3 (négations, PR #177) doit s'appliquer aussi au
    chemin du rapprochement par ligne : une porte « non coupe-feu » ne doit
    jamais prixer une ligne « coupe feu »."""
    assert negation_recherche.negation_presente(
        "porte metallique multi usage non coupe feu", "porte coupe feu") == "non coupe feu"
