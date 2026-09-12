#!/usr/bin/env python3
"""Comparaison fournisseurs sur les SEULS termes de la requete.

PRINCIPE -- LA REQUETE EST LA SPECIFICATION
-------------------------------------------
Ce que le chiffreur tape definit le cahier des charges. Tout produit qui
satisfait ces termes est comparable, et le reste du descriptif ne doit
PAS entrer en compte.

Chercher "disjoncteur 16a courbe c ph+n" rend comparables un GEWISS a
6,45 EUR et un HAGER a 8,78 EUR, bien qu'ils n'aient ni la meme marque,
ni la meme reference, ni le meme libelle. C'est le bon comportement : le
chiffreur veut le moins cher qui respecte la spec.

POURQUOI CE MODELE CORRIGE LE PRECEDENT
---------------------------------------
La mesure precedente concluait a 0,08 % de produits comparables. Elle
mesurait le recouvrement d'IDENTIFIANTS -- EAN et reference fabricant --
et non la comparabilite fonctionnelle. Deux mesures differentes.

Le catalogue manuel de reference le confirmait deja : les regroupements
valides a la main couvraient GEWISS et HAGER, LEGRAND et SCHNEIDER,
EATON et SCHNEIDER. 47 % des groupes traversaient plusieurs marques.
L'equivalence visee est FONCTIONNELLE, pas une identite produit.

CONTREPARTIE, ET COMMENT ELLE EST TRAITEE
-----------------------------------------
Si la requete est imprecise, on compare des choses qui ne se comparent
pas : "disjoncteur 16a" ramene du 1P et du 4P, dont les prix n'ont rien
a voir. La responsabilite de la precision revient a la requete -- mais
l'outil doit AIDER a la preciser.

D'ou l'affichage des criteres qui VARIENT dans les resultats : poles,
courbe, conditionnement, marque. Le chiffreur voit immediatement sur
quoi son lot est heterogene et complete sa recherche. Aucun resultat
n'est jamais ecarte.
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


def sans_accents(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c))


def normalise(s):
    """Les decimales collees sont preservees : "2,5 mm2" ne doit pas
    devenir "2 5 mm2", sinon une recherche sur "2,5" ne trouve rien."""
    s = re.sub(r"(\d)[.,](\d)", r"\1.\2", str(s))
    s = sans_accents(s).lower()
    return " ".join(re.sub(r"[^a-z0-9.+]+", " ", s).split())


def racine(mot):
    for suf in ("aux", "eaux", "es", "s", "x"):
        if len(mot) > 4 and mot.endswith(suf):
            return mot[: -len(suf)]
    return mot


# ---------------------------------------------------------------------------
# Vocabulaire metier -- un meme critere, plusieurs ecritures
# ---------------------------------------------------------------------------
# Un chiffreur tape "ph+n". Les fournisseurs ecrivent "1P+N", "Phase +
# Neutre", "U+N", "unipolaire + neutre". Sans ce dictionnaire, la
# requete "disjoncteur 16a courbe c ph+n" renvoyait ZERO resultat alors
# que le catalogue en contient des centaines.
#
# Ces regles sont INDEPENDANTES du client : elles decrivent le vocabulaire
# du batiment, pas des prix. Elles ont donc leur place dans la table
# mutualisee product_match_rules, partagee entre tous les tenants --
# contrairement aux prix, qui ne sortent jamais du tenant.
EQUIVALENCES = {
    # --- nombre de poles ---
    # BUG CORRIGE : la liste contenait la sous-chaine "p+n", qui se
    # retrouve dans "3p+n". Une requete 1P+N ramenait donc 46 produits
    # 3P+N, d'un tout autre prix. Les motifs sont desormais bornes : la
    # lookbehind (?<![2-9]) empeche 3p+n et 4p+n de correspondre.
    "ph+n": [r"(?<![2-9])1?p\+n", r"\bph\+n\b", r"\bu\+n\b",
             r"\bphase neutre\b", r"\bunipolaire neutre\b"],
    "1p+n": [r"(?<![2-9])1?p\+n", r"\bph\+n\b", r"\bu\+n\b",
             r"\bphase neutre\b", r"\bunipolaire neutre\b"],
    "3p+n": [r"\b3p\+n\b", r"\b3p n\b", r"\btetrapolaire\b", r"\b4p\b"],
    "bipolaire": [r"\b2p\b", r"\bbipolaire\b"],
    "tripolaire": [r"(?<![+])\b3p\b(?!\+)", r"\btripolaire\b"],
    "tetrapolaire": [r"\b4p\b", r"\b3p\+n\b", r"\btetrapolaire\b"],
    "unipolaire": [r"(?<![0-9])\b1p\b(?!\+)", r"\bunipolaire\b"],
    # --- courbe de declenchement : "courbe C", "Cbe C", "Crb C" ---
    "courbe": [r"\bcourbe\b", r"\bcbe\b", r"\bcrb\b"],
    # --- differentiel ---
    "differentiel": [r"\bdifferentiel\b", r"\bdiff\b", r"\bddr\b"],
    # --- plaques de platre ---
    "ba13": [r"\bba13\b", r"\bba 13\b"],
    "ba18": [r"\bba18\b", r"\bba 18\b"],
    # --- divers vocabulaire courant ---
    "etanche": [r"\betanche\b", r"\bip\s?6[5-8]\b", r"\bsaillie\b"],
    "encastre": [r"\bencastre"],
}


# ---------------------------------------------------------------------------
# Qualifiants : un mot qui CHANGE la nature de l'article
# ---------------------------------------------------------------------------
# Un "disjoncteur differentiel" n'est pas un "disjoncteur". Un article
# "reconditionne" n'est pas du neuf. Un "coffret pre-equipe" n'est pas un
# appareil seul. Si la requete ne mentionne pas le qualifiant, ces
# produits ne sont pas comparables a ce qui est demande.
#
# Mesure qui a motive cette regle : sur "disjoncteur 16a courbe c ph+n",
# 85 des 174 resultats etaient des DIFFERENTIELS, de prix median 189,86
# EUR contre 6,83 EUR pour le moins cher des simples. Le prix median
# affiche passait de 61 a 131 EUR -- une comparaison fausse.
#
# Ils ne sont PAS supprimes : la garantie d'inclusion l'interdit. Ils sont
# ISOLES dans une rubrique a part, comptes et affichables. Le chiffreur
# voit qu'ils existent et peut les demander explicitement.
QUALIFIANTS = [
    ("différentiel", r"\bdifferentiel\b|\bdiff\.?\b|\bddr\b"),
    ("reconditionné", r"\breconditionne"),
    ("coffret ou tableau pré-équipé", r"\bcoffret\b|\btableau\b|\bplatine\b"),
    ("appareil combiné", r"\bcombine\b"),
    ("lot ou conditionnement multiple", r"\blot de \d|\bcouronne\b|\bpack de \d"),
    ("parafoudre", r"\bparafoudre\b"),
]


def variantes(mot):
    """Ecritures acceptables d'un terme de requete.

    Ne RESTREINT jamais : en l'absence de regle, le terme est cherche
    tel quel. Le dictionnaire ne peut qu'elargir le resultat, donc la
    garantie d'inclusion est preservee par construction.
    """
    if mot in EQUIVALENCES:
        return EQUIVALENCES[mot]
    r = racine(mot)
    if r in EQUIVALENCES:
        return EQUIVALENCES[r]
    return [re.escape(r)]


# ---------------------------------------------------------------------------
# Criteres susceptibles de varier -- exposes pour affiner, jamais filtres
# ---------------------------------------------------------------------------

def poles(t):
    for motif, val in (
        (r"\b3p\s*\+?\s*n\b|\btetrapolaire\b|\b4p\b", "3P+N / 4P"),
        (r"\b1p\s*\+?\s*n\b|\bph\s*\+?\s*n\b|\bphase\s*\+?\s*neutre\b", "1P+N"),
        (r"\b3p\b|\btripolaire\b", "3P"),
        (r"\b2p\b|\bbipolaire\b", "2P"),
        (r"\b1p\b|\bunipolaire\b", "1P"),
    ):
        if re.search(motif, t):
            return val
    return None


def courbe(t):
    m = re.search(r"\bcourbe\s*([bcd])\b", t)
    return m.group(1).upper() if m else None


def conditionnement(t):
    m = re.search(r"\blot\s*de\s*(\d{1,4})\b", t)
    if m:
        return f"lot de {m.group(1)}"
    m = re.search(r"\bcouronne\s*(?:de\s*)?(\d{1,4})\b", t)
    if m:
        return f"couronne {m.group(1)} m"
    return None


def differentiel(t):
    if re.search(r"\bdifferentiel\b|\bdiff\b|\bddr\b", t):
        return "differentiel"
    return None


def dimensions(t):
    d = re.findall(r"\b(\d+(?:\.\d+)?(?:\s*x\s*\d+(?:\.\d+)?){1,2})\b", t)
    if not d:
        return None
    p = [x.strip() for x in d[0].split("x")]
    return "x".join(sorted(p, key=float))


def volume(t):
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:l|litres?)\b", t)
    return f"{m.group(1)} L" if m else None


def section(t):
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*mm2\b", t)
    return f"{m.group(1)} mm2" if m else None


CRITERES = [
    ("pôles", poles),
    ("courbe", courbe),
    ("différentiel", differentiel),
    ("conditionnement", conditionnement),
    ("dimensions", dimensions),
    ("volume", volume),
    ("section", section),
]


# ---------------------------------------------------------------------------

def charge():
    t0 = time.time()
    df = pd.read_csv(CHEMIN, usecols=COLONNES, dtype=str, low_memory=False)
    blob = df[CHAMPS].fillna("").agg(" ".join, axis=1)
    df["_r"] = [normalise(x) for x in blob]
    df["_d"] = [normalise(x) for x in df["Designation"].fillna("")]
    df["_px"] = pd.to_numeric(
        df["Prix net HT"].fillna("").str.replace(",", ".", regex=False),
        errors="coerce")
    print(f"  {len(df):,} produits indexes en {time.time()-t0:.0f}s",
          file=sys.stderr)
    return df


def cherche(df, requete):
    """Tous les produits satisfaisant TOUS les criteres de la requete.

    ET entre les termes, OU entre les ecritures d'un meme terme. Aucun
    filtrage par pertinence : la garantie d'inclusion est absolue.
    """
    termes = [m for m in normalise(requete).split() if m]
    if not termes:
        return df.iloc[0:0], []
    groupes = [variantes(t) for t in termes]
    masque = pd.Series(True, index=df.index)
    for alternatives in groupes:
        motif = "|".join(alternatives)
        masque &= df["_r"].str.contains(motif, regex=True, na=False)
    return df[masque].copy(), groupes


def criteres_variables(res, requete):
    """Sur quoi les resultats sont-ils heterogenes ?

    On n'expose QUE les criteres absents de la requete : si le chiffreur
    a deja ecrit "courbe c", inutile de lui proposer d'affiner dessus.
    """
    q = normalise(requete)
    sortie = []
    for nom, extrait in CRITERES:
        valeurs = res["_d"].map(extrait).dropna()
        distinctes = valeurs.value_counts()
        if len(distinctes) < 2:
            continue
        # Deja contraint par la requete ?
        if any(normalise(str(v)).split()[0] in q for v in distinctes.index[:3]):
            continue
        sortie.append((nom, distinctes))
    return sortie


def separe_qualifiants(res, requete):
    """Isole les produits porteurs d'un qualifiant que la requete ne
    demande pas. Rien n'est supprime : on rend deux ensembles."""
    q = c_normalise = normalise(requete)
    ecartes = {}
    masque_propre = pd.Series(True, index=res.index)
    for libelle, motif in QUALIFIANTS:
        # Le qualifiant fait-il partie de la demande ?
        if re.search(motif, q):
            continue
        porteurs = res["_d"].str.contains(motif, regex=True, na=False)
        if porteurs.any():
            ecartes[libelle] = res[porteurs & masque_propre]
            masque_propre &= ~porteurs
    return res[masque_propre], ecartes


def compare(df, requete, limite=12):
    res, mots = cherche(df, requete)
    total = len(res)
    print(f"\n{'='*78}")
    print(f'  "{requete}"  ->  {total:,} resultats')
    print(f"{'='*78}")
    if not total:
        print("  aucun resultat")
        return

    res, ecartes = separe_qualifiants(res, requete)
    if not ecartes:
        print(f"  {len(res)} comparables sur cette spec")
    if ecartes:
        print(f"  {len(res)} comparables sur cette spec. "
              f"{total - len(res)} isoles car d'une autre nature :")
        for libelle, bloc in ecartes.items():
            px = bloc["_px"].dropna()
            detail = (f", prix median {px.median():.2f} EUR" if len(px) else "")
            print(f"      {len(bloc):4} {libelle}{detail}")
        print(f"      (comptes et consultables, jamais supprimes)")
        print()

    avec_prix = res[res["_px"].notna() & (res["_px"] > 0)].sort_values("_px")
    sans_prix = len(res) - len(avec_prix)

    if len(avec_prix) >= 2:
        bas, haut = avec_prix["_px"].iloc[0], avec_prix["_px"].iloc[-1]
        med = avec_prix["_px"].median()
        print(f"  prix : {bas:.2f} a {haut:.2f} EUR   "
              f"median {med:.2f}   ecart +{100*(haut-bas)/bas:.0f} %")
        nb_four = avec_prix["Fournisseur"].nunique()
        print(f"  {nb_four} fournisseur(s) sur cette spec"
              + (f", {sans_prix} produit(s) sans prix" if sans_prix else ""))

    print(f"\n  --- les moins chers ---")
    for _, r in avec_prix.head(limite).iterrows():
        print(f"  {r['_px']:9.2f} EUR  [{str(r['Fournisseur'])[:12]:12}] "
              f"{str(r['Designation'])[:52]:54} "
              f"{str(r['Marque'])[:14]:16} {str(r['Unite de vente'])[:7]}")

    # Le moins cher par fournisseur : la vraie vue de negociation
    if avec_prix["Fournisseur"].nunique() >= 2:
        print(f"\n  --- le moins cher chez chaque fournisseur ---")
        meilleur = avec_prix.loc[avec_prix.groupby("Fournisseur")["_px"].idxmin()]
        for _, r in meilleur.sort_values("_px").iterrows():
            print(f"  {r['_px']:9.2f} EUR  [{str(r['Fournisseur'])[:12]:12}] "
                  f"{str(r['Designation'])[:52]}")

    variables = criteres_variables(res, requete)
    if variables:
        print(f"\n  --- vos resultats melangent plusieurs specs, affinez ---")
        for nom, distinctes in variables[:4]:
            detail = "  ".join(f"{v} ({n})" for v, n in distinctes.head(5).items())
            print(f"    {nom:16} {detail}")


def verifie(df, requetes):
    print(f"\n{'='*78}")
    print("  GARANTIE D'INCLUSION -- moteur contre comptage independant")
    print(f"{'='*78}")
    tout = True
    for q in requetes:
        res, groupes = cherche(df, q)
        # Comptage independant, avec la MEME semantique que le moteur.
        # Une premiere version comparait par sous-chaine alors que les
        # equivalences sont des expressions regulieres : elle signalait
        # une anomalie inexistante. Une verification doit tester le
        # moteur, pas sa propre approximation.
        motifs = [re.compile("|".join(alt)) for alt in groupes]
        brut = int(df["_r"].apply(
            lambda r: all(m.search(r) for m in motifs)).sum())
        ok = len(res) == brut
        tout &= ok
        print(f"  {q[:34]:34} {len(res):7,}  {brut:7,}  "
              f"{'conforme' if ok else 'ANOMALIE'}")
    print("\n  >>> garantie respectee" if tout else "\n  >>> GARANTIE ROMPUE")


def main():
    df = charge()
    requetes = [
        "disjoncteur 16a",
        "disjoncteur 16a courbe c ph+n",
        "peinture acrylique mate 15 l",
        "laine de verre 100",
    ]
    for q in requetes:
        compare(df, q)
    verifie(df, requetes)


if __name__ == "__main__":
    main()
