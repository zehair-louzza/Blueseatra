"""Classement par pertinence des résultats de recherche (02/10/2026).

CONSTAT UTILISATEUR : « porte-coupe-feu » affichait d'abord un panneau PVC
(1,80 €), un judas, une gâche — des ACCESSOIRES — parce que le tri était au
prix. Les vraies portes (bloc-porte coupe-feu, 150 à 255 €) arrivaient en
4e position.

PRINCIPE : un produit EST ce que sa désignation annonce en premier ; un
accessoire le MENTIONNE en fin de libellé (« gâche ... pour portes
coupe-feu »). Le score récompense donc la position TOTALE de chaque mot
recherché dans le texte normalisé : 1/position. « bloc porte coupe feu »
porte@2 coupe@3 feu@4 = 1,08 ; « panneau pvc porte coupe feu » =
0,78 ; « gâche ... porte coupe feu » (mots en fin) ≈ 0,1.

Le score ne remplace jamais le filtre (tous les mots doivent être présents,
c'est offres_candidates qui le garantit) : il ne réordonne que des résultats
déjà corrects. Égalité de score → ordre du prix croissant conservé.

Module AUTONOME (aucun import métier) : utilisé par le comparateur
(fournisseur_recherche) et le sélecteur d'articles du devis
(catalogue_chiffrage) sans cycle d'imports.
"""
from __future__ import annotations

import re
import unicodedata


def _racine(mot: str) -> str:
    """Absorbe les pluriels simples : « portes » -> « porte »."""
    for suffixe in ("aux", "eaux", "es", "s", "x"):
        if len(mot) > 4 and mot.endswith(suffixe):
            return mot[: -len(suffixe)]
    return mot


def normalise(texte: str) -> str:
    """Même normalisation que blueseatra.normalise_recherche (minuscules,
    sans accents, chiffres à virgule point, séparateurs espaces)."""
    texte = re.sub(r"(\d)[.,](\d)", r"\1.\2", str(texte or ""))
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9.+]+", " ", texte.lower()).split())


def _position(mots_norm: list[str], mot: str) -> int | None:
    """Position 1-based de `mot` dans le texte ; racine en repli (pluriel) ;
    None si absent -- un mot absent contribue 0 pour TOUTES les lignes, sans
    quoi la longueur du libelle fausserait le classement."""
    if mot in mots_norm:
        return mots_norm.index(mot) + 1
    r = _racine(mot)
    for i, m in enumerate(mots_norm):
        if m.startswith(r):
            return i + 1
    return None


def score(texte_norm: str, requete: str) -> float:
    """Pertinence d'un texte NORMALISÉ pour une requête libre.

    Somme de 1/position de chaque mot de la requête (les mots d'une
    lettre, purement techniques, sont ignorés). Plus le produit mène avec
    les mots demandés, plus le score est haut ; 0 pour une requête vide,
    un texte vide ou des mots introuvables (le prix reprend alors la main).
    """
    mots_req = [m for m in normalise(requete).split() if len(m) >= 2]
    if not mots_req:
        return 0.0
    mots_norm = (texte_norm or "").split()
    total = 0.0
    for mot in mots_req:
        pos = _position(mots_norm, mot)
        if pos is not None:
            total += 1.0 / pos
    return total
