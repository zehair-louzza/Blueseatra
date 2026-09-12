"""Reconstruit une designation lisible et triable a partir d'un libelle
fournisseur brut.

LE PROBLEME OBSERVE
-------------------
Les cinq fournisseurs n'ecrivent pas leurs libelles de la meme facon.
Mesure sur les 914 628 lignes du catalogue consolide :

  - 23 % des libelles de disjoncteur ne commencent PAS par le type
    produit. Ils commencent par une gamme ("Acti9 C60H-DC - Disjoncteur
    modulaire - 2P - 2A") ou par une reference ("SN201SL Disjoncteur
    modulaire System pro M", "iC60N Disjoncteur Acti9").
  - Chez Rexel, 3,5 % des libelles commencent par une reference, contre
    0,0 % chez Prolians.

Consequence a l'ecran : la colonne Designation est tronquee, et ce qui
est tronque est justement ce qui distingue les articles. Deux lignes
affichant "Disjoncteur modulaire U+N 16A courbe C DX3 4500A/6kA - ..."
peuvent etre deux produits differents.

CE QUE FAIT CE MODULE
---------------------
Il remet le TYPE en tete, puis les attributs discriminants dans un
ordre FIXE, puis la marque et la gamme, et enfin le reste du libelle.
L'ordre des attributs suit leur pouvoir de discrimination mesure sur
les 26 860 libelles de disjoncteur :

    pouvoir de coupure  69,9 %
    calibre             50,9 %
    poles               46,1 %
    courbe              24,6 %

Le calibre et les poles passent devant le pouvoir de coupure malgre une
couverture plus faible : ce sont eux que le chiffreur cherche. Un
disjoncteur se demande "16A 1P+N courbe C", jamais "6000A".

CE QU'IL NE FAIT PAS
--------------------
Il ne reecrit pas le libelle d'origine, qui reste conserve tel quel. La
designation canonique est une colonne EN PLUS. Un libelle fournisseur
est une donnee contractuelle : il doit rester consultable a
l'identique, et c'est lui qui figurera sur le devis.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Normalisation de base
# ---------------------------------------------------------------------------


def sans_accent(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


# Mots colles. Mesure : 147 libelles contiennent "disjoncteur" sans que
# le type soit reconnu, parce qu'ils sont ecrits "DisjoncteurDC
# (S203MUC) 3P 10KA 440VDC" -- sans espace. La detection exige une
# frontiere de mot apres le type, qui n'existe pas entre "r" et "D".
#
# On decolle donc un mot d'une sequence de majuscules qui le suit,
# AVANT de passer en minuscules. La condition est stricte pour ne pas
# hacher les references : il faut au moins quatre minuscules devant,
# suivies de deux majuscules au moins. "DisjoncteurDC" est decolle,
# "iDT40T" ne l'est pas -- une seule minuscule devant.
# Deux formes : mot suivi de MAJUSCULES ("DisjoncteurDC"), et mot suivi
# d'une majuscule puis d'un chiffre ("CableU1000R2V" -> reference).
RE_COLLE = re.compile(r"([a-z]{4,})([A-Z]{2,}|[A-Z]\d)")


def aplatit(t: str) -> str:
    """Minuscules, sans accent, ponctuation reduite a des espaces."""
    t = sans_accent(str(t or ""))
    t = RE_COLLE.sub(r"\1 \2", t)
    t = t.lower()
    # Exposants ramenes a des chiffres, comme le fait translate() dans
    # blueseatra.normalise_recherche. Sans cela "mm²" perd son carre et
    # "2,5 mm²" ne correspond plus a une recherche "2.5 mm2".
    t = t.replace("¹", "1").replace("²", "2").replace("³", "3")
    t = re.sub(r"[^a-z0-9+/.,\-]+", " ", t)
    return " ".join(t.split())


# ---------------------------------------------------------------------------
# Types de produit
# ---------------------------------------------------------------------------
# L'ordre compte : les motifs les plus SPECIFIQUES d'abord. "disjoncteur
# differentiel" doit etre reconnu avant "disjoncteur", sinon un
# differentiel serait range parmi les disjoncteurs simples -- et sur les
# 16A du catalogue, 22 % des lignes sont des differentiels, a 215,25 EUR
# de prix median contre 110,68 EUR. Les confondre fausse tout devis.

TYPES = [
    # --- protection modulaire ---------------------------------------------
    ("interrupteur differentiel",
     r"\binter(?:rupteur)?\s+differentiel\b|\bid\s+\d+\s?a\b|"
     r"\binterrupteur\s+diff\b"),
    ("disjoncteur differentiel",
     r"\bdisj(?:oncteur)?\s+differentiel\b|\bdisjoncteur\s+diff\b|"
     r"\bdpn\s*vigi\b|\bdisjoncteur\b.{0,40}\bvigi\b|"
     r"\bdisjoncteur\b.{0,30}\b\d{1,3}\s?ma\b"),
    ("disjoncteur moteur",
     r"\bdisjoncteur\s+moteur\b|\bdisjoncteur\s+magneto\s*thermique\s+moteur\b"),
    ("disjoncteur de branchement",
     r"\bdisjoncteur\s+de\s+branchement\b|\bdisjoncteur\s+abonne\b"),
    ("disjoncteur", r"\bdisjoncteur[sx]?\b|\bdisj\b|\bmcb\b"),
    ("bloc differentiel", r"\bbloc\s+differentiel\b|\bvigi\b"),
    ("porte fusible", r"\bporte\s*-?\s*fusible\b|\bsectionneur\s+fusible\b"),
    ("fusible", r"\bfusible[s]?\b|\bcartouche\s+fusible\b"),
    ("parafoudre", r"\bparafoudre\b|\bparasurtension\b"),
    ("contacteur", r"\bcontacteur\b"),
    ("telerupteur", r"\btelerupteur\b"),
    ("relais", r"\brelais\b"),
    ("sectionneur", r"\bsectionneur\b|\binterrupteur\s+sectionneur\b"),
    ("coffret", r"\bcoffret\b|\btableau\s+electrique\b|\barmoire\s+electrique\b"),
    ("peigne", r"\bpeigne\b|\brepartiteur\b|\bbornier\b"),
    # --- cables et conduits -----------------------------------------------
    ("cable", r"\bcable[s]?\b|\bru02v\b|\br2v\b|\bu1000\b"),
    ("fil", r"\bfil\s+(?:h07|rigide|souple)\b|\bh07v\b"),
    ("gaine", r"\bgaine\b|\bicta\b|\btpc\b"),
    ("goulotte", r"\bgoulotte\b|\bmoulure\b|\bplinthe\s+electrique\b"),
    ("chemin de cables", r"\bchemin\s+de\s+cables?\b|\bdalle\s+marine\b"),
    ("conduit", r"\bconduit\b|\btube\s+irl\b|\birl\b"),
    # --- appareillage ------------------------------------------------------
    ("prise de courant",
     r"\bprise\s+(?:de\s+courant|2p\+t|murale)\b|\bpc\s+2p\+t\b"),
    ("interrupteur", r"\binterrupteur\b|\bva\s*-?\s*et\s*-?\s*vient\b|\bpoussoir\b"),
    ("boite d encastrement", r"\bboite\s+d[e']?\s*encastrement\b|\bboitier\b"),
    ("obturateur", r"\bobturateur\b"),
    # --- eclairage ---------------------------------------------------------
    ("projecteur", r"\bprojecteur\b|\bspot\s+exterieur\b"),
    # "applique" est AMBIGU et c'est mesure : 16 167 libelles commencent
    # par ce mot, et beaucoup ne sont pas des luminaires --
    #   "Applique equerre avec ecrou - M1/2\" x M3/4\""   -> raccord
    #   "Aquastat applique a ressort AAR 20/90 C"         -> thermostat
    #   "Thermometre genie climatique applique"           -> thermometre
    #   "Applique led BOREAL - 7W - 308 mm - blanc"        -> luminaire
    #
    # En plomberie, "en applique" qualifie un mode de POSE, pas le
    # produit. Le mot etant en tete du libelle, la regle du mot
    # principal ne peut pas trancher.
    #
    # On exige donc un signe d'eclairage : le motif ne correspond que si
    # le libelle porte aussi led, W, lumen, temperature de couleur ou
    # un mot du domaine.
    ("applique",
     r"\bapplique\b(?=.*(?:\bled\b|\blumen\b|\blm\b|\d+\s?w\b|"
     r"\d{4}\s?k\b|\beclairage\b|\bluminaire\b|\bmurale?\b|"
     r"\bhublot\b|\bspot\b))"
     r"|(?:(?:\bled\b|\blumen\b|\d+\s?w\b|\d{4}\s?k\b|"
     r"\beclairage\b).*\bapplique\b)"),
    ("downlight", r"\bdownlight\b|\bencastre\s+led\b|\bencastrable[s]?\b"),
    ("reglette", r"\breglette\b|\bbandeau\s+led\b"),
    ("luminaire", r"\bluminaire\b|\bhublot\b|\bplafonnier\b|\bsuspension\b"),
    ("lampe", r"\blampe\b|\bampoule\b|\btube\s+led\b|\bspot\b"),
    ("ruban led", r"\bruban\s+led\b|\bstrip\s+led\b"),
    # --- plomberie / CVC ---------------------------------------------------
    ("robinet", r"\brobinet\b|\bmitigeur\b|\bmelangeur\b"),
    ("raccord", r"\braccord\b|\bcoude\b|\bte\s+egal\b|\bmanchon\b"),
    ("tube", r"\btube\b|\btuyau\b|\bper\b|\bmulticouche\b"),
    ("vanne", r"\bvanne\b|\bclapet\b"),
    ("radiateur", r"\bradiateur\b|\bseche\s*-?\s*serviette\b"),
    ("ventilateur", r"\bventilateur\b|\bvmc\b|\bextracteur\b"),
    ("chauffe eau", r"\bchauffe\s*-?\s*eau\b|\bballon\b|\bcumulus\b"),
    # --- second oeuvre -----------------------------------------------------
    ("plaque de platre", r"\bplaque\s+de\s+platre\b|\bba13\b|\bplacoplatre\b|\bplaco\b"),
    ("rail", r"\brail\b|\bmontant\b|\bfourrure\b"),
    ("isolant", r"\bisolant\b|\blaine\s+de\s+(?:verre|roche)\b|\bpanneau\s+isolant\b"),
    ("enduit", r"\benduit\b|\bmortier\b|\bcolle\b"),
    ("peinture", r"\bpeinture\b|\bsous\s*-?\s*couche\b|\bimpression\b|\blaque\b"),
    ("carrelage", r"\bcarrelage\b|\bfaience\b|\bcarreau\b|\bgres\b"),
    ("parquet", r"\bparquet\b|\bstratifie\b|\blame\s+pvc\b"),
    ("porte", r"\bporte\b|\bbloc\s*-?\s*porte\b|\bhuisserie\b"),
    ("serrure", r"\bserrure\b|\bcylindre\b|\bbequille\b"),
    ("vis", r"\bvis\b|\bcheville\b|\bboulon\b|\becrou\b"),
    # --- consommables ------------------------------------------------------
    ("gant", r"\bgant[s]?\b"),
    ("casque", r"\bcasque\b"),
    ("chaussure", r"\bchaussure[s]?\b|\bbasket\s+de\s+securite\b"),
    ("outil", r"\bperceuse\b|\bvisseuse\b|\bmeuleuse\b|\bscie\b|\bpince\b|\btournevis\b"),
]

TYPES_COMPILES = [(nom, re.compile(motif)) for nom, motif in TYPES]


# Un article DESTINE a un appareil n'est pas cet appareil. Mesure sur
# une recherche reelle "disjoncteur" triee par prix : les quatre offres
# les moins cheres etaient
#
#   2,95 EUR  "systeme repiquage universel POUR disjoncteur"
#   3,58 EUR  "cache borne 1 pole POUR disjoncteur modulaire"
#   4,58 EUR  "Peigne 1P disjoncteur S200C 13x1P"
#   7,60 EUR  "Borne de raccordement POUR disjoncteur 1P+N"
#
# aucune n'etant un disjoncteur. Le "moins cher" annonce au chiffreur
# etait donc un accessoire a 2,95 EUR au lieu d'un disjoncteur a
# 5,99 EUR.
RE_POUR = re.compile(r"\b(?:pour|destine a|adapte a|compatible)\b")


def detecte_type(plat: str) -> str | None:
    """Type du produit, determine par le MOT DE TETE du libelle.

    POURQUOI LA POSITION DANS LE LIBELLE, ET PAS L'ORDRE DE MA LISTE
    -----------------------------------------------------------------
    Une premiere version renvoyait le premier type reconnu dans l'ordre
    de TYPES. "Peigne 1P disjoncteur S200C" etait donc classe
    "disjoncteur", parce que disjoncteur figure avant peigne dans ma
    liste -- alors que le libelle annonce un peigne des son premier mot.

    En francais, le premier nom d'un libelle est le nom principal :
    "peigne ... disjoncteur" designe un peigne, "disjoncteur ...
    modulaire" designe un disjoncteur. On retient donc le type dont la
    correspondance apparait le PLUS TOT dans le libelle.

    A position egale, l'ordre de TYPES tranche -- il place les types
    specifiques avant les generiques, ce qui garde "disjoncteur
    differentiel" devant "disjoncteur".
    """
    meilleur = None
    for rang, (nom, motif) in enumerate(TYPES_COMPILES):
        m = motif.search(plat)
        if m and (meilleur is None or m.start() < meilleur[0]):
            meilleur = (m.start(), rang, nom)
    return meilleur[2] if meilleur else None


# ---------------------------------------------------------------------------
# Attributs discriminants
# ---------------------------------------------------------------------------
# Chaque attribut est un couple (extraction, mise en forme). Ils sont
# extraits du libelle puis reecrits sous une forme UNIQUE, pour que
# "ph+n", "1P+N", "U+N" et "phase + neutre" -- qui designent la meme
# chose -- deviennent comparables.

# CALIBRE -- trois pieges, tous mesures sur le catalogue reel.
#
# 1. Le "a" de l'ampere se confond avec la preposition francaise "a".
#    L'accent disparait a la normalisation, donc "230 a 400Vca" donnait
#    un calibre de 230A, et "boites de sol 12 a 18" un calibre de 12A.
#    Sur "Acti9 Vigi NG125 - Bloc diff. 230 a 400Vca - 2P 63A", le vrai
#    calibre est 63A : la valeur retenue etait une TENSION.
#    -> on refuse un "a" suivi d'un nombre : c'est un intervalle.
#
# 2. Un calibre nul n'existe pas. "0A" apparaissait dans le catalogue.
#
# 3. Le pouvoir de coupure s'ecrit aussi en amperes ("4500A"). Il est
#    borne a trois chiffres ici, et la paire "4500A/6kA" est ecartee
#    par le (?!\s*/) qui suit.
#    L'ESPACE TRANCHE. "24A" colle l'unite au nombre ; "230 a 400" ne
#    colle rien, parce que le "a" y est la preposition. Deux motifs
#    donc : l'unite collee est acceptee meme suivie d'un nombre
#    ("Contacteur 24A 400V" est bien un 24A), l'unite detachee est
#    refusee dans ce cas ("230 a 400Vca" est un intervalle de tension).
RE_CALIBRE_COLLE = re.compile(r"\b([1-9]\d{0,2})a\b(?!\s*/)")
RE_CALIBRE_ESPACE = re.compile(r"\b([1-9]\d{0,2}) a\b(?!\s*/)(?!\s*\d)")


def _calibre(plat: str) -> str | None:
    m = RE_CALIBRE_COLLE.search(plat) or RE_CALIBRE_ESPACE.search(plat)
    return f"{int(m.group(1))}A" if m else None
RE_COURBE = re.compile(r"\b(?:courbe|cbe|crb|c\.?b\.?e\.?)\s*([bcdkz])\b")
RE_SENSIBILITE = re.compile(r"\b(\d{1,3})\s?ma\b")
RE_SECTION = re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s?mm2\b")
RE_DIAMETRE = re.compile(r"\bd(?:iam(?:etre)?)?\.?\s?(\d{1,3})\b|\bo\s?(\d{2,3})\b")
RE_PUISSANCE = re.compile(r"\b(\d{1,4}(?:[.,]\d)?)\s?(w|kw)\b")
RE_TENSION = re.compile(r"\b(\d{2,3})\s?v(?:ca|cc|ac|dc)?\b")
RE_TEMP_K = re.compile(r"\b(\d{4})\s?k\b")

# Poles : toutes les ecritures rencontrees dans le catalogue.
# ATTENTION A "TETRAPOLAIRE". Le mot signifie "quatre poles" et ne dit
# PAS si le neutre est protege. Il ne peut donc pas servir a distinguer
# 4P de 3P+N, qui sont deux appareils electriquement differents : 4P
# protege ses quatre poles, 3P+N protege trois poles et fait passer le
# neutre.
#
# Une premiere version rangeait "tetrapolaire" avec 3P+N. Resultat
# mesure sur un libelle reel : "Disjoncteur modulaire 4P 16A courbe C
# 6kA - Acti9 iC60N tetrapolaire" etait lu 3P+N, alors que le libelle
# annonce 4P explicitement. Une recherche de 3P+N aurait fait remonter
# un 4P, et inversement.
#
# Les ecritures EXPLICITES sont donc testees d'abord ; "tetrapolaire" ne
# sert de repli que si aucune ne figure.
POLES = [
    (r"\b1\s?p\s?\+\s?n\b|\bu\s?\+\s?n\b|\bph\s?\+\s?n\b|"
     r"\bphase\s?\+?\s?neutre\b|\buni(?:polaire)?\s?\+\s?neutre\b", "1P+N"),
    (r"\b3\s?p\s?\+\s?n\b|\btri\s?\+\s?n\b|\btri\s?\+\s?neutre\b", "3P+N"),
    (r"\b2\s?p\s?\+\s?n\b", "2P+N"),
    (r"\b4\s?p\b", "4P"),
    (r"\b3\s?p\b|\btri(?:polaire)?\b", "3P"),
    (r"\b2\s?p\b|\bbi(?:polaire)?\b", "2P"),
    (r"\b1\s?p\b|\bunipolaire\b", "1P"),
    # Repli : quatre poles, repartition inconnue.
    (r"\btetrapolaire\b|\btetra\b", "4P"),
]
POLES_COMPILES = [(re.compile(m), v) for m, v in POLES]

# Pouvoir de coupure. MESURE IMPORTANTE : "4500A/6kA" apparait 124 fois
# et "6000A/10kA" 643 fois SUR LA MEME LIGNE. Ce sont deux expressions
# du meme appareil -- la valeur en amperes suit la norme domestique
# NF EN 60898, celle en kA la norme industrielle IEC 60947-2.
#
# On retient la valeur en AMPERES quand les deux figurent. On ne
# convertit JAMAIS l'une en l'autre : les paires observees sont
# majoritairement coherentes (4500<->6kA, 6000<->10kA, 10000<->15kA)
# mais pas toutes (6000<->50kA sur 52 lignes, 10000<->70kA sur 14). Une
# conversion systematique fabriquerait donc de faux rapprochements.
RE_PDC_PAIRE = re.compile(r"\b(\d{3,5})\s?a\s*/\s*(\d{1,2}(?:[.,]\d)?)\s?ka\b")
RE_PDC_A = re.compile(r"\b(3000|4500|6000|10000|15000|20000|25000)\s?a\b")
RE_PDC_KA = re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s?ka\b")


def extrait_attributs(libelle: str) -> dict:
    """Attributs techniques reperes dans un libelle, sous forme unifiee."""
    plat = aplatit(libelle)
    a: dict[str, str] = {}

    calibre = _calibre(plat)
    if calibre:
        a["calibre"] = calibre

    m = RE_COURBE.search(plat)
    if m:
        a["courbe"] = f"courbe {m.group(1).upper()}"

    for motif, valeur in POLES_COMPILES:
        if motif.search(plat):
            a["poles"] = valeur
            break

    # Pouvoir de coupure : la paire d'abord, sinon l'une ou l'autre.
    m = RE_PDC_PAIRE.search(plat)
    if m:
        a["pdc"] = f"{int(m.group(1))}A"
    else:
        m = RE_PDC_A.search(plat)
        if m:
            a["pdc"] = f"{int(m.group(1))}A"
        else:
            m = RE_PDC_KA.search(plat)
            if m:
                a["pdc"] = f"{m.group(1).replace(',', '.')}kA"

    m = RE_SENSIBILITE.search(plat)
    if m:
        a["sensibilite"] = f"{int(m.group(1))}mA"

    m = RE_SECTION.search(plat)
    if m:
        a["section"] = f"{m.group(1).replace(',', '.')}mm2"

    m = RE_PUISSANCE.search(plat)
    if m:
        unite = m.group(2).upper()
        a["puissance"] = f"{m.group(1).replace(',', '.')}{unite}"

    m = RE_TEMP_K.search(plat)
    if m:
        a["temperature"] = f"{m.group(1)}K"

    m = RE_TENSION.search(plat)
    if m:
        a["tension"] = f"{m.group(1)}V"

    return a


# ---------------------------------------------------------------------------
# Qualifiants a ne jamais avaler silencieusement
# ---------------------------------------------------------------------------
# Un libelle peut porter une mention qui change la NATURE de l'article.
# Les ignorer, c'est comparer un article seul a un lot de 50, ou un
# disjoncteur a son accessoire.

RE_LOT = re.compile(r"\blot\s+de\s+(\d+)\b|\bpar\s+(\d+)\s*(?:u|pieces?)\b|"
                    r"\bsachet\s+de\s+(\d+)\b|\bboite\s+de\s+(\d+)\b")
RE_ACCESSOIRE = re.compile(
    r"\baccessoire\b|\bcontact\s+auxiliaire\b|\bbobine\b|\bcommande\s+rotative\b|"
    r"\bplastron\b|\bcache\b|\bobturateur\b|\bborne\s+de\s+rechange\b|"
    r"\bpiece\s+detachee\b|\bkit\s+de\s+fixation\b")


def qualifiants(libelle: str) -> dict:
    """Mentions qui empechent une comparaison de prix directe."""
    plat = aplatit(libelle)
    q: dict[str, object] = {}

    m = RE_LOT.search(plat)
    if m:
        q["lot"] = int(next(g for g in m.groups() if g))

    if RE_ACCESSOIRE.search(plat):
        q["accessoire"] = True

    # "pour disjoncteur", "adapte a un coffret" : l'article est DESTINE a
    # l'appareil, il n'est pas l'appareil. Sans cette regle, un systeme
    # de repiquage a 2,95 EUR etait annonce comme le disjoncteur le
    # moins cher.
    m = RE_POUR.search(plat)
    if m:
        avant = detecte_type(plat[:m.start()])
        apres = detecte_type(plat[m.end():])
        if apres:
            q["destine_a"] = apres
            # Accessoire SEULEMENT si rien d'identifiable ne precede le
            # "pour". "Coffret 13 modules pour disjoncteur" est un
            # coffret -- un produit a part entiere, decrit par son
            # usage. "Systeme repiquage universel pour disjoncteur" n'a
            # aucun type avant le "pour" : c'est bien un accessoire.
            if not avant:
                q["accessoire"] = True

    if re.search(r"\bdc\b|\bcourant\s+continu\b|\bphotovoltaique\b", plat):
        q["courant_continu"] = True

    if re.search(r"\breconditionne\b|\boccasion\b|\bdeclasse\b", plat):
        q["reconditionne"] = True

    return q


# ---------------------------------------------------------------------------
# Designation canonique
# ---------------------------------------------------------------------------
# ORDRE DES ATTRIBUTS. Fixe volontairement, du plus cherche au moins
# cherche par un chiffreur, et non par frequence d'apparition : on
# demande "un 16A 1P+N courbe C", jamais "un 6000A".
ORDRE = ["calibre", "courbe", "poles", "sensibilite", "section",
         "puissance", "temperature", "pdc", "tension"]

# Un libelle commencant par une reference : jeton melangeant lettres ET
# chiffres. Mesure : 2,9 % des libelles du catalogue, jusqu'a 3,5 % chez
# Rexel. Exemples reels : "SN201SL Disjoncteur modulaire", "iC60N
# Disjoncteur Acti9", "FR-N1XD4AR TORS.BRAN.AL".
RE_REF_TETE = re.compile(
    r"^(?=[A-Za-z0-9\-/\.]*[A-Za-z])(?=[A-Za-z0-9\-/\.]*\d)"
    r"([A-Za-z0-9\-/\.]{4,})\s+")


def designation_canonique(libelle: str, marque: str | None = None,
                          max_longueur: int = 150) -> dict:
    """Recompose le libelle : TYPE en tete, puis attributs, puis le reste.

    Renvoie un dictionnaire pour que l'appelant puisse afficher la
    designation courte dans une colonne etroite et garder le detail
    ailleurs, sans troncature aveugle -- c'est la troncature qui
    masquait justement l'information distinctive.
    """
    brut = str(libelle or "").strip()
    plat = aplatit(brut)

    type_produit = detecte_type(plat)
    attrs = extrait_attributs(brut)
    quals = qualifiants(brut)

    # Reference eventuellement placee en tete du libelle.
    ref_tete = None
    m = RE_REF_TETE.match(brut)
    if m and not detecte_type(aplatit(m.group(1))):
        # On ne retire le premier jeton que s'il ne porte pas lui-meme le
        # type : "R2V 3G2.5" commence par ce qui EST le produit.
        ref_tete = m.group(1)

    # --- construction ------------------------------------------------------
    tete: list[str] = []
    if type_produit:
        tete.append(type_produit.capitalize())
    for cle in ORDRE:
        if attrs.get(cle):
            tete.append(attrs[cle])

    if marque and aplatit(marque) not in plat:
        tete.append(str(marque).strip())

    # Les qualifiants sont AFFICHES, jamais absorbes : c'est ce qui
    # empeche de comparer un lot de 50 a une piece seule.
    marques_qual = []
    if quals.get("lot"):
        marques_qual.append(f"LOT DE {quals['lot']}")
    if quals.get("accessoire"):
        marques_qual.append("ACCESSOIRE")
    if quals.get("courant_continu"):
        marques_qual.append("DC")
    if quals.get("reconditionne"):
        marques_qual.append("RECONDITIONNE")

    courte = " ".join(tete)
    if marques_qual:
        courte = f"[{' · '.join(marques_qual)}] {courte}"
    if not courte.strip():
        courte = brut[:max_longueur]

    return {
        "designation_courte": courte[:max_longueur],
        "type_produit": type_produit,
        "attributs": attrs,
        "qualifiants": quals,
        "reference_en_tete": ref_tete,
        "libelle_origine": brut,
    }


# ---------------------------------------------------------------------------
# Filtre par precision
# ---------------------------------------------------------------------------


def attributs_recherche(requete: str) -> dict:
    """Attributs EXIGES par la requete.

    "disjoncteur" n'exige rien : tous les disjoncteurs sortent.
    "disjoncteur 16a" exige calibre=16A : les 20A sont ecartes.
    """
    return extrait_attributs(requete)


def article_conforme(requete: str, libelle: str) -> tuple[bool, str | None]:
    """L'article respecte-t-il toutes les precisions de la requete ?

    Renvoie (conforme, motif du rejet). La regle est la CONTRADICTION,
    jamais la ressemblance : un attribut absent du libelle ne provoque
    pas de rejet -- seule une valeur DIFFERENTE le fait.

    Mesure de la session precedente : filtrer sur la ressemblance de
    libelle faisait chuter le rappel de 97 % a 9 %. Le libelle sert a
    detecter une contradiction, pas a mesurer une proximite.
    """
    exiges = attributs_recherche(requete)
    if not exiges:
        return True, None

    trouves = extrait_attributs(libelle)
    for cle, valeur in exiges.items():
        presente = trouves.get(cle)
        if presente is not None and presente != valeur:
            return False, f"{cle} : {presente} au lieu de {valeur}"
    return True, None


def niveau_conformite(requete: str, libelle: str) -> dict:
    """Classe l'article par rapport aux precisions de la requete.

    POURQUOI UN NIVEAU, ET PAS UN SIMPLE OUI/NON
    ---------------------------------------------
    Mesure sur les 26 860 libelles de disjoncteur du catalogue :
    "disjoncteur 16A" laisse passer 14 052 lignes, dont 862 seulement
    annoncent explicitement 16A. Les 13 190 autres ne mentionnent AUCUN
    calibre : la regle de contradiction ne les ecarte pas, a juste titre
    -- un libelle muet n'est pas un libelle contraire, et le calibre
    peut figurer dans une autre colonne ou dans la fiche produit.

    Mais afficher 14 052 lignes quand on demande du 16A revient a ne pas
    filtrer. Et les ecarter ferait perdre de vrais articles.

    D'ou trois niveaux, tries dans cet ordre :

      exact       tous les attributs precises sont presents ET egaux
      partiel     certains presents et egaux, les autres muets
      non precise aucun attribut precise n'est mentionne
      (ecarte)    au moins un attribut CONTREDIT la requete

    L'ecran affiche les exacts en premier et peut masquer les muets sur
    un clic. Rien n'est perdu, rien n'est noye.
    """
    exiges = attributs_recherche(requete)
    trouves = extrait_attributs(libelle)

    if not exiges:
        return {"conforme": True, "niveau": "exact", "score": 100,
                "confirmes": [], "muets": [], "motif": None}

    confirmes, muets = [], []
    for cle, valeur in exiges.items():
        presente = trouves.get(cle)
        if presente is None:
            muets.append(cle)
        elif presente == valeur:
            confirmes.append(cle)
        else:
            return {"conforme": False, "niveau": "ecarte", "score": 0,
                    "confirmes": confirmes, "muets": muets,
                    "motif": f"{cle} : {presente} au lieu de {valeur}"}

    if not confirmes:
        niveau = "non precise"
    elif muets:
        niveau = "partiel"
    else:
        niveau = "exact"

    # Le score sert au tri : la proportion d'attributs confirmes.
    score = round(100 * len(confirmes) / len(exiges))
    return {"conforme": True, "niveau": niveau, "score": score,
            "confirmes": confirmes, "muets": muets, "motif": None}


# Ordre d'affichage des niveaux.
RANG_NIVEAU = {"exact": 0, "partiel": 1, "non precise": 2, "ecarte": 3}


# ---------------------------------------------------------------------------
# Unite de vente
# ---------------------------------------------------------------------------
# MESURE : le catalogue porte 39 unites distinctes, dont 9 groupes qui ne
# different que par la casse ou l'accent -- "Piece"/"piece",
# "Boite"/"boite", "Lot"/"lot", "Carton"/"carton"... Comptees comme
# differentes, elles empechent de comparer un prix a la piece chez un
# fournisseur avec un prix a la piece chez un autre.
#
# 39 -> 30 valeurs apres unification.

UNITES = {
    "piece": "pièce", "pieces": "pièce", "pc": "pièce", "pce": "pièce",
    "u": "pièce", "unite": "pièce", "unites": "pièce", "un": "pièce",
    "metre": "mètre", "metres": "mètre", "ml": "mètre", "m": "mètre",
    "metre lineaire": "mètre",
    "metre carre": "m²", "m2": "m²", "metres carres": "m²",
    "metre cube": "m³", "m3": "m³",
    "kilogramme": "kg", "kg": "kg", "kilo": "kg", "kilos": "kg",
    "tonne": "tonne", "t": "tonne",
    "litre": "litre", "l": "litre", "litres": "litre",
    "boite": "boîte", "boites": "boîte", "bte": "boîte",
    "carton": "carton", "cartons": "carton", "ctn": "carton",
    "sachet": "sachet", "sac": "sac", "sacs": "sac",
    "sac-sachet": "sac", "sac sachet": "sac",
    "rouleau": "rouleau", "rouleaux": "rouleau", "rlx": "rouleau",
    "paquet": "paquet", "paquets": "paquet", "paq": "paquet",
    "lot": "lot", "lots": "lot",
    "bidon": "bidon", "bidons": "bidon",
    "palette": "palette", "palettes": "palette", "pal": "palette",
    "couronne": "couronne", "couronnes": "couronne",
    "barre": "barre", "barres": "barre",
    "plaque": "plaque", "plaques": "plaque",
    "panneau": "panneau", "panneaux": "panneau",
    "jeu": "jeu", "kit": "kit", "coffret": "coffret",
    "seau": "seau", "pot": "pot", "tube": "tube", "cartouche": "cartouche",
    "touret": "touret", "botte": "botte", "ensemble": "ensemble",
    "heure": "heure", "h": "heure", "jour": "jour",
}


def unite_canonique(unite: str | None) -> str | None:
    """Ramene une unite de vente a une forme unique.

    La casse et les accents ne portent aucune information ici : "Piece"
    et "piece" sont la meme unite. Les garder distinctes empeche de
    comparer un prix a la piece entre deux fournisseurs.

    Une unite inconnue est renvoyee telle quelle, sans etre inventee --
    mieux vaut une unite non reconnue qu'une unite fausse.
    """
    if unite is None:
        return None
    brut = str(unite).strip()
    # Residus d'extraction web collees a l'unite. Mesure sur le
    # catalogue reel : "PiecePrecedent1Suivant",
    # "Metre carrePrecedent1Suiv" -- du texte de pagination happe lors
    # de la collecte, qui fabrique autant de fausses unites.
    brut = re.sub(r"(?i)pr[eé]c[eé]dent\s*\d*\s*suiv\w*", "", brut)
    brut = re.sub(r"(?i)\b(suivant|precedent|page\s*\d+)\b", "", brut)
    brut = brut.strip(" -_·|")
    if not brut:
        return None
    cle = aplatit(brut)
    cle = re.sub(r"[^a-z0-9 ]+", " ", cle)
    cle = " ".join(cle.split())
    return UNITES.get(cle, brut)
