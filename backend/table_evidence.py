"""Preuves déterministes issues des tableaux markdown d'un document source.

Lit UNIQUEMENT les colonnes désignation / unité / quantité des tableaux dont
les en-têtes sont reconnus. Les colonnes de prix ne sont jamais lues : aucun
montant ne peut devenir une quantité ni servir à un calcul.

La liaison avec une ligne de l'IA est EXACTE (désignation normalisée
identique, unique dans le document) ; jamais approximative.
"""
from __future__ import annotations

import math
import re
import unicodedata

_HEADERS = {
    "designation": {"designation", "designations", "libelle", "description", "prestation",
                    "prestations", "ouvrage", "intitule", "article"},
    "unit": {"unite", "unites", "u", "unit"},
    "quantity": {"qte", "qtes", "quantite", "quantites", "qt", "nombre", "nb"},
}
# Unités reconnues (clé normalisée). Une unité inconnue ou vide retire toute
# autorité à la quantité de la ligne : elle reste à relever.
_UNITS = {"u", "un", "unite", "unites", "ens", "ensemble", "forfait", "ft", "fft", "f",
          "point", "points", "pt", "pts", "m", "ml", "m2", "m3", "kg", "t", "h", "j",
          "jour", "jours", "l", "lot", "pce", "piece", "pieces", "paire", "pm"}
_SEPARATOR = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
# Entier ou décimal, milliers séparés par espace : « 14 », « 1 000 », « 2,5 ».
_NUMBER = re.compile(r"^\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?$|^\d+(?:[.,]\d+)?$")


def key(text) -> str:
    """Normalisation de comparaison exacte : accents, casse, ponctuation et
    espaces neutralisés. Ce n'est PAS une ressemblance : les mots et leur
    ordre doivent être identiques."""
    decomposed = unicodedata.normalize("NFKD", str(text or "").lower())
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    bare = bare.replace("œ", "oe").replace("æ", "ae")
    # Tout autre caractère (apostrophe typographique, ponctuation) sépare.
    return " ".join(re.findall(r"[a-z0-9]+", bare))


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _header_map(cells):
    """(colonnes, est_un_entete). Colonnes None si l'en-tête est incomplet
    (désignation, unité ET quantité requises) ou ambigu (rôle en double)."""
    found, duplicate = {}, False
    for i, cell in enumerate(cells):
        name = key(cell)
        for field, names in _HEADERS.items():
            if name in names:
                duplicate |= field in found
                found.setdefault(field, i)
    if not {"designation", "quantity"} <= set(found):
        return None, False
    if duplicate or "unit" not in found:
        return None, True  # tableau refusé : aucune ligne n'en fait autorité
    return found, True


def _quantity(cell):
    text = (cell or "").strip()
    if not _NUMBER.match(text):
        return None  # prix (€), caractéristique (150 L, 32 A), texte, vide
    value = float(re.sub(r"[ \u00a0\u202f]", "", text).replace(",", "."))
    if not math.isfinite(value) or value <= 0:
        return None
    return int(value) if value.is_integer() else value


def parse_quantity_rows(raw_text: str) -> list[dict]:
    """Lignes de quantité des tableaux markdown à en-têtes reconnus.

    Chaque ligne : source_id (« T<table>R<ligne> », stable pour un même
    texte), source_text (ligne EXACTE du document), designation, unit,
    quantity (nombre > 0 ou None), quantity_text (cellule Qté exacte).
    Les lignes sans unité ni quantité (sous-totaux, titres) sont omises ;
    une quantité vide ou une unité vide/inconnue donne quantity=None.
    Un en-tête incomplet ou à rôle doublé (deux « Qté ») invalide le tableau.
    """
    rows, table, columns, index = [], 0, None, 0
    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            columns = None  # fin de tableau
            continue
        if _SEPARATOR.match(stripped):
            continue
        cells = _cells(stripped)
        header, is_header = _header_map(cells)
        if is_header:
            table, columns, index = table + 1, header, 0
            continue
        if columns is None:
            continue
        index += 1

        def cell(field):
            i = columns.get(field)
            return cells[i] if i is not None and i < len(cells) else ""

        designation, unit, qty_cell = cell("designation"), cell("unit"), cell("quantity")
        if not designation or (not unit and not qty_cell):
            continue
        known_unit = key(unit) in _UNITS
        rows.append({"source_id": f"T{table}R{index}", "source_text": line,
                     "designation": designation, "unit": unit.lower() if known_unit else None,
                     "quantity": _quantity(qty_cell) if known_unit else None,
                     "quantity_text": qty_cell})
    return rows


def match_row(rows, label, source_row_id=None, proof=None):
    """(ligne, conflit) pour la ligne source dont la désignation est
    exactement `label`.

    (None, False) : aucune ligne de tableau ne porte ce libellé (le
    garde-fou prose s'applique). (None, True) : CONFLIT -- désignation en
    double, source_row_id fourni absent/différent, ou citation de l'IA
    appartenant à une autre ligne ; la ligne reste bloquée, sans repli prose.
    """
    wanted = key(label)
    same = [r for r in rows if wanted and key(r["designation"]) == wanted]
    if not same:
        return None, bool(source_row_id)
    if len(same) != 1:
        return None, True
    found = same[0]
    if source_row_id and source_row_id != found["source_id"]:
        return None, True
    if proof and f" {key(proof)} " not in f" {key(found['source_text'])} ":
        return None, True  # citation d'un autre objet : pas de rattachement
    return found, False
