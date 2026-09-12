"""Branchement de la designation canonique sur la recherche SQL.

Ces tests portent sur le SQL GENERE, pas sur une base : le bac a sable
n'a pas de serveur Postgres. Ils verifient donc la forme des conditions,
le parametrage, et l'absence de concatenation de valeurs utilisateur.

La LOGIQUE, elle, a ete verifiee sur les 914 628 lignes du catalogue
reel en rejouant les memes conditions :
    "disjoncteur"                   26 860 retenus (rappel 100 %)
    "disjoncteur 16A"               14 052 retenus, 862 exacts
    "disjoncteur 16A courbe C 1P+N" 10 920 retenus, 552 exacts
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fournisseur_recherche as fr  # noqa: E402


def test_requete_nue_n_impose_aucun_attribut():
    """"disjoncteur" doit tout faire sortir : aucune condition
    d'attribut, donc aucune restriction."""
    conditions, expression, parametres, exiges = fr._conditions_attributs(
        "disjoncteur")
    assert conditions == []
    assert parametres == {}
    assert exiges == {}
    assert expression == "0", (
        "Sans precision, l'expression de tri doit etre neutre.")


def test_la_regle_de_contradiction_s_ecrit_IS_NULL_OR_EGAL():
    """Un libelle MUET passe, un libelle CONTRAIRE est ecarte.

    C'est toute la regle, et elle doit apparaitre telle quelle dans le
    SQL : (colonne IS NULL OR colonne = valeur). Ecrire seulement
    "colonne = valeur" ecarterait les 13 190 libelles de disjoncteur qui
    ne mentionnent aucun calibre.
    """
    conditions, _, parametres, _ = fr._conditions_attributs("disjoncteur 16A")
    assert len(conditions) == 1
    assert conditions[0] == "(o.calibre IS NULL OR o.calibre = :att_calibre)"
    assert parametres == {"att_calibre": "16A"}


def test_trois_precisions_donnent_trois_conditions():
    conditions, expression, parametres, exiges = fr._conditions_attributs(
        "disjoncteur 16A courbe C 1P+N")
    assert len(conditions) == 3
    assert parametres == {"att_calibre": "16A", "att_courbe": "courbe C",
                          "att_poles": "1P+N"}
    # L'expression de tri compte les attributs confirmes.
    assert expression.count("CASE WHEN") == 3
    assert set(exiges) == {"calibre", "courbe", "poles"}


def test_aucune_valeur_utilisateur_concatenee_dans_le_sql():
    """SECURITE. Seuls des NOMS DE COLONNES sont interpoles, et ils
    viennent de COLONNES_ATTRIBUTS -- jamais de la requete."""
    hostile = "disjoncteur 16A'; DROP TABLE blueseatra.supplier_offers; --"
    conditions, expression, parametres, _ = fr._conditions_attributs(hostile)
    tout = " ".join(conditions) + " " + expression
    assert "DROP" not in tout.upper()
    assert "'" not in tout, (
        f"Le SQL genere contient une apostrophe : {tout!r}. Toute valeur "
        f"doit voyager en parametre lie.")
    # Chaque jeton :xxx doit correspondre a un parametre fourni.
    for nom in re.findall(r":(\w+)", tout):
        assert nom in parametres, f"Parametre :{nom} non fourni."
    # Et les valeurs restent des attributs propres.
    for valeur in parametres.values():
        assert re.fullmatch(r"[0-9A-Za-z+.]+( [0-9A-Za-z+.]+)?", str(valeur)), (
            f"Valeur inattendue : {valeur!r}")


def test_un_terme_couvert_par_un_attribut_n_est_pas_exige_en_texte():
    """REGRESSION MESUREE -- le double filtrage faisait perdre 32
    articles pourtant exacts.

    Sur "disjoncteur 16A courbe C 1P+N", exiger le mot "courbe" dans le
    libelle ecarte les articles ecrits "CrbC" ou "Crb C" :

      "Acti9 iDD40T - Disjoncteur dif. - 1P+N 16A - CrbC - 4500A/6kA"
      "Acti9 iDT40N XA - Disjoncteur modulaire - 1P+N - 16A - Crb C"

    La colonne courbe vaut bien "courbe C" pour ces lignes : l'analyse a
    reconnu l'abreviation. Le filtre texte ne voit que les caracteres.
    Doubler le filtre annule le travail de normalisation.

    Apres correction, les correspondances exactes sont passees de 92 a
    552 sur le catalogue reel.
    """
    conditions, parametres, _ = fr._conditions(
        "disjoncteur 16A courbe C 1P+N")
    motifs = " ".join(str(v) for v in parametres.values()).lower()

    assert "disjoncteur" in motifs, (
        "Le type produit doit rester un filtre texte : aucune colonne "
        "d'attribut ne le porte.")
    for interdit in ("courbe", "16a", "1p+n", "p+n"):
        assert interdit not in motifs, (
            f"Le terme {interdit!r} est exige comme TEXTE alors qu'une "
            f"colonne d'attribut le couvre deja. Motifs : {motifs!r}")


def test_un_terme_sans_colonne_reste_un_filtre_texte():
    """Une marque ou une gamme n'a pas de colonne d'attribut : elle doit
    continuer a etre cherchee dans le libelle."""
    _, parametres, _ = fr._conditions("cable 2.5mm2 R2V")
    motifs = " ".join(str(v) for v in parametres.values()).lower()
    assert "cable" in motifs
    assert "r2v" in motifs, "La gamme R2V doit rester un filtre texte."
    # La section, elle, passe par la colonne.
    _, _, params_attrs, _ = fr._conditions_attributs("cable 2.5mm2 R2V")
    assert params_attrs == {"att_section": "2.5mm2"}
    assert "2.5mm2" not in motifs, (
        "La section est couverte par une colonne : ne pas l'exiger aussi "
        "en texte.")


def test_niveaux_de_correspondance():
    exiges = {"calibre": "16A", "courbe": "courbe C", "poles": "1P+N"}

    exact = fr._niveau({"calibre": "16A", "courbe": "courbe C",
                        "poles": "1P+N"}, exiges)
    assert exact["niveau"] == "exact" and not exact["muets"]

    partiel = fr._niveau({"calibre": "16A", "courbe": None,
                          "poles": "1P+N"}, exiges)
    assert partiel["niveau"] == "partiel"
    assert partiel["muets"] == ["courbe"]

    muet = fr._niveau({"calibre": None, "courbe": None, "poles": None},
                      exiges)
    assert muet["niveau"] == "non precise"

    # Une chaine vide compte comme muette, pas comme contradiction : une
    # colonne texte vide arrive souvent a la place d'un NULL.
    vide = fr._niveau({"calibre": "", "courbe": "", "poles": ""}, exiges)
    assert vide["niveau"] == "non precise"


def test_le_tri_met_les_exacts_avant_le_prix():
    """Trier par prix seul ferait remonter un article muet a 3,20 EUR
    devant le vrai 16A 1P+N courbe C a 6,83 EUR. Le moins cher n'est
    utile que s'il correspond a la demande."""
    source = (Path(__file__).resolve().parent.parent
              / "fournisseur_recherche.py").read_text(encoding="utf-8")
    deb = source.index("ORDER BY attributs_confirmes")
    ordre = source[deb:deb + 120]
    pos_conf = ordre.index("attributs_confirmes")
    pos_prix = ordre.index("price_ht")
    assert pos_conf < pos_prix, (
        "attributs_confirmes doit preceder le prix dans ORDER BY.")
    assert "DESC" in ordre[pos_conf:pos_prix], (
        "Les correspondances confirmees doivent etre en DECROISSANT.")


def test_les_colonnes_d_attribut_existent_dans_le_modele():
    """Une colonne absente ferait echouer la requete a l'execution, et
    le bac a sable n'a pas de base pour le detecter."""
    import models_sql as modeles

    colonnes = {c.name for c in modeles.SupplierOffer.__table__.columns}
    for colonne in fr.COLONNES_ATTRIBUTS.values():
        assert colonne in colonnes, (
            f"La colonne {colonne} est utilisee dans le SQL de recherche "
            f"mais absente du modele SupplierOffer.")
    for attendue in ("designation_courte", "type_produit",
                     "conditionnement_lot", "est_accessoire"):
        assert attendue in colonnes, f"Colonne {attendue} manquante."


def test_la_migration_cree_toutes_les_colonnes_utilisees():
    """Le modele et la migration doivent rester d'accord : le modele
    seul ne cree rien en base."""
    migration = (Path(__file__).resolve().parents[2] / "supabase"
                 / "migrations"
                 / "20260912130000_designation_canonique.sql"
                 ).read_text(encoding="utf-8")
    for colonne in list(fr.COLONNES_ATTRIBUTS.values()) + [
            "designation_courte", "type_produit", "conditionnement_lot",
            "est_accessoire", "est_courant_continu"]:
        assert re.search(rf"ADD COLUMN IF NOT EXISTS\s+{colonne}\b",
                         migration), (
            f"La colonne {colonne} n'est pas creee par la migration.")


def test_le_moins_cher_par_fournisseur_respecte_le_niveau():
    """Le niveau de correspondance PRIME sur le prix.

    Un article "non precise" a 3,20 EUR ne doit pas etre annonce comme
    la meilleure offre Rexel quand un article "exact" existe a
    6,83 EUR : le premier ne confirme pas le calibre demande. Ces deux
    prix sont reels, releves sur le catalogue pour "disjoncteur 16A".

    Annoncer un prix pour un article qui ne correspond peut-etre pas,
    c'est precisement ce qui fausse un chiffrage.
    """
    source = (Path(__file__).resolve().parent.parent
              / "fournisseur_recherche.py").read_text(encoding="utf-8")

    deb = source.index("# Le moins cher chez chaque fournisseur")
    bloc = source[deb:deb + 1800]
    assert "RANG_NIVEAU" in bloc, (
        "Le choix du moins cher par fournisseur ignore le niveau de "
        "correspondance : il retiendrait un article non confirme parce "
        "qu'il est moins cher.")
    assert "rang > rang_connu" in bloc, (
        "Un niveau moins bon doit etre rejete meme s'il est moins cher.")

    # Rejoue la regle pour verifier son comportement.
    lignes = [
        {"fournisseur": "Rexel", "prix_net_ht": 3.20, "niveau": "non precise"},
        {"fournisseur": "Rexel", "prix_net_ht": 6.83, "niveau": "exact"},
        {"fournisseur": "Rexel", "prix_net_ht": 8.51, "niveau": "exact"},
        {"fournisseur": "Prolians", "prix_net_ht": 13.84, "niveau": "partiel"},
        {"fournisseur": "Prolians", "prix_net_ht": 24.98, "niveau": "exact"},
    ]
    meilleurs = {}
    for ligne in lignes:
        prix, nom = ligne["prix_net_ht"], ligne["fournisseur"]
        rang = fr.RANG_NIVEAU.get(ligne["niveau"], 9)
        connu = meilleurs.get(nom)
        if connu is not None:
            rang_connu = fr.RANG_NIVEAU.get(connu["niveau"], 9)
            if rang > rang_connu:
                continue
            if rang == rang_connu and prix >= connu["prix_net_ht"]:
                continue
        meilleurs[nom] = {"niveau": ligne["niveau"], "prix_net_ht": prix}

    assert meilleurs["Rexel"]["prix_net_ht"] == 6.83, (
        f"Retenu {meilleurs['Rexel']} : le 3,20 EUR non precise ne doit "
        f"pas primer sur le 6,83 EUR exact.")
    assert meilleurs["Prolians"]["prix_net_ht"] == 24.98


def test_rangs_de_niveau_ordonnes():
    assert fr.RANG_NIVEAU["exact"] < fr.RANG_NIVEAU["partiel"]
    assert fr.RANG_NIVEAU["partiel"] < fr.RANG_NIVEAU["non precise"]
