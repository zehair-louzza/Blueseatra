"""Relances par e-mail : messagerie d'envoi, envoi par clic et envoi automatique.

Spécification : docs/specs/module-clients.md (« Envoi des relances par
e-mail »). L'envoi lui-même est dans envoi_relances.py (SMTP, sans base).

- L'utilisateur relit, modifie l'objet et le texte, puis clique sur
  « Envoyer » : le serveur envoie depuis la boîte de l'entreprise et marque
  la relance « faite ».
- Si l'entreprise l'a activé, la tâche de fond envoie seule les relances
  par e-mail arrivées à échéance (toutes les 5 minutes). Seules partent les
  relances dont l'échéance tombe après l'activation : un retard plus ancien
  reste à traiter à la main.
- Une relance n'est jamais envoyée deux fois : elle est réservée
  (`envoi_statut = 'envoi'`) par une mise à jour conditionnelle avant
  l'envoi. Un contact opposé aux relances ne reçoit jamais d'e-mail.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

import clients_module as cm
import envoi_relances as er
from database import auth_session, system_context, tenant_context

log = logging.getLogger("blueseatra.relances_email")

INTERVALLE_S = 300            # balayage de la tâche de fond
MAX_PAR_CYCLE = 20            # e-mails par entreprise et par balayage
MAX_TENTATIVES_AUTO = 3
AUTEUR_AUTO = "envoi automatique"

_chiffrer = None
_dechiffrer = None


class MessagerieIn(BaseModel):
    hote: str = Field(max_length=253)
    port: int
    identifiant: str = Field(min_length=1, max_length=255)
    mot_de_passe: Optional[str] = Field(default=None, max_length=500)   # vide : inchangé
    expediteur_email: str = Field(max_length=255)
    expediteur_nom: str = Field(default="", max_length=120)
    signature: str = Field(default="", max_length=2000)
    copie_cachee: bool = True
    actif: bool = True


class TexteIn(BaseModel):
    objet: Optional[str] = Field(default=None, max_length=er.OBJET_MAX)
    brouillon: Optional[str] = Field(default=None, max_length=er.TEXTE_MAX)


class RelanceIndisponible(Exception):
    """Relance déjà envoyée, en cours d'envoi, traitée ou hors e-mail."""


# --- Messagerie d'envoi --------------------------------------------------------

async def _messagerie_ligne() -> dict | None:
    return await cm._q("SELECT * FROM blueseatra.messagerie_smtp WHERE tenant_id = :tenant_id", {}, un=True)


def _vue(m: dict | None) -> dict:
    if not m:
        return {"configuree": False, "actif": False, "port": 465, "copie_cachee": True}
    champs = ("hote", "port", "identifiant", "expediteur_email", "expediteur_nom", "signature",
              "copie_cachee", "actif", "verifie_le", "derniere_erreur", "maj_le")
    return {"configuree": True, "mot_de_passe_defini": bool(m.get("mot_de_passe"))} | {k: m.get(k) for k in champs}


async def messagerie() -> er.Messagerie:
    m = await _messagerie_ligne()
    if not m or not m["actif"]:
        raise er.ErreurBoite("La messagerie d'envoi n'est pas configurée ou est désactivée (Relances > Règles).")
    mdp = _dechiffrer(m["mot_de_passe"]) if _dechiffrer else ""
    if not mdp:
        raise er.ErreurBoite("Mot de passe SMTP illisible : enregistrez-le de nouveau dans la messagerie d'envoi.")
    return er.Messagerie(hote=m["hote"], port=m["port"], identifiant=m["identifiant"], mot_de_passe=mdp,
                         expediteur_email=m["expediteur_email"], expediteur_nom=m["expediteur_nom"],
                         signature=m["signature"], copie_cachee=m["copie_cachee"])


async def enregistrer_messagerie(b: MessagerieIn, acteur: str) -> dict:
    if b.port not in er.PORTS:
        raise er.ErreurBoite("Port SMTP non pris en charge : utilisez 465 (SSL) ou 587 (STARTTLS).")
    hote = await asyncio.to_thread(er.verifier_hote, b.hote, b.port)
    if not er.email_valide(b.expediteur_email):
        raise er.ErreurEnvoi("Adresse d'expédition invalide.")
    existante = await _messagerie_ligne()
    mdp = None
    if b.mot_de_passe:
        mdp = _chiffrer(b.mot_de_passe) if _chiffrer else ""
        if not mdp.startswith("enc::"):
            raise er.ErreurEnvoi("Chiffrement indisponible sur le serveur (APP_ENCRYPTION_KEY) : mot de passe non enregistré.")
    elif not existante:
        raise er.ErreurEnvoi("Mot de passe SMTP obligatoire.")
    await cm._q("""
        INSERT INTO blueseatra.messagerie_smtp (tenant_id, hote, port, identifiant, mot_de_passe, expediteur_email,
                    expediteur_nom, signature, copie_cachee, actif, maj_par, maj_le)
        VALUES (:tenant_id, :hote, :port, :identifiant, :mdp, :expediteur_email, :expediteur_nom, :signature,
                :copie_cachee, :actif, :p, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            verifie_le = CASE WHEN messagerie_smtp.hote = EXCLUDED.hote AND messagerie_smtp.port = EXCLUDED.port
                               AND messagerie_smtp.identifiant = EXCLUDED.identifiant
                               AND messagerie_smtp.expediteur_email = EXCLUDED.expediteur_email
                               AND :mdp_inchange THEN messagerie_smtp.verifie_le END,
            hote = EXCLUDED.hote, port = EXCLUDED.port, identifiant = EXCLUDED.identifiant,
            mot_de_passe = CASE WHEN :mdp_inchange THEN messagerie_smtp.mot_de_passe ELSE EXCLUDED.mot_de_passe END,
            expediteur_email = EXCLUDED.expediteur_email, expediteur_nom = EXCLUDED.expediteur_nom,
            signature = EXCLUDED.signature, copie_cachee = EXCLUDED.copie_cachee, actif = EXCLUDED.actif,
            maj_par = EXCLUDED.maj_par, maj_le = now()""",
        {"hote": hote, "port": b.port, "identifiant": b.identifiant.strip(),
         "mdp": mdp or (existante or {}).get("mot_de_passe"), "mdp_inchange": mdp is None,
         "expediteur_email": b.expediteur_email.strip(), "expediteur_nom": b.expediteur_nom.strip(),
         "signature": b.signature.strip(), "copie_cachee": b.copie_cachee, "actif": b.actif, "p": acteur},
        ecrit=True)
    if not b.actif:
        await cm._q("UPDATE blueseatra.regles_relance SET envoi_auto = false, envoi_auto_depuis = NULL "
                    "WHERE tenant_id = :tenant_id", {}, ecrit=True)
    await cm._audit_log(acteur, "relances.mailbox_update", "", {"hote": hote, "port": b.port, "actif": b.actif,
                                                                "mot_de_passe_change": mdp is not None})
    return _vue(await _messagerie_ligne())


async def tester_messagerie(acteur: str) -> dict:
    """E-mail de test envoyé à l'adresse d'expédition elle-même."""
    try:
        m = await messagerie()
        msg = er.construire_message(er.Messagerie(**{**m.__dict__, "copie_cachee": False}), m.expediteur_email,
                                    "Test Blueseatra : messagerie d'envoi des relances",
                                    "Bonjour,\n\nCet e-mail confirme que Blueseatra peut envoyer les relances de devis "
                                    "depuis cette boîte.\n\nAucune action n'est nécessaire.")
        await asyncio.to_thread(er.envoyer, m, msg)
    except er.ErreurEnvoi as e:
        await cm._q("UPDATE blueseatra.messagerie_smtp SET verifie_le = NULL, derniere_erreur = :e "
                    "WHERE tenant_id = :tenant_id", {"e": str(e)[:500]}, ecrit=True)
        await cm._audit_log(acteur, "relances.mailbox_test", "", {"ok": False})
        raise
    await cm._q("UPDATE blueseatra.messagerie_smtp SET verifie_le = now(), derniere_erreur = NULL "
                "WHERE tenant_id = :tenant_id", {}, ecrit=True)
    await cm._audit_log(acteur, "relances.mailbox_test", "", {"ok": True})
    return _vue(await _messagerie_ligne())


# --- Texte et envoi d'une relance -------------------------------------------------

_MODIFIABLE = ("statut IN ('prevue', 'reportee') AND canal = 'email' "
               "AND (envoi_statut IS NULL OR envoi_statut = 'echec' "
               "     OR (envoi_statut = 'envoi' AND envoi_tente_le < now() - interval '15 minutes'))")


async def modifier_texte(rid: str, b: TexteIn) -> dict:
    x = await cm._q(f"""UPDATE blueseatra.relances SET objet = coalesce(:o, objet), brouillon = coalesce(:b, brouillon)
                         WHERE tenant_id = :tenant_id AND id = :id AND {_MODIFIABLE}
                         RETURNING id, objet, brouillon""",
                    {"id": rid, "o": er._ligne(b.objet, er.OBJET_MAX) if b.objet is not None else None,
                     "b": b.brouillon}, un=True, ecrit=True)
    if not x:
        raise RelanceIndisponible("Texte non modifiable : relance déjà envoyée, en cours d'envoi, traitée ou hors e-mail.")
    return x


async def _destinataire(rid: str) -> dict:
    return await cm._q("""
        SELECT x.client_id, x.contact_id, x.devis_id, x.rang, q.number AS numero,
               coalesce(k.accepte_relances, true) AS accepte,
               CASE WHEN coalesce(k.accepte_relances, true) THEN coalesce(k.email, c.email) END AS email
          FROM blueseatra.relances x
          LEFT JOIN blueseatra.quotes q ON q.tenant_id = x.tenant_id AND q.id = x.devis_id
          LEFT JOIN blueseatra.clients c ON c.tenant_id = x.tenant_id AND c.id = x.client_id
          LEFT JOIN blueseatra.contacts k ON k.tenant_id = x.tenant_id AND k.id = x.contact_id
         WHERE x.tenant_id = :tenant_id AND x.id = :id""", {"id": rid}, un=True)


async def _echec(rid: str, erreur: str):
    await cm._q("UPDATE blueseatra.relances SET envoi_statut = 'echec', envoi_erreur = :e "
                "WHERE tenant_id = :tenant_id AND id = :id", {"id": rid, "e": erreur[:500]}, ecrit=True)


async def envoyer_relance(rid: str, auteur: str, *, auto: bool = False, texte: TexteIn | None = None) -> dict:
    """Envoie une relance par e-mail. ErreurEnvoi : échec lisible, tracé sur la relance."""
    m = await messagerie()
    t = texte or TexteIn()
    limite = f" AND envoi_tentatives < {MAX_TENTATIVES_AUTO}" if auto else ""
    x = await cm._q(f"""UPDATE blueseatra.relances
                           SET envoi_statut = 'envoi', envoi_tente_le = now(), envoi_tentatives = envoi_tentatives + 1,
                               envoi_erreur = NULL, objet = coalesce(:o, objet), brouillon = coalesce(:b, brouillon)
                         WHERE tenant_id = :tenant_id AND id = :id AND {_MODIFIABLE}{limite}
                         RETURNING *""",
                    {"id": rid, "o": er._ligne(t.objet, er.OBJET_MAX) if t.objet is not None else None,
                     "b": t.brouillon}, un=True, ecrit=True)
    if not x:
        raise RelanceIndisponible("Relance déjà envoyée, en cours d'envoi, traitée ou hors e-mail.")
    d = await _destinataire(rid)
    if not d["accepte"]:
        await _echec(rid, "Le contact s'est opposé aux relances : aucun e-mail envoyé.")
        raise er.ErreurEnvoi("Le contact s'est opposé aux relances : aucun e-mail envoyé.")
    if not er.email_valide(d["email"]):
        await _echec(rid, "Aucune adresse e-mail valide pour ce contact.")
        raise er.ErreurEnvoi("Aucune adresse e-mail valide pour ce contact.")
    objet = x.get("objet") or f"Devis {d.get('numero') or ''}".strip()
    try:
        msg = er.construire_message(m, d["email"], objet, x.get("brouillon") or "")
        mid = await asyncio.to_thread(er.envoyer, m, msg)
    except er.ErreurEnvoi as e:
        await _echec(rid, str(e))
        raise
    await cm._q("""UPDATE blueseatra.relances
                      SET statut = 'faite', envoi_statut = 'envoye', envoye_le = now(), envoye_par = :p,
                          faite_par = :p, faite_le = now(), envoi_destinataire = :dest, envoi_message_id = :mid,
                          objet = :objet
                    WHERE tenant_id = :tenant_id AND id = :id""",
                {"id": rid, "p": auteur, "dest": d["email"], "mid": mid[:255], "objet": objet}, ecrit=True)
    if d.get("client_id"):
        await cm._echange(d["client_id"], "relance",
                          f"Relance {d['rang']} envoyée par e-mail à {d['email']} (« {objet} »)"
                          + (", automatiquement." if auto else "."),
                          auteur, devis_id=d["devis_id"], contact_id=d.get("contact_id"), relance_id=rid)
    await cm._audit_log(auteur, "relances.email_sent", rid, {"auto": auto})
    return {"ok": True, "envoye_a": d["email"], "objet": objet}


# --- Envoi automatique à l'échéance -----------------------------------------------

_A_ENVOYER = text(f"""
    SELECT x.tenant_id, x.id
      FROM blueseatra.relances x
      JOIN blueseatra.regles_relance g ON g.tenant_id = x.tenant_id AND g.actif AND g.envoi_auto
      JOIN blueseatra.messagerie_smtp m ON m.tenant_id = x.tenant_id AND m.actif AND m.verifie_le IS NOT NULL
     WHERE x.canal = 'email' AND x.statut IN ('prevue', 'reportee')
       AND x.echeance <= now() AND x.echeance >= g.envoi_auto_depuis
       AND x.envoi_tentatives < {MAX_TENTATIVES_AUTO}
       AND (x.envoi_statut IS NULL
            OR (x.envoi_statut = 'echec' AND x.envoi_tente_le < now() - interval '1 hour')
            OR (x.envoi_statut = 'envoi' AND x.envoi_tente_le < now() - interval '15 minutes'))
     ORDER BY x.echeance
     LIMIT 200""")


async def relances_a_envoyer() -> list[tuple[str, str]]:
    """Balayage transverse assumé (toutes entreprises) : moteur AUTH, voir database.system_context."""
    async with system_context():
        async with auth_session() as s:
            return [(str(t), str(i)) for t, i in (await s.execute(_A_ENVOYER)).all()]


async def envoyer_echeances() -> int:
    envoyees, par_tenant, en_panne = 0, {}, set()
    for tid, rid in await relances_a_envoyer():
        if tid in en_panne or par_tenant.get(tid, 0) >= MAX_PAR_CYCLE:
            continue
        par_tenant[tid] = par_tenant.get(tid, 0) + 1
        async with tenant_context(tid):
            try:
                await envoyer_relance(rid, AUTEUR_AUTO, auto=True)
                envoyees += 1
            except RelanceIndisponible:
                continue
            except er.ErreurBoite as e:
                # Boîte en panne (mot de passe, serveur) : on n'insiste pas sur les suivantes de ce balayage,
                # et l'erreur s'affiche dans la messagerie d'envoi.
                log.warning("Envoi automatique : boîte d'envoi en échec pour une entreprise (%s)", e)
                en_panne.add(tid)
                await cm._q("UPDATE blueseatra.messagerie_smtp SET derniere_erreur = :e WHERE tenant_id = :tenant_id",
                            {"e": str(e)[:500]}, ecrit=True)
            except er.ErreurEnvoi as e:
                log.warning("Envoi automatique : relance %s non envoyée (%s)", rid, e)
    if envoyees:
        log.info("Envoi automatique : %d relance(s) envoyée(s)", envoyees)
    return envoyees


async def boucle_envoi_auto():
    if os.environ.get("BLUESEATRA_ENVOI_AUTO", "1") == "0":
        log.info("Envoi automatique des relances coupé (BLUESEATRA_ENVOI_AUTO=0)")
        return
    await asyncio.sleep(60)
    while True:
        try:
            await envoyer_echeances()
        except Exception:  # noqa: BLE001 -- la boucle ne doit jamais s'arrêter
            log.exception("Envoi automatique des relances : balayage en échec")
        await asyncio.sleep(INTERVALLE_S)


# --- Routes -------------------------------------------------------------------------

def build_router(require_role, *, chiffrer, dechiffrer) -> APIRouter:
    global _chiffrer, _dechiffrer
    _chiffrer, _dechiffrer = chiffrer, dechiffrer
    r = APIRouter()
    ecriture = Depends(require_role("owner", "admin", "operator"))
    gestion = Depends(require_role("owner", "admin"))

    def _http(fn):
        async def appel(*a, **k):
            try:
                return await fn(*a, **k)
            except RelanceIndisponible as e:
                raise HTTPException(409, str(e))
            except er.ErreurEnvoi as e:
                raise HTTPException(400, str(e))
        return appel

    @r.get("/messagerie")
    async def lire(cu=gestion):
        return _vue(await _messagerie_ligne())

    @r.put("/messagerie")
    async def ecrire(b: MessagerieIn, cu=gestion):
        return await _http(enregistrer_messagerie)(b, cu.email)

    @r.post("/messagerie/test")
    async def tester(cu=gestion):
        return await _http(tester_messagerie)(cu.email)

    @r.patch("/relances/{rid}/texte")
    async def texte(rid: str, b: TexteIn, cu=ecriture):
        return await _http(modifier_texte)(rid, b)

    @r.post("/relances/{rid}/envoyer")
    async def envoyer(rid: str, b: TexteIn | None = None, cu=ecriture):
        x = await cm._q("SELECT canal, statut FROM blueseatra.relances WHERE tenant_id = :tenant_id AND id = :id",
                        {"id": rid}, un=True)
        if not x:
            raise HTTPException(404, "Relance introuvable.")
        if x["canal"] != "email":
            raise HTTPException(400, "Cette relance n'est pas prévue par e-mail.")
        return await _http(envoyer_relance)(rid, cu.email, texte=b)

    return r
