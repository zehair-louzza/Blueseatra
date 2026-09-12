#!/usr/bin/env python3
"""LOT 0 -- mesure du taux de rapprochement automatique reel.

Vraie tache metier mesuree ici : le client possede un catalogue d'articles
canoniques ("Disjoncteur ph+N 10 A courbe C"). Il recoit un tarif
fournisseur dont chaque ligne est une designation en texte libre
("HAGER Disjoncteur Phase + Neutre 10A 3kA Courbe C bornes a vis"). Pour
chaque ligne fournisseur, il faut retrouver A QUEL article canonique elle
correspond.

C'est une CLASSIFICATION, pas un regroupement : le referentiel existe
deja. C'est exactement ce que fait matching.py pour demande -> catalogue.

VERITE TERRAIN : les 1002 offres du catalogue reel, chacune deja
rattachee a la main par l'utilisateur a l'un des 397 articles. On rejoue
donc l'algorithme a l'aveugle et on compare a sa decision.
"""
import json
import re
import sys
import unicodedata
from collections import Counter

# --- normalisation, reprise de la logique de matching.py -----------------

def normalise(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


# Variantes de raison sociale : c'est la MEME marque. Destine a alimenter
# la table mutualisee product_match_rules.
SUFFIXES_SOCIETE = (
    " snc", " s n c", " sas", " sa", " sarl", " france", " electric",
    " electrique", " group", " groupe", " se", " ag", " gmbh", " spa",
)


def normalise_marque(m):
    n = normalise(m)
    if not n:
        return ""
    change = True
    while change:
        change = False
        for suf in SUFFIXES_SOCIETE:
            if n.endswith(suf):
                n = n[: -len(suf)].strip()
                change = True
    return n


# --- extraction d'attributs techniques ----------------------------------
# Le coeur du probleme : l'equivalence est fonctionnelle, donc il faut
# comparer des CARACTERISTIQUES, pas des libelles.

def attributs(texte):
    """Extrait les grandeurs techniques d'une designation en texte libre.

    BUG CORRIGE : normalise() remplace tout non-alphanumerique par une
    espace, donc "2,5 mm2" devenait "2 5 mm2" et la section etait perdue.
    Consequence mesuree : confusion systematique entre fil 1,5 mm2 et
    2,5 mm2 -- deux articles de prix differents. On protege donc les
    separateurs decimaux AVANT de normaliser.
    """
    t = re.sub(r"(\d)[.,](\d)", r"\1DECIMALE\2", str(texte or ""))
    t = normalise(t).replace("decimale", ".")
    a = {}

    # Calibre en amperes : "10 a", "10a", "16 amperes"
    m = re.findall(r"\b(\d{1,4})\s*(?:a|amp|amperes?)\b", t)
    if m:
        a["ampere"] = sorted({int(x) for x in m})

    # Sensibilite differentielle en milliamperes
    m = re.findall(r"\b(\d{2,4})\s*ma\b", t)
    if m:
        a["milliampere"] = sorted({int(x) for x in m})

    # Courbe de declenchement
    m = re.search(r"\bcourbe\s*([bcd])\b", t)
    if m:
        a["courbe"] = m.group(1)

    # Nombre de poles, sous toutes ses ecritures
    if re.search(r"\bph\s*n\b|\bphase\s*neutre\b|\b1p\s*n\b", t):
        a["poles"] = "ph+n"
    elif re.search(r"\btetrapolaire\b|\b4p\b|\b3p\s*n\b", t):
        a["poles"] = "4p"
    elif re.search(r"\btripolaire\b|\b3p\b", t):
        a["poles"] = "3p"
    elif re.search(r"\bbipolaire\b|\b2p\b", t):
        a["poles"] = "2p"
    elif re.search(r"\bunipolaire\b|\b1p\b", t):
        a["poles"] = "1p"

    # Section de cable en mm2
    m = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*mm2?\b", t)
    if m:
        a["section"] = sorted({x.replace(",", ".") for x in m})

    # Dimensions et diametres
    m = re.findall(r"\b(?:diam|diametre|d)\s*(\d{1,3})\b", t)
    if m:
        a["diametre"] = sorted({int(x) for x in m})

    # Puissance
    m = re.findall(r"\b(\d{1,5})\s*(?:w|watts?)\b", t)
    if m:
        a["watt"] = sorted({int(x) for x in m})

    # Tension
    m = re.findall(r"\b(\d{2,4})\s*v\b", t)
    if m:
        a["volt"] = sorted({int(x) for x in m})

    # Volume / contenance
    m = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*(?:l|litres?)\b", t)
    if m:
        a["litre"] = sorted({x.replace(",", ".") for x in m})

    # Nombre de modules
    m = re.findall(r"\b(\d{1,2})\s*modules?\b", t)
    if m:
        a["modules"] = sorted({int(x) for x in m})

    return a


# Discriminants de FAMILLE : deux designations qui divergent sur l'un de
# ces axes ne designent jamais le meme article, meme si leurs libelles se
# ressemblent beaucoup. Chaque entree provient d'un faux positif observe.
DISCRIMINANTS = (
    # (nom de l'axe, {valeur: motif})
    ("protection", {
        "differentiel": r"\bdifferentiel|\bdiff\b|\bddr\b|\bid\b",
        "parafoudre": r"\bparafoudre\b",
    }),
    ("pose", {
        "etanche": r"\betanche|\bip\s*[5-7]\d\b|\bsaillie\b",
        "encastre": r"\bencastre|\bencastrement\b",
    }),
    ("fonction", {
        "minuterie": r"\bminuterie\b|\bminuteur\b",
        "telerupteur": r"\btelerupteur\b",
        "contacteur": r"\bcontacteur\b",
        "interrupteur_sect": r"\binterrupteur\s*sectionneur\b|\bsectionneur\b",
    }),
)


def famille(texte):
    """Position du texte sur chaque axe discriminant, ou None si muet."""
    t = normalise(texte)
    out = {}
    for axe, valeurs in DISCRIMINANTS:
        for val, motif in valeurs.items():
            if re.search(motif, t):
                out[axe] = val
                break
    return out


MOTS_VIDES = {
    "de", "du", "la", "le", "les", "des", "a", "au", "aux", "et", "en",
    "pour", "avec", "sur", "par", "ou", "un", "une", "the", "of",
}


def jetons(texte):
    return {j for j in normalise(texte).split() if j not in MOTS_VIDES and len(j) > 1}


def score(offre, article):
    """Score de correspondance offre -> article canonique. 0 a 100."""
    d_off = offre.get("designation") or ""
    d_art = " ".join(filter(None, [
        article.get("article"), article.get("sous_famille"),
    ]))

    # 0. Famille de produit : divergence = rejet immediat.
    # Un disjoncteur DIFFERENTIEL n'est pas un disjoncteur simple ; une
    # prise ETANCHE n'est pas une prise encastree ; une MINUTERIE n'est
    # pas un telerupteur. Ces confusions representaient la majorite des
    # faux positifs de la premiere mesure.
    f_off, f_art = famille(d_off), famille(d_art)
    for axe in set(f_off) & set(f_art):
        if f_off[axe] != f_art[axe]:
            return 0
    # Asymetrie volontaire : si l'ARTICLE porte un discriminant que
    # l'offre ne mentionne pas, on n'elimine pas -- l'offre peut etre
    # simplement moins bavarde. L'inverse non plus.

    at_off, at_art = attributs(d_off), attributs(d_art)

    # 1. Compatibilite des attributs techniques : critere ELIMINATOIRE.
    # Un 10 A et un 16 A ne sont jamais le meme article, quelle que soit
    # la ressemblance des libelles. C'est ce qui evite les faux positifs.
    communs = set(at_off) & set(at_art)
    for cle in communs:
        v_off, v_art = at_off[cle], at_art[cle]
        if isinstance(v_off, list) and isinstance(v_art, list):
            if not (set(v_off) & set(v_art)):
                return 0
        elif v_off != v_art:
            return 0

    if not communs and (at_art or at_off):
        # L'article porte des attributs que l'offre ne mentionne pas :
        # rapprochement possible mais non confirme.
        bonus_attr = 0
    else:
        bonus_attr = 26 * len(communs)

    # 2. Recouvrement lexical
    j_off, j_art = jetons(d_off), jetons(d_art)
    if not j_art:
        return 0
    recouvrement = len(j_off & j_art) / len(j_art)

    # 3. Marque, si les deux cotes la renseignent
    m_off = normalise_marque(offre.get("marque"))
    m_art = normalise_marque(article.get("marque"))
    bonus_marque = 0
    if m_off and m_art:
        bonus_marque = 12 if m_off == m_art else -6

    return max(0, min(100, 58 * recouvrement + bonus_attr + bonus_marque))


# --- mesure --------------------------------------------------------------

def main():
    d = json.load(open("/home/user/workspace/repo/backend/catalogue_data.json"))
    articles = d["articles"]
    groupes = [a for a in articles if a.get("offers")]

    # Caracterisation : marques normalisees
    vrai_multi, variante, mono, sans = 0, 0, 0, 0
    for a in groupes:
        brutes = {(o.get("marque") or "").strip().upper()
                  for o in a["offers"] if o.get("marque")}
        nettes = {normalise_marque(m) for m in brutes} - {""}
        if not nettes:
            sans += 1
        elif len(nettes) > 1:
            vrai_multi += 1
        elif len(brutes) > 1:
            variante += 1
        else:
            mono += 1

    print("=" * 68)
    print("NATURE DU REGROUPEMENT -- apres normalisation des marques")
    print("=" * 68)
    n = len(groupes)
    print(f"  equivalence FONCTIONNELLE (marques vraiment differentes) : "
          f"{vrai_multi:3} / {n}  ({100*vrai_multi/n:.0f} %)")
    print(f"  meme marque, orthographes differentes                    : "
          f"{variante:3} / {n}  ({100*variante/n:.0f} %)")
    print(f"  une seule marque, ecriture constante                     : "
          f"{mono:3} / {n}  ({100*mono/n:.0f} %)")
    print(f"  aucune marque renseignee                                 : "
          f"{sans:3} / {n}  ({100*sans/n:.0f} %)")

    # Mesure du rapprochement, a l'aveugle
    print()
    print("=" * 68)
    print("RAPPROCHEMENT AUTOMATIQUE -- 1002 offres contre 397 articles")
    print("=" * 68)

    SEUIL_AUTO = 55      # au-dessus : rattachement automatique
    SEUIL_PROPOSE = 32   # entre les deux : proposition a valider

    auto_bon, auto_faux, propose_bon, propose_faux, aucun = 0, 0, 0, 0, 0
    faux_positifs = []
    non_trouves = []

    for vrai in groupes:
        for offre in vrai["offers"]:
            classement = []
            for cand in articles:
                s = score(offre, cand)
                if s > 0:
                    classement.append((s, cand))
            classement.sort(key=lambda x: -x[0])

            if not classement:
                aucun += 1
                if len(non_trouves) < 5:
                    non_trouves.append(
                        (offre.get("designation", "")[:62], vrai["article"][:40]))
                continue

            meilleur_score, meilleur = classement[0]
            juste = meilleur["code"] == vrai["code"]

            if meilleur_score >= SEUIL_AUTO:
                if juste:
                    auto_bon += 1
                else:
                    auto_faux += 1
                    if len(faux_positifs) < 6:
                        faux_positifs.append((
                            offre.get("designation", "")[:56],
                            vrai["article"][:34],
                            meilleur["article"][:34],
                            round(meilleur_score),
                        ))
            elif meilleur_score >= SEUIL_PROPOSE:
                propose_bon += 1 if juste else 0
                propose_faux += 0 if juste else 1
            else:
                aucun += 1
                if len(non_trouves) < 5:
                    non_trouves.append(
                        (offre.get("designation", "")[:62], vrai["article"][:40]))

    total = auto_bon + auto_faux + propose_bon + propose_faux + aucun
    print(f"  total d'offres rejouees : {total}\n")
    print(f"  rattachees AUTOMATIQUEMENT et justes   : {auto_bon:4}  "
          f"({100*auto_bon/total:5.1f} %)")
    print(f"  rattachees automatiquement mais FAUSSES: {auto_faux:4}  "
          f"({100*auto_faux/total:5.1f} %)   <-- le cas grave")
    print(f"  proposees a valider, bonne proposition  : {propose_bon:4}  "
          f"({100*propose_bon/total:5.1f} %)")
    print(f"  proposees a valider, mauvaise           : {propose_faux:4}  "
          f"({100*propose_faux/total:5.1f} %)")
    print(f"  aucun rapprochement                     : {aucun:4}  "
          f"({100*aucun/total:5.1f} %)")

    if auto_bon + auto_faux:
        precision = 100 * auto_bon / (auto_bon + auto_faux)
        print(f"\n  PRECISION du rattachement automatique : {precision:.1f} %")
        print(f"  (part des rattachements automatiques qui sont corrects)")

    if faux_positifs:
        print("\n  --- faux positifs : confusions a corriger ---")
        for des, attendu, obtenu, sc in faux_positifs:
            print(f"    offre    : {des}")
            print(f"      attendu: {attendu}")
            print(f"      obtenu : {obtenu}  (score {sc})")

    if non_trouves:
        print("\n  --- offres non rapprochees ---")
        for des, attendu in non_trouves:
            print(f"    {des}")
            print(f"      -> aurait du etre : {attendu}")


main()


# --- balayage de seuil : le compromis automatisation / fiabilite --------

def balayage():
    """A quel taux d'automatisation peut-on tenir quelle precision ?

    C'est LA question produit. Un rattachement automatique faux coute
    beaucoup plus cher qu'un rattachement manquant : on chiffre un
    article au prix d'un autre, et on le decouvre sur la facture.
    """
    d = json.load(open("/home/user/workspace/repo/backend/catalogue_data.json"))
    articles = d["articles"]
    groupes = [a for a in articles if a.get("offers")]

    # Calcul unique du meilleur candidat et de sa justesse par offre
    evalues = []
    for vrai in groupes:
        for offre in vrai["offers"]:
            meilleur_s, meilleur_c = 0, None
            for cand in articles:
                s = score(offre, cand)
                if s > meilleur_s:
                    meilleur_s, meilleur_c = s, cand
            evalues.append((
                meilleur_s,
                bool(meilleur_c and meilleur_c["code"] == vrai["code"]),
            ))

    total = len(evalues)
    print()
    print("=" * 68)
    print("COMPROMIS AUTOMATISATION / FIABILITE")
    print("=" * 68)
    print("  seuil | auto  | dont justes | precision | faux auto | restant")
    print("  ------+-------+-------------+-----------+-----------+--------")
    for seuil in (20, 25, 30, 35, 40, 45, 50, 55, 60, 70):
        auto = [(s, j) for s, j in evalues if s >= seuil]
        if not auto:
            continue
        justes = sum(1 for _, j in auto if j)
        faux = len(auto) - justes
        prec = 100 * justes / len(auto)
        print(f"   {seuil:4} | {100*len(auto)/total:4.1f}% | "
              f"{100*justes/total:10.1f}% | {prec:8.1f}% | "
              f"{faux:4} offres | {100*(total-len(auto))/total:5.1f}%")

    # Plafond theorique : le bon article est-il au moins trouve ?
    trouve = sum(1 for s, j in evalues if j and s > 0)
    print(f"\n  PLAFOND -- le bon article est le 1er candidat : "
          f"{100*trouve/total:.1f} % des offres")
    jamais = sum(1 for s, _ in evalues if s == 0)
    print(f"  PLANCHER -- aucun candidat trouve            : "
          f"{100*jamais/total:.1f} % des offres")


balayage()


def top_n():
    """Le bon article est-il dans les N premiers candidats ?

    Decide la FORME de l'interface. Si le bon article est presque
    toujours dans les 3 premiers, l'ecran devient "choisir parmi 3"
    au lieu de "chercher dans 397" -- un geste de deux secondes.
    """
    d = json.load(open("/home/user/workspace/repo/backend/catalogue_data.json"))
    articles = d["articles"]
    groupes = [a for a in articles if a.get("offers")]

    rangs = []
    for vrai in groupes:
        for offre in vrai["offers"]:
            classement = sorted(
                ((score(offre, c), c["code"]) for c in articles),
                key=lambda x: -x[0],
            )
            rang = next(
                (i + 1 for i, (s, code) in enumerate(classement)
                 if code == vrai["code"] and s > 0),
                None,
            )
            rangs.append(rang)

    total = len(rangs)
    print()
    print("=" * 68)
    print("LE BON ARTICLE EST-IL DANS LES N PREMIERS ?")
    print("=" * 68)
    cumul = 0
    for n in (1, 2, 3, 5, 10):
        dedans = sum(1 for r in rangs if r is not None and r <= n)
        print(f"  top {n:2} : {100*dedans/total:5.1f} %  ({dedans}/{total})")
    absent = sum(1 for r in rangs if r is None)
    print(f"  jamais : {100*absent/total:5.1f} %  ({absent}/{total})")


top_n()
