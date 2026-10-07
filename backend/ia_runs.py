"""Tâches IA asynchrones sur le VPS (Hermès `/v1/runs`) : lancer, interroger, arrêter.

Pourquoi (07/10/2026)
---------------------
Avec `/v1/chat/completions`, le site gardait une connexion ouverte pendant des minutes. Si le
délai était dépassé ou si l'utilisateur supprimait la demande, le site coupait sa connexion mais le
calcul continuait sur le VPS, et les calculs abandonnés faisaient attendre les suivants.

Avec `/v1/runs` :
- `POST /v1/runs` rend tout de suite un `run_id` ;
- `GET /v1/runs/{run_id}` est le POINT DE CONTRÔLE : le site peut toujours demander au VPS où en est
  la tâche (started, running, completed, failed, cancelled...) et lire le résultat dès qu'il est prêt ;
- `POST /v1/runs/{run_id}/stop` interrompt la tâche : c'est ce qui libère le VPS.

Reprise : l'en-tête `Idempotency-Key` (dérivé de la demande, de la tentative et du contenu) fait que
relancer le même appel, par exemple après un redémarrage du site, renvoie la tâche d'origine au lieu
d'en créer une deuxième.

Périmètre : seulement les appels faits pendant le traitement d'une demande (contexte `demande()`).
Les autres appels IA restent sur `/v1/chat/completions`.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import hashlib
import json
import logging
import time

import httpx

log = logging.getLogger("blueseatra.ia_runs")

TERMINAUX = frozenset({"completed", "failed", "cancelled", "interrupted"})
# Codes HTTP à la CRÉATION qui signifient « cette passerelle ne sait pas faire » : repli sur chat/completions.
CODES_REPLI = frozenset({400, 404, 405, 422, 501})

_DEMANDE: contextvars.ContextVar[dict | None] = contextvars.ContextVar("ia_runs_demande", default=None)
_RUNS_ACTIFS: dict[str, dict[str, dict]] = {}     # demande -> {run_id: {url, headers}}
_ARRETEES: set[str] = set()


class RunsIndisponible(RuntimeError):
    """L'interface /v1/runs n'est pas utilisable pour cet appel : repli sur chat/completions."""


class RunAnnule(RuntimeError):
    """La demande a été arrêtée par l'utilisateur."""


class RunEchec(RuntimeError):
    """La tâche s'est terminée en échec côté VPS."""


class DelaiDepasse(RuntimeError):
    """Le délai est dépassé : la tâche a été arrêtée sur le VPS."""


# ---------- contexte d'une demande ----------

def cle_demande(tenant_id: str, request_id: str) -> str:
    """Toutes les tables de suivi sont cloisonnées par entreprise : un arrêt ou un état ne traverse jamais un tenant."""
    return f"{tenant_id}:{request_id}"


@contextlib.contextmanager
def demande(request_id: str, nonce: str, suivi=None, tenant_id: str = ""):
    """Déclare la demande en cours de traitement. `suivi(infos)` reçoit les changements d'état."""
    jeton = _DEMANDE.set({"id": cle_demande(tenant_id, request_id), "nonce": nonce, "suivi": suivi})
    try:
        yield
    finally:
        _DEMANDE.reset(jeton)


def ouvrir(request_id: str, nonce: str, suivi=None, tenant_id: str = ""):
    """Variante sans `with` de demande() : renvoie le jeton à passer à fermer()."""
    return _DEMANDE.set({"id": cle_demande(tenant_id, request_id), "nonce": nonce, "suivi": suivi})


def fermer(jeton) -> None:
    with contextlib.suppress(ValueError):
        _DEMANDE.reset(jeton)


def contexte() -> dict | None:
    return _DEMANDE.get()


def est_arretee(request_id: str) -> bool:
    return request_id in _ARRETEES


def reinitialiser(request_id: str) -> None:
    """Nouvelle tentative (Retraiter) : lève l'arrêt précédent."""
    _ARRETEES.discard(request_id)


def runs_actifs(request_id: str) -> dict[str, dict]:
    return dict(_RUNS_ACTIFS.get(request_id, {}))


# ---------- appels HTTP ----------

def cle_idempotence(request_id: str, nonce: str, role: str, corps: dict) -> str:
    empreinte = hashlib.sha256(json.dumps(corps, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return hashlib.sha256(f"{request_id}|{nonce}|{role}|{empreinte}".encode()).hexdigest()


def construire_corps(model: str, provider: str, system_prompt: str | None, user_message: str,
                     image_b64: str | None = None) -> dict:
    """Corps de POST /v1/runs. Une image passe par une liste de contenus (texte + image)."""
    if image_b64:
        entree = [{"role": "user", "content": [
            {"type": "text", "text": user_message},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}}]}]
    else:
        entree = user_message
    corps = {"input": entree, "model": model, "provider": provider}
    if system_prompt:
        corps["instructions"] = system_prompt
    return corps


async def lancer(url: str, headers: dict, corps: dict, cle: str | None) -> str:
    entetes = dict(headers)
    if cle:
        entetes["Idempotency-Key"] = cle
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{url}/v1/runs", json=corps, headers=entetes)
    if r.status_code in CODES_REPLI:
        raise RunsIndisponible(f"/v1/runs refusé (HTTP {r.status_code}) : {(r.text or '')[:160]}")
    if r.status_code >= 400:
        raise RuntimeError(f"Hermès /v1/runs HTTP {r.status_code}: {(r.text or '')[:180]}")
    run_id = (r.json() or {}).get("run_id")
    if not run_id:
        raise RunsIndisponible("/v1/runs n'a pas renvoyé de run_id")
    return run_id


async def etat(url: str, headers: dict, run_id: str) -> dict:
    """POINT DE CONTRÔLE : état actuel de la tâche, tel que le VPS le connaît."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f"{url}/v1/runs/{run_id}", headers=headers)
    if r.status_code == 404:
        return {"status": "inconnue", "run_id": run_id}
    if r.status_code >= 400:
        raise RuntimeError(f"Hermès GET /v1/runs HTTP {r.status_code}")
    return r.json()


async def arreter_run(url: str, headers: dict, run_id: str) -> bool:
    """Demande l'arrêt sur le VPS. Ne lève jamais."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f"{url}/v1/runs/{run_id}/stop", headers=headers)
        log.info("ia_run_stop run=%s http=%s", run_id, r.status_code)
        return r.status_code < 400
    except Exception:  # noqa: BLE001
        log.warning("ia_run_stop impossible run=%s", run_id, exc_info=True)
        return False


async def arreter_demande(request_id: str) -> int:
    """Arrête sur le VPS toutes les tâches en cours d'une demande. Ne lève jamais."""
    _ARRETEES.add(request_id)
    actifs = runs_actifs(request_id)
    resultats = await asyncio.gather(*[arreter_run(i["url"], i["headers"], rid) for rid, i in actifs.items()],
                                     return_exceptions=True)
    return sum(1 for r in resultats if r is True)


def _intervalle(ecoule: float) -> float:
    """Interrogations espacées au fil du temps : réactif au début, discret ensuite."""
    return 2.0 if ecoule < 60 else 4.0 if ecoule < 300 else 8.0


async def _signaler(ctx: dict | None, **infos):
    suivi = (ctx or {}).get("suivi")
    if suivi is None:
        return
    try:
        await suivi(infos)
    except Exception:  # noqa: BLE001
        log.debug("suivi des tâches non enregistré", exc_info=True)


async def executer(url: str, headers: dict, corps: dict, *, role: str, delai: float,
                   dormir=asyncio.sleep) -> str:
    """Lance la tâche, l'interroge jusqu'à sa fin et rend sa sortie texte.

    - délai dépassé : la tâche est ARRÊTÉE sur le VPS (plus de calcul abandonné), DelaiDepasse ;
    - demande arrêtée par l'utilisateur : la tâche est arrêtée, RunAnnule ;
    - annulation asyncio (suppression, arrêt du serveur) : la tâche est arrêtée avant de relayer.
    """
    ctx = contexte()
    demande_id = (ctx or {}).get("id")
    if demande_id and est_arretee(demande_id):
        raise RunAnnule("Demande arrêtée")
    cle = cle_idempotence(demande_id, ctx["nonce"], role, corps) if ctx else None
    run_id = await lancer(url, headers, corps, cle)
    if demande_id:
        _RUNS_ACTIFS.setdefault(demande_id, {})[run_id] = {"url": url, "headers": headers}
    await _signaler(ctx, run_id=run_id, role=role, statut="started")
    debut = time.monotonic()
    dernier = None
    try:
        while True:
            if demande_id and est_arretee(demande_id):
                await arreter_run(url, headers, run_id)
                raise RunAnnule("Demande arrêtée")
            ecoule = time.monotonic() - debut
            if ecoule > delai:
                await arreter_run(url, headers, run_id)
                raise DelaiDepasse(f"délai de {int(delai)} s dépassé, tâche arrêtée sur le VPS (run {run_id})")
            e = await etat(url, headers, run_id)
            statut = e.get("status")
            if statut != dernier:
                dernier = statut
                await _signaler(ctx, run_id=run_id, role=role, statut=statut)
            if statut == "completed":
                sortie = (e.get("output") or "").strip()
                if not sortie:
                    raise RunEchec(f"tâche terminée sans sortie (run {run_id})")
                return sortie
            if statut in ("failed", "interrupted"):
                raise RunEchec(f"tâche {statut} sur le VPS : {str(e.get('error') or '')[:160]} (run {run_id})")
            if statut == "cancelled":
                raise RunAnnule(f"tâche arrêtée sur le VPS (run {run_id})")
            if statut == "inconnue":
                raise RunEchec(f"tâche introuvable sur le VPS (run {run_id}), probablement redémarré")
            await dormir(_intervalle(ecoule))
    except asyncio.CancelledError:
        # Le site abandonne (suppression, arrêt) : on ne laisse pas le calcul tourner sur le VPS.
        with contextlib.suppress(Exception):
            await asyncio.shield(asyncio.wait_for(arreter_run(url, headers, run_id), 10))
        raise
    finally:
        if demande_id:
            _RUNS_ACTIFS.get(demande_id, {}).pop(run_id, None)
            if not _RUNS_ACTIFS.get(demande_id):
                _RUNS_ACTIFS.pop(demande_id, None)
