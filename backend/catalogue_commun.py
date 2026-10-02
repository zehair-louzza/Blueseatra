"""Catalogue fournisseurs COMMUN a toutes les entreprises.

Modele
------
Le catalogue commun (version test du referentiel TCE 2026, ~944 000
lignes) est stocke UNE seule fois sous un tenant systeme dedie,
TENANT_COMMUN, qui n'a aucun utilisateur. Chaque entreprise le lit en
plus de ses propres catalogues ; personne ne peut y ecrire depuis le site.

Les imports faits par une entreprise restent sous SON tenant_id et ne
sont visibles que d'elle : rien ne change pour eux.

Qui peut faire quoi -- le catalogue commun n'est JAMAIS supprime
------------------------------------------------------------------
- Proprietaire ou admin d'une entreprise : MASQUER le catalogue commun
  chez lui, et le reafficher. Les autres entreprises ne sont pas affectees.
- Proprietaire du tenant plateforme (TENANT_PLATEFORME, Blueseatra) :
  masquer ou reafficher le catalogue commun pour TOUTES les entreprises.
  Le masquage global prime sur les choix individuels.

Aucune route du site ne supprime une ligne du catalogue commun : c'est une
decision du proprietaire (23/09/2026). Masquer est instantane et reversible.

Securite
--------
Toutes les requetes filtrent tenant_id explicitement (mode repli sous
`postgres` BYPASSRLS, voir fournisseur_recherche.py). Sous blueseatra_app,
la migration 20260923200000 n'ouvre QUE la lecture des lignes du tenant
commun ; l'ecriture reste soumise a tenant_id = current_tenant(), d'ou le
passage par tenant_context(TENANT_COMMUN) pour le masquage global.
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import text

from database import get_current_tenant, tenant_context, tenant_session

log = logging.getLogger("blueseatra.catalogue_commun")

TENANT_COMMUN = os.environ.get(
    "BLUESEATRA_TENANT_CATALOGUE_COMMUN", "00000000-0000-4000-8000-000000000c0d")
TENANT_PLATEFORME = os.environ.get(
    "BLUESEATRA_TENANT_PLATEFORME", "781a064a-566c-436b-b901-f67259bd5ceb")


def peut_masquer_pour_tous(role: str, tenant_id: str) -> bool:
    return role == "owner" and tenant_id == TENANT_PLATEFORME


def peut_masquer(role: str) -> bool:
    return role in ("owner", "admin")


def _tenant_courant() -> str:
    tenant = get_current_tenant()
    if not tenant:
        raise RuntimeError("Catalogue commun appele sans tenant courant.")
    return tenant


async def masquages(session, tenant: str) -> dict:
    r = await session.execute(text("""
        SELECT m.tenant_id FROM blueseatra.catalogue_commun_masque m
        WHERE m.tenant_id = :tenant_id OR m.tenant_id = :commun
    """), {"tenant_id": tenant, "commun": TENANT_COMMUN})
    ids = {row[0] for row in r.all()}
    return {"pour_moi": tenant in ids, "pour_tous": TENANT_COMMUN in ids}


async def est_masque(session, tenant: str) -> bool:
    m = await masquages(session, tenant)
    return m["pour_moi"] or m["pour_tous"]


async def etat(role: str) -> dict:
    tenant = _tenant_courant()
    async with tenant_session() as session:
        m = await masquages(session, tenant)
        r = await session.execute(text("""
            SELECT count(*) AS fournisseurs, coalesce(sum(v.item_count), 0) AS lignes,
                   max(v.activated_at) AS mis_en_ligne
            FROM blueseatra.catalogs c
            JOIN blueseatra.catalog_versions v
              ON v.id = c.active_version_id AND v.tenant_id = c.tenant_id
            WHERE c.tenant_id = :commun
        """), {"commun": TENANT_COMMUN})
        ligne = dict(r.mappings().one())
    return {
        "existe": int(ligne["fournisseurs"] or 0) > 0,
        "fournisseurs": int(ligne["fournisseurs"] or 0),
        "lignes": int(ligne["lignes"] or 0),
        "mis_en_ligne": ligne["mis_en_ligne"],
        "masque": m["pour_moi"] or m["pour_tous"],
        "masque_pour_moi": m["pour_moi"],
        "masque_pour_tous": m["pour_tous"],
        "peut_masquer": peut_masquer(role),
        "peut_masquer_pour_tous": peut_masquer_pour_tous(role, tenant),
    }


async def masquer(utilisateur: str, masque: bool) -> dict:
    tenant = _tenant_courant()
    if tenant == TENANT_COMMUN:
        raise PermissionError("Operation impossible sur le tenant systeme.")
    async with tenant_session() as session:
        if masque:
            await session.execute(text("""
                INSERT INTO blueseatra.catalogue_commun_masque (tenant_id, masque_le, masque_par)
                VALUES (:tenant_id, to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), :par)
                ON CONFLICT (tenant_id) DO NOTHING
            """), {"tenant_id": tenant, "par": utilisateur})
        else:
            await session.execute(text("""
                DELETE FROM blueseatra.catalogue_commun_masque
                WHERE tenant_id = :tenant_id
            """), {"tenant_id": tenant})
        await session.commit()
    log.info("catalogue commun %s par %s (tenant %s)",
             "masque" if masque else "reaffiche", utilisateur, tenant)
    _invalider_sources(get_current_tenant())
    return {"masque": masque}


async def masquer_pour_tous(role: str, utilisateur: str, masque: bool) -> dict:
    """Masquage GLOBAL : une ligne tenant_id = TENANT_COMMUN dans la table
    de masquage. Ecrite sous tenant_context(TENANT_COMMUN) pour passer la
    politique WITH CHECK ; aucune donnee du catalogue n'est touchee."""
    tenant = _tenant_courant()
    if not peut_masquer_pour_tous(role, tenant):
        raise PermissionError("Seul le proprietaire du compte Blueseatra peut masquer le "
                              "catalogue commun pour toutes les entreprises.")
    async with tenant_context(TENANT_COMMUN):
        async with tenant_session() as session:
            if masque:
                await session.execute(text("""
                    INSERT INTO blueseatra.catalogue_commun_masque (tenant_id, masque_le, masque_par)
                    VALUES (:commun, to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), :par)
                    ON CONFLICT (tenant_id) DO NOTHING
                """), {"commun": TENANT_COMMUN, "par": utilisateur})
            else:
                await session.execute(text("""
                    DELETE FROM blueseatra.catalogue_commun_masque
                    WHERE tenant_id = :commun
                """), {"commun": TENANT_COMMUN})
            await session.commit()
    log.warning("catalogue commun %s pour TOUTES les entreprises par %s",
                "masque" if masque else "reaffiche", utilisateur)
    _invalider_sources(None)
    return {"masque_pour_tous": masque}


def _invalider_sources(tenant: str | None) -> None:
    """Le masquage change les sources visibles : vide le cache de la recherche
    d'articles du devis (catalogue_chiffrage, import tardif pour eviter le cycle)."""
    try:
        import catalogue_chiffrage
        catalogue_chiffrage.invalider_sources(tenant)
    except Exception:  # pragma: no cover
        pass
