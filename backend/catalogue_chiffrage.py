"""Sources fournisseurs du chiffrage : activer/desactiver les catalogues
fournisseurs visibles par l'entreprise pour chiffrer les devis.

Pourquoi ce module
------------------
Le chiffrage des devis s'appuie sur LE catalogue tarifaire actif de
l'entreprise (pricing_items, import CSV). Les catalogues fournisseurs
(967 563 offres dans supplier_offers) ne peuvent pas y etre copies :
les prix passeraient en double et la memoire du service y passerait.

Ce module fait le pont SANS copie :
- l'entreprise choisit quels catalogues fournisseurs elle active pour le
  chiffrage (table chiffrage_sources, une ligne par choix, jamais de
  suppression de contenu) ;
- la recherche d'articles du devis (GET /catalog/search) interroge en SQL
  les offres des seules sources activees, via la colonne generee
  recherche_norm et son index trigramme (meme chemin que
  fournisseur_recherche), et les renvoie dans la meme forme que les
  pricing_items pour que le selecteur du devis les affiche tels quels.

Securite
--------
Meme regle que catalogue_navigation : une cle fournie par le client n'est
jamais crue. Elle est resolue parmi les fournisseurs VISIBLES par
l'entreprise (les siens + le catalogue commun non masque), et un catalogue
fournisseur masque ou disparu est ignore sans erreur. Le tenant_id est
filtre explicitement dans chaque requete (mode repli sous postgres
BYPASSRLS).
"""
from __future__ import annotations

import logging

from sqlalchemy import text

import asyncio

import catalogue_navigation
import catalogue_commun
from database import get_current_tenant, tenant_context, tenant_session
from fournisseur_recherche import _conditions

log = logging.getLogger("blueseatra.catalogue_chiffrage")

# Articles fournisseurs renvoyes en complement de la recherche du selecteur
# de devis : assez pour couvrir un choix, pas assez pour peser sur la page.
LIMITE_RECHERCHE = 40


def _tenant() -> str:
    tenant = get_current_tenant()
    if not tenant:
        raise RuntimeError(
            "catalogue_chiffrage appele sans tenant courant : en mode repli, "
            "l'absence de filtre exposerait tous les tenants.")
    return tenant


async def _etats(session, tenant: str) -> dict[str, bool]:
    r = await session.execute(text("""
        SELECT s.cle, s.actif
          FROM blueseatra.chiffrage_sources s
         WHERE s.tenant_id = :tenant_id
    """), {"tenant_id": tenant})
    return {row[0]: bool(row[1]) for row in r.all()}


async def etats() -> dict[str, bool]:
    """Etat (cle -> actif) des sources choisies par l'entreprise."""
    return await _etats_tenant(_tenant())


async def liste() -> dict:
    """Fournisseurs visibles par l'entreprise, avec leur etat de chiffrage.

    Reutilise le parcours du catalogue fournisseurs (meme visibilite :
    propres imports + catalogue commun non masque) et ajoute le drapeau
    actif_chiffrage. Une source activee puis masquee reste en base mais
    n'est plus proposee : elle reaparaitra si le masquage est leve.
    """
    tenant = _tenant()
    donnees = await catalogue_navigation.fournisseurs()
    etats = await _etats_tenant(tenant)
    sources = []
    for f in donnees.get("fournisseurs", []):
        ligne = dict(f)
        ligne["actif_chiffrage"] = bool(etats.get(f["cle"], False))
        sources.append(ligne)
    return {"sources": sources,
            "total_references": donnees.get("total_references", 0)}


async def _etats_tenant(tenant: str) -> dict[str, bool]:
    async with tenant_session() as session:
        return await _etats(session, tenant)


async def basculer(cle: str, actif: bool, utilisateur: str | None = None) -> dict:
    """Active ou desactive une source pour le chiffrage de CETTE entreprise.

    La cle est validee parmi les fournisseurs visibles (_resoudre de
    catalogue_navigation leve LookupError sinon) : impossible d'activer un
    catalogue d'une autre entreprise ou le catalogue commun masque.
    Desactiver n'efface rien : la ligne passe a actif = false, le contenu
    du fournisseur est intact et reactive en un clic.
    """
    tenant = _tenant()
    async with tenant_session() as session:
        await catalogue_navigation._resoudre(session, tenant, cle)  # LookupError si invalide
        if actif:
            await session.execute(text("""
                INSERT INTO blueseatra.chiffrage_sources
                       (tenant_id, cle, actif, cree_le, maj_le, par)
                VALUES (:tenant_id, :cle, true,
                        to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                        to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                        :par)
                ON CONFLICT (tenant_id, cle) DO UPDATE
                   SET actif = true,
                       maj_le = to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            """), {"tenant_id": tenant, "cle": cle, "par": utilisateur})
        else:
            await session.execute(text("""
                UPDATE blueseatra.chiffrage_sources
                   SET actif = false,
                       maj_le = to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                 WHERE tenant_id = :tenant_id AND cle = :cle
            """), {"tenant_id": tenant, "cle": cle})
        await session.commit()
    log.info("source chiffrage %s (%s) par %s (tenant %s)",
             "activee" if actif else "desactivee", cle, utilisateur, tenant)
    return {"cle": cle, "actif": actif}


# --- Candidats fournisseurs pour le rapprochement d'un devis --------------

def _libelles_extraits(extraits: dict, maxi: int = 15) -> list[str]:
    """Libelles a chercher dans les catalogues fournisseurs : ceux des lignes
    de la demande, sinon la description generale. Uniques, dans l'ordre."""
    libelles = []
    for li in (extraits.get("line_items") or []):
        lb = str(li.get("label") or li.get("description") or "").strip()
        if lb:
            libelles.append(lb)
    if not libelles:
        lb = str(extraits.get("description") or extraits.get("work_type") or "").strip()
        if lb:
            libelles.append(lb)
    vus, uniq = set(), []
    for lb in libelles:
        cle = lb.lower()
        if cle not in vus:
            vus.add(cle)
            uniq.append(lb)
    return uniq[:maxi]


async def candidats_rapprochement(tenant_id: str, extraits: dict,
                                  par_ligne: int = 8) -> list[dict]:
    """Articles candidats des sources fournisseurs ACTIVEES par l'entreprise,
    pour le rapprochement automatique d'un devis.

    Complète le catalogue tarifaire interne (s'il existe) et le remplace
    s'il n'y en a pas : c'est l'entreprise qui choisit ses catalogues de
    chiffrage via les boutons d'activation. Chaque libellé de la demande est
    recherché dans les sources actives (index trigramme) et les meilleures
    offres par libellé deviennent candidates.

    Ne lève JAMAIS : sans source active, sans libellé ou en cas d'erreur,
    retourne [] — la génération du devis ne doit pas échouer pour ça.
    """
    libelles = _libelles_extraits(extraits or {})
    if not libelles:
        return []
    try:
        async with tenant_context(tenant_id):
            # Recherches par libellé en parallele (jeton borne : la base est
            # lointaine et le pool de connexions limite, command_timeout
            # 30 s) : sequentiel, 15 libelles x 3 s = 45 s ; x3, ~15 s.
            sem = asyncio.Semaphore(3)

            async def une_recherche(lb):
                async with sem:
                    return await rechercher(lb, par_ligne)

            resultats = await asyncio.gather(*(une_recherche(lb) for lb in libelles),
                                             return_exceptions=True)
            vus, candidats = set(), []
            for lot in resultats:
                for article in (lot if isinstance(lot, list) else []):
                    if article["id"] not in vus:
                        vus.add(article["id"])
                        candidats.append(article)
            return candidats[:120]
    except Exception:
        log.exception("candidats fournisseurs indisponibles (tenant %s)", tenant_id)
        return []


async def a_sources_actives(tenant_id: str) -> bool:
    """L'entreprise a-t-elle au moins une source fournisseur activee ET
    encore visible ? Distingue « aucune source activee » (la generation de
    devis doit refuser avec le message explicite) de « sources actives mais
    aucune offre ne correspond » (la generation doit produire un devis avec
    des lignes a confirmer, jamais echouer — constate en production le
    01/10/2026 sur « trou evacuation rongeurs » : 0 offre sur 967 563,
    requete refusee a tort).
    """
    try:
        async with tenant_context(tenant_id):
            actifs = {c for c, a in (await _etats_tenant(tenant_id)).items() if a}
            if not actifs:
                return False
            visibles = {f["cle"] for f in
                        (await catalogue_navigation.fournisseurs()).get("fournisseurs", [])}
            return bool(actifs & visibles)
    except Exception:
        log.exception("etat des sources indisponible (tenant %s)", tenant_id)
        return False


# --- Recherche des articles pour le selecteur du devis ---------------------

def _en_article(offre: dict) -> dict:
    """Une offre fournisseur dans la forme d'un pricing_item du selecteur.

    Le selecteur du devis (QuoteEditor) et addFromCatalog ne connaissent que
    les champs des pricing_items : on les fournit tels quels, avec un marqueur
    `source` pour que l'interface affiche la provenance fournisseur. L'id est
    prefixe pour ne jamais entrer en collision avec un pricing_item.
    """
    fournisseur = offre.get("fournisseur")
    return {
        "id": f"frn:{offre['id']}",
        "item_code": offre.get("reference_fournisseur") or offre["id"],
        "item_label": offre.get("designation"),
        "label_norm": None,
        "category": offre.get("famille"),
        "family": offre.get("famille"),
        "unit": offre.get("unite_vente") or "u",
        "brand": offre.get("marque"),
        "supplier_main": fournisseur,
        "suppliers": [fournisseur] if fournisseur else [],
        "unit_price_ht": offre.get("prix_net_ht"),
        "vat_rate": 20,
        "margin": 0,
        "min_qty": offre.get("conditionnement") or 1,
        "currency": "EUR",
        "is_active": True,
        "source": "fournisseur",
        "source_fournisseur": fournisseur,
        "url_produit": offre.get("url_produit"),
    }


async def rechercher(q: str, limite: int = LIMITE_RECHERCHE) -> list[dict]:
    """Articles des catalogues fournisseurs ACTIVES, formes pour le devis.

    Retourne [] sans requete, sans source activee ou en cas d'erreur : le
    chiffrage ne doit jamais echouer a cause d'une source complementaire.
    """
    q = (q or "").strip()
    if not q:
        return []
    tenant = _tenant()
    try:
        actifs = {c for c, a in (await _etats_tenant(tenant)).items() if a}
        if not actifs:
            return []
        # Ne garder que les sources encore visibles (resolution securisee),
        # AVEC leur tenant : chaque source appartient soit a l'entreprise,
        # soit au tenant du catalogue commun -- jamais devine, lu sur le
        # parcours lui-meme. Un filtre par tenant EXACT par branche permet a
        # l'index (tenant_id, version_id) de servir chaque branche ; un OR
        # sur deux tenants, lui, l'empêchait et la requête finissait en
        # TimeoutError (command_timeout 30 s, constate en production).
        visibles = {f["cle"]: f for f in
                    (await catalogue_navigation.fournisseurs()).get("fournisseurs", [])}
        cles = [c for c in actifs if c in visibles]
        if not cles:
            return []

        conds, params, _ = _conditions(q)
        params.update(tenant_id=tenant, commun=catalogue_commun.TENANT_COMMUN, limite=limite)
        # UNION ALL par source : chaque branche profite de l'index
        # (tenant_id, version_id) et de l'index trigramme recherche_norm,
        # puis renvoie ses k meilleures offres. Une clause OR unique sur les
        # 8+ sources actives forçait un parcours quasi complet (30-50 s en
        # production) ; chaque branche top-k coute quelques centaines de ms.
        branches = []
        for i, cle in enumerate(cles):
            params[f"t{i}"] = (catalogue_commun.TENANT_COMMUN
                                 if visibles[cle].get("catalogue_commun") else tenant)
            if cle.startswith("hist:"):
                params[f"h{i}"] = cle[5:]
                filtre = f"""o.tenant_id = :t{i} AND o.supplier_id = :h{i}
                    AND o.is_active
                    AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                        SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = :t{i}))"""
            else:
                # Cle de version : UUID globalement unique, resolue ci-dessus
                # parmi les fournisseurs visibles de cette entreprise, et son
                # tenant derive du parcours (entreprise ou commun) -- jamais
                # de la cle client.
                params[f"v{i}"] = cle
                filtre = f"o.tenant_id = :t{i} AND o.version_id = :v{i} AND o.is_active"
            # Deux temps, comme fournisseur_recherche : (1) la sous-requete
            # SANS tri filtre par trigramme (idx_offers_recherche_trgm) —
            # avec un ORDER BY price dans la branche, le planificateur
            # choisissait le scan de l'index par prix en filtrant les termes
            # rares : 960k lignes parcourues, TimeoutError command_timeout
            # 30 s (constate en production sur "trou evacuation rongeurs") ;
            # (2) le tri par prix se fait ensuite sur les <= 200 id retenus.
            branches.append(f"""
                (SELECT {catalogue_navigation.CHAMPS}
                   FROM (SELECT o.id
                           FROM blueseatra.supplier_offers o
                          WHERE ({filtre})
                            AND ({' AND '.join(conds)})
                          LIMIT 200) sel
                   JOIN blueseatra.supplier_offers o ON o.id = sel.id
                   LEFT JOIN blueseatra.suppliers f
                          ON f.id = o.supplier_id AND f.tenant_id = o.tenant_id)
            """)
        sql = text(f"""
            SELECT * FROM ({' UNION ALL '.join(branches)}) offres
            ORDER BY prix_net_ht ASC NULLS LAST, id
            LIMIT :limite
        """)
        async with tenant_session() as session:
            lignes = [dict(r) for r in (await session.execute(sql, params)).mappings()]
        return [_en_article(l) for l in lignes]
    except Exception:
        log.exception("recherche chiffrage fournisseurs echouee (tenant %s)", tenant)
        return []
