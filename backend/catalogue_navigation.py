"""Navigation dans les catalogues fournisseurs : liste des fournisseurs visibles
par l'entreprise, puis parcours page par page de leurs produits.

Pourquoi un module a part de fournisseur_recherche
--------------------------------------------------
La recherche repond a « quel est le moins cher pour ce besoin ». Ici on
repond a « que vend ce fournisseur » : l'utilisateur ouvre un fournisseur et
feuillette son catalogue, filtre par famille ou par mot.

Performance (mesuree le 24/09/2026 sur 967 563 offres)
------------------------------------------------------
Compter les offres a la volee coute ~9,4 s (parcours complet de la table).
La liste des fournisseurs lit donc `catalog_versions.item_count`, deja tenu a
jour par l'import, et ne compte en direct que les offres historiques sans
catalogue (quelques centaines au plus). Les produits d'un fournisseur sont
lus par (tenant_id, version_id) : index idx_offers_tenant_version, et
l'index de la migration 20260924010000 pour le tri par designation.

Securite
--------
Meme regle que fournisseur_recherche : tenant_id filtre EXPLICITEMENT dans
chaque requete (mode repli sous `postgres` BYPASSRLS). Une cle de catalogue
fournie par le client n'est jamais crue : elle est resolue parmi les seules
versions actives de l'entreprise et du catalogue commun non masque.
"""
from __future__ import annotations

from sqlalchemy import text

import catalogue_commun
from database import get_current_tenant, tenant_session
from fournisseur_recherche import _conditions

TAILLE_DEFAUT = 50
TAILLE_MAX = 200
# Au-dela, un total exact coute un parcours complet ; on affiche « 10 000+ ».
PLAFOND_COMPTE = 10000
# Avec un mot cherche, compter au-dela coute plus cher que la page elle-meme
# sur Rexel (747 771 lignes) ; l'ecran affiche alors "Plus de 1 000".
PLAFOND_COMPTE_RECHERCHE = 1000

# Versions ACTIVES visibles par l'entreprise : les siennes + le commun si
# non masque. Le fournisseur est lu sur une offre de la version (index
# idx_offers_tenant_version, une seule ligne).
SQL_CATALOGUES = """
    SELECT v.id            AS version_id,
           c.tenant_id     AS tenant_id,
           c.name          AS catalogue,
           v.item_count    AS references_,
           v.activated_at  AS active_le,
           (c.tenant_id = :commun) AS catalogue_commun,
           -- Une seule offre lue (LIMIT 1 sur l'index tenant/version), puis le
           -- fournisseur : la jointure directe parcourait des centaines de
           -- milliers d'offres par fournisseur (24 s en production).
           (SELECT f.name FROM blueseatra.suppliers f
             WHERE f.tenant_id = c.tenant_id
               AND f.id = (SELECT o.supplier_id FROM blueseatra.supplier_offers o
                            WHERE o.tenant_id = c.tenant_id AND o.version_id = v.id
                            LIMIT 1)) AS fournisseur
      FROM blueseatra.catalogs c
      JOIN blueseatra.catalog_versions v
        ON v.id = c.active_version_id AND v.tenant_id = c.tenant_id
     WHERE (c.tenant_id = :tenant_id OR (:avec_commun AND c.tenant_id = :commun))
     ORDER BY v.item_count DESC
"""

# Offres historiques de l'entreprise, importees avant le versionnage : sans
# catalogue, ou rattachees a un catalogue jamais cree.
SQL_HISTORIQUE = """
    SELECT o.supplier_id   AS supplier_id,
           f.name          AS fournisseur,
           count(*)        AS references_,
           max(o.source_date) AS derniere_maj
      FROM blueseatra.supplier_offers o
      LEFT JOIN blueseatra.suppliers f
             ON f.id = o.supplier_id AND f.tenant_id = o.tenant_id
     WHERE o.tenant_id = :tenant_id
       AND o.is_active
       AND (o.catalog_id IS NULL
            OR o.catalog_id NOT IN (SELECT c.id FROM blueseatra.catalogs c
                                    WHERE c.tenant_id = :tenant_id))
     GROUP BY o.supplier_id, f.name
"""

CHAMPS = """
    o.id,
    f.name              AS fournisseur,
    o.raw_label         AS designation,
    o.brand             AS marque,
    o.raw_reference     AS reference_fournisseur,
    o.manufacturer_ref  AS reference_fabricant,
    o.ean               AS code_ean,
    o.price_ht          AS prix_net_ht,
    (o.raw_row->>'prix_public_ht') AS prix_public_ht,
    o.raw_unit          AS unite_vente,
    o.packaging_qty     AS conditionnement,
    o.raw_row->>'famille'      AS famille,
    o.raw_row->>'sous_famille' AS sous_famille,
    o.product_url       AS url_produit,
    o.source_date       AS date_prix,
    (o.tenant_id = :commun) AS catalogue_commun
"""

# Familles d'une version : immuables tant que la version existe (une
# nouvelle version a un nouvel identifiant), donc mises en cache.
SQL_FAMILLES = """
    SELECT o.raw_row->>'famille' AS famille, count(*) AS nb
      FROM blueseatra.supplier_offers o
     WHERE (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
       AND o.tenant_id = :vt AND o.version_id = :version
     GROUP BY 1
     ORDER BY 2 DESC
"""

_cache_familles: dict[str, list[dict]] = {}


def _iso(v):
    """Les dates sont en texte ou en date selon la table : rendre du texte."""
    if not v:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _tenant() -> str:
    tenant = get_current_tenant()
    if not tenant:
        raise RuntimeError(
            "catalogue_navigation appele sans tenant courant : en mode repli, "
            "l'absence de filtre exposerait tous les tenants.")
    return tenant


def _params(tenant: str, avec_commun: bool) -> dict:
    return {"tenant_id": tenant, "commun": catalogue_commun.TENANT_COMMUN,
            "avec_commun": avec_commun}


async def fournisseurs() -> dict:
    """Fournisseurs visibles par l'entreprise, avec leur nombre de produits."""
    tenant = _tenant()
    async with tenant_session() as session:
        avec_commun = not await catalogue_commun.est_masque(session, tenant)
        p = _params(tenant, avec_commun)
        cats = [dict(r) for r in (await session.execute(text(SQL_CATALOGUES), p)).mappings()]
        hist = [dict(r) for r in (await session.execute(text(SQL_HISTORIQUE), p)).mappings()]

    liste = [{
        "cle": c["version_id"],
        "fournisseur": c["fournisseur"] or c["catalogue"].removeprefix("Tarif ").strip(),
        "references": int(c["references_"] or 0),
        "derniere_maj": _iso(c["active_le"]),
        "catalogue_commun": bool(c["catalogue_commun"]),
    } for c in cats if (c["references_"] or 0) > 0]
    liste += [{
        "cle": f"hist:{h['supplier_id']}",
        "fournisseur": h["fournisseur"] or "Fournisseur sans nom",
        "references": int(h["references_"]),
        "derniere_maj": _iso(h["derniere_maj"]),
        "catalogue_commun": False,
    } for h in hist]
    liste.sort(key=lambda x: -x["references"])
    return {"fournisseurs": liste,
            "total_references": sum(x["references"] for x in liste)}


async def _resoudre(session, tenant: str, cle: str) -> tuple[str, dict]:
    """Traduit une cle client en clause WHERE sure. Jamais crue telle quelle."""
    avec_commun = not await catalogue_commun.est_masque(session, tenant)
    p = _params(tenant, avec_commun)
    if cle.startswith("hist:"):
        p["supplier_id"] = cle[5:]
        return ("""o.tenant_id = :tenant_id AND o.supplier_id = :supplier_id AND o.is_active
                   AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                        SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = :tenant_id))""", p)
    cats = (await session.execute(text(SQL_CATALOGUES), p)).mappings().all()
    trouve = next((c for c in cats if c["version_id"] == cle), None)
    if not trouve:
        raise LookupError("Catalogue introuvable ou masqué pour cette entreprise.")
    p.update(vt=trouve["tenant_id"], version=cle)
    # :vt vaut soit l'entreprise, soit le tenant commun -- verifie ci-dessus.
    return "o.tenant_id = :vt AND o.version_id = :version AND o.is_active", p


async def produits(cle: str, page: int = 1, taille: int = TAILLE_DEFAUT,
                   q: str = "", famille: str = "") -> dict:
    tenant = _tenant()
    page = max(1, int(page))
    taille = max(1, min(int(taille), TAILLE_MAX))
    async with tenant_session() as session:
        where, p = await _resoudre(session, tenant, cle)
        conds = [where]
        if famille:
            conds.append("o.raw_row->>'famille' = :famille")
            p["famille"] = famille
        q = (q or "").strip()
        if q:
            c, pq, _ = _conditions(q)
            conds += c
            p.update(pq)
        clause = " AND ".join(conds)
        plafond = PLAFOND_COMPTE_RECHERCHE if q else PLAFOND_COMPTE
        p.update(limite=taille + 1, decalage=(page - 1) * taille, plafond=plafond + 1)
        # Les deux requetes filtrent tenant_id via `clause` (voir _resoudre).
        if q:
            # Recherche en deux temps : les identifiants de la page sont lus
            # dans l'index compact idx_offers_recherche_prix_v2 (tri par
            # prix, index-only), puis seules ces lignes sont lues en table.
            # En une seule requete, PostgreSQL lisait chaque fiche candidate
            # (1,1 ko) : > 60 s pour "disjoncteur" dans Rexel, 1,3 s ainsi.
            sql = text(f"""
                WITH page AS MATERIALIZED (
                    SELECT o.id, o.price_ht
                      FROM blueseatra.supplier_offers o
                     WHERE {clause} AND (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
                     ORDER BY o.price_ht ASC NULLS LAST, o.id
                     LIMIT :limite OFFSET :decalage)
                SELECT {CHAMPS}
                  FROM page
                  JOIN blueseatra.supplier_offers o ON o.id = page.id
                  LEFT JOIN blueseatra.suppliers f
                         ON f.id = o.supplier_id AND f.tenant_id = o.tenant_id
                 WHERE (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
                 ORDER BY page.price_ht ASC NULLS LAST, page.id
            """)
        else:
            sql = text(f"""
                SELECT {CHAMPS}
                  FROM blueseatra.supplier_offers o
                  LEFT JOIN blueseatra.suppliers f
                         ON f.id = o.supplier_id AND f.tenant_id = o.tenant_id
                 WHERE {clause} AND (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
                 ORDER BY o.raw_label, o.id
                 LIMIT :limite OFFSET :decalage
            """)
        lignes = [dict(r) for r in (await session.execute(sql, p)).mappings()]
        total = None
        if q or famille:
            compte = text(f"""
                SELECT count(*) FROM (
                    SELECT 1 FROM blueseatra.supplier_offers o
                     WHERE {clause} AND (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
                     LIMIT :plafond) s
            """)
            total = int((await session.execute(compte, p)).scalar() or 0)

    suivante = len(lignes) > taille
    lignes = lignes[:taille]
    for l in lignes:
        pp = l.get("prix_public_ht")
        try:
            l["prix_public_ht"] = round(float(pp), 4) if pp not in (None, "") else None
        except (TypeError, ValueError):
            l["prix_public_ht"] = None
        l["date_prix"] = _iso(l.get("date_prix"))
    return {
        "cle": cle, "page": page, "taille": taille,
        "total": total,
        "total_plafonne": bool(total and total > (PLAFOND_COMPTE_RECHERCHE if q else PLAFOND_COMPTE)),
        "page_suivante": suivante, "produits": lignes,
    }


async def familles(cle: str) -> dict:
    tenant = _tenant()
    async with tenant_session() as session:
        where, p = await _resoudre(session, tenant, cle)
        if cle in _cache_familles:
            return {"cle": cle, "familles": _cache_familles[cle]}
        if cle.startswith("hist:"):
            sql = text(f"""SELECT o.raw_row->>'famille' AS famille, count(*) AS nb
                             FROM blueseatra.supplier_offers o
                            WHERE {where} AND o.tenant_id = :tenant_id
                            GROUP BY 1 ORDER BY 2 DESC""")
        else:
            sql = text(SQL_FAMILLES)
        rows = [{"famille": r["famille"], "nb": int(r["nb"])}
                for r in (await session.execute(sql, p)).mappings() if r["famille"]]
    if not cle.startswith("hist:"):
        _cache_familles[cle] = rows
    return {"cle": cle, "familles": rows}
