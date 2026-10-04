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

import json
import logging
import re
import time

from sqlalchemy import text

import asyncio

import catalogue_navigation
import catalogue_commun
import pertinence
from designation_fournisseur import designation_affichee
from database import get_current_tenant, tenant_context, tenant_session
from fournisseur_recherche import termes_recherche

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
    invalider_sources(tenant)
    return {"cle": cle, "actif": actif}


# --- Candidats fournisseurs pour le rapprochement d'un devis --------------

# Mots d'une prestation (pas d'un article) : ils ne figurent JAMAIS dans
# une désignation catalogue et cassent la recherche AND-tous-les-mots.
# Constat réel du 04/10/2026 (devis BS-2026-0055) : « fourniture et pose de
# prises 2p+t 16 a, gamme blanche standard » = 10 mots → 0 résultat, alors
# que le catalogue Rexel vend des prises 2P+T. La requête matériau courte
# (« prise 2p+t 16 a ») les trouve toutes.
_MOTS_PRESTATION = re.compile(
    r"\b(?:fourniture|fournitures|fournir|pose|poses|et|de|des|du|d|un|une|"
    r"le|la|les|avec|pour|sur|sous|au|aux|en|"
    r"installation|installe|installee|installer|creation|creations|creer|"
    r"mise|place|adaptation|protection|proteger|reparation|reparer|"
    r"remplacement|remplacer|depose|deposer|evacuation|evacuer|"
    r"raccordement|raccordements|raccorder|essais|essai|verifier|"
    r"verification|verifications|etiquette|remise|gamme|standard|type|"
    r"existant|existants|existante|existantes|chantier|appareillage|"
    r"appareillages|element|elements|dechet|dechets|gravat|gravats|"
    r"dedie|dediee|dediees|dedie)\b", re.I)

# Mots d'UNE lettre ambigus : « a » et « l » sont tantôt des articles (à
# retirer), tantôt des UNITÉS après un chiffre (« 16 a » = ampères,
# « 150 l » = litres — jamais retirés).
_MOTS_UNE_LETTRE = {"a", "l", "à"}


def requete_materielle(label: str) -> str:
    """Extrait la requête ARTICLE d'un libellé de prestation.

    « fourniture et pose de prises 2p+t 16 a, gamme blanche standard »
      → « prise 2p+t 16 a »
    « fourniture et pose d'un chauffe-eau electric vertical 150 l, ... »
      → « chauffe eau electric vertical 150 l »

    Règles : coupe à la première virgule (les qualificatifs qui suivent
    décrivent la prestation, pas l'article), retire les mots de prestation
    (une lettre après un chiffre = une unité, conservée), singulierise les
    pluriels longs. Le résultat est NORMALISÉ (mêmes règles que
    pertinence.normalise) : prêt pour une recherche catalogue.
    """
    s = str(label or "").strip()
    if not s:
        return ""
    s = s.split(",")[0]
    s = _MOTS_PRESTATION.sub(" ", s)
    mots = pertinence.normalise(s).split()
    gardes = []
    for i, m in enumerate(mots):
        if m in _MOTS_UNE_LETTRE:
            precedent = mots[i - 1] if i > 0 else ""
            if not (precedent[:-1].isdigit() or precedent.isdigit()):
                continue  # article, pas une unité
        gardes.append(m)
    # Singulier des pluriels longs (prises -> prise) : les désignations
    # catalogue sont majoritairement au singulier.
    singuliers = [m[:-1] if len(m) > 4 and m.endswith("s") and not m.endswith("ss") else m
                  for m in gardes]
    return " ".join(singuliers)


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
            # 04/10/2026 : la recherche se fait sur la REQUÊTE MATÉRIAU
            # (mots de l'article, pas de la prestation) — un libellé de
            # devis de 10 mots ne matche aucune désignation catalogue avec
            # la sémantique AND-tous-les-mots. Repli sur le libellé complet
            # si la requête matériau ne trouve rien.
            sem = asyncio.Semaphore(3)

            async def une_recherche(lb):
                async with sem:
                    for q in (requete_materielle(lb), lb):
                        if not q:
                            continue
                        offres = await rechercher(q, par_ligne)
                        if offres:
                            return offres
                    return []

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


async def meilleures_offres_par_ligne(tenant_id: str, extraits: dict,
                                      par_ligne: int = 6) -> dict[str, list[dict]]:
    """Meilleures offres fournisseurs PAR LIGNE de la demande, pour le menu
    de choix par ligne dans l'éditeur de devis (04/10/2026).

    Renvoie {libellé_normalisé: [offres]} — chaque offre avec fournisseur,
    désignation, référence, prix net HT et unité. L'offre de tête est celle
    que le devis applique par défaut (pertinence puis prix, la recherche
    classe déjà ainsi) ; les suivantes sont les alternatives du menu.

    Ne lève JAMAIS : sans source active, sans libellé ou en erreur, {}.
    """
    libelles = _libelles_extraits(extraits or {})
    if not libelles:
        return {}
    try:
        async with tenant_context(tenant_id):
            sem = asyncio.Semaphore(3)

            async def une_recherche(lb):
                async with sem:
                    for q in (requete_materielle(lb), lb):
                        if not q or len(q) < 3:
                            continue
                        offres = await rechercher(q, par_ligne)
                        if offres:
                            return lb, offres
                    return lb, []

            resultats = await asyncio.gather(*(une_recherche(lb) for lb in libelles),
                                             return_exceptions=True)
            sortie: dict[str, list[dict]] = {}
            for res in resultats:
                if not isinstance(res, tuple):
                    continue
                lb, offres = res
                if offres:
                    sortie[lb.lower()] = offres
            return sortie
    except Exception:
        log.exception("offres par ligne indisponibles (tenant %s)", tenant_id)
        return {}


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
        "item_label": designation_affichee(
            offre.get("designation"), offre.get("marque"),
            offre.get("reference_fabricant"), offre.get("reference_fournisseur")),
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


# Sources actives et visibles d'une entreprise, gardees 20 s (02/10/2026).
# Mesure en production : relire les bascules puis la liste des fournisseurs
# coutait 2 sessions (~400 ms) a CHAQUE frappe dans la recherche d'articles du
# devis. Invalide aussitot par basculer() et par le masquage du catalogue
# commun (catalogue_commun.masquer*) ; une activation de version faite par le
# script d'import (hors API) est prise en compte en 20 s au plus.
_SOURCES_TTL_S = 20.0
_cache_sources: dict[str, tuple[float, list[str], dict]] = {}


_cache_visibles: dict[str, tuple[float, list[str]]] = {}


def invalider_sources(tenant: str | None = None) -> None:
    if tenant is None:
        _cache_sources.clear()
        _cache_visibles.clear()
    else:
        _cache_sources.pop(tenant, None)
        _cache_visibles.pop(tenant, None)


async def sources_visibles(tenant: str) -> list[str]:
    """Cles de toutes les sources VISIBLES (comparateur), gardees 20 s.

    Meme invalidation que _sources_recherche : bascule, masquage du
    catalogue commun.
    """
    entree = _cache_visibles.get(tenant)
    if entree and entree[0] > time.monotonic():
        return entree[1]
    cles = [f["cle"] for f in
            (await catalogue_navigation.fournisseurs()).get("fournisseurs", []) if f.get("cle")]
    _cache_visibles[tenant] = (time.monotonic() + _SOURCES_TTL_S, cles)
    return cles


async def _sources_recherche(tenant: str) -> tuple[list[str], dict]:
    """(cles des sources actives ET visibles, fournisseurs visibles par cle)."""
    entree = _cache_sources.get(tenant)
    if entree and entree[0] > time.monotonic():
        return entree[1], entree[2]
    actifs = {c for c, a in (await _etats_tenant(tenant)).items() if a}
    visibles = {}
    if actifs:
        visibles = {f["cle"]: f for f in
                    (await catalogue_navigation.fournisseurs()).get("fournisseurs", [])}
    cles = [c for c in actifs if c in visibles]
    _cache_sources[tenant] = (time.monotonic() + _SOURCES_TTL_S, cles, visibles)
    return cles, visibles


# Recherche parallele : au plus 3 groupes, et au plus 4 sessions de recherche
# simultanees pour tout le processus (pool metier : 5 + 2 connexions), afin de
# laisser des connexions libres aux autres requetes.
_GROUPES_MAX = 3
_SOURCES_PAR_GROUPE_MIN = 3
_SEUIL_PETITE_SOURCE = 2000
_sessions_recherche = asyncio.Semaphore(4)


def repartir_sources(cles: list[str], visibles: dict) -> list[list[str]]:
    """Repartit les sources en groupes de cout comparable.

    Le cout d'une source est a peu pres constant au-dela de quelques
    milliers de references (balayage de l'index trigramme) et quasi nul en
    dessous (index par version). Plus grosse d'abord, dans le groupe le
    moins charge ; l'ordre des cles est conserve dans chaque groupe.
    """
    if len(cles) <= _SOURCES_PAR_GROUPE_MIN:
        return [list(cles)]
    n = min(_GROUPES_MAX, -(-len(cles) // _SOURCES_PAR_GROUPE_MIN))
    poids = {c: (1.0 if int((visibles.get(c) or {}).get("references") or 0) > _SEUIL_PETITE_SOURCE
                 else 0.1) for c in cles}
    charges = [0.0] * n
    groupes: list[list[str]] = [[] for _ in range(n)]
    for c in sorted(cles, key=lambda c: -poids[c]):
        i = charges.index(min(charges))
        groupes[i].append(c)
        charges[i] += poids[c]
    rang = {c: k for k, c in enumerate(cles)}
    return [sorted(g, key=rang.get) for g in groupes if g]


async def _chercher_groupe(cles: list[str], visibles: dict, tenant: str,
                           termes: list, limite: int) -> list[dict]:
    """Offres les moins cheres d'un groupe de sources, dans sa propre session."""
    params = {"tenant_id": tenant, "commun": catalogue_commun.TENANT_COMMUN,
              "limite": limite, "termes": json.dumps(termes)}
    # Une branche par source active : blueseatra.offres_candidates
    # renvoie jusqu'a 200 identifiants par source via l'index
    # trigramme. Sous RLS, une requete directe ne pouvait pas l'utiliser
    # (LIKE n'est pas LEAKPROOF) : TimeoutError (command_timeout 30 s)
    # constate en production le 01/10/2026 sur "prise". La fonction
    # refuse tout tenant autre que l'entreprise ou le catalogue commun ;
    # le tenant de chaque branche vient du parcours, jamais du client.
    branches = []
    for i, cle in enumerate(cles):
        params[f"t{i}"] = [catalogue_commun.TENANT_COMMUN
                           if visibles[cle].get("catalogue_commun") else tenant]
        params[f"v{i}"] = None if cle.startswith("hist:") else cle
        params[f"h{i}"] = cle[5:] if cle.startswith("hist:") else None
        branches.append(
            f"SELECT c.id FROM blueseatra.offres_candidates("
            f"CAST(:t{i} AS text[]), CAST(:termes AS jsonb), 200, "
            f":v{i}, :h{i}, false, false) c")
    sql = text(f"""
        WITH sel AS MATERIALIZED ({' UNION ALL '.join(branches)})
        SELECT {catalogue_navigation.CHAMPS}
          FROM sel
          JOIN blueseatra.supplier_offers o ON o.id = sel.id
          LEFT JOIN blueseatra.suppliers f
                 ON f.id = o.supplier_id AND f.tenant_id = o.tenant_id
         WHERE (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
         ORDER BY o.price_ht ASC NULLS LAST, o.id
         LIMIT :limite
    """)
    async with _sessions_recherche:
        async with tenant_session() as session:
            return [dict(r) for r in (await session.execute(sql, params)).mappings()]


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
        # Ne garder que les sources encore visibles (resolution securisee),
        # AVEC leur tenant : chaque source appartient soit a l'entreprise,
        # soit au tenant du catalogue commun -- jamais devine, lu sur le
        # parcours lui-meme. Un filtre par tenant EXACT par branche permet a
        # l'index (tenant_id, version_id) de servir chaque branche ; un OR
        # sur deux tenants, lui, l'empêchait et la requête finissait en
        # TimeoutError (command_timeout 30 s, constate en production).
        cles, visibles = await _sources_recherche(tenant)
        if not cles:
            return []

        termes = termes_recherche(q)
        if not termes:
            return []
        # Sources reparties en groupes interroges EN PARALLELE, chacun dans sa
        # session (02/10/2026). Mesure en production : chaque source paie
        # ~35 ms d'index trigramme pour un mot long (« disjoncteur »), en
        # serie dans une seule requete : 9 sources = ~330 ms. Chaque groupe
        # renvoie ses `limite` offres les moins cheres ; le meilleur
        # `limite` global est donc exactement le meme qu'en une requete.
        groupes = repartir_sources(cles, visibles)
        if len(groupes) == 1:
            lignes = await _chercher_groupe(groupes[0], visibles, tenant, termes, limite)
        else:
            resultats = await asyncio.gather(
                *(_chercher_groupe(g, visibles, tenant, termes, limite) for g in groupes))
            lignes = [l for r in resultats for l in r]
        # Pertinence d'abord, prix ensuite : la designation qui MENE avec les
        # mots demandes (« bloc porte coupe feu ») passe devant l'accessoire
        # moins cher qui les mentionne en fin de libelle (« gache pour
        # porte coupe-feu »). Egalite de score -> prix croissant, comme avant.
        lignes.sort(key=lambda l: (
            -pertinence.score(pertinence.normalise(l.get("designation") or ""), q),
            l.get("prix_net_ht") is None, l.get("prix_net_ht") or 0.0, str(l.get("id"))))
        lignes = lignes[:limite]
        return [_en_article(l) for l in lignes]
    except Exception:
        log.exception("recherche chiffrage fournisseurs echouee (tenant %s)", tenant)
        return []
