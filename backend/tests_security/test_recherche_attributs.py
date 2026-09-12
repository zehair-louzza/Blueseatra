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
    la meilleure offre Rexel quand un "exact" existe a 6,83 EUR : le
    premier ne confirme pas le calibre demande. Ces deux prix sont
    reels, releves en base sur "disjoncteur 16A".

    Test de COMPORTEMENT, pas de presence de code. La version
    precedente cherchait une chaine dans le fichier source : la
    mutation `if False and ligne.get("est_accessoire")` la laissait
    intacte et passait sans etre detectee.
    """
    meilleurs = fr.meilleurs_par_fournisseur([
        {"fournisseur": "Rexel", "prix_net_ht": 3.20, "niveau": "non precise"},
        {"fournisseur": "Rexel", "prix_net_ht": 6.83, "niveau": "exact"},
        {"fournisseur": "Rexel", "prix_net_ht": 8.51, "niveau": "exact"},
        {"fournisseur": "Prolians", "prix_net_ht": 13.84, "niveau": "partiel"},
        {"fournisseur": "Prolians", "prix_net_ht": 24.98, "niveau": "exact"},
    ])
    assert meilleurs["Rexel"]["prix_net_ht"] == 6.83, (
        f"Retenu {meilleurs['Rexel']['prix_net_ht']} EUR : le 3,20 EUR "
        f"non precise ne doit pas primer sur le 6,83 EUR exact.")
    assert meilleurs["Rexel"]["niveau"] == "exact"
    assert meilleurs["Prolians"]["prix_net_ht"] == 24.98

    # ORDRE INVERSE -- indispensable.
    # Dans la liste ci-dessus, la ligne "non precise" arrive en premier
    # et se fait remplacer : le test passait meme en supprimant la garde
    # `if rang > rang_connu`. Mutation non detectee, verifie.
    #
    # Ici la moins bonne correspondance arrive EN DERNIER et moins
    # chere : sans la garde, elle ecraserait la bonne.
    inverse = fr.meilleurs_par_fournisseur([
        {"fournisseur": "Rexel", "prix_net_ht": 6.83, "niveau": "exact"},
        {"fournisseur": "Rexel", "prix_net_ht": 3.20, "niveau": "non precise"},
    ])
    assert inverse["Rexel"]["prix_net_ht"] == 6.83, (
        f"Retenu {inverse['Rexel']['prix_net_ht']} EUR : une "
        f"correspondance moins bonne ne doit JAMAIS remplacer une "
        f"meilleure, meme si elle est moins chere.")
    assert inverse["Rexel"]["niveau"] == "exact"

    # Et a niveau egal, le moins cher gagne bien -- quel que soit
    # l'ordre d'arrivee.
    for lignes in ([{"fournisseur": "X", "prix_net_ht": 9.0, "niveau": "exact"},
                    {"fournisseur": "X", "prix_net_ht": 4.0, "niveau": "exact"}],
                   [{"fournisseur": "X", "prix_net_ht": 4.0, "niveau": "exact"},
                    {"fournisseur": "X", "prix_net_ht": 9.0, "niveau": "exact"}]):
        assert fr.meilleurs_par_fournisseur(lignes)["X"]["prix_net_ht"] == 4.0


def test_un_accessoire_n_est_jamais_le_moins_cher():
    """MESURE REELLE -- recherche "disjoncteur" en base, triee par prix.
    Les quatre premieres offres renvoyees etaient :

        2,95 EUR  "systeme repiquage universel POUR disjoncteur"
        3,58 EUR  "cache borne 1 pole POUR disjoncteur modulaire"
        4,58 EUR  "Peigne 1P disjoncteur S200C 13x1P"
        7,60 EUR  "Borne de raccordement POUR disjoncteur 1P+N"

    Aucune n'est un disjoncteur. Le premier VRAI disjoncteur etait a
    5,99 EUR. Annoncer 2,95 EUR comme meilleur prix fausse le chiffrage
    d'un facteur deux.

    Les accessoires restent visibles dans la liste des resultats,
    signales ; seul le panneau de negociation les ignore.
    """
    meilleurs = fr.meilleurs_par_fournisseur([
        {"fournisseur": "Rexel", "prix_net_ht": 2.95, "niveau": "exact",
         "est_accessoire": True,
         "designation": "systeme repiquage universel pour disjoncteur"},
        {"fournisseur": "Rexel", "prix_net_ht": 3.58, "niveau": "exact",
         "est_accessoire": True,
         "designation": "cache borne 1 pole pour disjoncteur modulaire"},
        {"fournisseur": "Rexel", "prix_net_ht": 5.99, "niveau": "exact",
         "est_accessoire": False,
         "designation": "Disjoncteur Automatique 16A 4,5kA"},
    ])
    assert meilleurs["Rexel"]["prix_net_ht"] == 5.99, (
        f"Retenu {meilleurs['Rexel']['prix_net_ht']} EUR : les "
        f"accessoires a 2,95 et 3,58 EUR doivent etre ignores.")
    assert "Disjoncteur" in meilleurs["Rexel"]["designation"]


def test_un_prix_nul_ou_absent_est_ignore():
    """Un prix a zero n'est pas une bonne affaire, c'est une donnee
    manquante. Le retenir afficherait 0,00 EUR comme meilleur prix."""
    meilleurs = fr.meilleurs_par_fournisseur([
        {"fournisseur": "Rexel", "prix_net_ht": 0, "niveau": "exact"},
        {"fournisseur": "Rexel", "prix_net_ht": None, "niveau": "exact"},
        {"fournisseur": "Rexel", "prix_net_ht": 6.83, "niveau": "exact"},
    ])
    assert meilleurs["Rexel"]["prix_net_ht"] == 6.83


def test_aucune_offre_exploitable_ne_produit_aucune_entree():
    assert fr.meilleurs_par_fournisseur([]) == {}
    assert fr.meilleurs_par_fournisseur([
        {"fournisseur": "Rexel", "prix_net_ht": 2.95, "est_accessoire": True},
    ]) == {}


def test_rangs_de_niveau_ordonnes():
    assert fr.RANG_NIVEAU["exact"] < fr.RANG_NIVEAU["partiel"]
    assert fr.RANG_NIVEAU["partiel"] < fr.RANG_NIVEAU["non precise"]
