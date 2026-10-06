"""Cache des extractions IA, par entreprise et par empreinte du contenu (diagnostic du 06/10/2026).

Pourquoi
--------
Sur le processeur du VPS, une extraction coûte de quelques minutes (texte) à plusieurs
dizaines de minutes (OCR). Un même document réimporté, ou une demande remise en file après
un redémarrage, refaisait tout le calcul.

Ce qui est mis en cache
-----------------------
Uniquement le résultat structuré (le JSON ``extracted``), jamais le fichier lui-même : les PDF
et leurs rendus ne sont toujours pas conservés (voir ``create_request``).

La clé est le SHA-256 de : l'empreinte de configuration (fournisseur, modèle, OCR préféré,
consigne et schéma d'extraction, code d'extraction) + la nature de la source + le contenu
(texte, octets de l'image, octets des pages rendues). Tout changement de modèle, de consigne
ou de code d'extraction produit une autre clé : un résultat ancien n'est jamais resservi.

Règles
------
- Par entreprise : clé primaire (tenant_id, cle) et RLS sur current_tenant().
- Seuls les résultats SANS erreur et de confiance suffisante (statut « done ») sont écrits :
  une extraction douteuse n'est jamais figée.
- « Retraiter » ignore le cache (``invalider``) : l'utilisateur demande un nouvel essai.
- Conservation : 30 jours, purge à chaque écriture. Les anonymisations RGPD vident le cache
  de l'entreprise (``purger_entreprise``) : il contient des données personnelles extraites.
- Facturation inchangée : la réservation du devis assisté et des pages se fait avant, comme
  toujours. Le cache économise du calcul, pas du quota.
- Disponibilité : si la table est absente (migration non appliquée) ou en erreur, le cache est
  silencieusement ignoré et l'extraction se fait normalement. Un cache en panne ne doit jamais
  empêcher une entreprise de travailler.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os

from sqlalchemy import text

from database import tenant_context, tenant_session

log = logging.getLogger("blueseatra.cache_ia")

# À incrémenter pour invalider volontairement tous les résultats (changement de format).
VERSION_CACHE = "1"
CONSERVATION_JOURS = 30
# Confiance minimale pour figer un résultat (au-dessous : statut « needs_review »).
CONFIANCE_MIN = 0.6

_DOSSIER = os.path.dirname(os.path.abspath(__file__))
_FICHIERS_EXTRACTION = ("ai_service.py", "tce_v4.py")


@functools.lru_cache(maxsize=1)
def _empreinte_code() -> str:
    """Hash des fichiers qui produisent et post-traitent l'extraction."""
    h = hashlib.sha256()
    for nom in _FICHIERS_EXTRACTION:
        try:
            with open(os.path.join(_DOSSIER, nom), "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(nom.encode())
    return h.hexdigest()


def empreinte_configuration(settings: dict | None) -> str:
    """Tout ce qui, hors contenu du document, peut changer le résultat d'une extraction."""
    import ai_service  # import tardif : ai_service est lourd et n'a pas besoin de ce module

    s = settings or {}
    elements = {
        "version": VERSION_CACHE,
        "fournisseur": s.get("ai_provider") or "",
        "modele": s.get("ai_model") or "",
        "ocr": s.get("ocr_model_preference") or "",
        "consigne": hashlib.sha256((getattr(ai_service, "EXTRACTION_SYSTEM", "") or "").encode()).hexdigest(),
        "schema": getattr(ai_service, "SCHEMA_EXTRACTION", None),
        "strict": bool(getattr(ai_service, "IA_SCHEMA_STRICT", True)),
        "cascade": [getattr(ai_service, n, "") for n in (
            "HERMES_STRUCTURING_MODEL_1", "HERMES_STRUCTURING_MODEL_2", "HERMES_STRUCTURING_MODEL_3",
            "HERMES_OCR_MODEL", "HERMES_OCR_GLM_MODEL", "HERMES_VISION_MODEL")],
        "code": _empreinte_code(),
    }
    return hashlib.sha256(json.dumps(elements, sort_keys=True, default=str).encode()).hexdigest()


def _cle(configuration: str, source: str, contenu: bytes) -> str:
    h = hashlib.sha256()
    h.update(configuration.encode())
    h.update(b"\0" + source.encode() + b"\0")
    h.update(hashlib.sha256(contenu).digest())
    return h.hexdigest()


def cle_demande(req: dict, settings: dict | None, vision_pages: list | None = None) -> tuple[str, str] | None:
    """(source, clé) d'une demande, ou None si son contenu n'est pas disponible ou pas cachable.

    Reprend exactement les branches de ``process_request`` : pages rendues en mémoire (PDF
    scanné), image conservée en base, ou texte.
    """
    stype = req.get("source_type")
    texte = req.get("raw_text") or ""
    if stype == "pdf_ocr":
        if not vision_pages:
            return None
        h = hashlib.sha256()
        for page in vision_pages:
            h.update(hashlib.sha256(bytes(page)).digest())
        return "pdf_ocr", _cle(empreinte_configuration(settings), "pdf_ocr", h.digest())
    if stype == "image" and req.get("file_b64"):
        import base64
        try:
            octets = base64.b64decode(req["file_b64"])
        except Exception:  # noqa: BLE001
            return None
        return "image", _cle(empreinte_configuration(settings), "image", octets)
    if texte.strip():
        # from_file change le comportement de l'extraction : il fait partie de la clé.
        marque = "fichier" if stype != "text" else "saisie"
        return "texte", _cle(empreinte_configuration(settings), f"texte-{marque}", texte.encode("utf-8"))
    return None


def cachable(extracted: dict | None) -> bool:
    if not isinstance(extracted, dict) or extracted.get("_error"):
        return False
    try:
        return float(extracted.get("confidence") or 0) >= CONFIANCE_MIN
    except (TypeError, ValueError):
        return False


def _table_absente(exc: Exception) -> bool:
    nom = type(getattr(exc, "orig", exc)).__name__
    msg = str(exc)
    return "UndefinedTable" in nom or "does not exist" in msg or "n'existe pas" in msg


async def lire(tenant_id: str, cle: str) -> dict | None:
    """Résultat en cache, ou None. Ne lève jamais."""
    try:
        async with tenant_context(tenant_id):
            async with tenant_session() as s:
                r = await s.execute(text(
                    "UPDATE blueseatra.cache_ia SET dernier_acces = now(), reutilisations = reutilisations + 1 "
                    "WHERE tenant_id = :t AND cle = :c AND cree_le > now() - make_interval(days => :j) "
                    "RETURNING resultat, cree_le"),
                    {"t": tenant_id, "c": cle, "j": CONSERVATION_JOURS})
                ligne = r.first()
                await s.commit()
    except Exception as exc:  # noqa: BLE001
        if _table_absente(exc):
            log.warning("cache_ia : migration absente, cache ignoré")
        else:
            log.exception("cache_ia : lecture impossible, extraction normale")
        return None
    if not ligne:
        return None
    resultat = ligne[0]
    if isinstance(resultat, str):
        resultat = json.loads(resultat)
    if isinstance(resultat, dict):
        resultat = dict(resultat)
        resultat["_cache_ia"] = ligne[1].isoformat() if hasattr(ligne[1], "isoformat") else str(ligne[1])
    return resultat


async def ecrire(tenant_id: str, cle: str, source: str, extracted: dict) -> bool:
    """Enregistre un résultat valide et purge les entrées périmées. Ne lève jamais."""
    if not cachable(extracted):
        return False
    resultat = {k: v for k, v in extracted.items() if k != "_cache_ia"}
    try:
        async with tenant_context(tenant_id):
            async with tenant_session() as s:
                await s.execute(text(
                    "DELETE FROM blueseatra.cache_ia WHERE tenant_id = :t "
                    "AND cree_le < now() - make_interval(days => :j)"),
                    {"t": tenant_id, "j": CONSERVATION_JOURS})
                await s.execute(text(
                    "INSERT INTO blueseatra.cache_ia (tenant_id, cle, source, resultat) "
                    "VALUES (:t, :c, :src, CAST(:r AS jsonb)) "
                    "ON CONFLICT (tenant_id, cle) DO UPDATE SET resultat = EXCLUDED.resultat, "
                    "source = EXCLUDED.source, cree_le = now(), dernier_acces = now(), reutilisations = 0"),
                    {"t": tenant_id, "c": cle, "src": source,
                     "r": json.dumps(resultat, ensure_ascii=False, default=str)})
                await s.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        if _table_absente(exc):
            log.warning("cache_ia : migration absente, résultat non mis en cache")
        else:
            log.exception("cache_ia : écriture impossible")
        return False


async def invalider(tenant_id: str, cle: str) -> None:
    """« Retraiter » demande un nouvel essai : l'entrée de ce contenu est retirée."""
    try:
        async with tenant_context(tenant_id):
            async with tenant_session() as s:
                await s.execute(text("DELETE FROM blueseatra.cache_ia WHERE tenant_id = :t AND cle = :c"),
                                {"t": tenant_id, "c": cle})
                await s.commit()
    except Exception as exc:  # noqa: BLE001
        if not _table_absente(exc):
            log.exception("cache_ia : invalidation impossible")


async def purger_entreprise(tenant_id: str) -> int:
    """Vide le cache d'une entreprise (anonymisation RGPD). Ne lève jamais."""
    try:
        async with tenant_context(tenant_id):
            async with tenant_session() as s:
                r = await s.execute(text("DELETE FROM blueseatra.cache_ia WHERE tenant_id = :t"), {"t": tenant_id})
                await s.commit()
                return r.rowcount or 0
    except Exception as exc:  # noqa: BLE001
        if not _table_absente(exc):
            log.exception("cache_ia : purge impossible")
        return 0
