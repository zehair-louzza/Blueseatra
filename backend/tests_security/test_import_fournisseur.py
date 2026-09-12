"""Association des colonnes d'un tarif fournisseur.

Un mauvais champ associe fausse tout : un prix public pris pour un prix
net gonfle les devis, un mauvais fournisseur rend la comparaison
absurde. Ces tests protegent l'algorithme d'affectation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fournisseur_import as fi  # noqa: E402


# --- classeur fournisseur reel, 22 colonnes -----------------------------
COLONNES_REELLES = [
    "Code", "Sous-famille", "Article (désignation interne)", "Unité",
    "Désignation fournisseur", "Marque", "Réf. fabricant", "Réf. fournisseur",
    "Fournisseur retenu", "Prix achat HT", "Type de prix", "Prix public réf.",
    "Remise", "Date prix", "Fiabilité", "Conditionnement",
    "Point de contrôle", "Marge %", "Prix vente HT", "TVA %",
    "Retrait / disponibilité", "Fiche produit",
]

# --- catalogue consolide, 12 colonnes -----------------------------------
COLONNES_CONSOLIDE = [
    "Fournisseur", "Famille", "Sous-famille", "Designation", "Marque",
    "Reference fournisseur", "Reference fabricant", "Code EAN",
    "Prix net HT", "Prix public HT", "Eco-contribution HT", "Unite de vente",
]


def test_affectation_choisit_la_meilleure_colonne_pas_la_premiere():
    """REGRESSION -- deux erreurs mesurees sur un vrai classeur.

    La premiere version parcourait les champs dans l'ordre et prenait la
    PREMIERE colonne correspondante. Sur ce fichier a 22 colonnes, elle
    associait :

        "Fournisseur"           -> "Désignation fournisseur"
        "Référence fournisseur" -> "Code"

    Les bonnes colonnes ("Fournisseur retenu", "Réf. fournisseur")
    existaient mais arrivaient plus loin dans le fichier. L'ordre des
    colonnes ne doit jouer aucun role.
    """
    m = fi.suggere_mapping(COLONNES_REELLES)

    assert m["fournisseur"] == "Fournisseur retenu", (
        "Le champ Fournisseur doit pointer sur « Fournisseur retenu », pas "
        f"sur « {m['fournisseur']} ». Dans un en-tete francais le premier "
        "mot est le nom principal : « Designation fournisseur » designe "
        "une designation, pas un fournisseur."
    )
    assert m["reference_fournisseur"] == "Réf. fournisseur", (
        "Le champ Reference fournisseur doit pointer sur « Réf. "
        f"fournisseur », pas sur « {m['reference_fournisseur']} ». Un "
        "synonyme long et specifique (« ref fournisseur ») doit l'emporter "
        "sur un synonyme court et generique (« code »)."
    )


def test_prix_net_et_prix_public_ne_se_confondent_pas():
    """Confondre les deux gonflerait tous les devis.

    Le prix public est le tarif affiche, le prix net celui reellement
    paye apres remise. Sur le catalogue consolide, l'ecart median entre
    les deux est considerable.
    """
    for colonnes, attendu_net, attendu_public in (
        (COLONNES_REELLES, "Prix achat HT", "Prix public réf."),
        (COLONNES_CONSOLIDE, "Prix net HT", "Prix public HT"),
    ):
        m = fi.suggere_mapping(colonnes)
        assert m["prix_net_ht"] == attendu_net, (
            f"prix_net_ht -> {m['prix_net_ht']!r}, attendu {attendu_net!r}")
        assert m["prix_public_ht"] == attendu_public, (
            f"prix_public_ht -> {m['prix_public_ht']!r}, "
            f"attendu {attendu_public!r}")
        assert m["prix_net_ht"] != m["prix_public_ht"], (
            "Les deux prix pointent sur la meme colonne.")


def test_catalogue_consolide_entierement_reconnu():
    """Les 12 colonnes du catalogue consolide doivent toutes trouver
    preneur, et aucun champ requis ne doit manquer."""
    m = fi.suggere_mapping(COLONNES_CONSOLIDE)
    associees = {v for v in m.values() if v}
    non_associees = [c for c in COLONNES_CONSOLIDE if c not in associees]
    assert not non_associees, (
        f"Colonnes non reconnues : {non_associees}")
    manquants = [c["libelle"] for c in fi.CHAMPS_FOURNISSEUR
                 if c["requis"] and not m.get(c["cle"])]
    assert not manquants, f"Champs requis non associes : {manquants}"


def test_une_colonne_n_est_jamais_affectee_deux_fois():
    """Sinon un meme prix servirait de net ET de public."""
    for colonnes in (COLONNES_REELLES, COLONNES_CONSOLIDE):
        m = fi.suggere_mapping(colonnes)
        prises = [v for v in m.values() if v]
        doublons = {c for c in prises if prises.count(c) > 1}
        assert not doublons, f"Colonnes affectees plusieurs fois : {doublons}"


def test_nombres_a_la_francaise():
    """Une virgule prise pour un separateur de milliers transformerait
    2,5 en 25 -- une erreur de prix d'un facteur dix."""
    cas = {
        "1 234,56": 1234.56,
        "1.234,56": 1234.56,
        "2,5": 2.5,
        "4.424": 4.424,
        "13,7431": 13.7431,
        "12 €": 12.0,
        "-3,5": -3.5,
        "": None,
        "   ": None,
        "texte": None,
    }
    for brut, attendu in cas.items():
        obtenu = fi.nombre(brut)
        assert obtenu == attendu, (
            f"nombre({brut!r}) = {obtenu!r}, attendu {attendu!r}")


def test_nom_de_fournisseur_sans_date():
    """Un "09-2026" resté collé creerait un fournisseur distinct a chaque
    mise a jour mensuelle, et la comparaison se ferait entre deux
    versions du meme fournisseur au lieu d'entre enseignes."""
    import pandas as pd

    cas = {
        "export Point.P 09-2026.xlsx": "Point.P",
        "SFIC 2026-09 maj.xlsx": "SFIC",
        "prolians liste 15/03/2026.csv": "prolians",
        "Rexel.xlsx": "Rexel",
    }
    vide = pd.DataFrame()
    for nom, attendu in cas.items():
        obtenu = fi.devine_fournisseur(vide, {}, nom)
        assert obtenu == attendu, (
            f"devine_fournisseur({nom!r}) = {obtenu!r}, attendu {attendu!r}")


def test_colonne_fournisseur_unique_prime_sur_le_nom_de_fichier():
    """Un export propre a un fournisseur porte son nom en colonne : c'est
    plus fiable que le nom du fichier, que l'utilisateur renomme."""
    import pandas as pd

    df = pd.DataFrame({"Fournisseur": ["Rexel"] * 5,
                       "Designation": ["a", "b", "c", "d", "e"]})
    m = fi.suggere_mapping(list(df.columns))
    assert fi.devine_fournisseur(df, m, "tarif_inconnu_2026.csv") == "Rexel"

    # Plusieurs fournisseurs dans le fichier : on ne devine PAS, sous
    # peine d'attribuer tout le tarif au premier nom rencontre.
    melange = pd.DataFrame({"Fournisseur": ["Rexel", "Prolians"],
                            "Designation": ["a", "b"]})
    m2 = fi.suggere_mapping(list(melange.columns))
    assert fi.devine_fournisseur(melange, m2, "consolide.csv") != "Rexel"


def test_aucune_donnee_perdue_silencieusement_a_l_insertion():
    """REGRESSION -- pg_adapter.insert_many() filtre les cles inconnues.

    La ligne responsable :

        rows = [{k: v for k, v in d.items() if k in cols} for d in docs]

    Une faute de frappe sur un nom de colonne ne leve donc AUCUNE
    erreur : elle fait disparaitre la valeur. Un prix ecrit sous
    "prix_ht" au lieu de "price_ht" produirait un catalogue entier sans
    aucun prix, importe avec succes.

    Ce test compare les cles ecrites par l'import aux colonnes du
    modele.
    """
    import re
    from pathlib import Path

    import models_sql as modeles

    colonnes = {c.name for c in modeles.SupplierOffer.__table__.columns}
    source = (Path(__file__).resolve().parent.parent / "server.py").read_text(
        encoding="utf-8")

    debut = source.find("lot.append({")
    assert debut > 0, (
        "Le bloc d'insertion des offres fournisseur est introuvable dans "
        "server.py : ce test doit etre mis a jour avec le code.")
    fin = source.find("})", debut)
    bloc = source[debut:fin]

    ecrites = set(re.findall(r'"([a-z_]+)":', bloc))
    inconnues = sorted(ecrites - colonnes)
    assert not inconnues, (
        f"Ces cles ne correspondent a aucune colonne de supplier_offers : "
        f"{inconnues}. insert_many() les supprimera SANS erreur et la "
        f"donnee sera perdue."
    )

    # Les champs sans lesquels une offre n'a aucune valeur.
    indispensables = {
        "tenant_id", "supplier_id", "version_id", "raw_label", "price_ht",
        "is_active",
    }
    manquants = sorted(indispensables - ecrites)
    assert not manquants, (
        f"Champs indispensables non renseignes a l'import : {manquants}. "
        f"Sans tenant_id l'offre est invisible, sans price_ht elle est "
        f"incomparable, sans is_active elle n'entre pas dans la recherche."
    )


def test_les_tables_fournisseur_sont_connues_de_l_adaptateur():
    """pg_adapter leve AttributeError sur une table absente de MODELS.

    Les tables du module Fournisseur n'existaient que dans la migration
    SQL : le premier db.supplier_offers.insert_many() echouait.
    """
    import pg_adapter

    for table in ("suppliers", "supplier_offers", "canonical_products"):
        assert table in pg_adapter.MODELS, (
            f"La table {table} est absente de pg_adapter.MODELS : tout "
            f"appel db.{table}.* leverait AttributeError."
        )
        # Et elle ne doit PAS etre traitee comme une table
        # d'authentification : le chemin metier doit passer par
        # tenant_session pour que RLS et app.tenant_id s'appliquent.
        assert table not in pg_adapter.TABLES_AUTH, (
            f"{table} est classee table d'AUTHENTIFICATION : elle "
            f"passerait par le role privilegie, hors RLS."
        )


def test_les_valeurs_ecrites_respectent_les_contraintes_CHECK():
    """REGRESSION -- l'import ecrivait match_status='pending', valeur
    REFUSEE par la base.

    La contrainte supplier_offers_match_status_chk n'autorise que
    matched / proposed / to_confirm / orphan / rejected. Tout import
    aurait echoue des la premiere ligne.

    Ce bug etait INVISIBLE en test : aucun test Python ne peut deviner
    une contrainte CHECK cote serveur, et le bac a sable n'a pas de
    Postgres. Il a fallu une ecriture reelle en base pour le detecter.

    Ce test lit donc les contraintes dans le FICHIER DE MIGRATION et
    verifie que les valeurs ecrites par server.py les respectent.
    """
    import re
    from pathlib import Path

    racine = Path(__file__).resolve().parents[2]
    migration = (racine / "supabase" / "migrations"
                 / "20260912020000_module_fournisseur.sql"
                 ).read_text(encoding="utf-8")
    serveur = (racine / "backend" / "server.py").read_text(encoding="utf-8")

    # Contraintes de la forme : colonne IN ('a','b','c')
    contraintes = {}
    for colonne, liste in re.findall(
            r"(\w+)\s+IN\s*\(([^)]+)\)", migration):
        valeurs = set(re.findall(r"'([^']+)'", liste))
        if valeurs:
            contraintes.setdefault(colonne, set()).update(valeurs)

    assert "match_status" in contraintes, (
        "La contrainte sur match_status n'a pas ete trouvee dans la "
        "migration : ce test doit etre mis a jour.")

    # Valeurs que le code d'import ecrit pour ces colonnes.
    debut = serveur.find("lot.append({")
    assert debut > 0
    bloc = serveur[debut:serveur.find("})", debut)]

    for colonne, autorisees in contraintes.items():
        for valeur in re.findall(rf'"{colonne}":\s*"([^"]+)"', bloc):
            assert valeur in autorisees, (
                f"L'import ecrit {colonne}={valeur!r}, refuse par la "
                f"contrainte CHECK. Valeurs autorisees : "
                f"{sorted(autorisees)}. Une valeur interdite fait "
                f"echouer l'import des la premiere ligne."
            )


def test_packaging_qty_strictement_positif():
    """supplier_offers_packaging_chk exige packaging_qty > 0.

    L'import ecrit `num(...) or 1.0` : une valeur absente, nulle ou
    illisible retombe donc sur 1. Sans ce repli, une colonne de
    conditionnement vide ferait echouer toute la ligne.
    """
    import re
    from pathlib import Path

    serveur = (Path(__file__).resolve().parents[1] / "server.py").read_text(
        encoding="utf-8")
    debut = serveur.find('"packaging_qty"')
    extrait = serveur[debut:debut + 200]
    assert "or 1" in extrait, (
        f"packaging_qty doit retomber sur une valeur positive. "
        f"Extrait : {extrait[:120]!r}")


# --- catalogue reel La Plateforme du Batiment, 15 colonnes -------------
COLONNES_LA_PLATEFORME = [
    "Fournisseur", "Metier", "Famille", "Categorie", "Designation",
    "Marque", "Reference", "Prix net HT", "Unite de vente",
    "Qte conditionnement", "Unite conditionnement", "Stock depot",
    "Stock livraison", "Cycle de vie", "Fiche produit",
]


def test_quantite_par_conditionnement_reconnue():
    """REGRESSION -- "Qte conditionnement" n'etait pas reconnue.

    Mesure sur le catalogue reel La Plateforme (24 600 lignes) : la
    colonne restait non associee. Sans elle, une boite de 100 vis est
    comparee a la vis a l'unite -- le prix du conditionnement passe
    pour un prix unitaire, et le devis est faux d'un facteur 100.

    909 lignes du catalogue ont un conditionnement superieur a 1.
    """
    m = fi.suggere_mapping(COLONNES_LA_PLATEFORME)
    assert m["quantite_conditionnement"] == "Qte conditionnement", (
        f"Associe a {m.get('quantite_conditionnement')!r} : la colonne "
        f"« Qte conditionnement » doit etre reconnue.")


def test_stock_n_est_pas_un_delai():
    """REGRESSION -- "Stock depot" etait range dans le champ Delai.

    Un etat de stock n'est pas une duree. La table a une colonne
    availability dediee ; mettre "En stock" dans la colonne des delais
    de livraison affiche une information fausse au chiffreur.
    """
    m = fi.suggere_mapping(COLONNES_LA_PLATEFORME)
    assert m["disponibilite"] == "Stock depot", (
        f"disponibilite -> {m.get('disponibilite')!r}, attendu "
        f"« Stock depot ».")
    assert m.get("delai") is None, (
        f"delai -> {m.get('delai')!r} : aucune colonne de ce catalogue "
        f"n'exprime un delai, le champ doit rester vide.")


def test_import_ecrit_la_disponibilite_dans_sa_propre_colonne():
    import re
    from pathlib import Path

    serveur = (Path(__file__).resolve().parents[1] / "server.py").read_text(
        encoding="utf-8")
    debut = serveur.find("lot.append({")
    bloc = serveur[debut:serveur.find("})", debut)]
    assert re.search(r'"availability":\s*val\(ligne, mapping, "disponibilite"\)',
                     bloc), (
        "La disponibilite doit etre ecrite dans la colonne availability, "
        "distincte de delay.")


def test_catalogue_la_plateforme_entierement_exploitable():
    """Aucun champ requis ne doit manquer sur ce catalogue reel."""
    m = fi.suggere_mapping(COLONNES_LA_PLATEFORME)
    manquants = [c["libelle"] for c in fi.CHAMPS_FOURNISSEUR
                 if c["requis"] and not m.get(c["cle"])]
    assert not manquants, f"Champs requis non associes : {manquants}"
    # Les colonnes attendues, une a une.
    for cle, colonne in (("designation", "Designation"),
                         ("prix_net_ht", "Prix net HT"),
                         ("reference_fournisseur", "Reference"),
                         ("marque", "Marque"),
                         ("unite_vente", "Unite de vente"),
                         ("url_produit", "Fiche produit")):
        assert m[cle] == colonne, f"{cle} -> {m[cle]!r}, attendu {colonne!r}"
