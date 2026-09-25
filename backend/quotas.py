"""Compteurs et quotas par entreprise (ticket #89).

Ce qui est compté
-----------------
- ``devis_ia`` : une demande lue et structurée par l'IA (un devis assisté).
- ``page_lue`` : une page lue sur photo ou scan (PDF sans calque texte,
  image). Un PDF au calque texte lisible ne consomme aucune page.

Tout le reste (devis manuels, PDF, catalogues, catalogue commun,
comparateur) est illimité et n'est jamais compté.

Où vit la logique
-----------------
Dans la base (migration 20260925090000) : registre en ajout seul, verrou
par entreprise, dotation du mois, forfait avant recharges. Ce module ne
fait qu'appeler ``quota_reserver`` / ``quota_annuler`` et lire les soldes,
qui sont toujours la somme des lignes du registre.

Application ou observation
--------------------------
``BLUESEATRA_QUOTAS_APPLIQUES=1`` : au-delà du quota, la demande est
refusée par une erreur 402 claire (jamais 500). Par défaut : mode
observation, tout est compté et rien n'est refusé, pour vérifier les
compteurs en production avant de les appliquer.

Disponibilité
-------------
Si la migration n'est pas encore appliquée (tables absentes), les
fonctions journalisent un avertissement et laissent passer : un compteur
manquant ne doit jamais empêcher une entreprise de travailler.
"""
from __future__ import annotations

import json
import logging
import os

from sqlalchemy import text

from database import get_current_tenant, tenant_session

log = logging.getLogger("blueseatra.quotas")

UNITES = ("devis_ia", "page_lue")

MESSAGES = {
    "essai_termine": "Votre essai de 14 jours est terminé. Choisissez une offre pour continuer "
                     "à préparer des devis avec l'IA ; vos données restent consultables.",
    "lecture_seule": "Votre espace est en lecture seule. Réglez votre abonnement pour relancer "
                     "la préparation de devis par l'IA.",
    "suspendu": "Votre espace est suspendu. Contactez Blueseatra.",
    "quota_atteint_devis_ia": "Vous avez utilisé tous les devis assistés par l'IA de votre offre "
                              "pour cette période. Ajoutez une recharge ou passez à l'offre "
                              "supérieure ; la saisie manuelle reste disponible.",
    "quota_atteint_page_lue": "Vous avez utilisé toutes les pages lues (photos et scans) de votre "
                              "offre pour cette période. Ajoutez une recharge, ou envoyez un PDF "
                              "avec texte, qui ne consomme aucune page.",
}


def quotas_appliques() -> bool:
    return os.environ.get("BLUESEATRA_QUOTAS_APPLIQUES", "0").strip().lower() in ("1", "true", "oui")


class QuotaAtteint(Exception):
    """Levée uniquement en mode application ; convertie en HTTP 402."""

    def __init__(self, motif: str):
        self.motif = motif
        super().__init__(MESSAGES.get(motif, "Quota atteint."))


def _tenant() -> str:
    t = get_current_tenant()
    if not t:
        raise RuntimeError("quotas appelé sans tenant courant")
    return t


def _migration_absente(exc: Exception) -> bool:
    nom = type(getattr(exc, "orig", exc)).__name__
    msg = str(exc)
    return ("UndefinedTable" in nom or "UndefinedFunction" in nom
            or "does not exist" in msg or "n'existe pas" in msg)


def pages_a_compter(source_type: str | None, nb_pages_vision: int = 0) -> int:
    """Pages lues visuellement pour une nouvelle demande."""
    if source_type == "pdf_ocr":
        return max(int(nb_pages_vision or 0), 0)
    if source_type == "image":
        return 1
    return 0


async def reserver(demande_id: str | None, devis: int, pages: int, acteur: str | None) -> dict:
    """Réserve les unités d'une demande. Lève QuotaAtteint en mode application."""
    if devis <= 0 and pages <= 0:
        return {"autorise": True, "rien_a_compter": True}
    tenant = _tenant()
    bloquer = quotas_appliques()
    try:
        async with tenant_session() as s:
            r = await s.execute(text(
                "SELECT blueseatra.quota_reserver(:tenant_id, :demande, :devis, :pages, :acteur, :bloquer)"),
                {"tenant_id": tenant, "demande": demande_id, "devis": int(devis),
                 "pages": int(pages), "acteur": acteur, "bloquer": bloquer})
            res = r.scalar_one()
            await s.commit()
    except Exception as exc:  # noqa: BLE001
        if _migration_absente(exc):
            log.warning("quotas : migration absente, consommation non comptée (%s)", exc)
        else:
            # Un compteur en panne ne doit jamais empêcher une entreprise de
            # travailler : on laisse passer et on le signale dans les journaux.
            log.exception("quotas : réservation impossible, demande %s laissée passer", demande_id)
        return {"autorise": True, "non_compte": True}
    if isinstance(res, str):
        res = json.loads(res)
    if not res.get("autorise"):
        raise QuotaAtteint(res.get("motif") or "quota_atteint")
    if res.get("depassement"):
        log.info("quotas (observation) : dépassement %s pour le tenant %s", res.get("motif"), tenant)
    return res


async def annuler(demande_id: str, motif: str) -> int:
    """Rend les unités d'une demande (extraction échouée). Idempotent."""
    tenant = _tenant()
    try:
        async with tenant_session() as s:
            r = await s.execute(text(
                "SELECT blueseatra.quota_annuler(:tenant_id, :demande, :motif)"),
                {"tenant_id": tenant, "demande": demande_id, "motif": (motif or "")[:300]})
            n = int(r.scalar_one() or 0)
            await s.commit()
            return n
    except Exception as exc:  # noqa: BLE001
        if _migration_absente(exc):
            return 0
        log.exception("quotas : annulation impossible pour la demande %s", demande_id)
        return 0


_SQL_ETAT = """
    SELECT a.offre_code, a.statut, a.periode_debut, a.essai_fin_le, a.sieges_supplementaires,
           o.nom, o.prix_mensuel_ht_cents, o.sieges, o.devis_ia, o.pages_lues, o.import_mo,
           o.essai_jours, blueseatra.quota_periode(a, o) AS periode_courante,
           CASE WHEN o.essai_jours IS NOT NULL THEN a.essai_fin_le
                ELSE blueseatra.quota_periode(a, o) + interval '1 month' END AS periode_fin
      FROM blueseatra.quota_abonnement(:tenant_id) a
      JOIN blueseatra.offres o ON o.code = a.offre_code
"""

_SQL_SOLDES = """
    SELECT unite,
           coalesce(sum(quantite) FILTER (WHERE reserve = 'forfait' AND nature = 'dotation'
                                          AND periode_debut = :periode), 0) AS dotation,
           coalesce(-sum(quantite) FILTER (WHERE reserve = 'forfait' AND nature IN ('consommation', 'annulation')
                                           AND periode_debut = :periode), 0) AS utilise_forfait,
           coalesce(-sum(quantite) FILTER (WHERE reserve = 'recharge' AND nature IN ('consommation', 'annulation')
                                           AND cree_le >= :periode), 0) AS utilise_recharge,
           coalesce(sum(quantite) FILTER (WHERE reserve = 'forfait' AND periode_debut = :periode), 0) AS solde_forfait,
           coalesce(sum(quantite) FILTER (WHERE reserve = 'recharge'), 0) AS solde_recharge
      FROM blueseatra.registre_consommation
     WHERE tenant_id = :tenant_id
     GROUP BY unite
"""


def projeter(utilise: int, inclus, recharge: int, debut, fin, maintenant=None) -> dict:
    """Projection linéaire à la fin de la période, et date d'épuisement prévue.

    Rythme = consommation depuis le début de la période / jours écoulés
    (au moins un jour, pour ne pas extrapoler une seule heure d'activité).
    """
    from datetime import datetime, timezone
    maintenant = maintenant or datetime.now(timezone.utc)
    if not debut or not fin:
        return {"projection_fin_periode": None, "epuisement_prevu_le": None}
    ecoules = max((maintenant - debut).total_seconds() / 86400, 1.0)
    total = max((fin - debut).total_seconds() / 86400, ecoules)
    rythme = utilise / ecoules
    projete = int(round(rythme * total))
    epuise = None
    if inclus is not None and rythme > 0:
        from datetime import timedelta
        restant = max(int(inclus) + int(recharge or 0) - utilise, 0)
        date = maintenant + timedelta(days=restant / rythme)
        if date < fin:
            epuise = date.isoformat()
    return {"rythme_par_jour": round(rythme, 2), "projection_fin_periode": projete, "epuisement_prevu_le": epuise}


_SQL_RAPPROCHEMENT = """
    WITH net AS (
        SELECT demande_id, -sum(quantite) AS consomme
          FROM blueseatra.registre_consommation
         WHERE tenant_id = :tenant_id AND unite = 'devis_ia' AND demande_id IS NOT NULL
           AND nature IN ('consommation', 'annulation')
         GROUP BY demande_id
    ), debut AS (
        SELECT min(cree_le) AS le FROM blueseatra.registre_consommation WHERE tenant_id = :tenant_id
    )
    SELECT r.id, r.title, r.status, r.created_at, coalesce(n.consomme, 0) AS consomme
      FROM blueseatra.requests r
      LEFT JOIN net n ON n.demande_id = r.id
     WHERE r.tenant_id = :tenant_id
       AND r.created_at >= coalesce((SELECT to_char(le AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') FROM debut), '9999')
"""


async def rapprochement() -> dict:
    """Compare chaque demande IA au registre (ticket #89).

    Attendu : une demande lue (done, needs_review) a consommé exactement 1
    devis assisté ; une demande en échec a été remboursée (0) ; une demande en
    cours est réservée (1) ou pas encore comptée (0). Tout autre cas est un
    écart à examiner. Lecture seule.
    """
    tenant = _tenant()
    try:
        async with tenant_session() as s:
            rows = (await s.execute(text(_SQL_RAPPROCHEMENT), {"tenant_id": tenant})).mappings().all()
    except Exception as exc:  # noqa: BLE001
        if _migration_absente(exc):
            return {"disponible": False}
        raise
    ecarts, resume = [], {"lues": 0, "echouees": 0, "en_cours": 0}
    for r in rows:
        st, c = r["status"], int(r["consomme"] or 0)
        if st in ("done", "needs_review"):
            resume["lues"] += 1
            ok = c == 1
        elif st in ("failed", "error"):
            resume["echouees"] += 1
            ok = c == 0
        else:
            resume["en_cours"] += 1
            ok = c in (0, 1)
        if not ok:
            ecarts.append({"demande_id": r["id"], "titre": r["title"], "statut": st, "consomme": c})
    return {"disponible": True, "demandes_examinees": len(rows), **resume,
            "ecarts": ecarts, "conforme": not ecarts}


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


async def etat(nb_membres: int | None = None) -> dict:
    """Offre, période et jauges de l'entreprise courante (lecture seule)."""
    tenant = _tenant()
    try:
        async with tenant_session() as s:
            a = (await s.execute(text(_SQL_ETAT), {"tenant_id": tenant})).mappings().one()
            soldes = {r["unite"]: dict(r) for r in (await s.execute(
                text(_SQL_SOLDES), {"tenant_id": tenant, "periode": a["periode_courante"]})).mappings().all()}
            await s.commit()   # l'essai est créé au premier affichage
    except Exception as exc:  # noqa: BLE001
        if _migration_absente(exc):
            return {"disponible": False, "application": quotas_appliques()}
        raise
    jauges = {}
    for u, inclus in (("devis_ia", a["devis_ia"]), ("page_lue", a["pages_lues"])):
        so = soldes.get(u, {})
        utilise = int(so.get("utilise_forfait") or 0) + int(so.get("utilise_recharge") or 0)
        recharge = max(int(so.get("solde_recharge") or 0), 0)
        jauges[u] = {
            "inclus": inclus,
            "utilise": utilise,
            "recharge_restante": recharge,
            # Avant la première consommation de la période, la dotation n'est
            # pas encore écrite : le forfait restant vaut alors l'inclus.
            "restant": None if inclus is None
            else max((int(so.get("solde_forfait") or 0) if so.get("dotation") else
                      inclus - int(so.get("utilise_forfait") or 0)), 0) + recharge,
        }
    for u, j in jauges.items():
        j.update(projeter(j["utilise"], j["inclus"], j["recharge_restante"],
                          a["periode_courante"], a["periode_fin"]))
    sieges_inclus = None if a["sieges"] is None else a["sieges"] + int(a["sieges_supplementaires"] or 0)
    return {
        "disponible": True,
        "application": quotas_appliques(),
        "offre": {"code": a["offre_code"], "nom": a["nom"],
                  "prix_mensuel_ht": None if a["prix_mensuel_ht_cents"] is None
                  else a["prix_mensuel_ht_cents"] / 100,
                  "import_mo": a["import_mo"]},
        "statut": a["statut"],
        "essai_fin_le": _iso(a["essai_fin_le"]),
        "periode": {"debut": _iso(a["periode_courante"]), "fin": _iso(a["periode_fin"])},
        "jauges": jauges,
        "sieges": {"inclus": sieges_inclus, "utilises": nb_membres},
    }


async def historique(limite: int = 50, decalage: int = 0) -> list[dict]:
    tenant = _tenant()
    limite = max(1, min(int(limite), 200))
    decalage = max(0, int(decalage))
    try:
        async with tenant_session() as s:
            rows = (await s.execute(text("""
                SELECT id, cree_le, unite, quantite, nature, reserve, periode_debut,
                       demande_id, annule_id, acteur, motif
                  FROM blueseatra.registre_consommation
                 WHERE tenant_id = :tenant_id
                 ORDER BY cree_le DESC, id DESC
                 LIMIT :limite OFFSET :decalage
            """), {"tenant_id": tenant, "limite": limite, "decalage": decalage})).mappings().all()
    except Exception as exc:  # noqa: BLE001
        if _migration_absente(exc):
            return []
        raise
    return [{k: _iso(v) for k, v in dict(r).items()} for r in rows]


async def verifier_siege(nb_membres_actuels: int) -> None:
    """Refuse (en mode application) un membre au-delà des sièges de l'offre."""
    if not quotas_appliques():
        return
    e = await etat()
    if not e.get("disponible"):
        return
    inclus = e["sieges"]["inclus"]
    if inclus is not None and nb_membres_actuels >= inclus:
        raise QuotaAtteint("sieges")


MESSAGES["sieges"] = ("Tous les sièges de votre offre sont occupés. Ajoutez un siège "
                      "(15 € HT par mois) ou passez à l'offre supérieure.")
