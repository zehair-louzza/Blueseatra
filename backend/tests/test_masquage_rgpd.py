"""Masquage RGPD avant tout envoi à un modèle hors du VPS. Données 100 % fictives."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

import masquage_rgpd as m

ENTITES = m.Entites(
    sites=["BOUTIQUE LUMIA Forum des Lilas"],
    donneurs_ordre=["MAINTEX SERVICES"],
    clients=["LUMIA"],
    personnes=["Héloïse Martinot"],
    adresses=["14 rue des Peupliers, 75020 Paris"],
)


def _masque(texte, entites=ENTITES):
    return m.masquer(texte, entites)


def test_adresse_numero_voie_code_postal_ville():
    r = _masque("Intervention au 24 avenue de la République, 75011 Paris pour 3 spots.")
    assert "République" not in r.texte and "75011" not in r.texte and "Paris" not in r.texte
    assert "[adresse_1]" in r.texte and "3 spots" in r.texte


def test_adresse_en_majuscules_et_zone_activite():
    r = _masque("Z.A. Les Saules - 1411, route de Varennes -\n01990 SAINT DENIS SUR LOIRE")
    for fuite in ("Saules", "Varennes", "01990", "SAINT DENIS"):
        assert fuite not in r.texte


def test_noms_connus_du_saas_masques_sans_tenir_compte_casse_ni_accents():
    r = _masque("Site : boutique lumia FORUM DES LILAS. Devis à MAINTEX SERVICES.")
    assert "lumia" not in r.texte.lower() and "maintex" not in r.texte.lower()
    assert "[site_1]" in r.texte and "[donneur_ordre_1]" in r.texte


def test_prenom_apres_cordialement_et_champ_interlocuteur():
    r = _masque("Merci.\nCordialement,\nYasmina\n05 11 22 33 44\n")
    assert "Yasmina" not in r.texte and "05 11" not in r.texte
    r = _masque("Interlocuteur : Jean-Marc Ollivier\nContact : Mme Ducros")
    assert "Ollivier" not in r.texte and "Ducros" not in r.texte and "Jean-Marc" not in r.texte


def test_prenom_dans_le_texte_libre_avec_son_nom():
    r = _masque("Demande de devis : 3 spots LED, client Sophie Garnier, urgent.")
    assert "Sophie" not in r.texte and "Garnier" not in r.texte and "3 spots LED" in r.texte


def test_identifiants():
    texte = ("Mail : achats@maintex.fr Tél. : +33 (0) 4 72 00 11 22 portable 06.12.34.56.78 "
             "IBAN : FR76 1234 5678 9012 3456 7890 123 BIC : ABCDFRPPXXX Siret : 881 214 365 000 36 "
             "N° de TVA : FR63 881 214 365 N° Dossier DI : 26060951 www.maintex.fr")
    r = _masque(texte)
    for fuite in ("achats@", "72 00", "06.12", "FR76", "ABCDFRPP", "881 214", "FR63", "26060951", "maintex.fr"):
        assert fuite not in r.texte, fuite


def test_le_vocabulaire_technique_reste_intact():
    texte = ("Remplacement ballon d'eau chaude 100L, cylindre européen 30x30, câble R2V 3G2,5, "
             "peinture blanche mate, pierre naturelle, porte coupe-feu 2 vantaux, disjoncteur 16A courbe C.")
    r = _masque(texte)
    assert r.texte == texte and not r.correspondances


def test_restauration_de_la_reponse_du_modele():
    r = _masque("Client : LUMIA, site au 14 rue des Peupliers, 75020 Paris.")
    reponse = '{"client": "[client_1]", "adresse": "[adresse_1]"}'
    restaure = m.restaurer(reponse, r.correspondances)
    assert "LUMIA" in restaure and "Peupliers" in restaure


def test_controle_avant_envoi_bloque_toute_fuite_residuelle():
    with pytest.raises(m.FuitePossible):
        m.verifier_avant_envoi("écrire à achats@maintex.fr", ENTITES)
    with pytest.raises(m.FuitePossible):
        m.verifier_avant_envoi("le site BOUTIQUE LUMIA Forum des Lilas", ENTITES)
    m.verifier_avant_envoi(_masque("écrire à achats@maintex.fr pour LUMIA").texte, ENTITES)


def test_texte_vide_ou_absent():
    assert m.masquer("", ENTITES).texte == ""
    assert m.masquer(None, ENTITES).texte == ""


# --- Fuites relevées à la relecture des 26 demandes réelles (09/10/2026), reproduites avec des données fictives.
def test_telephone_a_points_en_fin_de_phrase_et_numero_tronque():
    r = _masque("merci de nous contacter au 04.72.11.22.33. Rappel au 05 86 30 08 1")
    assert "72.11" not in r.texte and "86 30" not in r.texte


def test_voie_abregee_ou_sans_numero_et_centres_commerciaux():
    textes = ["63 Av. de Vincennes,", "[adresse_1], avenue Parmentine 75011", "14 Cours Du Rhône",
              "C.Cial. Forum des Peupliers Niv (-)3", "Val d'Orge Shopping Centre", "Centre commercial les 4 Chênes"]
    for t in textes:
        r = _masque(t)
        for fuite in ("Vincennes", "Parmentine", "Rhône", "Peupliers", "Orge", "Chênes"):
            assert fuite not in r.texte, (t, r.texte)


def test_prenom_rare_apres_cordialement_dans_une_ligne_et_avant_devis_gratuit():
    r = _masque("Merci de bien détailler votre devis. Cordialement, Zéphyrine")
    assert "Zéphyrine" not in r.texte
    r = _masque("!! Merci de détailler au mieux !!\nZéphyrine\nDevis GRATUIT à adresser EXCLUSIVEMENT à X")
    assert "Zéphyrine" not in r.texte


def test_representant_et_raison_sociale_d_un_bloc_de_coordonnees():
    r = _masque("Le demandeur est la société, représentée par Kaelig Tranvouez.")
    assert "Kaelig" not in r.texte and "Tranvouez" not in r.texte
    r = _masque("ATELIER TECHNIQUE VORNIER\nTél. : 01 23 45 67 89\nEntreprise\nAtelier Technique Vornier")
    assert "VORNIER" not in r.texte and "Vornier" not in r.texte


def test_les_produits_d_une_ligne_qui_porte_une_adresse_restent_lisibles():
    r = _masque("Remplacement de 3 spots LED 230V au 24 avenue de la République, client LUMIA.")
    assert "3 spots LED 230V" in r.texte


def test_attention_n_est_pas_un_nom_de_personne():
    r = _masque("ATTENTION : toute intervention non validée ne sera pas payée.")
    assert "toute intervention non validée" in r.texte
