"""Synchronisation demande -> devis : articles suggeres sur les lignes a confirmer.

PROBLEME (12/10/2026)
---------------------
Le devis genere depuis une demande reprend bien les lignes de la demande,
mais en production 332 lignes de devis sont « to_confirm » et 287 d'entre
elles n'ont AUCUNE suggestion d'article : le chiffreur doit rechercher
chaque article a la main pour finaliser le devis. Les suggestions G3 de
la page demande ne sont ni persistees ni reportees dans le devis
(limite documentee dans docs/rgpd-masquage-ia-externe.md).

SOLUTION
--------
Deux routes, montees dans server.py :
    import devis_sync
    api.include_router(devis_sync.build_router(get_current, require_role))

1. POST /requests/{id}/sync-articles-devis
   Pour chaque ligne a confirmer du brouillon lie a la demande, ecrit une
   suggestion d'article (suggested_item_code/label/prix) :
   catalogue tarifaire interne actif d'abord (recherche par mots + BM25 de
   recherche_g3.Index, mesuree le 08/10/2026), puis offres des catalogues
   fournisseurs actives pour le chiffrage (catalogue_chiffrage.rechercher,
   classees pertinence puis prix). Avec ?appliquer=true, la suggestion est
   en outre PRIXEE immediatement (voir route 2).

2. POST /quotes/{id}/appliquer-articles
   Promeut les suggestions deja ecrites : matched_item_code/label, unite,
   prix HT du catalogue (JAMAIS un prix invente par une IA), montant de
   ligne et totaux recalcules. La ligne passe « proposed » : la validation
   humaine en aval est inchangee, le devis reste un brouillon.

Deterministe et sans appel IA : reutilise exactement les memes recherches
que le selecteur d'articles du devis. Chaque ecriture est journalisee
(audit_logs, actions devis.sync_articles / devis.appliquer_articles).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

import catalogue_chiffrage
import matching
import recherche_g3
from database import tenant_context
from pg_adapter import PGDatabase

log = logging.getLogger("blueseatra.devis_sync")

# PGDatabase est sans etat (simple aiguillage nom de table -> modele) :
# une instance par module est sure.
db = PGDatabase()

LIGNES_STRUCTURANTES = {"lot", "sublot", "note", "page_break"}
# Main-d'oeuvre et deplacement sont deja prixes a la generation (tarifs imposes).
LIGNES_DEJA_TARIFEES = {"labor", "travel"}

CHAMPS_SUGGESTION = ("suggested_item_code", "suggested_label", "suggested_unit_price_ht",
                     "suggested_unite", "suggested_origine", "suggested_fournisseur")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _libelle_ligne(ligne: dict) -> str:
    return str(ligne.get("request_label") or ligne.get("description") or "").strip()


def _est_a_sourcer(ligne: dict) -> bool:
    """Ligne de travaux en attente d'un article : ni structure, ni MO/deplacement,
    ni deja matchee, et encore a confirmer."""
    if not isinstance(ligne, dict):
        return False
    if ligne.get("line_type") in LIGNES_STRUCTURANTES | LIGNES_DEJA_TARIFEES:
        return False
    if ligne.get("matched_item_code"):
        return False
    return ligne.get("status") == "to_confirm"


async def _catalogue_actif(tenant_id: str) -> list[dict]:
    """Articles de la version active du catalogue tarifaire de l'entreprise."""
    cat = await db.catalogs.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not cat or not cat.get("active_version_id"):
        return []
    return await db.pricing_items.find(
        {"tenant_id": tenant_id, "version_id": cat["active_version_id"]}, {"_id": 0}
    ).to_list(5000)


async def _meilleur_fournisseur(libelle: str) -> dict | None:
    """Meilleure offre des catalogues fournisseurs actives (pertinence puis prix).

    La requete materiau (mots de l'article, pas de la prestation) est
    essayee d'abord, puis le libelle complet -- meme repli que
    candidats_rapprochement du 04/10/2026.
    """
    for q in (catalogue_chiffrage.requete_materielle(libelle), libelle):
        q = (q or "").strip()
        if len(q) < 3:
            continue
        offres = await catalogue_chiffrage.rechercher(q, 4)
        if offres:
            return offres[0]
    return None


def _en_suggestion(article: dict, origine: str) -> dict:
    return {
        "suggested_item_code": article.get("item_code"),
        "suggested_label": article.get("item_label"),
        "suggested_unit_price_ht": article.get("unit_price_ht"),
        "suggested_unite": article.get("unit"),
        "suggested_origine": origine,
        "suggested_fournisseur": article.get("source_fournisseur") or article.get("supplier_main"),
    }


async def suggerer_pour_ligne(ligne: dict, index: recherche_g3.Index,
                              avec_fournisseurs: bool = True) -> dict | None:
    """Meilleur article pour une ligne a confirmer : interne d'abord, fournisseur sinon."""
    libelle = _libelle_ligne(ligne)
    if len(libelle) < 3:
        return None
    if index.articles:
        candidats = index.candidats(matching.article_only(libelle) or libelle, n=1)
        if candidats:
            return _en_suggestion(candidats[0], "catalogue")
    if avec_fournisseurs:
        offre = await _meilleur_fournisseur(libelle)
        if offre:
            return _en_suggestion(offre, "fournisseur")
    return None


def _appliquer(ligne: dict) -> bool:
    """Promeut la suggestion en article prixe. Retourne True si applique.

    Le prix vient TOUJOURS du catalogue (interne ou offre fournisseur) ;
    sans prix catalogue la ligne reste a confirmer, jamais de prix invente.
    TVA laissee vide (consigne en vigueur). Le statut passe « proposed » :
    la validation humaine reste obligatoire avant envoi du devis.
    """
    code = ligne.get("suggested_item_code")
    if not code:
        return False
    try:
        prix = float(ligne.get("suggested_unit_price_ht"))
    except (TypeError, ValueError):
        return False
    ligne["matched_item_code"] = code
    ligne["matched_label"] = ligne.get("suggested_label")
    if ligne.get("suggested_unite"):
        ligne["unit"] = ligne["suggested_unite"]
    ligne["unit_price_ht"] = prix
    ligne["line_ht"] = matching.line_amount_ht(ligne.get("qty"), prix, 0)
    if ligne.get("qty") is not None:
        ligne["status"] = "proposed"
    origine = ligne.get("suggested_origine") or "catalogue"
    ligne["reasons"] = list(ligne.get("reasons") or []) + ["sync_demande", f"origine_{origine}"]
    for cle in CHAMPS_SUGGESTION:
        ligne.pop(cle, None)
    return True


def _totaux(lines: list) -> tuple[float, float, float]:
    """(total_ht, total_vat, total_ttc) : somme des montants des lignes.

    TVA volontairement vide (consigne en vigueur) : total_ttc == total_ht.
    """
    ht = round(sum(float(l["line_ht"]) for l in lines
                   if isinstance(l, dict) and isinstance(l.get("line_ht"), (int, float))), 2)
    return ht, 0.0, ht


async def _enregistrer(tenant_id: str, quote_id: str, lines: list,
                       actor: str, action: str, meta: dict) -> None:
    total_ht, total_vat, total_ttc = _totaux(lines)
    await db.quotes.update_one(
        {"id": quote_id, "tenant_id": tenant_id},
        {"$set": {"lines": lines, "total_ht": total_ht,
                  "total_vat": total_vat, "total_ttc": total_ttc}})
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "tenant_id": tenant_id, "actor": actor,
        "action": action, "target": quote_id, "meta": meta,
        "created_at": _now_iso()})


async def sync_request_quotes(tenant_id: str, request_id: str, actor: str,
                              appliquer: bool = False) -> dict:
    """Ecrit une suggestion d'article sur chaque ligne a confirmer du
    brouillon le plus recent de la demande (et les prixe si appliquer)."""
    req = await db.requests.find_one({"id": request_id, "tenant_id": tenant_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "Demande introuvable")
    devis = await db.quotes.find_one(
        {"tenant_id": tenant_id, "request_id": request_id, "status": "draft"},
        {"_id": 0}, sort=[("created_at", -1)])
    if not devis:
        raise HTTPException(409, "Aucun brouillon de devis pour cette demande : "
                                 "generez-le d'abord (bouton « Generer un devis »).")
    async with tenant_context(tenant_id):
        items = await _catalogue_actif(tenant_id)
        index = recherche_g3.Index(items)
        fournisseurs = await catalogue_chiffrage.a_sources_actives(tenant_id)
        lines = list(devis.get("lines") or [])

        cibles = [l for l in lines if _est_a_sourcer(l) and not l.get("suggested_item_code")]
        sem = asyncio.Semaphore(3)  # meme enveloppe que la recherche du selecteur

        async def _une(ligne: dict) -> int:
            async with sem:
                sug = await suggerer_pour_ligne(ligne, index, fournisseurs)
                if sug:
                    ligne.update(sug)
                    return 1
                return 0

        resultats = await asyncio.gather(*(_une(l) for l in cibles), return_exceptions=True)
        proposees = sum(r for r in resultats if isinstance(r, int))
        if any(isinstance(r, Exception) for r in resultats):
            log.warning("sync-articles : %d ligne(s) en echec (devis %s)",
                        sum(1 for r in resultats if isinstance(r, Exception)), devis["id"])

        appliquees = 0
        if appliquer:
            for ligne in lines:
                if _est_a_sourcer(ligne) and ligne.get("suggested_item_code") and _appliquer(ligne):
                    appliquees += 1

        if proposees or appliquees:
            await _enregistrer(tenant_id, devis["id"], lines, actor, "devis.sync_articles",
                               {"request_id": request_id, "suggestions": proposees,
                                "appliquees": appliquees})

    return {
        "quote_id": devis["id"],
        "lignes_a_confirmer": sum(1 for l in lines if _est_a_sourcer(l)),
        "suggestions": proposees,
        "appliquees": appliquees,
        "catalogue_interne": len(items),
        "catalogues_fournisseurs": bool(fournisseurs),
    }


async def apply_quote_suggestions(tenant_id: str, quote_id: str, actor: str) -> dict:
    """Promeut les suggestions existantes d'un brouillon en lignes pricees."""
    devis = await db.quotes.find_one({"id": quote_id, "tenant_id": tenant_id}, {"_id": 0})
    if not devis:
        raise HTTPException(404, "Devis introuvable")
    if devis.get("status") != "draft":
        raise HTTPException(409, "Seul un brouillon peut etre modifie")
    lines = list(devis.get("lines") or [])
    appliquees = 0
    for ligne in lines:
        if isinstance(ligne, dict) and _est_a_sourcer(ligne) and _appliquer(ligne):
            appliquees += 1
    if not appliquees:
        return {"quote_id": quote_id, "appliquees": 0,
                "remarque": "Aucune suggestion a appliquer : lancez d'abord la "
                            "synchronisation (bouton « Reporter dans le devis » de la demande)."}
    await _enregistrer(tenant_id, quote_id, lines, actor, "devis.appliquer_articles",
                       {"appliquees": appliquees})
    return {"quote_id": quote_id, "appliquees": appliquees,
            "total_ht": _totaux(lines)[0]}


def build_router(get_current, require_role) -> APIRouter:
    """Routes de synchronisation demande -> devis (meme patron que clients_module)."""
    r = APIRouter()
    ecriture = Depends(require_role("owner", "admin", "operator"))

    @r.post("/requests/{request_id}/sync-articles-devis")
    async def sync_articles_devis(request_id: str,
                                  appliquer: bool = Query(False),
                                  cu=ecriture):
        actor = getattr(cu, "email", None) or getattr(cu, "id", None) or "inconnu"
        return await sync_request_quotes(cu.tenant_id, request_id, actor, appliquer)

    @r.post("/quotes/{quote_id}/appliquer-articles")
    async def appliquer_articles(quote_id: str, cu=ecriture):
        actor = getattr(cu, "email", None) or getattr(cu, "id", None) or "inconnu"
        return await apply_quote_suggestions(cu.tenant_id, quote_id, actor)

    return r
