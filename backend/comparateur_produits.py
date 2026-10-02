"""Comparateur : prix comparables et regroupement des offres par produit.

Format unique des offres fournisseurs, étape 2 (02/10/2026). La table
blueseatra.offres_normalisees (migration 20261002010000) donne, pour chaque
offre :

- une clé produit (`GTIN:<14 chiffres>` ou `MR:<marque>:<réf. fabricant>`),
  identique chez tous les fournisseurs qui vendent le même article, même si
  leurs désignations n'ont rien en commun ;
- un prix par unité de base (`prix_net_ht_unite_base`) : YESSS publie ses
  câbles « pour 100 m » ou « pour 1 000 m », Rexel au mètre. Comparer les prix
  bruts compare 146,61 € (100 m) à 1,08 € (1 m).

Ce module est PUR (aucun accès base) : il reçoit des dictionnaires et en
renvoie. Les requêtes vivent dans fournisseur_recherche.py.

Règles :
- Le prix comparable d'une offre est son prix par unité de base s'il est
  connu, sinon son prix net brut (offre non encore normalisée). Une offre
  sans prix n'est jamais « la moins chère ».
- Un groupe ne compare que des offres de même unité de base. Si un même
  produit est vendu au mètre chez l'un et à la pièce chez l'autre, l'écart
  n'est pas calculé (`unites_differentes`) : il serait faux.
- Un fournisseur ne compte qu'une fois par produit : son offre la moins chère.
  Les autres sont comptées (`autres_offres`), pas affichées.
"""
from __future__ import annotations

# Plafonds de la réponse : un écran exploite une vingtaine de produits, et
# chaque offre sérialisée coûte de la bande passante sur mobile.
MAX_GROUPES = 20
MAX_OFFRES_PAR_GROUPE = 12

# Anomalies montrées à l'utilisateur. Les autres (GTIN_CLE…) servent au
# contrôle qualité, pas à la décision d'achat.
ANOMALIES_AFFICHEES = (
    "UNITE_SUPPOSEE", "UNITE_INCONNUE", "PRIX_NET_SUP_PUBLIC",
    "PRIX_EXTREME", "ECART_PRIX_PRODUIT",
)

# Colonnes de offres_normalisees recopiées sur chaque ligne de résultat.
CHAMPS_NORMALISES = (
    "cle_produit", "niveau_identification", "unite_base",
    "qte_par_conditionnement", "prix_unite_base_ht", "unite_code",
    "marque_canonique", "ref_fabricant_normalisee", "gtin", "prix_public_ht",
)


def _positif(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def prix_comparable(ligne: dict) -> float | None:
    """Prix par unité de base, sinon prix net brut ; None si aucun prix."""
    p = _positif(ligne.get("prix_unite_base_ht"))
    return p if p is not None else _positif(ligne.get("prix_net_ht"))


def cle_tri(ligne: dict) -> tuple:
    """Tri par prix comparable croissant, offres sans prix en dernier."""
    p = prix_comparable(ligne)
    return (p is None, p if p is not None else 0.0, str(ligne.get("id") or ""))


def enrichir(ligne: dict, norm: dict | None) -> dict:
    """Recopie sur la ligne les champs normalisés de l'offre (en place).

    Ne remplace jamais une valeur source : la désignation, la marque et le
    prix publiés par le fournisseur restent ceux affichés. Le prix public
    n'est complété que s'il manque (il n'est pas lu dans supplier_offers).
    """
    if not norm:
        return ligne
    for k in CHAMPS_NORMALISES:
        if k == "prix_public_ht":
            if ligne.get(k) is None and norm.get(k) is not None:
                ligne[k] = float(norm[k])
            continue
        v = norm.get(k)
        if k in ("qte_par_conditionnement", "prix_unite_base_ht") and v is not None:
            v = float(v)
        ligne[k] = v
    ligne["anomalies"] = [a for a in (norm.get("anomalies") or []) if a in ANOMALIES_AFFICHEES]
    return ligne


def _ecart_pct(bas: float | None, haut: float | None) -> int | None:
    if not bas or not haut or bas <= 0:
        return None
    return round(100 * (haut - bas) / bas)


def regrouper_par_produit(offres: list[dict], ids_trouves: set[str] | None = None,
                          ordre: list[str] | None = None,
                          max_groupes: int = MAX_GROUPES) -> list[dict]:
    """Produits vendus par au moins deux fournisseurs, offres comparées.

    `offres`      : offres déjà enrichies (enrichir), y compris celles qui ne
                    contiennent pas les termes de la recherche mais portent la
                    même clé produit qu'un résultat.
    `ids_trouves` : ids renvoyés par la recherche texte. Les autres offres
                    sont marquées `designation_differente` : c'est l'apport du
                    format unique (même produit, autre libellé).
    `ordre`       : clés produit dans l'ordre des résultats (les plus
                    pertinentes d'abord) ; à défaut, ordre des offres.
    """
    ids_trouves = ids_trouves or set()
    par_cle: dict[str, list[dict]] = {}
    for o in offres:
        cle = o.get("cle_produit")
        if cle:
            par_cle.setdefault(cle, []).append(o)

    rang = {c: i for i, c in enumerate(ordre or [])}
    groupes = []
    for cle, liste in par_cle.items():
        # La moins chère de chaque fournisseur.
        meilleures: dict[str, dict] = {}
        nombre: dict[str, int] = {}
        for o in sorted(liste, key=cle_tri):
            nom = o.get("fournisseur") or "inconnu"
            nombre[nom] = nombre.get(nom, 0) + 1
            meilleures.setdefault(nom, o)
        if len(meilleures) < 2:
            continue
        retenues = sorted(meilleures.values(), key=cle_tri)
        unites = {o.get("unite_base") for o in retenues if prix_comparable(o) is not None}
        unites_differentes = len(unites) > 1
        prix = [prix_comparable(o) for o in retenues if prix_comparable(o) is not None]
        bas = min(prix) if prix else None
        haut = max(prix) if prix else None

        # Libellé du groupe : la désignation la plus complète (les libellés
        # amputés à la source sont les plus courts).
        designation = max((o.get("designation") or "" for o in retenues), key=len) or None
        gtin = next((o.get("gtin") for o in retenues if o.get("gtin")), None)
        if not gtin and cle.startswith("GTIN:"):
            gtin = cle[5:]

        lignes = []
        for o in retenues[:MAX_OFFRES_PAR_GROUPE]:
            p = prix_comparable(o)
            lignes.append({
                "id": o.get("id"),
                "fournisseur": o.get("fournisseur"),
                "designation": o.get("designation"),
                "reference_fournisseur": o.get("reference_fournisseur"),
                "prix_net_ht": _arrondi(o.get("prix_net_ht")),
                "prix_unite_base_ht": _arrondi(p, 4),
                "unite_vente": o.get("unite_vente"),
                "unite_base": o.get("unite_base"),
                "qte_par_conditionnement": o.get("qte_par_conditionnement"),
                "ecart_pct": None if unites_differentes or p is None else _ecart_pct(bas, p),
                "url_produit": o.get("url_produit"),
                "catalogue_commun": o.get("catalogue_commun"),
                # Rattachée par marque + référence : pas de GTIN chez ce fournisseur.
                "par_reference": o.get("niveau_identification") == "MARQUE_REF",
                "designation_differente": o.get("id") not in ids_trouves,
                "autres_offres": nombre[o.get("fournisseur") or "inconnu"] - 1,
                "anomalies": o.get("anomalies") or [],
            })
        groupes.append({
            "cle_produit": cle,
            "designation": designation,
            "marque": next((o.get("marque_canonique") or o.get("marque")
                            for o in retenues if o.get("marque_canonique") or o.get("marque")), None),
            "reference_fabricant": next((o.get("ref_fabricant_normalisee") or o.get("reference_fabricant")
                                         for o in retenues
                                         if o.get("ref_fabricant_normalisee") or o.get("reference_fabricant")), None),
            "gtin": gtin,
            "unite_base": None if unites_differentes else next(iter(unites), None),
            "unites_differentes": unites_differentes,
            "nb_fournisseurs": len(meilleures),
            "prix_min": _arrondi(bas, 4),
            "prix_max": _arrondi(haut, 4),
            "ecart_pct": None if unites_differentes else _ecart_pct(bas, haut),
            "offres": lignes,
            "_rang": rang.get(cle, len(rang) + len(groupes)),
        })

    # Les plus pertinents (premiers résultats) d'abord ; à pertinence égale,
    # le plus de fournisseurs.
    groupes.sort(key=lambda g: (g["_rang"], -g["nb_fournisseurs"]))
    for g in groupes:
        g.pop("_rang")
    return groupes[:max_groupes]


def meilleurs_par_fournisseur(lignes: list[dict]) -> list[dict]:
    """La moins chère de chaque fournisseur, au prix comparable."""
    meilleurs: dict[str, dict] = {}
    for ligne in sorted(lignes, key=cle_tri):
        p = prix_comparable(ligne)
        nom = ligne.get("fournisseur") or "inconnu"
        if p is None or nom in meilleurs:
            continue
        meilleurs[nom] = {
            "fournisseur": nom,
            "prix_net_ht": _arrondi(ligne.get("prix_net_ht")),
            "prix_unite_base_ht": _arrondi(p, 4),
            "unite_base": ligne.get("unite_base"),
            "qte_par_conditionnement": ligne.get("qte_par_conditionnement"),
            "designation": ligne.get("designation"),
            "id": ligne.get("id"),
        }
    return sorted(meilleurs.values(), key=lambda x: x["prix_unite_base_ht"])


def _arrondi(v, n: int = 2):
    f = _positif(v)
    return round(f, n) if f is not None else None
