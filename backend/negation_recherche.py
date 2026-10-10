"""Exclusion des désignations qui NIENT un terme de la recherche (04/10/2026).

CONSTAT UTILISATEUR : « porte coupe feu » ramenait des portes Prolians
« multi-usage TWIN NON coupe-feu » — les mots demandés y sont tous
présents, mais le libellé affirme le CONTRAIRE de la recherche. Le filtre
mot par mot ne voit pas la négation ; la pertinence la reléguait en fin
de classement, mais un tri par prix la faisait remonter en tête de
tableau (constat visuel du 04/10/2026).

PRINCIPE : « la pertinence trie, elle ne filtre jamais » reste vrai pour
la pertinence. La négation est d'une autre nature : la désignation
contredit EXPLICITEMENT la demande — ces lignes sont des faux positifs du
filtre de mots, pas des résultats moins pertinents. Elles sont exclues
des résultats, jamais silencieusement : le compte, les motifs et des
exemples sont renvoyés à l'interface et affichés.

DÉTECTÉ : « non » suivi d'un groupe de mots de la requête (1 à 3 mots
consécutifs) ; « sans » suivi d'un groupe d'au moins 2 mots (le « sans »
d'un seul mot a trop de faux positifs légitimes : « vis sans fin »,
« câble sans gaine » pour la requête « vis » ou « câble »).

Module AUTONOME (aucun import métier), testé sans base de données.
"""
from __future__ import annotations

from pertinence import normalise

# Fenêtres de mots consécutifs de la requête considérées : 1 à 3 mots.
_LONGUEUR_MAX = 3
# « sans » exige au moins 2 mots : les composés du bâtiment (« vis sans
# fin », « courroie sans fin ») ne sont pas des négations du mot « vis ».
_MIN_SANS = 2


def _ngrammes_requete(requete_norm: str) -> list[tuple[str, ...]]:
    """Groupes de mots consécutifs de la requête, du plus long au plus court.

    Le plus long d'abord : sur « porte coupe feu », le motif « non coupe
    feu » (2 mots) est plus précis que « non coupe » (1 mot) — on veut
    rapporter le premier.
    """
    mots = requete_norm.split()
    sortie: list[tuple[str, ...]] = []
    for n in range(min(_LONGUEUR_MAX, len(mots)), 0, -1):
        for i in range(len(mots) - n + 1):
            sortie.append(tuple(mots[i:i + n]))
    return sortie


def negation_presente(recherche_norm: str, requete: str) -> str | None:
    """Motif de négation trouvé dans une désignation pour cette requête.

    Renvoie le motif lisible (« non coupe feu ») ou None. Une désignation
    sans « non » ni « sans » n'est jamais exclue ; une négation qui porte
    sur des mots HORS requête non plus (« porte non isole » pour la
    requête « porte coupe feu » : la porte est bien non isolée, elle reste
    une porte coupe-feu possible).
    """
    ngrammes = _ngrammes_requete(normalise(requete))
    if not ngrammes:
        return None
    par_longueur: dict[int, set[tuple[str, ...]]] = {}
    for g in ngrammes:
        par_longueur.setdefault(len(g), set()).add(g)
    tokens = normalise(recherche_norm or "").split()
    for i, mot in enumerate(tokens):
        if mot not in ("non", "sans"):
            continue
        mini = _MIN_SANS if mot == "sans" else 1
        for n in range(min(_LONGUEUR_MAX, len(tokens) - i - 1), mini - 1, -1):
            fenetre = tuple(tokens[i + 1:i + 1 + n])
            if fenetre in par_longueur.get(n, set()):
                return f"{mot} " + " ".join(fenetre)
    return None


def exclure(lignes: list[dict], requete: str) -> tuple[list[dict], dict | None]:
    """Sépare les lignes dont la désignation nie un terme de la requête.

    Renvoie (lignes_retenues, rapport). Le rapport est None quand rien
    n'est exclu ; sinon il porte le compte, les motifs uniques triés et
    jusqu'à 3 désignations exemples — tout ce que l'interface affiche.
    """
    if not lignes or not (requete or "").strip():
        return lignes, None
    retenues: list[dict] = []
    motifs: dict[str, int] = {}
    exemples: list[str] = []
    exclues: list[dict] = []
    for l in lignes:
        motif = negation_presente(
            l.get("recherche_norm") or l.get("designation") or "", requete)
        if motif is None:
            retenues.append(l)
            continue
        exclues.append(l)
        motifs[motif] = motifs.get(motif, 0) + 1
        exemple = (l.get("designation") or l.get("recherche_norm") or "").strip()
        if exemple and len(exemples) < 3:
            exemples.append(exemple[:120])
    if not exclues:
        return retenues, None
    return retenues, {
        "nombre": len(exclues),
        "motifs": sorted(motifs, key=lambda m: (-motifs[m], m)),
        "exemples": exemples,
    }