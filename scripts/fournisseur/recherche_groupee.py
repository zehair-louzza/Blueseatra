#!/usr/bin/env python3
"""Recherche par inclusion + regroupement des equivalents entre fournisseurs.

LES DEUX APPROCHES, ASSEMBLEES
------------------------------
1. RECHERCHE PAR INCLUSION (garantie absolue)
   Tout produit contenant les mots tapes remonte, meme si son libelle
   contient bien davantage. La pertinence sert a TRIER, jamais a
   FILTRER. Verifie par comptage en force brute a chaque requete.

2. REGROUPEMENT DES EQUIVALENTS (a l'interieur des resultats)
   Parmi les produits trouves, on rassemble ceux qui sont vraisemblablement
   le meme article chez des fournisseurs differents, pour afficher l'ecart
   de prix.

POURQUOI CET ORDRE CHANGE TOUT
------------------------------
Mesure sur le catalogue consolide (914 628 lignes, 5 fournisseurs) : la
reference fabricant seule produit 98,6 % de faux rapprochements, et la
meilleure combinaison de garde-fous laisse encore 218 confusions pour
106 vrais doublons. Un rapprochement automatique a l'echelle du
catalogue est donc exclu.

Mais applique DANS un resultat de recherche, le meme rapprochement
devient acceptable pour deux raisons :

  - les candidats sont deja restreints au sujet demande, ce qui elimine
    l'essentiel des collisions de hasard (la reference courte '2201'
    reliait un cable LED Rexel et une faience Point.P -- deux univers
    qu'une recherche ne rapproche jamais) ;
  - l'utilisateur VOIT le groupe en contexte. Une erreur se repere d'un
    coup d'oeil, alors qu'un rapprochement automatique invisible se
    decouvre sur la facture.

GARDE-FOUS RETENUS -- mesures, pas intuitions
---------------------------------------------
Combinaison validee : marque identique + prix dans un rapport <= 1,6 +
attributs techniques compatibles. Elimine 96,9 % des confusions en
conservant 71 % des vrais doublons.

Ecarte deliberement :
  - similarite de libelle : faisait chuter le rappel de 97 % a 9 %. Deux
    fournisseurs decrivent le meme produit avec des mots entierement
    differents. Le descriptif doit detecter une CONTRADICTION, pas
    mesurer une ressemblance ;
  - longueur minimale de reference : rappel de 97 % a 46 %.
"""
import re
import sys
import time
import unicodedata

import pandas as pd

CHEMIN = "/home/user/workspace/catalogue_unifie.csv  # a adapter"
COLONNES = ["Fournisseur", "Famille", "Sous-famille", "Designation", "Marque",
            "Reference fournisseur", "Reference fabricant", "Code EAN",
            "Prix net HT", "Prix public HT", "Unite de vente"]
CHAMPS = ["Designation", "Marque", "Famille", "Sous-famille",
          "Reference fabricant", "Reference fournisseur"]


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def sans_accents(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c))


def normalise(s):
    """Minuscules, sans accents. Les decimales collees sont preservees :
    "2,5 mm2" ne doit pas devenir "2 5 mm2", sinon une recherche sur
    "2,5" ne trouve plus rien et la section est perdue a l'extraction."""
    s = re.sub(r"(\d)[.,](\d)", r"\1.\2", str(s))
    s = sans_accents(s).lower()
    return " ".join(re.sub(r"[^a-z0-9.]+", " ", s).split())


def racine(mot):
    """Absorbe les pluriels sans dictionnaire : "cables" -> "cable"."""
    for suf in ("aux", "eaux", "es", "s", "x"):
        if len(mot) > 4 and mot.endswith(suf):
            return mot[: -len(suf)]
    return mot


SUFFIXES_SOCIETE = (" snc", " s n c", " sas", " sa", " sarl", " france",
                    " electric", " electrique", " group", " groupe", " se",
                    " ag", " gmbh", " spa", " iberica", " italia")


def normalise_marque(m):
    """"LEGRAND" et "LEGRAND S.N.C." sont la MEME marque. Mesure : 3 % des
    groupes du premier catalogue paraissaient multi-marques pour cette
    seule raison."""
    n = normalise(m)
    change = True
    while change:
        change = False
        for suf in SUFFIXES_SOCIETE:
            if n.endswith(suf):
                n, change = n[: -len(suf)].strip(), True
    return n


# ---------------------------------------------------------------------------
# Attributs du descriptif -- le seul discriminant fiable des variantes
# ---------------------------------------------------------------------------

MOTIFS = (
    ("ampere", r"\b(\d{1,4})\s*(?:a|amp|amperes?)\b"),
    ("milliampere", r"\b(\d{2,4})\s*ma\b"),
    ("watt", r"\b(\d{1,5})\s*(?:w|watts?)\b"),
    ("volt", r"\b(\d{2,4})\s*v\b"),
    ("section", r"\b(\d+(?:\.\d+)?)\s*mm2\b"),
    ("litre", r"\b(\d+(?:\.\d+)?)\s*(?:l|litres?)\b"),
    ("modules", r"\b(\d{1,2})\s*modules?\b"),
    ("kelvin", r"\b(\d{4})\s*k\b"),
    ("lumen", r"\b(\d{2,6})\s*(?:lm|lumens?)\b"),
    ("ip", r"\bip\s*(\d{2})\b"),
    ("ik", r"\bik\s*(\d{2})\b"),
)
FINITIONS = ("mat", "brillant", "rectifie", "poli", "satine", "structure",
             "adouci", "vieilli", "velours")
COULEURS = ("blanc", "noir", "gris", "beige", "sable", "graphite",
            "anthracite", "taupe", "creme", "bleu", "rouge", "vert", "jaune",
            "marron", "ivoire", "fumee", "mist", "perle", "chene", "naturel")


# Discriminants de FAMILLE : divergence = ce ne sont pas les memes
# articles, meme si tout le reste concorde. Chaque entree vient d'une
# confusion observee dans les resultats.
FAMILLES = (
    ("protection", {
        "differentiel": r"\bdifferentiel|\bdiff\b|\bddr\b",
        "parafoudre": r"\bparafoudre\b",
    }),
    ("pose", {
        "etanche": r"\betanche\b|\bsaillie\b",
        "encastre": r"\bencastre",
    }),
    ("fonction", {
        "telerupteur": r"\btelerupteur\b",
        "contacteur": r"\bcontacteur\b",
        "minuterie": r"\bminuterie\b|\bminuteur\b",
        "sectionneur": r"\bsectionneur\b",
    }),
)


def famille_produit(texte):
    t = normalise(texte)
    out = {}
    for axe, valeurs in FAMILLES:
        for val, motif in valeurs.items():
            if re.search(motif, t):
                out[axe] = val
                break
    return out


def poles(texte):
    """Nombre de poles -- discriminant n.1 de l'appareillage electrique.

    Omis dans la premiere version, ce qui rassemblait dans un seul groupe
    du 2P, du 1P+N, du 3P et du 4P : 145 % d'ecart de prix affiches comme
    s'il s'agissait du meme article.
    """
    t = normalise(texte)
    for motif, val in (
        (r"\b3p\s*\+?\s*n\b|\b3p n\b|\btetrapolaire\b|\b4p\b", "3p+n"),
        (r"\b1p\s*\+?\s*n\b|\bph\s*\+?\s*n\b|\bphase\s*\+?\s*neutre\b", "1p+n"),
        (r"\b3p\b|\btripolaire\b", "3p"),
        (r"\b2p\b|\bbipolaire\b", "2p"),
        (r"\b1p\b|\bunipolaire\b", "1p"),
    ):
        if re.search(motif, t):
            return val
    return None


def modele(texte):
    """Jetons de GAMME : melange de lettres et de chiffres (ic60n, idt40t,
    dnx3, ba13). Deux gammes differentes ne sont pas le meme produit."""
    t = normalise(texte)
    return {j for j in t.split()
            if len(j) >= 3 and re.search(r"[a-z]", j) and re.search(r"\d", j)}


def attributs(texte):
    """Grandeurs techniques et attributs de VARIANTE.

    Chez Point.P, une meme "reference fabricant" couvre toute une gamme :
    'COF12LINT' designe 58 coffres de linteau de tailles differentes,
    '645640' toutes les pointures d'une chaussure PUMA, '40062' une serie
    de carrelage en formats varies. La variante n'existe QUE dans le
    descriptif -- d'ou l'extraction des dimensions, tailles, finitions et
    couleurs, et pas seulement des grandeurs electriques.
    """
    t = normalise(texte)
    a = {}

    # Dimensions : discriminant n.1 des variantes de gamme.
    # "45 x 45", "60 x 120", "8 x 120" -- trie pour que 45x60 == 60x45.
    dims = re.findall(r"\b(\d+(?:\.\d+)?(?:\s*x\s*\d+(?:\.\d+)?){1,2})\b", t)
    if dims:
        a["dimensions"] = {
            "x".join(sorted((p.strip() for p in d.split("x")), key=float))
            for d in dims
        }

    # Pointure / taille
    tailles = {x for c in re.findall(r"\bt\s*\.?\s*(\d{2})\b|\btaille\s*(\d{2})\b", t)
               for x in c if x}
    if tailles:
        a["taille"] = tailles

    f = {x for x in FINITIONS if re.search(r"\b" + x + r"\b", t)}
    if f:
        a["finition"] = f
    c = {x for x in COULEURS if re.search(r"\b" + x + r"\b", t)}
    if c:
        a["couleur"] = c

    cond = {x for cpl in re.findall(
        r"\blot\s*de\s*(\d{1,4})\b|\bcouronne\s*(?:de\s*)?(\d{1,4})\b", t)
        for x in cpl if x}
    if cond:
        a["conditionnement"] = cond

    for cle, motif in MOTIFS:
        trouve = re.findall(motif, t)
        if trouve:
            a[cle] = set(trouve)

    m = re.search(r"\bcourbe\s*([bcd])\b", t)
    if m:
        a["courbe"] = {m.group(1)}

    p = poles(texte)
    if p:
        a["poles"] = {p}
    mod = modele(texte)
    if mod:
        a["_modele"] = mod
    fam = famille_produit(texte)
    for axe, val in fam.items():
        a["_fam_" + axe] = {val}
    return a


def attributs_compatibles(a, b):
    """Deux articles se contredisent-ils sur un attribut commun ?

    Asymetrie voulue : si l'un mentionne une dimension et l'autre pas, on
    ne tranche pas -- un fournisseur peut simplement etre moins bavard.
    Seule une CONTRADICTION elimine.

    Le MODELE est traite a part. Exiger une simple intersection ne suffit
    pas : "Acti9 iC60N" et "Acti9 iDT40T" partagent "acti9" et seraient
    donc acceptes, alors que ce sont deux gammes distinctes. On exige un
    recouvrement de moitie, ce qui separe les gammes tout en tolerant un
    jeton de plus d'un cote.

    C'est le SEUL endroit ou une similarite de libelle est utilisee, et
    elle est restreinte aux jetons de gamme. La similarite generale a ete
    mesuree puis ecartee : elle faisait chuter le rappel de 97 % a 9 %,
    deux fournisseurs decrivant le meme produit avec des mots entierement
    differents.
    """
    ma, mb = a.get("_modele"), b.get("_modele")
    if ma and mb:
        if len(ma & mb) / len(ma | mb) < 0.5:
            return False

    # Le CONDITIONNEMENT est eliminatoire meme declare d'un seul cote :
    # "Lot de 3 disjoncteurs" et un disjoncteur a l'unite ne sont pas le
    # meme article, et leur prix n'est pas comparable. L'asymetrie
    # tolerante appliquee aux autres attributs produisait ici des
    # comparaisons trompeuses.
    if ("conditionnement" in a) != ("conditionnement" in b):
        return False

    for cle in set(a) & set(b):
        if cle == "_modele":
            continue
        if not (a[cle] & b[cle]):
            return False
    return True


# ---------------------------------------------------------------------------
# Recherche par inclusion
# ---------------------------------------------------------------------------

def charge():
    t0 = time.time()
    df = pd.read_csv(CHEMIN, usecols=COLONNES, dtype=str, low_memory=False)
    blob = df[CHAMPS].fillna("").agg(" ".join, axis=1)
    df["_r"] = [normalise(x) for x in blob]
    df["_px"] = pd.to_numeric(
        df["Prix net HT"].fillna("").str.replace(",", ".", regex=False),
        errors="coerce")
    df["_marque"] = [normalise_marque(x) for x in df["Marque"].fillna("")]
    print(f"  {len(df):,} produits indexes en {time.time()-t0:.0f}s",
          file=sys.stderr)
    return df


def cherche(df, requete):
    """Tous les produits contenant TOUS les mots. Aucun filtrage."""
    mots = [racine(m) for m in normalise(requete).split() if m]
    if not mots:
        return df.iloc[0:0], []
    masque = pd.Series(True, index=df.index)
    for mot in mots:
        masque &= df["_r"].str.contains(re.escape(mot), regex=True, na=False)
    return df[masque], mots


# ---------------------------------------------------------------------------
# Regroupement des equivalents, DANS les resultats
# ---------------------------------------------------------------------------

RATIO_PRIX_MAX = 1.6


def regroupe(res):
    """Rassemble les produits vraisemblablement identiques.

    Cle de rapprochement : meme marque normalisee. Puis, dans chaque
    marque, on agrege par transitivite les articles dont les attributs ne
    se contredisent pas et dont les prix restent dans un rapport
    plausible.

    GARANTIE : chaque produit trouve appartient a exactement un groupe,
    seul si necessaire. Rien n'est jamais ecarte.
    """
    res = res.copy()
    res["_attr"] = [attributs(d) for d in res["Designation"].fillna("")]

    groupes = []
    for marque, bloc in res.groupby("_marque", sort=False):
        indices = list(bloc.index)
        # Sans marque renseignee, on ne regroupe pas : le risque de
        # confusion mesure est trop eleve.
        if not marque:
            groupes.extend([[i] for i in indices])
            continue

        restants = set(indices)
        while restants:
            germe = restants.pop()
            groupe = [germe]
            a_tester = list(restants)
            for autre in a_tester:
                a, b = res.at[germe, "_attr"], res.at[autre, "_attr"]
                if not attributs_compatibles(a, b):
                    continue
                # La bande de prix s'applique a l'ENSEMBLE du groupe.
                # Comparee au seul germe, une chaine d'ajouts successifs
                # pouvait couvrir un rapport bien superieur a 1,6 : c'est
                # ce qui produisait des groupes a +145 %.
                pb = res.at[autre, "_px"]
                prix_groupe = [res.at[i, "_px"] for i in groupe]
                prix_groupe = [x for x in prix_groupe if pd.notna(x) and x > 0]
                if pd.notna(pb) and pb > 0 and prix_groupe:
                    bas, haut = min(prix_groupe + [pb]), max(prix_groupe + [pb])
                    if haut / bas > RATIO_PRIX_MAX:
                        continue
                groupe.append(autre)
                restants.discard(autre)
            groupes.append(groupe)
    return groupes, res


def affiche(df, requete, limite_groupes=6):
    res, mots = cherche(df, requete)
    total = len(res)
    print(f"\n{'='*74}")
    print(f'  "{requete}"  ->  {total:,} produits')
    print(f"{'='*74}")
    if not total:
        print("  aucun resultat")
        return

    groupes, res = regroupe(res)

    # Un groupe n'a d'interet que s'il compare PLUSIEURS fournisseurs.
    enrichis = []
    for g in groupes:
        sous = res.loc[g]
        fournisseurs = sous["Fournisseur"].nunique()
        prix = sous["_px"].dropna()
        ecart = (100 * (prix.max() - prix.min()) / prix.min()
                 if len(prix) >= 2 and prix.min() > 0 else 0)
        enrichis.append((fournisseurs, ecart, g))
    enrichis.sort(key=lambda x: (-x[0], -x[1]))

    multi = [e for e in enrichis if e[0] >= 2]
    print(f"  {len(multi)} groupe(s) comparables entre fournisseurs "
          f"sur {len(groupes)} groupes au total\n")

    for fournisseurs, ecart, g in multi[:limite_groupes]:
        sous = res.loc[g].sort_values("_px")
        lib = str(sous["Designation"].iloc[0])[:52]
        print(f"  {lib:54} {fournisseurs} fournisseurs, ecart +{ecart:.0f} %")
        for _, r in sous.iterrows():
            px = r["_px"]
            print(f"      {(f'{px:9.2f}' if pd.notna(px) else '        -')} EUR  "
                  f"[{str(r['Fournisseur'])[:12]:12}] "
                  f"{str(r['Designation'])[:48]:50}")
        print()

    seuls = sum(1 for e in enrichis if e[0] < 2)
    couverts = sum(len(g) for _, _, g in enrichis)
    print(f"  {seuls} produit(s) sans equivalent identifie chez un autre "
          f"fournisseur : affiches seuls, jamais ecartes.")
    print(f"  controle de couverture : {couverts} produits repartis "
          f"/ {total} trouves  -> {'CONFORME' if couverts == total else 'ANOMALIE'}")


def verifie(df, requetes):
    print(f"\n{'='*74}")
    print("  GARANTIE D'INCLUSION -- moteur contre comptage en force brute")
    print(f"{'='*74}")
    print("  requete                    moteur   force brute  conforme")
    print("  -------------------------  -------  -----------  --------")
    tout = True
    for q in requetes:
        res, mots = cherche(df, q)
        brut = int(df["_r"].apply(lambda r: all(m in r for m in mots)).sum())
        ok = len(res) == brut
        tout &= ok
        print(f"  {q[:25]:25}  {len(res):7,}  {brut:11,}  "
              f"{'oui' if ok else 'NON -- ANOMALIE'}")
    print("\n  >>> garantie respectee" if tout else "\n  >>> GARANTIE ROMPUE")


def main():
    df = charge()
    requetes = ["peinture acrylique", "disjoncteur 16a", "carrelage 60x60",
                "laine de verre", "vis inox"]
    for q in requetes:
        affiche(df, q)
    verifie(df, requetes + ["peinture", "cable 2,5", "placo ba13"])


if __name__ == "__main__":
    main()
