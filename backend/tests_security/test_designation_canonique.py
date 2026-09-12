"""Designation canonique et filtre par precision.

Cas construits a partir de la capture d'ecran fournie par
l'utilisateur : une liste censee montrer des disjoncteurs 16A 1P+N
courbe C, qui contenait en realite un 4P, un 3P+N, un lot de 3 et un
modele avec contact auxiliaire -- des prix non comparables.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import designation_canonique as dcq  # noqa: E402


CAPTURE = [
    "SN201SL Disjoncteur modulaire System pro M compact - 1P+N - 16A - courbe C",
    "iC60N Disjoncteur Acti9 - 1P+N - 16A - courbe C - 6000A/10kA",
    "Disjoncteur phase + neutre 16A courbe C 4,5kA Resi9 XE",
    "Disjoncteur modulaire U+N 16A courbe C DX3 4500A/6kA",
    "Disjoncteur modulaire 4P 16A courbe C 6kA - Acti9 iC60N tetrapolaire",
    "Disjoncteur 3P+N 16A courbe C 4500A DX3 - tetrapolaire",
    "Lot de 3 disjoncteurs modulaires U+N 16A courbe C 6kA",
]


def test_le_type_passe_en_tete():
    """23 % des libelles de disjoncteur commencent par une gamme ou une
    reference, pas par le type. La colonne Designation etant tronquee a
    l'ecran, c'est l'information distinctive qui disparait."""
    for libelle in CAPTURE:
        courte = dcq.designation_canonique(libelle)["designation_courte"]
        sans_drapeau = courte.split("] ")[-1]
        assert sans_drapeau.lower().startswith("disjoncteur"), (
            f"{libelle!r} donne {courte!r} : le type doit etre en tete."
        )


def test_tetrapolaire_ne_vaut_pas_3p_plus_n():
    """REGRESSION. "tetrapolaire" signifie "quatre poles" et ne dit pas
    si le neutre est protege. Il ne peut donc pas distinguer 4P de
    3P+N, qui sont deux appareils differents.

    Premiere version : "Disjoncteur modulaire 4P 16A ... tetrapolaire"
    etait lu 3P+N alors que le libelle annonce 4P explicitement.
    """
    quatre_p = dcq.extrait_attributs(
        "Disjoncteur modulaire 4P 16A courbe C 6kA - Acti9 iC60N tetrapolaire")
    assert quatre_p["poles"] == "4P", (
        f"Lu {quatre_p.get('poles')!r} : une ecriture EXPLICITE (4P) doit "
        f"primer sur le mot ambigu 'tetrapolaire'.")

    trois_pn = dcq.extrait_attributs(
        "Disjoncteur 3P+N 16A courbe C 4500A DX3 - tetrapolaire")
    assert trois_pn["poles"] == "3P+N"

    # Sans ecriture explicite, "tetrapolaire" vaut 4P : quatre poles,
    # repartition inconnue.
    assert dcq.extrait_attributs(
        "Disjoncteur tetrapolaire 16A")["poles"] == "4P"


def test_ecritures_equivalentes_des_poles():
    """1P+N s'ecrit de six facons dans le catalogue. Sans unification,
    une recherche de 1P+N ignorerait les cinq autres."""
    for libelle in ("Disjoncteur 1P+N 16A", "Disjoncteur U+N 16A",
                    "Disjoncteur ph+n 16A",
                    "Disjoncteur phase + neutre 16A",
                    "Disjoncteur phase neutre 16A",
                    "Disjoncteur unipolaire + neutre 16A"):
        assert dcq.extrait_attributs(libelle)["poles"] == "1P+N", libelle


def test_pouvoir_de_coupure_en_A_et_en_kA_du_meme_appareil():
    """MESURE : "4500A/6kA" figure 124 fois et "6000A/10kA" 643 fois SUR
    LA MEME LIGNE. La valeur en amperes suit NF EN 60898, celle en kA
    suit IEC 60947-2 -- un meme disjoncteur porte les deux.

    On retient l'ampere quand les deux figurent, et on ne convertit
    jamais : les paires observees ne sont pas toutes coherentes
    (6000<->50kA sur 52 lignes), donc convertir fabriquerait de faux
    rapprochements.
    """
    a = dcq.extrait_attributs("Disjoncteur 1P+N 16A courbe C 4500A/6kA")
    assert a["pdc"] == "4500A", f"Lu {a.get('pdc')!r}"
    b = dcq.extrait_attributs("Disjoncteur 2P 16A courbe C 400Vca 6000A/10kA")
    assert b["pdc"] == "6000A", f"Lu {b.get('pdc')!r}"
    # Seule la valeur en kA presente : on la garde telle quelle.
    c = dcq.extrait_attributs("Disjoncteur 16A courbe C 10kA industriel")
    assert c["pdc"] == "10kA", f"Lu {c.get('pdc')!r}"

    # Et le calibre ne doit pas etre confondu avec le pouvoir de coupure.
    assert a["calibre"] == "16A"
    assert b["calibre"] == "16A"


def test_garantie_d_inclusion_requete_nue():
    """"disjoncteur" doit TOUT faire sortir. Verifie sur les 26 860
    libelles reels : rappel 100 %."""
    for libelle in CAPTURE:
        assert dcq.article_conforme("disjoncteur", libelle)[0], libelle


def test_la_precision_ecarte_les_articles_contraires():
    """Demander du 1P+N ne doit pas faire remonter un 4P ni un 3P+N."""
    req = "disjoncteur 16A courbe C 1P+N"
    ecartes = [x for x in CAPTURE if not dcq.article_conforme(req, x)[0]]
    assert len(ecartes) == 2, f"Ecartes : {ecartes}"
    assert any("4P" in x for x in ecartes)
    assert any("3P+N" in x for x in ecartes)

    # Et un calibre different est ecarte.
    ok, motif = dcq.article_conforme("disjoncteur 16A",
                                     "Disjoncteur 1P+N 20A courbe C")
    assert not ok and "20A" in motif, motif


def test_un_libelle_muet_n_est_pas_un_libelle_contraire():
    """Regle de CONTRADICTION, pas de ressemblance. Mesure de la session
    precedente : filtrer sur la ressemblance de libelle faisait chuter
    le rappel de 97 % a 9 %."""
    ok, _ = dcq.article_conforme("disjoncteur 16A courbe C",
                                 "Disjoncteur modulaire 16A 1P+N")
    assert ok, ("La courbe n'est pas mentionnee : absence n'est pas "
                "contradiction, l'article doit etre conserve.")
    niveau = dcq.niveau_conformite("disjoncteur 16A courbe C",
                                   "Disjoncteur modulaire 16A 1P+N")
    assert niveau["niveau"] == "partiel"
    assert "courbe" in niveau["muets"]


def test_niveaux_de_conformite_ordonnes():
    """L'ecran affiche les correspondances exactes en tete. Mesure :
    "disjoncteur 16A" retient 14 052 lignes dont 862 seulement annoncent
    16A explicitement -- sans niveau, le filtre ne filtre rien."""
    req = "disjoncteur 16A courbe C"
    exact = dcq.niveau_conformite(req, "Disjoncteur 16A courbe C 1P+N")
    partiel = dcq.niveau_conformite(req, "Disjoncteur 16A 1P+N")
    muet = dcq.niveau_conformite(req, "Disjoncteur modulaire 1P+N")
    ecarte = dcq.niveau_conformite(req, "Disjoncteur 20A courbe C")

    assert exact["niveau"] == "exact"
    assert partiel["niveau"] == "partiel"
    assert muet["niveau"] == "non precise"
    assert ecarte["niveau"] == "ecarte" and not ecarte["conforme"]

    rangs = [dcq.RANG_NIVEAU[x["niveau"]]
             for x in (exact, partiel, muet, ecarte)]
    assert rangs == sorted(rangs), "Les niveaux doivent etre ordonnes."


def test_differentiel_separe_du_disjoncteur_simple():
    """MESURE : sur les disjoncteurs 16A du catalogue, 22 % sont en
    realite des differentiels -- 215,25 EUR de prix median contre
    110,68 EUR. Les confondre fausse tout devis."""
    for libelle in ("Disjoncteur differentiel 16A 30mA courbe C",
                    "DPN Vigi 16A 30mA", "Disjoncteur 16A courbe C 30mA"):
        t = dcq.detecte_type(dcq.aplatit(libelle))
        assert t == "disjoncteur differentiel", f"{libelle!r} -> {t!r}"

    assert dcq.detecte_type(dcq.aplatit(
        "Interrupteur differentiel 40A 30mA type AC")) == \
        "interrupteur differentiel"
    assert dcq.detecte_type(dcq.aplatit(
        "Disjoncteur 16A courbe C 1P+N 4500A")) == "disjoncteur"


def test_lot_et_accessoire_signales():
    """Un lot de 50 et une piece seule n'ont pas un prix comparable.
    Le qualifiant doit rester VISIBLE, jamais absorbe."""
    r = dcq.designation_canonique(
        "Lot de 50 disjoncteurs DNX3 4500 Phase + Neutre 16A courbe C")
    assert r["qualifiants"]["lot"] == 50
    assert "LOT DE 50" in r["designation_courte"]

    a = dcq.designation_canonique(
        "Disjoncteur 1P+N 16A courbe C avec contact auxiliaire")
    assert a["qualifiants"].get("accessoire")
    assert "ACCESSOIRE" in a["designation_courte"]


def test_mots_colles_reconnus():
    """MESURE : 147 libelles contenaient "disjoncteur" sans que le type
    soit reconnu, ecrits "DisjoncteurDC (S203MUC) 3P 10KA 440VDC".
    Ramene a 1 apres decollage."""
    assert dcq.detecte_type(dcq.aplatit(
        "DisjoncteurDC (S203MUC) 3P 10KA 440VDC Z-1A")) == "disjoncteur"
    assert dcq.detecte_type(dcq.aplatit("CableU1000R2V 3G2.5")) == "cable"
    # Une reference courte ne doit PAS etre hachee.
    assert "idt40t" in dcq.aplatit("Acti9 iDT40T - Disjoncteur modulaire")


def test_libelle_origine_toujours_conserve():
    """Le libelle fournisseur est une donnee contractuelle : c'est lui
    qui figure sur le devis et permet de commander l'article."""
    for libelle in CAPTURE:
        assert dcq.designation_canonique(libelle)["libelle_origine"] == libelle


def test_le_a_de_ampere_ne_se_confond_pas_avec_la_preposition():
    """REGRESSION MESUREE sur le catalogue reel.

    Le "a" de l'ampere et la preposition francaise "a" deviennent
    identiques une fois l'accent retire. Resultat observe :

      "Acti9 Vigi NG125 - Bloc diff. 230 a 400Vca - 2P 63A - 1000mA"
          -> calibre 230A   (c'est une TENSION, le calibre est 63A)
      "Boite d'encastrement pour boites de sol 12 a 18"
          -> calibre 12A    (c'est une plage de dimensions)

    38 lignes portaient un calibre de 230A et 1 087 un calibre de 400A,
    tous issus de tensions ou de references.

    L'ESPACE tranche : "24A" colle l'unite au nombre, "230 a 400" ne
    colle rien. Un calibre colle est donc accepte meme suivi d'un nombre
    -- "Contacteur 24A 400V" est bien un 24A.
    """
    cas = {
        "Acti9 Vigi NG125 - Bloc diff. 230 à 400Vca - 2P 63A - 1000mA": "63A",
        "Contacteur 110V AC 3NO 24A 400V AC3 - 11kW": "24A",
        "Boîte d'encastrement pour boîtes de sol 12 à 18": None,
        "Câble 3G2.5 de 10 à 50 m": None,
        "Coffret de 6 à 12 modules": None,
        "Disjoncteur 16A courbe C 1P+N 4500A/6kA": "16A",
        "Disjoncteur 16 A courbe C": "16A",
        "Disjoncteur 0A": None,
    }
    for libelle, attendu in cas.items():
        obtenu = dcq.extrait_attributs(libelle).get("calibre")
        assert obtenu == attendu, (
            f"{libelle!r}\n  calibre = {obtenu!r}, attendu {attendu!r}")


def test_unite_de_vente_unifiee():
    """MESURE : 39 unites distinctes dans le catalogue, dont 9 groupes
    qui ne different que par la casse ou l'accent.

    "Piece" et "piece" comptees separement empechent de comparer un prix
    a la piece entre deux fournisseurs.
    """
    for variantes, attendu in (
        (["Pièce", "pièce", "PIECE", "Unité", "U", "pc"], "pièce"),
        (["Boîte", "boite", "BOITE", "bte"], "boîte"),
        (["Sac-sachet", "sac", "Sacs"], "sac"),
        (["Mètre carré", "m2", "M²"], "m²"),
        (["Lot", "lot", "LOTS"], "lot"),
    ):
        obtenus = {dcq.unite_canonique(v) for v in variantes}
        assert obtenus == {attendu}, (
            f"{variantes} donnent {obtenus}, attendu {{{attendu!r}}}")

    # Une unite inconnue est conservee telle quelle : mieux vaut une
    # unite non reconnue qu'une unite inventee.
    assert dcq.unite_canonique("Conditionnement maison") == \
        "Conditionnement maison"
    assert dcq.unite_canonique("") is None
    assert dcq.unite_canonique(None) is None


def test_applique_exige_un_contexte_d_eclairage():
    """MESURE -- 16 167 libelles commencent par "Applique", et beaucoup
    ne sont pas des luminaires :

      "Applique equerre avec ecrou - M1/2\\" x M3/4\\""  -> raccord plomberie
      "Aquastat applique a ressort AAR 20/90 C"        -> thermostat
      "Thermometre genie climatique applique"          -> thermometre
      "Robinet applique de WC ECLAIR - G1\\"1/4"        -> robinet

    En plomberie, "en applique" qualifie un mode de POSE, pas le
    produit. Et le mot etant souvent en tete du libelle, la regle du mot
    principal ne peut pas trancher seule.

    Le type "applique" exige donc un signe d'eclairage dans le libelle.
    """
    # Luminaires : signe d'eclairage present.
    for libelle in ("Applique led BOREAL - 7W - 308 mm - blanc",
                    "Applique murale exterieure 12W 3000K",
                    "Applique 900 lumen blanche"):
        assert dcq.detecte_type(dcq.aplatit(libelle)) == "applique", libelle

    # Pas des luminaires : "applique" ne doit PAS etre retenu.
    for libelle in ("Aquastat applique a ressort AAR 20°C / 90°C",
                    "Thermometre genie climatique applique - 0_120 °C",
                    "Robinet applique de WC ECLAIR - G1\"1/4",
                    "Coude applique femelle LBP EASYTEC HT 52 a sertir"):
        t = dcq.detecte_type(dcq.aplatit(libelle))
        assert t != "applique", (
            f"{libelle!r} classe {t!r} : aucun signe d'eclairage, ce "
            f"n'est pas un luminaire.")


def test_unite_debarrassee_des_residus_d_extraction():
    """MESURE -- le catalogue porte des unites comme
    "PiecePrecedent1Suivant" et "Metre carrePrecedent1Suiv" : du texte
    de pagination happe lors de la collecte, colle a l'unite.

    Chacun fabrique une fausse unite distincte, et empeche de comparer
    un prix a la piece entre deux fournisseurs.
    """
    assert dcq.unite_canonique("PiècePrécédent1Suivant") == "pièce"
    assert dcq.unite_canonique("Mètre carréPrécédent1Suiv") == "m²"
    assert dcq.unite_canonique("Pièce Suivant") == "pièce"
    # Une unite propre n'est pas abimee au passage.
    assert dcq.unite_canonique("Pièce") == "pièce"
    assert dcq.unite_canonique("Blister") == "Blister"
