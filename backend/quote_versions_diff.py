"""Comparaison de deux versions d'un devis (ticket #85).

Fonctions pures, sans base : elles reçoivent deux instantanés de devis
(dictionnaires tels que stockés dans quotes / quote_versions.snapshot) et
renvoient les différences lisibles par l'interface.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict

CHAMPS_ENTETE = ("client", "client_final", "site", "object")
CHAMPS_LIGNE = ("qty", "unit", "unit_price_ht", "margin", "vat_rate", "line_ht")
TYPES_SANS_MONTANT = {"note", "page_break", "lot", "sublot"}


def _norm(txt) -> str:
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _cle(ligne: dict) -> tuple:
    return (ligne.get("line_type") or "generic", ligne.get("matched_item_code") or "", _norm(ligne.get("description")))


def _egal(a, b) -> bool:
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        try:
            return round(float(a or 0), 2) == round(float(b or 0), 2) and (a is None) == (b is None)
        except (TypeError, ValueError):
            return a == b
    return (a or None) == (b or None)


def _indexer(lignes):
    """Regroupe par clé en gardant l'ordre : deux lignes identiques restent deux lignes."""
    par = defaultdict(list)
    for i, l in enumerate(lignes or []):
        if (l.get("line_type") or "") == "page_break":
            continue
        par[_cle(l)].append((i, l))
    return par


def comparer(ancien: dict, nouveau: dict) -> dict:
    a_idx, n_idx = _indexer(ancien.get("lines")), _indexer(nouveau.get("lines"))
    ajoutees, supprimees, modifiees = [], [], []
    for cle in list(dict.fromkeys(list(a_idx) + list(n_idx))):
        av, nv = a_idx.get(cle, []), n_idx.get(cle, [])
        for k in range(max(len(av), len(nv))):
            if k >= len(av):
                ajoutees.append(_resume(nv[k][1]))
            elif k >= len(nv):
                supprimees.append(_resume(av[k][1]))
            else:
                la, ln = av[k][1], nv[k][1]
                if (la.get("line_type") or "") in TYPES_SANS_MONTANT:
                    continue
                champs = {c: {"avant": la.get(c), "apres": ln.get(c)} for c in CHAMPS_LIGNE if not _egal(la.get(c), ln.get(c))}
                if champs:
                    modifiees.append({**_resume(ln), "champs": champs})
    entete = {c: {"avant": ancien.get(c), "apres": nouveau.get(c)}
              for c in CHAMPS_ENTETE if (ancien.get(c) or "") != (nouveau.get(c) or "")}
    totaux = {}
    for c in ("total_ht", "total_vat", "total_ttc"):
        va, vn = float(ancien.get(c) or 0), float(nouveau.get(c) or 0)
        totaux[c] = {"avant": round(va, 2), "apres": round(vn, 2), "ecart": round(vn - va, 2)}
    return {
        "entete": entete, "ajoutees": ajoutees, "supprimees": supprimees, "modifiees": modifiees,
        "totaux": totaux,
        "identique": not (entete or ajoutees or supprimees or modifiees) and all(t["ecart"] == 0 for t in totaux.values()),
    }


def _resume(l: dict) -> dict:
    return {"type": l.get("line_type") or "generic", "description": l.get("description") or "",
            "code": l.get("matched_item_code"), "qty": l.get("qty"), "unit": l.get("unit"),
            "unit_price_ht": l.get("unit_price_ht"), "line_ht": l.get("line_ht")}


def resume_version(snapshot: dict) -> dict:
    lignes = [l for l in (snapshot.get("lines") or []) if (l.get("line_type") or "") not in TYPES_SANS_MONTANT]
    return {"total_ht": round(float(snapshot.get("total_ht") or 0), 2),
            "total_ttc": round(float(snapshot.get("total_ttc") or 0), 2), "lignes": len(lignes)}
