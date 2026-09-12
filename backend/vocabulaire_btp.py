"""Vocabulaire du batiment : un meme critere, plusieurs ecritures.

POURQUOI CE MODULE EXISTE
-------------------------
Un chiffreur tape "ph+n". Les fournisseurs ecrivent "1P+N", "Ph+N",
"U+N", "phase + neutre". Sans traduction, la requete
"disjoncteur 16a courbe c ph+n" renvoyait ZERO resultat alors que le
catalogue en contient des centaines.

CHAQUE ENTREE EST MESUREE, AUCUNE N'EST SUPPOSEE
-------------------------------------------------
Les occurrences ci-dessous ont ete comptees sur les 914 628 designations
du catalogue consolide (Rexel, Prolians, Point.P, La Plateforme, SFIC).
Une variante qui n'apparait pas dans les donnees n'a pas sa place ici :
elle elargirait la recherche sans rien ramener.

CES REGLES SONT MUTUALISABLES
-----------------------------
Elles decrivent le vocabulaire du metier, pas des prix. Elles profitent
donc a tous les tenants et ont leur place dans la table
`product_match_rules`, definie SANS tenant_id. Les prix, eux, ne sortent
jamais du tenant.

DEUX FORMES DE MOTIF
--------------------
  - chaine simple : cherchee telle quelle, acceleree par l'index
    trigramme (LIKE '%...%') ;
  - motif entre //: expression reguliere, pour les cas ou une borne est
    indispensable.

La distinction n'est pas cosmetique. La premiere version listait "p+n"
comme simple chaine ; or "p+n" est contenu dans "3p+n", si bien qu'une
requete 1P+N ramenait 46 disjoncteurs tetrapolaires, d'un tout autre
prix. Les notations de poles sont donc bornees par expression reguliere.
"""

# Prefixe marquant une expression reguliere plutot qu'une sous-chaine.
RE = "re:"


EQUIVALENCES: dict[str, list[str]] = {
    # =====================================================================
    # Nombre de poles -- 30 555 notations "\dp" dans le catalogue
    # =====================================================================
    # Bornes indispensables : (?<![2-9]) empeche 3p+n et 4p+n de repondre
    # a une demande 1P+N.
    "ph+n": [RE + r"(?<![2-9])1?p\+n", RE + r"\bph\+n\b", RE + r"\bu\+n\b",
             "phase neutre", "unipolaire neutre"],
    "1p+n": [RE + r"(?<![2-9])1?p\+n", RE + r"\bph\+n\b", RE + r"\bu\+n\b",
             "phase neutre", "unipolaire neutre"],
    "2p": [RE + r"\b2p\b(?!\+)", "bipolaire"],
    "bipolaire": [RE + r"\b2p\b(?!\+)", "bipolaire"],
    "3p": [RE + r"\b3p\b(?!\+)", "tripolaire"],
    "tripolaire": [RE + r"\b3p\b(?!\+)", "tripolaire"],
    "3p+n": [RE + r"\b3p\+n\b", RE + r"\b3p n\b", "tetrapolaire",
             RE + r"\b4p\b"],
    "4p": [RE + r"\b4p\b", RE + r"\b3p\+n\b", "tetrapolaire"],
    "tetrapolaire": [RE + r"\b4p\b", RE + r"\b3p\+n\b", "tetrapolaire"],
    "1p": [RE + r"(?<![0-9])\b1p\b(?!\+)", "unipolaire"],
    "unipolaire": [RE + r"(?<![0-9])\b1p\b(?!\+)", "unipolaire"],

    # =====================================================================
    # Courbe de declenchement
    # =====================================================================
    # "courbe" 5 766 | "cbe" 1 658 | "crb" 143 -- les trois sont reelles.
    "courbe": ["courbe", RE + r"\bcbe\b", RE + r"\bcrb\b"],

    # =====================================================================
    # Differentiel -- 3 209 "differentiel", 1 359 "diff"
    # =====================================================================
    # "id" (3 317 occurrences) et "ddr" (6) sont ECARTES : "id" apparait
    # massivement hors de ce sens (identifiant, RAL id, etc.) et
    # produirait un bruit considerable ; "ddr" est trop rare pour peser.
    "differentiel": ["differentiel", RE + r"\bdiff\b"],

    # =====================================================================
    # Materiaux
    # =====================================================================
    # "inox" 14 104 | "acier inoxydable" 637. Les nuances a2 (3 826),
    # a4 (1 929), 304 (664) et 316 (1 297) sont ECARTEES comme synonymes
    # automatiques : ce sont des chiffres courts qui apparaissent dans
    # des dizaines d'autres contextes. Le chiffreur qui veut de l'A2 le
    # tape explicitement.
    "inox": ["inox", "acier inoxydable"],
    # "aluminium" 20 276 | "alu" 8 630
    "aluminium": ["aluminium", RE + r"\balu\b"],
    "alu": ["aluminium", RE + r"\balu\b"],

    # =====================================================================
    # Platrerie
    # =====================================================================
    # "plaque de platre" 844 | "placo" 373 | "placoplatre" 76
    "ba13": ["ba13", "ba 13"],
    "ba18": ["ba18", "ba 18"],
    "placo": ["placo", "plaque de platre", "placoplatre"],
    "plaque de platre": ["placo", "plaque de platre", "placoplatre"],

    # =====================================================================
    # Isolation
    # =====================================================================
    # "laine de verre" 553. "mw" (405) ECARTE : deux lettres, trop
    # ambigu.
    "laine de verre": ["laine de verre"],

    # =====================================================================
    # Peinture -- "mat" 17 335, "mate" 91 ; "satine" 5 779, "satin" 752
    # =====================================================================
    "mat": [RE + r"\bmate?\b"],
    "mate": [RE + r"\bmate?\b"],
    "satin": [RE + r"\bsatine?\b"],
    "satine": [RE + r"\bsatine?\b"],

    # =====================================================================
    # Indices de protection -- "ip65" 11 520, "ip 65" 284
    # =====================================================================
    "ip65": ["ip65", "ip 65"],
    "ip44": ["ip44", "ip 44"],
    "ip20": ["ip20", "ip 20"],
    "etanche": ["etanche", "saillie", RE + r"\bip\s?6[5-8]\b"],
    "encastre": [RE + r"\bencastre"],

    # =====================================================================
    # Plomberie / chauffage
    # =====================================================================
    # "coude" 5 455 | "equerre" 2 121. "per" (815) et "multicouche" (572)
    # restent tels quels : "per" est trop court pour etre elargi sans
    # risque, mais assez specifique pour etre cherche seul.
    "coude": ["coude", "equerre"],
    "thermostatique": ["thermostatique"],
    "gaine icta": ["icta", "gaine annelee"],
    "icta": ["icta", "gaine annelee"],

    # =====================================================================
    # Visserie -- "tete fraisee" 2 254 | "tete plate" 322
    # =====================================================================
    # "tf" (2 060) ECARTE : deux lettres presentes dans de nombreuses
    # references fabricant.
    "tete fraisee": ["tete fraisee", "tete plate"],
}


# ===========================================================================
# Qualifiants : un mot qui CHANGE la nature de l'article
# ===========================================================================
# Un "disjoncteur differentiel" n'est pas un "disjoncteur". Un article
# "reconditionne" n'est pas du neuf. Un "coffret pre-equipe" n'est pas un
# appareil seul.
#
# MESURE QUI A MOTIVE CETTE REGLE
# --------------------------------
# Sur "disjoncteur 16a courbe c ph+n", 85 des 174 resultats etaient des
# DIFFERENTIELS, de prix median 189,86 EUR contre 6,83 EUR pour le moins
# cher des simples. Le prix median affiche etait de 131 EUR pour ce qui
# en vaut 33. La comparaison etait fausse.
#
# ILS NE SONT PAS SUPPRIMES
# --------------------------
# La garantie d'inclusion l'interdit : tout produit contenant les termes
# demandes doit rester accessible. Ils sont ISOLES dans une rubrique a
# part, comptes et consultables. Le chiffreur voit qu'ils existent et
# peut les demander explicitement.
QUALIFIANTS: list[tuple[str, str]] = [
    ("différentiel", r"\bdifferentiel\b|\bdiff\.?\b"),
    ("reconditionné", r"\breconditionne"),
    ("coffret ou tableau pré-équipé", r"\bcoffret\b|\btableau\b|\bplatine\b"),
    ("appareil combiné", r"\bcombine\b"),
    ("lot ou conditionnement multiple",
     r"\blot de \d|\bcouronne\b|\bpack de \d"),
    ("parafoudre", r"\bparafoudre\b"),
]


# ===========================================================================
# Termes COMPOSES : un critere ecrit en deux mots
# ===========================================================================
# "courbe c" est UN critere, pas deux. Traites separement, le "c" devient
# un motif LIKE '%c%' qui correspond a presque toutes les lignes du
# catalogue : la recherche perd sa pertinence et l'index trigramme ne
# sert plus a rien.
#
# Ces prefixes, suivis d'une seule lettre ou d'un seul chiffre, sont donc
# fusionnes en un terme unique avant expansion.
PREFIXES_COMPOSES = {
    "courbe": ["courbe", "cbe", "crb"],
    "cbe": ["courbe", "cbe", "crb"],
    "crb": ["courbe", "cbe", "crb"],
    "type": ["type", "tc"],
    "classe": ["classe", "cl"],
    "taille": ["taille", "t"],
}


def compose(prefixe: str, valeur: str) -> list[str]:
    """Motifs d'un critere en deux mots, avec espace optionnel.

    "courbe c" accepte "courbe c", "courbec", "cbe c", "crb c".
    """
    formes = PREFIXES_COMPOSES.get(prefixe, [prefixe])
    alternance = "|".join(formes)
    return [RE + rf"\b(?:{alternance}) ?{re_echappe(valeur)}\b"]


def re_echappe(txt: str) -> str:
    import re as _re
    return _re.escape(txt)


def re_est_nombre(txt: str) -> bool:
    import re as _re
    return bool(_re.fullmatch(r"\d+(?:\.\d+)?", txt))


# Unites d'une seule lettre, ecrites apres le nombre : "15 l", "100 w",
# "16 a", "230 v". Cas symetrique de "courbe c" : sans fusion, le "l" est
# ecarte comme trop court et le critere devient un simple "15", qui
# correspond a toute reference contenant ce nombre.
UNITES_COURTES = {
    "l": ["l", "litre", "litres"],
    "w": ["w", "watt", "watts"],
    "a": ["a", "amp", "ampere", "amperes"],
    "v": ["v", "volt", "volts"],
    "m": ["m", "metre", "metres", "ml"],
    "g": ["g", "gramme", "grammes"],
    "k": ["k", "kelvin"],
}


def compose_unite(nombre: str, unite: str) -> list[str]:
    """Motifs d'un couple nombre + unite, avec espace optionnel."""
    formes = UNITES_COURTES.get(unite, [unite])
    alternance = "|".join(formes)
    return [RE + rf"\b{re_echappe(nombre)} ?(?:{alternance})\b"]


# Mots vides : articles et prepositions. "laine de verre" produisait un
# motif LIKE '%de%' qui correspond a des centaines de milliers de lignes
# sans rien discriminer.
#
# Les ecarter ne peut qu'ELARGIR le resultat, donc la garantie
# d'inclusion est preservee : on ne risque pas de manquer un produit,
# seulement d'en accepter davantage -- ce qui est le comportement voulu.
MOTS_VIDES = {
    "de", "du", "la", "le", "les", "des", "et", "en", "au", "aux",
    "pour", "avec", "sur", "par", "un", "une", "ou", "dans", "sous",
}


def compose_dimension(a: str, b: str) -> list[str]:
    """Motifs d'une dimension "5 x 50", avec espaces optionnels.

    Format tres courant : visserie (5 x 50), carrelage (60 x 60),
    plaques (1200 x 600). Sans fusion, "5" et "50" sont cherches
    separement et "50" correspond a toute reference contenant ce nombre.

    L'ordre est accepte dans les deux sens : un carrelage 60x120 et un
    120x60 sont le meme format.
    """
    x, y = re_echappe(a), re_echappe(b)
    return [RE + rf"\b(?:{x} ?x ?{y}|{y} ?x ?{x})\b"]


def fusionne_composes(termes: list[str]) -> list[tuple[str, list[str]]]:
    """Regroupe les termes composes. Rend une liste (libelle, motifs).

    Le libelle sert a l'affichage : le chiffreur doit voir que sa saisie
    a ete comprise, sans lire d'expression reguliere.
    """
    sortie: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(termes):
        terme = termes[i]
        suivant = termes[i + 1] if i + 1 < len(termes) else None
        if (terme in PREFIXES_COMPOSES and suivant
                and len(suivant) == 1 and suivant.isalnum()):
            sortie.append((f"{terme} {suivant}", compose(terme, suivant)))
            i += 2
            continue
        # dimension : "5 x 50", "60 x 60", "1200 x 600"
        apres = termes[i + 2] if i + 2 < len(termes) else None
        if (re_est_nombre(terme) and suivant == "x" and apres
                and re_est_nombre(apres)):
            sortie.append((f"{terme} x {apres}",
                           compose_dimension(terme, apres)))
            i += 3
            continue
        # nombre + unite d'une lettre : "15 l", "100 w", "230 v"
        if (suivant and suivant in UNITES_COURTES
                and re_est_nombre(terme)):
            sortie.append((f"{terme} {suivant}",
                           compose_unite(terme, suivant)))
            i += 2
            continue
        # Un terme d'une seule lettre isole, ou un mot vide, est ignore :
        # il ferait un balayage complet sans apporter d'information.
        if len(terme) == 1 or terme in MOTS_VIDES:
            i += 1
            continue
        sortie.append((terme, variantes(terme)))
        i += 1
    return sortie


# ===========================================================================
# Libelles lisibles -- ce que l'utilisateur voit
# ===========================================================================
# Les motifs ci-dessus sont techniques. Afficher "\bcbe\b" a un chiffreur
# n'a aucun sens. Ce tableau donne, pour chaque terme reconnu, les
# ecritures en clair -- indispensable pour qu'une requete sans resultat
# reste comprehensible.
LIBELLES: dict[str, list[str]] = {
    "ph+n": ["1P+N", "Ph+N", "U+N", "phase + neutre"],
    "1p+n": ["1P+N", "Ph+N", "U+N", "phase + neutre"],
    "2p": ["2P", "bipolaire"],
    "bipolaire": ["2P", "bipolaire"],
    "3p": ["3P", "tripolaire"],
    "tripolaire": ["3P", "tripolaire"],
    "3p+n": ["3P+N", "4P", "tétrapolaire"],
    "4p": ["4P", "3P+N", "tétrapolaire"],
    "tetrapolaire": ["4P", "3P+N", "tétrapolaire"],
    "1p": ["1P", "unipolaire"],
    "unipolaire": ["1P", "unipolaire"],
    "courbe": ["courbe", "Cbe", "Crb"],
    "differentiel": ["différentiel", "diff."],
    "inox": ["inox", "acier inoxydable"],
    "aluminium": ["aluminium", "alu"],
    "alu": ["aluminium", "alu"],
    "placo": ["placo", "plaque de plâtre", "placoplâtre"],
    "plaque de platre": ["placo", "plaque de plâtre", "placoplâtre"],
    "mat": ["mat", "mate"],
    "mate": ["mat", "mate"],
    "satin": ["satin", "satiné"],
    "satine": ["satin", "satiné"],
    "etanche": ["étanche", "saillie", "IP65 à IP68"],
    "coude": ["coude", "équerre"],
    "icta": ["ICTA", "gaine annelée"],
    "gaine icta": ["ICTA", "gaine annelée"],
    "tete fraisee": ["tête fraisée", "tête plate"],
    "ba13": ["BA13", "BA 13"],
    "ba18": ["BA18", "BA 18"],
    "ip65": ["IP65", "IP 65"],
}


def libelles(terme: str) -> list[str] | None:
    """Ecritures en clair d'un terme, ou None si rien a signaler."""
    if terme in LIBELLES:
        return LIBELLES[terme]
    r = racine(terme)
    if r in LIBELLES:
        return LIBELLES[r]
    # Terme compose : "courbe c" -> on montre les prefixes acceptes
    parties = terme.split()
    if len(parties) == 2 and parties[0] in PREFIXES_COMPOSES:
        return [f"{f} {parties[1].upper()}"
                for f in PREFIXES_COMPOSES[parties[0]]]
    if len(parties) == 2 and parties[1] in UNITES_COURTES:
        return [f"{parties[0]} {f}" for f in UNITES_COURTES[parties[1]]]
    if len(parties) == 3 and parties[1] == "x":
        a, b = parties[0], parties[2]
        return [f"{a}x{b}", f"{b}x{a}", f"{a} x {b}"]
    return None


def variantes(terme: str) -> list[str]:
    """Ecritures acceptables d'un terme de requete.

    Ne RESTREINT jamais : sans regle connue, le terme est cherche tel
    quel. Le vocabulaire ne peut qu'elargir le resultat, donc la garantie
    d'inclusion est preservee par construction.
    """
    if terme in EQUIVALENCES:
        return EQUIVALENCES[terme]
    r = racine(terme)
    if r in EQUIVALENCES:
        return EQUIVALENCES[r]
    return [r]


def racine(mot: str) -> str:
    """Absorbe les pluriels sans dictionnaire : "cables" -> "cable"."""
    for suffixe in ("aux", "eaux", "es", "s", "x"):
        if len(mot) > 4 and mot.endswith(suffixe):
            return mot[: -len(suffixe)]
    return mot


def est_regex(motif: str) -> bool:
    return motif.startswith(RE)


def nu(motif: str) -> str:
    """Motif sans son prefixe de type."""
    return motif[len(RE):] if est_regex(motif) else motif
