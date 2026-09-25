"""Comparaison d'une version de catalogue avec la version active, et seuils de
sécurité avant activation (ticket #86). Fonctions pures.

Clé d'un article : référence (item_code) si elle est réelle, sinon libellé
normalisé. Les codes générés à l'import (ART-<ligne>) ne sont pas des
références : ils changent quand l'ordre des lignes change.
"""
from __future__ import annotations

import re

UNITES_CONNUES = {
    "u", "un", "unite", "pce", "pc", "piece", "ens", "ensemble", "lot", "forfait", "ft", "f",
    "m", "ml", "m2", "m²", "m3", "m³", "kg", "g", "t", "l", "litre", "h", "hr", "heure", "j", "jour",
    "rouleau", "boite", "sac", "paquet", "carton", "palette", "paire", "jeu", "kit", "bobine", "tube",
}
SEUILS = {
    "chute_lignes_pct": 20,        # BLOQUANT : la nouvelle version a 20 % d'articles en moins
    "prix_manquants_pct": 10,      # A_VERIFIER
    "rejets_pct": 5,               # A_VERIFIER ; 25 % = BLOQUANT
    "unites_inconnues_pct": 10,    # A_VERIFIER
    "variation_prix_pct": 30,      # une variation au-delà est signalée article par article
    "hausse_moyenne_pct": 15,      # A_VERIFIER
}
_ART = re.compile(r"^ART-\d+$")


def cle(it: dict) -> str:
    code = (it.get("item_code") or "").strip()
    if code and not _ART.match(code):
        return "ref:" + code.lower()
    return "lib:" + (it.get("label_norm") or (it.get("item_label") or "").lower()).strip()


def _prix(it):
    v = it.get("unit_price_ht")
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def comparer(actifs: list[dict], nouveaux: list[dict], limite_details: int = 50) -> dict:
    a = {cle(i): i for i in actifs}
    n = {cle(i): i for i in nouveaux}
    ajoutes = [k for k in n if k not in a]
    retires = [k for k in a if k not in n]
    hausses, baisses, variations, inchanges = [], [], [], 0
    for k in n.keys() & a.keys():
        pa, pn = _prix(a[k]), _prix(n[k])
        if not pa or not pn or pa == pn:
            inchanges += 1
            continue
        pct = round((pn - pa) / pa * 100, 1) if pa else None
        ligne = {"reference": n[k].get("item_code"), "libelle": n[k].get("item_label"), "avant": pa, "apres": pn, "variation_pct": pct}
        (hausses if pn > pa else baisses).append(ligne)
        if pct is not None:
            variations.append(pct)
    tri = lambda l: sorted(l, key=lambda x: -abs(x["variation_pct"] or 0))[:limite_details]
    return {
        "articles_avant": len(a), "articles_apres": len(n),
        "ajoutes": len(ajoutes), "retires": len(retires), "hausses": len(hausses), "baisses": len(baisses),
        "inchanges": inchanges,
        "variation_moyenne_pct": round(sum(variations) / len(variations), 1) if variations else 0.0,
        "exemples_ajoutes": [n[k].get("item_label") for k in ajoutes[:10]],
        "exemples_retires": [a[k].get("item_label") for k in retires[:10]],
        "plus_fortes_hausses": tri(hausses), "plus_fortes_baisses": tri(baisses),
    }


def controler(nouveaux: list[dict], erreurs: int, lignes_fichier: int, comparaison: dict | None) -> dict:
    """Seuils de sécurité. Verdict : BLOQUANT > A_VERIFIER > OK."""
    alertes = []
    nb = len(nouveaux)

    def alerte(niveau, code, message):
        alertes.append({"niveau": niveau, "code": code, "message": message})

    if nb == 0:
        alerte("BLOQUANT", "vide", "Aucun article valide dans cette version.")
    pct = lambda x, d: round(100 * x / d, 1) if d else 0.0
    # Un prix vide est enregistré à 0 par l'import : 0 € compte comme un prix manquant.
    sans_prix = sum(1 for i in nouveaux if not _prix(i))
    negatifs = sum(1 for i in nouveaux if (_prix(i) or 0) < 0)
    inconnues = sum(1 for i in nouveaux if (i.get("unit") or "").strip().lower().rstrip(".") not in UNITES_CONNUES)
    rejets = pct(erreurs, lignes_fichier)
    if negatifs:
        alerte("BLOQUANT", "prix_negatifs", f"{negatifs} article(s) avec un prix négatif.")
    if rejets >= 25:
        alerte("BLOQUANT", "rejets", f"{rejets} % des lignes du fichier ont été rejetées.")
    elif rejets >= SEUILS["rejets_pct"]:
        alerte("A_VERIFIER", "rejets", f"{rejets} % des lignes du fichier ont été rejetées.")
    if nb and pct(sans_prix, nb) >= SEUILS["prix_manquants_pct"]:
        alerte("A_VERIFIER", "prix_manquants", f"{pct(sans_prix, nb)} % des articles n'ont pas de prix ({sans_prix}).")
    if nb and pct(inconnues, nb) >= SEUILS["unites_inconnues_pct"]:
        alerte("A_VERIFIER", "unites", f"{pct(inconnues, nb)} % des articles ont une unité non reconnue.")
    if comparaison and comparaison["articles_avant"]:
        chute = pct(comparaison["articles_avant"] - comparaison["articles_apres"], comparaison["articles_avant"])
        if chute >= SEUILS["chute_lignes_pct"]:
            alerte("BLOQUANT", "chute_lignes",
                   f"La nouvelle version compte {chute} % d'articles en moins que la version active "
                   f"({comparaison['articles_apres']} contre {comparaison['articles_avant']}).")
        if comparaison["variation_moyenne_pct"] >= SEUILS["hausse_moyenne_pct"]:
            alerte("A_VERIFIER", "hausse_moyenne", f"Hausse moyenne de {comparaison['variation_moyenne_pct']} % sur les articles communs.")
        fortes = [x for x in comparaison["plus_fortes_hausses"] + comparaison["plus_fortes_baisses"]
                  if abs(x["variation_pct"] or 0) >= SEUILS["variation_prix_pct"]]
        if fortes:
            alerte("A_VERIFIER", "variations_fortes", f"{len(fortes)} article(s) varient de plus de {SEUILS['variation_prix_pct']} %.")
    niveaux = {a["niveau"] for a in alertes}
    verdict = "BLOQUANT" if "BLOQUANT" in niveaux else "A_VERIFIER" if niveaux else "OK"
    return {"verdict": verdict, "alertes": alertes, "seuils": SEUILS,
            "sans_prix": sans_prix, "unites_inconnues": inconnues, "taux_rejet_pct": rejets}
