#!/usr/bin/env python3
"""Quelle combinaison de mesures evite de confondre deux articles ?

METHODE -- l'EAN sert d'ARBITRE, pas de critere
-----------------------------------------------
Sur les 630 945 lignes qui portent a la fois un EAN a 13 chiffres et une
reference fabricant, l'EAN dit la verite sur l'identite produit. On peut
donc juger n'importe quel autre critere en comparant son verdict a celui
de l'EAN.

  POSITIFS : paires de meme EAN            -> vraiment le meme produit
  NEGATIFS : paires de meme REF FABRICANT
             mais d'EAN different            -> confusion a eviter

Mesure de depart : la reference fabricant seule produit 98,6 % de faux
rapprochements. C'est le probleme a corriger.
"""
import re
import unicodedata

import pandas as pd


def normalise(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


SUFFIXES = (" snc", " s n c", " sas", " sa", " sarl", " france", " electric",
            " electrique", " group", " groupe", " se", " ag", " gmbh", " spa",
            " iberica", " italia", " deutschland")


def normalise_marque(m):
    n = normalise(m)
    change = True
    while change:
        change = False
        for suf in SUFFIXES:
            if n.endswith(suf):
                n, change = n[: -len(suf)].strip(), True
    return n


def attributs(texte):
    """Grandeurs techniques ET attributs de VARIANTE du descriptif.

    POURQUOI LE DESCRIPTIF EST LA SEULE SOURCE FIABLE
    -------------------------------------------------
    Mesure sur le catalogue consolide (914 628 lignes, 5 fournisseurs) :
    la reference fabricant seule produit 98,6 % de faux rapprochements.
    Deux causes, toutes deux dans la donnee, pas dans l'algorithme :

      1. Chez Point.P, la "reference fabricant" designe une GAMME et non
         un produit. 'COF12LINT' couvre 58 coffres de linteau de tailles
         differentes ; '645640' toutes les pointures d'une chaussure
         PUMA ; '40062' toute une serie de carrelage Cinca en formats
         varies. La variante n'existe QUE dans le descriptif.

      2. Les references courtes se percutent par hasard entre univers
         sans rapport : '2201' relie un cable LED Rexel (EUROPOLE) et
         une faience Point.P (CINCA).

    Consequence : ce sont les DIMENSIONS, le FORMAT, la POINTURE, la
    FINITION et la COULEUR extraits du descriptif qui distinguent deux
    articles. D'ou l'extraction ci-dessous.

    Les decimales sont protegees avant normalisation, sinon "2,5 mm2"
    devient "2 5 mm2" et la section est perdue -- confusion mesuree
    entre fil 1,5 et 2,5 mm2.
    """
    t = re.sub(r"(\d)[.,](\d)", r"\1DEC\2", str(texte or ""))
    t = normalise(t).replace("dec", ".")
    a = {}

    # --- DIMENSIONS : le discriminant n.1 des variantes de gamme ---
    # "45 x 45", "60 x 120 cm", "8 x 120", "1200 x 600 x 50"
    dims = re.findall(r"\b(\d+(?:\.\d+)?(?:\s*x\s*\d+(?:\.\d+)?){1,2})\b", t)
    if dims:
        normalisees = set()
        for d in dims:
            parties = [p.strip() for p in d.split("x")]
            # trie : "45 x 60" et "60 x 45" designent le meme format
            normalisees.add("x".join(sorted(parties, key=float)))
        a["dimensions"] = normalisees

    # --- POINTURE / TAILLE : toutes les chaussures d'une gamme
    # partagent une seule reference fabricant ---
    m = re.findall(r"\bt\s*\.?\s*(\d{2})\b|\btaille\s*(\d{2})\b", t)
    tailles = {x for couple in m for x in couple if x}
    if tailles:
        a["taille"] = tailles

    # --- FINITION : mat et rectifie ne sont pas le meme carrelage ---
    finitions = {f for f in ("mat", "brillant", "rectifie", "poli", "satine",
                             "structure", "adouci", "vieilli")
                 if re.search(r"\b" + f + r"\b", t)}
    if finitions:
        a["finition"] = finitions

    # --- COULEUR : variante frequente au sein d'une meme gamme ---
    couleurs = {c for c in ("blanc", "noir", "gris", "beige", "sable",
                            "graphite", "anthracite", "taupe", "creme",
                            "bleu", "rouge", "vert", "jaune", "marron",
                            "ivoire", "fumee", "mist", "perle", "clementine",
                            "mandarine", "chene", "naturel")
                if re.search(r"\b" + c + r"\b", t)}
    if couleurs:
        a["couleur"] = couleurs

    # --- INDICES DE PROTECTION ET TYPES NORMALISES ---
    m = re.findall(r"\bip\s*(\d{2})\b", t)
    if m:
        a["ip"] = set(m)
    m = re.findall(r"\bik\s*(\d{2})\b", t)
    if m:
        a["ik"] = set(m)
    m = re.findall(r"\btype\s*(\d{1,3})\b|\btc\s*(\d)\b", t)
    types = {x for couple in m for x in couple if x}
    if types:
        a["type_num"] = types

    # --- GRANDEURS PHYSIQUES ---
    for cle, motif in (
        ("ampere", r"\b(\d{1,4})\s*(?:a|amp|amperes?)\b"),
        ("milliampere", r"\b(\d{2,4})\s*ma\b"),
        ("watt", r"\b(\d{1,5})\s*(?:w|watts?)\b"),
        ("volt", r"\b(\d{2,4})\s*v\b"),
        ("section", r"\b(\d+(?:\.\d+)?)\s*mm2\b"),
        ("litre", r"\b(\d+(?:\.\d+)?)\s*(?:l|litres?)\b"),
        ("modules", r"\b(\d{1,2})\s*modules?\b"),
        ("kelvin", r"\b(\d{4})\s*k\b"),
        ("lumen", r"\b(\d{2,6})\s*(?:lm|lumens?)\b"),
        ("conditionnement", r"\blot\s*de\s*(\d{1,4})\b|\bcouronne\s*(?:de\s*)?(\d{1,4})\b"),
    ):
        trouve = re.findall(motif, t)
        if trouve:
            plat = set()
            for x in trouve:
                if isinstance(x, tuple):
                    plat |= {y for y in x if y}
                else:
                    plat.add(x)
            if plat:
                a[cle] = plat

    m = re.search(r"\bcourbe\s*([bcd])\b", t)
    if m:
        a["courbe"] = m.group(1)
    return a


MOTS_VIDES = {"de", "du", "la", "le", "les", "des", "a", "au", "aux", "et",
              "en", "pour", "avec", "sur", "par", "ou", "un", "une", "mm",
              "cm", "type", "ref"}


def jetons(t):
    return {j for j in normalise(t).split() if j not in MOTS_VIDES and len(j) > 1}


# --- les mesures additionnelles, une par une ----------------------------

def g_marque(a, b):
    ma, mb = normalise_marque(a["marque"]), normalise_marque(b["marque"])
    if not ma or not mb:
        return True          # inconnue : on ne tranche pas
    return ma == mb


def g_longueur(a, b):
    return len(a["reff"]) >= 8


def g_unite(a, b):
    ua, ub = a["unite"], b["unite"]
    if not ua or not ub:
        return True
    return ua == ub


def g_libelle(a, b, seuil=0.45):
    ja, jb = jetons(a["des"]), jetons(b["des"])
    if not ja or not jb:
        return True
    return len(ja & jb) / len(ja | jb) >= seuil


def g_prix(a, b, ratio_max=1.6):
    pa, pb = a["px"], b["px"]
    if pd.isna(pa) or pd.isna(pb) or pa <= 0 or pb <= 0:
        return True
    return max(pa, pb) / min(pa, pb) <= ratio_max


def g_attributs(a, b):
    aa, ab = attributs(a["des"]), attributs(b["des"])
    for cle in set(aa) & set(ab):
        va, vb = aa[cle], ab[cle]
        if isinstance(va, set) and isinstance(vb, set):
            if not (va & vb):
                return False
        elif va != vb:
            return False
    return True


GARDES = [
    ("marque identique", g_marque),
    ("ref >= 8 caracteres", g_longueur),
    ("unite de vente identique", g_unite),
    ("libelles proches (>=45 %)", g_libelle),
    ("prix dans un rapport <= 1,6", g_prix),
    ("attributs techniques compatibles", g_attributs),
]


def evalue(v, pos, neg, gardes):
    def passe(i, j):
        a, b = v.loc[i], v.loc[j]
        return all(f(a, b) for _, f in gardes)

    vp = sum(1 for i, j in pos if passe(i, j))
    fp = sum(1 for i, j in neg if passe(i, j))
    return vp, fp


def main():
    v, pos, neg = pd.read_pickle("/tmp/jeu.pkl")
    print(f"jeu de test : {len(pos)} vrais doublons | {len(neg):,} confusions\n")

    print("=" * 74)
    print("EFFET DE CHAQUE MESURE, PRISE SEULE")
    print("=" * 74)
    print("  mesure additionnelle                 retenus  confusions  precision")
    print("  -----------------------------------  -------  ----------  ---------")
    vp0, fp0 = len(pos), len(neg)
    print(f"  {'(aucune) ref fabricant seule':35}  {vp0:7}  {fp0:10,}  "
          f"{100*vp0/(vp0+fp0):7.1f} %")
    for nom, f in GARDES:
        vp, fp = evalue(v, pos, neg, [(nom, f)])
        prec = 100 * vp / (vp + fp) if vp + fp else 0
        print(f"  {nom:35}  {vp:7}  {fp:10,}  {prec:7.1f} %")

    print()
    print("=" * 74)
    print("EFFET CUMULE -- on empile les mesures")
    print("=" * 74)
    print("  mesures cumulees                     retenus  confusions  precision")
    print("  -----------------------------------  -------  ----------  ---------")
    cumul = []
    for nom, f in GARDES:
        cumul.append((nom, f))
        vp, fp = evalue(v, pos, neg, cumul)
        prec = 100 * vp / (vp + fp) if vp + fp else 0
        rappel = 100 * vp / len(pos)
        print(f"  + {nom:33}  {vp:7}  {fp:10,}  {prec:7.1f} %"
              f"   (rappel {rappel:.0f} %)")

    print()
    print("=" * 74)
    print("CONCLUSION")
    print("=" * 74)
    vp, fp = evalue(v, pos, neg, GARDES)
    prec = 100 * vp / (vp + fp) if vp + fp else 0
    print(f"  Avec les 6 mesures : {prec:.1f} % de precision, "
          f"{100*vp/len(pos):.0f} % des vrais doublons retrouves.")
    print(f"  Confusions restantes : {fp} sur {len(neg):,} initialement "
          f"({100*(1-fp/len(neg)):.1f} % eliminees).")


main()


def recherche_combinaison():
    """Quelle combinaison maximise l'elimination SANS detruire le rappel ?

    Enseignement de la mesure precedente : exiger des libelles PROCHES
    fait chuter le rappel de 97 % a 9 %, parce que deux fournisseurs
    decrivent le meme produit avec des mots entierement differents.

    Le descriptif ne doit donc pas mesurer une RESSEMBLANCE mais detecter
    une CONTRADICTION : si l'un dit 45x45 et l'autre 60x120, ce ne sont
    pas les memes articles -- meme si aucun mot ne se ressemble.
    """
    import itertools as it

    v, pos, neg = pd.read_pickle("/tmp/jeu.pkl")
    dispo = dict(GARDES)

    print()
    print("=" * 74)
    print("RECHERCHE DE LA MEILLEURE COMBINAISON")
    print("=" * 74)
    print("  On exige un rappel >= 70 % : en dessous, l'outil rate trop de")
    print("  vrais doublons pour etre utile.\n")

    resultats = []
    noms = list(dispo)
    for taille in range(1, len(noms) + 1):
        for combi in it.combinations(noms, taille):
            gardes = [(n, dispo[n]) for n in combi]
            vp, fp = evalue(v, pos, neg, gardes)
            rappel = 100 * vp / len(pos)
            elimine = 100 * (1 - fp / len(neg))
            if rappel >= 70:
                resultats.append((elimine, rappel, vp, fp, combi))

    resultats.sort(key=lambda x: (-x[0], -x[1]))
    print("  elimine  rappel  retenus  confus.  combinaison")
    print("  -------  ------  -------  -------  -----------")
    for elim, rap, vp, fp, combi in resultats[:8]:
        print(f"  {elim:6.1f}%  {rap:5.0f}%  {vp:7}  {fp:7}  "
              f"{' + '.join(c.split(' (')[0] for c in combi)}")

    if resultats:
        elim, rap, vp, fp, combi = resultats[0]
        print()
        print("=" * 74)
        print("COMBINAISON RETENUE")
        print("=" * 74)
        for c in combi:
            print(f"    - {c}")
        print(f"\n  Elimine {elim:.1f} % des confusions "
              f"({len(neg):,} -> {fp}) en conservant {rap:.0f} % des vrais "
              f"doublons.")
        print(f"\n  Lecture honnete : il reste {fp} confusions pour {vp} vrais")
        print(f"  doublons. Le rapprochement AUTOMATIQUE reste donc exclu --")
        print(f"  ces mesures servent a PROPOSER un candidat a valider, pas a")
        print(f"  decider seul.")


recherche_combinaison()
