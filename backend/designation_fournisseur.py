"""Désignation affichée d'une offre fournisseur.

Pourquoi
--------
Quelques fournisseurs publient des libellés amputés de leur début : chez Rexel,
45 accessoires d'éclairage RZB s'appellent « , D 350 H 1, blanc » (le fabricant
lui-même ne leur donne qu'un nom de dimensions), un article Daikin commence par
« .ERAMIC FIBRE… » et un Blm par « - Boite de dérivation… ». Mesuré le
01/10/2026 : 47 lignes sur 747 771 chez Rexel. Le libellé est déjà ainsi dans
le fichier source : ce n'est pas l'import qui le coupe.

Règle
-----
Le libellé brut (`raw_label`) n'est JAMAIS modifié en base : il reste la trace
fidèle de la source. Seul l'affichage change. Quand le libellé commence par une
ponctuation, on retire cette ponctuation et on le préfixe par la marque et la
référence fabricant (à défaut, la référence fournisseur), qui identifient le
produit sans ambiguïté :

    « , D 350 H 1, blanc »  ->  « RZB 982552.002 · D 350 H 1, blanc »

Un libellé normal est renvoyé tel quel, au caractère près.
"""
from __future__ import annotations

import re

# Ponctuation en tête de libellé (après d'éventuels espaces) : virgule,
# point-virgule, point, deux-points, tirets, puces, barres. Un simple espace
# en tête ne suffit pas à déclarer le libellé amputé.
_PONCTUATION = r",;.:\-\u2010-\u2015\u00b7\u2022/|"
_DEBUT_AMPUTE = re.compile(rf"^\s*[{_PONCTUATION}]")
_A_RETIRER = re.compile(rf"^[\s{_PONCTUATION}]+")
SEPARATEUR = " \u00b7 "


def designation_affichee(designation: str | None, marque: str | None = None,
                         reference_fabricant: str | None = None,
                         reference_fournisseur: str | None = None) -> str | None:
    """Désignation lisible pour l'écran, sans jamais inventer de nom."""
    if designation is None:
        return None
    if not _DEBUT_AMPUTE.match(designation):
        return designation
    reste = _A_RETIRER.sub("", designation).strip()
    marque = (marque or "").strip()
    reference = (reference_fabricant or reference_fournisseur or "").strip()
    # Évite « RZB RZB982552.002 » quand la référence reprend déjà la marque.
    if marque and reference.lower().startswith(marque.lower()):
        marque = ""
    prefixe = " ".join(x for x in (marque, reference) if x)
    if prefixe and reste:
        return f"{prefixe}{SEPARATEUR}{reste}"
    return reste or prefixe or designation.strip()


def nettoyer_ligne(ligne: dict) -> dict:
    """Applique designation_affichee à une ligne issue de CHAMPS (en place)."""
    if "designation" in ligne:
        ligne["designation"] = designation_affichee(
            ligne.get("designation"), ligne.get("marque"),
            ligne.get("reference_fabricant"), ligne.get("reference_fournisseur"))
    return ligne
