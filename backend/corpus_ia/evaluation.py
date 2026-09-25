"""Notation d'une extraction face au corpus BTP annoté (ticket #88).

Chaque cas vaut un point par critère attendu : parties (donneur d'ordre,
client final), lieu, urgence, langue, lignes (nombre minimal, mots-clés) et
absence de prix. Comparaison sans accents ni casse, par inclusion.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

CORPUS = Path(__file__).with_name("demandes_btp.json")
SEUIL_BASCULE = 0.80   # taux de réussite minimal avant tout changement de modèle en production


def _n(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


def noter(sortie: dict, attendu: dict) -> tuple[int, int, list[str]]:
    points, total, echecs = 0, 0, []

    def crit(nom, ok):
        nonlocal points, total
        total += 1
        points += int(bool(ok))
        if not ok:
            echecs.append(nom)

    parties = " ".join(_n(sortie.get(k)) for k in ("donneur_d_ordre", "client_name", "client_final"))
    for k in ("donneur_d_ordre", "client_final"):
        if k in attendu:
            crit(k, _n(attendu[k]) in parties)
    if "location" in attendu:
        lieu = " ".join(_n(sortie.get(k)) for k in ("location", "intervention_site", "intervention_address", "client_address"))
        crit("location", _n(attendu["location"]) in lieu)
    for k in ("urgency", "language"):
        if k in attendu:
            crit(k, _n(sortie.get(k)) == _n(attendu[k]))
    lignes = sortie.get("line_items") or []
    crit("lignes_min", len(lignes) >= attendu.get("lignes_min", 1))
    texte_lignes = " ".join(_n(json.dumps(l, ensure_ascii=False)) for l in lignes) + " " + _n(sortie.get("description"))
    for mot in attendu.get("mots_lignes", []):
        crit(f"ligne:{mot}", _n(mot) in texte_lignes)
    if attendu.get("aucun_prix"):
        crit("aucun_prix", not any(k in json.dumps(lignes).lower() for k in ('"unit_price', '"prix', '"price')))
    return points, total, echecs


def charger() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))
