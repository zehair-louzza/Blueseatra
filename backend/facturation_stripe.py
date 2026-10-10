"""Facturation Stripe (ticket #90).

- Abonnements Initial, Pilotage, Performance (mensuel ou annuel), siège
  supplémentaire et recharges, créés dans Stripe par
  `scripts/stripe/creer_catalogue.py` et retrouvés par `lookup_key`.
- Paiement par Stripe Checkout ; gestion (changement d'offre, moyens de
  paiement, annulation) par le portail client Stripe.
- Webhook signé et idempotent : chaque événement est enregistré par son
  identifiant avant d'être appliqué ; un doublon ne produit aucun effet.
- Cycle de vie : essai → actif → impayé (lecture seule) → suspendu, jamais de
  suppression de données.

Sécurité : les clés live sont refusées tant que BLUESEATRA_STRIPE_LIVE=1
n'est pas défini explicitement.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import ssl
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from contact_blueseatra import CONTACT_EMAIL
from database import auth_session, tenant_session

log = logging.getLogger("blueseatra.stripe")
API = "https://api.stripe.com/v1"

OFFRES_PAYANTES = ("initial", "pilotage", "performance")
RECHARGES = {                       # lookup_key → (unité, quantité)
    "recharge_devis_25": ("devis_ia", 25),
    "recharge_devis_100": ("devis_ia", 100),
    "recharge_pages_500": ("page_lue", 500),
}
STATUTS = {                         # statut Stripe → statut Blueseatra
    # past_due : Stripe relance le paiement pendant quelques jours ; l'espace
    # reste actif pendant ces relances, puis passe en lecture seule (unpaid).
    "trialing": "actif", "active": "actif", "past_due": "actif",
    "unpaid": "lecture_seule", "incomplete": "lecture_seule",
    "canceled": "lecture_seule", "incomplete_expired": "lecture_seule", "paused": "suspendu",
}


def lookup_offre(offre: str, periodicite: str) -> str:
    return f"{offre}_{periodicite}"


def _cle() -> str:
    cle = os.environ.get("STRIPE_SECRET_KEY", "")
    if not cle:
        raise HTTPException(503, f"Paiement en ligne pas encore activé. Pour changer d'offre, écrivez à {CONTACT_EMAIL}.")
    if cle.startswith(("sk_live_", "rk_live_")) and os.environ.get("BLUESEATRA_STRIPE_LIVE") != "1":
        raise HTTPException(503, "Clé Stripe live refusée : la bascule en production n'a pas été validée.")
    return cle


def mode_test() -> bool:
    return not os.environ.get("STRIPE_SECRET_KEY", "").startswith(("sk_live_", "rk_live_"))


def _aplatir(d, prefixe=""):
    """Encodage formulaire Stripe : metadata[a]=x, line_items[0][price]=y."""
    out = []
    for k, v in (d.items() if isinstance(d, dict) else enumerate(d)):
        cle = f"{prefixe}[{k}]" if prefixe else str(k)
        if isinstance(v, (dict, list)):
            out += _aplatir(v, cle)
        elif v is not None:
            out.append((cle, "true" if v is True else "false" if v is False else str(v)))
    return out


def _tls():
    """Vérification TLS normale ; derrière un proxy d'entreprise (SSL_CERT_FILE défini),
    le contrôle X.509 « strict » de Python 3.13+ est relâché, la vérification reste active."""
    cafile = os.environ.get("SSL_CERT_FILE")
    if not cafile:
        return True
    ctx = ssl.create_default_context(cafile=cafile)
    ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    return ctx


async def stripe(methode: str, chemin: str, donnees: dict | None = None, idempotence: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {_cle()}", "Stripe-Version": "2024-06-20"}
    if idempotence:
        h["Idempotency-Key"] = idempotence
    def _appel():
        with httpx.Client(timeout=20, verify=_tls()) as c:
            if methode == "GET":
                return c.get(API + chemin, params=_aplatir(donnees or {}), headers=h)
            return c.post(API + chemin, content=urlencode(_aplatir(donnees or {})),
                          headers={**h, "Content-Type": "application/x-www-form-urlencoded"})

    # Client synchrone exécuté dans un fil : compatible avec tous les proxys HTTPS.
    r = await asyncio.to_thread(_appel)
    corps = r.json()
    if r.status_code >= 400:
        msg = (corps.get("error") or {}).get("message", "erreur Stripe")
        log.warning("stripe %s %s -> %s : %s", methode, chemin, r.status_code, msg)
        raise HTTPException(502, f"Stripe : {msg}")
    return corps


async def prix_par_lookup(cles: list[str]) -> dict:
    r = await stripe("GET", "/prices", {"lookup_keys": cles, "active": True, "limit": 100})
    return {p["lookup_key"]: p for p in r.get("data", [])}


# --- Signature du webhook --------------------------------------------------------

def verifier_signature(corps: bytes, entete: str, secret: str, tolerance: int = 300, maintenant: int | None = None) -> dict:
    """Vérifie l'en-tête Stripe-Signature (t=…,v1=…) selon la méthode documentée par Stripe."""
    if not entete or not secret:
        raise ValueError("signature absente")
    morceaux = dict(p.split("=", 1) for p in entete.split(",") if "=" in p)
    t = morceaux.get("t")
    signatures = [v for k, v in (p.split("=", 1) for p in entete.split(",") if "=" in p) if k == "v1"]
    if not t or not signatures:
        raise ValueError("signature mal formée")
    attendu = hmac.new(secret.encode(), f"{t}.".encode() + corps, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(attendu, s) for s in signatures):
        raise ValueError("signature invalide")
    if abs((maintenant or int(time.time())) - int(t)) > tolerance:
        raise ValueError("signature expirée")
    return json.loads(corps)


# --- Application des événements (moteur système : pas d'utilisateur) ---------------

async def _enregistrer(s, evt: dict, tenant: str | None) -> bool:
    """True si l'événement est nouveau. L'identifiant Stripe garantit l'idempotence."""
    r = await s.execute(text("""INSERT INTO blueseatra.stripe_evenements (id, type, tenant_id, mode_test, charge)
                                VALUES (:id, :type, :tenant_id, :test, CAST(:charge AS jsonb))
                                ON CONFLICT (id) DO NOTHING RETURNING id"""),
                        {"id": evt["id"], "type": evt["type"], "tenant_id": tenant,
                         "test": not evt.get("livemode", False), "charge": json.dumps(evt)})
    return r.first() is not None


def _tenant_de(obj: dict) -> str | None:
    md = obj.get("metadata") or {}
    return md.get("tenant_id") or obj.get("client_reference_id") or (
        (obj.get("subscription_details") or {}).get("metadata") or {}).get("tenant_id") or (
        ((obj.get("parent") or {}).get("subscription_details") or {}).get("metadata") or {}).get("tenant_id")


async def _maj_abonnement(s, tenant: str, sub: dict):
    item = ((sub.get("items") or {}).get("data") or [{}])[0]
    prix = item.get("price") or {}
    lk = prix.get("lookup_key") or ""
    offre, _, periodicite = lk.partition("_")
    if offre not in OFFRES_PAYANTES:
        offre = (sub.get("metadata") or {}).get("offre")
    statut = STATUTS.get(sub.get("status"), "lecture_seule")
    fin = item.get("current_period_end") or sub.get("current_period_end")
    await s.execute(text("""
        INSERT INTO blueseatra.stripe_abonnements (tenant_id, customer_id, subscription_id, price_id, offre_code,
               periodicite, statut_stripe, periode_fin, annulation_fin_periode, mode_test, maj_le)
        VALUES (:tenant_id, :cus, :sub, :price, :offre, :per, :st, to_timestamp(:fin), :annul, :test, now())
        ON CONFLICT (tenant_id) DO UPDATE SET customer_id = EXCLUDED.customer_id, subscription_id = EXCLUDED.subscription_id,
               price_id = EXCLUDED.price_id, offre_code = coalesce(EXCLUDED.offre_code, blueseatra.stripe_abonnements.offre_code),
               periodicite = coalesce(EXCLUDED.periodicite, blueseatra.stripe_abonnements.periodicite),
               statut_stripe = EXCLUDED.statut_stripe, periode_fin = EXCLUDED.periode_fin,
               annulation_fin_periode = EXCLUDED.annulation_fin_periode, mode_test = EXCLUDED.mode_test, maj_le = now()"""),
        {"tenant_id": tenant, "cus": sub.get("customer"), "sub": sub.get("id"), "price": prix.get("id"),
         "offre": offre if offre in OFFRES_PAYANTES else None, "per": periodicite if periodicite in ("mensuel", "annuel") else None,
         "st": sub.get("status"), "fin": fin or 0, "annul": bool(sub.get("cancel_at_period_end")),
         "test": not sub.get("livemode", False)})
    if offre in OFFRES_PAYANTES:
        sieges_sup = sum(int(i.get("quantity") or 0) for i in (sub.get("items") or {}).get("data", [])
                         if ((i.get("price") or {}).get("lookup_key") or "").startswith("siege_"))
        # Nouvelle offre payée : la période repart du début de l'abonnement Stripe.
        await s.execute(text("""UPDATE blueseatra.abonnements SET offre_code = CAST(:offre AS varchar), statut = :st,
                                       sieges_supplementaires = :sieges,
                                       periode_debut = CASE WHEN offre_code <> CAST(:offre AS varchar) OR statut = 'essai'
                                                            THEN to_timestamp(:debut) ELSE periode_debut END,
                                       essai_fin_le = NULL
                                 WHERE tenant_id = :tenant_id AND offre_code NOT IN ('interne', 'signature')"""),
                        {"tenant_id": tenant, "offre": offre, "st": statut, "sieges": sieges_sup,
                         "debut": sub.get("current_period_start") or item.get("current_period_start") or int(time.time())})
    else:
        await s.execute(text("""UPDATE blueseatra.abonnements SET statut = :st
                                 WHERE tenant_id = :tenant_id AND offre_code NOT IN ('interne', 'signature')"""),
                        {"tenant_id": tenant, "st": statut})


async def appliquer_evenement(evt: dict) -> str:
    obj = (evt.get("data") or {}).get("object") or {}
    tenant = _tenant_de(obj)
    async with auth_session() as s:
        if not await _enregistrer(s, evt, tenant):
            await s.commit()
            return "doublon"
        resultat, detail = "traite", None
        t = evt["type"]
        if not tenant:
            resultat, detail = "ignore", "aucune entreprise dans les métadonnées"
        elif t == "checkout.session.completed" and obj.get("mode") == "payment":
            pack = (obj.get("metadata") or {}).get("recharge")
            if pack in RECHARGES and obj.get("payment_status") == "paid":
                unite, qte = RECHARGES[pack]
                await s.execute(text("SELECT blueseatra.quota_crediter_recharge(:tenant_id, :u, :q, 'stripe', :m)"),
                                {"tenant_id": tenant, "u": unite, "q": qte, "m": f"Recharge {pack} ({obj.get('id')})"})
            else:
                resultat, detail = "ignore", "paiement non confirmé ou recharge inconnue"
        elif t in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
            await _maj_abonnement(s, tenant, obj)
        elif t in ("invoice.paid", "invoice.payment_failed", "checkout.session.completed"):
            pass   # l'état vient de customer.subscription.* ; enregistré pour la réconciliation
        else:
            resultat = "ignore"
        await s.execute(text("""UPDATE blueseatra.stripe_evenements SET statut = :st, detail = :d, traite_le = now()
                                 WHERE id = :id"""), {"st": resultat, "d": detail, "id": evt["id"]})
        await s.execute(text("""INSERT INTO blueseatra.audit_logs (id, tenant_id, actor, action, target, meta, created_at)
                                 SELECT gen_random_uuid()::text, CAST(:tenant_id AS varchar), 'stripe', :a, :id,
                                        CAST(:m AS jsonb), to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
                                  WHERE CAST(:tenant_id AS varchar) IS NOT NULL"""),
                        {"tenant_id": tenant, "a": f"stripe.{t}", "id": evt["id"], "m": json.dumps({"resultat": resultat})})
        await s.commit()
    log.info("stripe_evenement id=%s type=%s resultat=%s", evt["id"], evt["type"], resultat)
    return resultat


# --- Routes -------------------------------------------------------------------------

class CheckoutIn(BaseModel):
    offre: str
    periodicite: str = "mensuel"
    sieges_supplementaires: int = 0


class RechargeIn(BaseModel):
    pack: str


def _url_retour() -> str:
    return os.environ.get("BLUESEATRA_APP_URL", "https://blueseatra.com").rstrip("/") + "/app/billing"


async def _customer(tenant_id: str, email: str) -> str:
    async with tenant_session() as s:
        r = (await s.execute(text("SELECT customer_id FROM blueseatra.stripe_abonnements WHERE tenant_id = :tenant_id"),
                             {"tenant_id": tenant_id})).first()
    if r and r[0]:
        return r[0]
    c = await stripe("POST", "/customers", {"email": email, "metadata": {"tenant_id": tenant_id}},
                     idempotence=f"customer-{tenant_id}")
    return c["id"]


def build_router(get_current, require_role) -> APIRouter:
    r = APIRouter(prefix="/api")
    facturation = Depends(require_role("owner", "billing_admin"))

    @r.post("/abonnement/checkout")
    async def checkout(b: CheckoutIn, cu=facturation):
        if b.offre not in OFFRES_PAYANTES or b.periodicite not in ("mensuel", "annuel"):
            raise HTTPException(400, "Offre ou périodicité inconnue.")
        cles = [lookup_offre(b.offre, b.periodicite)] + ([f"siege_{b.periodicite}"] if b.sieges_supplementaires else [])
        prix = await prix_par_lookup(cles)
        if cles[0] not in prix:
            raise HTTPException(503, "Offre absente du catalogue Stripe : lancer scripts/stripe/creer_catalogue.py.")
        lignes = [{"price": prix[cles[0]]["id"], "quantity": 1}]
        if b.sieges_supplementaires:
            lignes.append({"price": prix[cles[1]]["id"], "quantity": max(0, min(b.sieges_supplementaires, 50))})
        session = await stripe("POST", "/checkout/sessions", {
            "mode": "subscription", "customer": await _customer(cu.tenant_id, cu.email),
            "client_reference_id": cu.tenant_id, "line_items": lignes,
            "subscription_data": {"metadata": {"tenant_id": cu.tenant_id, "offre": b.offre}},
            "metadata": {"tenant_id": cu.tenant_id, "offre": b.offre},
            "allow_promotion_codes": True, "billing_address_collection": "required",
            "tax_id_collection": {"enabled": True}, "customer_update": {"name": "auto", "address": "auto"},
            "locale": "fr",
            "success_url": _url_retour() + "?paiement=ok", "cancel_url": _url_retour() + "?paiement=annule",
        })
        return {"url": session["url"], "mode_test": mode_test()}

    @r.post("/abonnement/recharge")
    async def recharge(b: RechargeIn, cu=facturation):
        if b.pack not in RECHARGES:
            raise HTTPException(400, "Recharge inconnue.")
        prix = await prix_par_lookup([b.pack])
        if b.pack not in prix:
            raise HTTPException(503, "Recharge absente du catalogue Stripe.")
        session = await stripe("POST", "/checkout/sessions", {
            "mode": "payment", "customer": await _customer(cu.tenant_id, cu.email),
            "client_reference_id": cu.tenant_id, "line_items": [{"price": prix[b.pack]["id"], "quantity": 1}],
            "metadata": {"tenant_id": cu.tenant_id, "recharge": b.pack},
            "payment_intent_data": {"metadata": {"tenant_id": cu.tenant_id, "recharge": b.pack}},
            "locale": "fr", "success_url": _url_retour() + "?recharge=ok", "cancel_url": _url_retour(),
        })
        return {"url": session["url"], "mode_test": mode_test()}

    @r.post("/abonnement/portail")
    async def portail(cu=facturation):
        async with tenant_session() as s:
            row = (await s.execute(text("SELECT customer_id FROM blueseatra.stripe_abonnements WHERE tenant_id = :tenant_id"),
                                   {"tenant_id": cu.tenant_id})).first()
        if not row or not row[0]:
            raise HTTPException(404, "Aucun abonnement payé pour l'instant.")
        p = await stripe("POST", "/billing_portal/sessions", {"customer": row[0], "return_url": _url_retour(), "locale": "fr"})
        return {"url": p["url"]}

    @r.get("/abonnement/stripe")
    async def etat_stripe(cu=Depends(get_current)):
        async with tenant_session() as s:
            row = (await s.execute(text("""SELECT offre_code, periodicite, statut_stripe, periode_fin, annulation_fin_periode, mode_test
                                             FROM blueseatra.stripe_abonnements WHERE tenant_id = :tenant_id"""),
                                   {"tenant_id": cu.tenant_id})).mappings().first()
        return {"paiement_disponible": bool(os.environ.get("STRIPE_SECRET_KEY")), "mode_test": mode_test(),
                "abonnement": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(row).items()} if row else None}

    @r.post("/stripe/webhook", include_in_schema=False)
    async def webhook(request: Request, stripe_signature: str | None = Header(default=None)):
        corps = await request.body()
        try:
            evt = verifier_signature(corps, stripe_signature or "", os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
        except ValueError as e:
            log.warning("stripe webhook refusé : %s", e)
            raise HTTPException(400, "Signature Stripe invalide")
        if evt.get("livemode") and os.environ.get("BLUESEATRA_STRIPE_LIVE") != "1":
            raise HTTPException(400, "Événement live refusé")
        return {"recu": True, "resultat": await appliquer_evenement(evt)}

    return r
