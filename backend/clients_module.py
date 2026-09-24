"""Module Clients : clients, contacts, chantiers, échanges, suggestions IA
et relances de devis. Spécification : docs/specs/module-clients.md.

Sécurité
--------
- Toutes les requêtes passent par tenant_session() (RLS sous blueseatra_app)
  ET filtrent tenant_id explicitement (mode repli sous postgres).
- Aucune route ne supprime : archivage, anonymisation, annulation.
- L'IA ne crée rien seule : elle écrit des suggestions avec leur preuve.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import text

import relances_regles as rr
from database import get_current_tenant, tenant_session

log = logging.getLogger("blueseatra.clients")

TYPES_CLIENT = ("entreprise", "particulier", "syndic", "bailleur", "collectivite", "enseigne")
ISSUES = ("en_attente", "accepte", "refuse", "sans_suite")
RESULTATS = ("sans_reponse", "a_rappeler", "accepte", "refuse", "en_reflexion")
TAILLE_PAGE_MAX = 100


# --- Outils ------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def normaliser(*parts: Any) -> str:
    s = " ".join(str(p) for p in parts if p)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(sas|sarl|sa|sci|eurl|sasu|snc|scop|ste|societe|groupe|ets|etablissements)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _siret(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    d = re.sub(r"\D", "", v)
    return d if len(d) == 14 else None


def _tenant() -> str:
    t = get_current_tenant()
    if not t:
        raise RuntimeError("module Clients appelé sans tenant courant")
    return t


def _ligne(row) -> dict:
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, (datetime, date)):
            v = v.isoformat()
        elif hasattr(v, "as_tuple"):          # Decimal
            v = float(v)
        out[k] = v
    return out


async def _q(sql: str, params: dict, *, un: bool = False, ecrit: bool = False):
    params = {"tenant_id": _tenant(), **params}
    async with tenant_session() as s:
        r = await s.execute(text(sql), params)
        rows = [_ligne(x) for x in r.mappings().all()] if r.returns_rows else []
        if ecrit:
            await s.commit()
    return (rows[0] if rows else None) if un else rows


async def _audit_log(actor: str, action: str, target: str, meta: dict | None = None):
    await _q("""INSERT INTO blueseatra.audit_logs (id, tenant_id, actor, action, target, meta, created_at)
                VALUES (:id, :tenant_id, :actor, :action, :target, CAST(:meta AS jsonb), :at)""",
             {"id": _id(), "actor": actor, "action": action, "target": target,
              "meta": json.dumps(meta or {}), "at": _maintenant().isoformat()}, ecrit=True)


async def _echange(client_id: str, type_: str, resume: str, auteur: str | None, **liens):
    await _q("""INSERT INTO blueseatra.echanges_clients
                  (tenant_id, client_id, contact_id, devis_id, chantier_id, relance_id, type, resume, auteur)
                VALUES (:tenant_id, :client_id, :contact_id, :devis_id, :chantier_id, :relance_id, :type, :resume, :auteur)""",
             {"client_id": client_id, "type": type_, "resume": resume[:2000], "auteur": auteur,
              "contact_id": liens.get("contact_id"), "devis_id": liens.get("devis_id"),
              "chantier_id": liens.get("chantier_id"), "relance_id": liens.get("relance_id")}, ecrit=True)


# --- Schémas -------------------------------------------------------------------

class Adresse(BaseModel):
    ligne1: Optional[str] = None
    ligne2: Optional[str] = None
    code_postal: Optional[str] = None
    ville: Optional[str] = None
    pays: Optional[str] = "France"


class ClientIn(BaseModel):
    type: str = "entreprise"
    raison_sociale: str = Field(min_length=1, max_length=255)
    nom_commercial: Optional[str] = None
    siret: Optional[str] = None
    tva_intra: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Adresse = Adresse()
    site_web: Optional[str] = None
    langue: str = "fr"
    delai_paiement_j: Optional[int] = Field(default=None, ge=0, le=120)
    etiquettes: list[str] = []
    notes: Optional[str] = None


class ContactIn(BaseModel):
    civilite: Optional[str] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    fonction: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    mobile: Optional[str] = None
    langue: str = "fr"
    principal: bool = False
    accepte_relances: bool = True


class ChantierIn(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    code_site: Optional[str] = None
    adresse: Adresse = Adresse()
    acces: Optional[str] = None


class EchangeIn(BaseModel):
    type: str = "note"
    resume: str = Field(min_length=1, max_length=2000)
    contact_id: Optional[str] = None
    devis_id: Optional[str] = None
    chantier_id: Optional[str] = None
    corrige_id: Optional[int] = None


class IssueIn(BaseModel):
    issue: str
    motif: Optional[str] = None


class FaiteIn(BaseModel):
    resultat: str
    note: Optional[str] = None


class ReporterIn(BaseModel):
    jours_ouvres: Optional[int] = Field(default=None, ge=1, le=60)
    date: Optional[date] = None


class ReglesIn(BaseModel):
    actif: bool = True
    delais_jours_ouvres: list[int] = [3, 7, 14]
    delais_urgent: list[int] = [1, 2, 4]
    max_relances: int = Field(default=3, ge=0, le=6)
    validite_devis_jours: int = Field(default=30, ge=7, le=180)
    rappel_avant_expiration_j: int = Field(default=3, ge=0, le=15)
    seuil_appel_ht: float = Field(default=10000, ge=0)
    heure_relance: str = "09:00"


class LierIn(BaseModel):
    client_id: Optional[str] = None
    client_final_id: Optional[str] = None
    chantier_id: Optional[str] = None
    contact_id: Optional[str] = None
    valable_jusqu_au: Optional[date] = None


# --- Clients -----------------------------------------------------------------

def _valider_client(b: ClientIn) -> dict:
    if b.type not in TYPES_CLIENT:
        raise HTTPException(400, "Type de client inconnu.")
    if b.langue not in ("fr", "en"):
        raise HTTPException(400, "Langue : fr ou en.")
    siret = _siret(b.siret)
    if b.siret and not siret:
        raise HTTPException(400, "Le SIRET doit comporter 14 chiffres.")
    d = b.model_dump()
    d["siret"] = siret
    d["adresse"] = json.dumps(b.adresse.model_dump())
    d["etiquettes"] = [e.strip()[:40] for e in b.etiquettes if e.strip()][:20]
    d["recherche_norm"] = normaliser(b.raison_sociale, b.nom_commercial, b.adresse.ville, siret)
    return d


_CHAMPS_CLIENT = ("type, raison_sociale, nom_commercial, siret, tva_intra, email, telephone, adresse, "
                  "site_web, langue, delai_paiement_j, etiquettes, notes, recherche_norm")


async def creer_client(b: ClientIn, acteur: str, source: str = "manuel") -> dict:
    d = _valider_client(b)
    d.update(id=_id(), source=source, acteur=acteur)
    try:
        row = await _q(f"""INSERT INTO blueseatra.clients (id, tenant_id, {_CHAMPS_CLIENT}, source, cree_par)
            VALUES (:id, :tenant_id, :type, :raison_sociale, :nom_commercial, :siret, :tva_intra, :email,
                    :telephone, CAST(:adresse AS jsonb), :site_web, :langue, :delai_paiement_j,
                    :etiquettes, :notes, :recherche_norm, :source, :acteur)
            RETURNING *""", d, un=True, ecrit=True)
    except Exception as exc:  # noqa: BLE001
        if "clients_siret_unique" in str(exc):
            raise HTTPException(409, "Un client actif porte déjà ce SIRET.")
        raise
    await _audit_log(acteur, "client.create", row["id"], {"source": source})
    return row


async def lire_client(client_id: str) -> dict:
    row = await _q("SELECT * FROM blueseatra.clients WHERE tenant_id = :tenant_id AND id = :id",
                   {"id": client_id}, un=True)
    if not row:
        raise HTTPException(404, "Client introuvable.")
    return row


def build_router(get_current, require_role) -> APIRouter:
    r = APIRouter()
    lecture = Depends(require_role("owner", "admin", "operator", "viewer"))
    ecriture = Depends(require_role("owner", "admin", "operator"))
    gestion = Depends(require_role("owner", "admin"))

    @r.get("/clients")
    async def lister(q: str = "", type: str = "", etiquette: str = "", en_attente: bool = False,
                     archives: bool = False, page: int = Query(1, ge=1), taille: int = Query(50, ge=1, le=TAILLE_PAGE_MAX),
                     cu=lecture):
        cond = ["c.tenant_id = :tenant_id", "c.archive_le IS NOT NULL" if archives else "c.archive_le IS NULL"]
        p: dict = {"limite": taille, "decalage": (page - 1) * taille}
        if q.strip():
            cond.append("c.recherche_norm LIKE :motif")
            p["motif"] = f"%{normaliser(q)}%"
        if type in TYPES_CLIENT:
            cond.append("c.type = :type")
            p["type"] = type
        if etiquette.strip():
            cond.append(":etiquette = ANY(c.etiquettes)")
            p["etiquette"] = etiquette.strip()
        if en_attente:
            cond.append("""EXISTS (SELECT 1 FROM blueseatra.quotes q WHERE q.tenant_id = c.tenant_id
                           AND q.client_id = c.id AND q.status = 'sent' AND coalesce(q.issue, 'en_attente') = 'en_attente')""")
        where = " AND ".join(cond)
        rows = await _q(f"""
            SELECT c.id, c.type, c.raison_sociale, c.nom_commercial, c.siret, c.email, c.telephone,
                   c.adresse->>'ville' AS ville, c.etiquettes, c.archive_le,
                   (SELECT count(*) FROM blueseatra.quotes q WHERE q.tenant_id = c.tenant_id AND q.client_id = c.id
                      AND q.status = 'sent' AND coalesce(q.issue, 'en_attente') = 'en_attente') AS devis_en_cours,
                   (SELECT coalesce(sum(q.total_ht), 0) FROM blueseatra.quotes q WHERE q.tenant_id = c.tenant_id
                      AND q.client_id = c.id AND q.status = 'sent' AND coalesce(q.issue, 'en_attente') = 'en_attente') AS montant_en_cours,
                   (SELECT max(e.survenu_le) FROM blueseatra.echanges_clients e WHERE e.tenant_id = c.tenant_id
                      AND e.client_id = c.id) AS dernier_echange,
                   (SELECT min(x.echeance) FROM blueseatra.relances x WHERE x.tenant_id = c.tenant_id
                      AND x.client_id = c.id AND x.statut IN ('prevue', 'reportee')) AS prochaine_relance
              FROM blueseatra.clients c WHERE {where}
             ORDER BY c.raison_sociale LIMIT :limite OFFSET :decalage""", p)
        total = (await _q(f"SELECT count(*) AS n FROM blueseatra.clients c WHERE {where}",
                          {k: v for k, v in p.items() if k not in ("limite", "decalage")}, un=True))["n"]
        return {"clients": rows, "total": total, "page": page, "taille": taille}

    @r.post("/clients")
    async def creer(b: ClientIn, cu=ecriture):
        return await creer_client(b, cu.email)

    @r.get("/clients/{client_id}")
    async def lire(client_id: str, cu=lecture):
        return await lire_client(client_id)

    @r.patch("/clients/{client_id}")
    async def modifier(client_id: str, b: ClientIn, cu=ecriture):
        await lire_client(client_id)
        d = _valider_client(b)
        d["id"] = client_id
        sets = ", ".join(f"{c.strip()} = :{c.strip()}" for c in _CHAMPS_CLIENT.split(","))
        sets = sets.replace("adresse = :adresse", "adresse = CAST(:adresse AS jsonb)")
        try:
            row = await _q(f"UPDATE blueseatra.clients SET {sets}, maj_le = now() "
                           "WHERE tenant_id = :tenant_id AND id = :id RETURNING *", d, un=True, ecrit=True)
        except Exception as exc:  # noqa: BLE001
            if "clients_siret_unique" in str(exc):
                raise HTTPException(409, "Un client actif porte déjà ce SIRET.")
            raise
        await _audit_log(cu.email, "client.update", client_id)
        return row

    @r.post("/clients/{client_id}/archiver")
    async def archiver(client_id: str, cu=gestion):
        await lire_client(client_id)
        await _q("UPDATE blueseatra.clients SET archive_le = now(), maj_le = now() "
                 "WHERE tenant_id = :tenant_id AND id = :id", {"id": client_id}, ecrit=True)
        await annuler_relances(client_id=client_id, evenement="client_archive")
        await _audit_log(cu.email, "client.archive", client_id)
        return {"ok": True}

    @r.post("/clients/{client_id}/restaurer")
    async def restaurer(client_id: str, cu=gestion):
        await lire_client(client_id)
        await _q("UPDATE blueseatra.clients SET archive_le = NULL, maj_le = now() "
                 "WHERE tenant_id = :tenant_id AND id = :id", {"id": client_id}, ecrit=True)
        await _audit_log(cu.email, "client.restore", client_id)
        return {"ok": True}

    @r.get("/clients/{client_id}/resume")
    async def resume(client_id: str, cu=lecture):
        await lire_client(client_id)
        k = await _q("""
            SELECT coalesce(sum(total_ht) FILTER (WHERE issue = 'accepte'), 0) AS signe_ht,
                   count(*) FILTER (WHERE status = 'sent' AND coalesce(issue, 'en_attente') = 'en_attente') AS en_attente,
                   coalesce(sum(total_ht) FILTER (WHERE status = 'sent' AND coalesce(issue, 'en_attente') = 'en_attente'), 0) AS en_attente_ht,
                   count(*) FILTER (WHERE issue = 'accepte') AS acceptes,
                   count(*) FILTER (WHERE issue IN ('accepte', 'refuse', 'sans_suite')) AS conclus,
                   avg(extract(epoch FROM (issue_le - CAST(nullif(sent_at, '') AS timestamptz))) / 86400)
                       FILTER (WHERE issue_le IS NOT NULL AND nullif(sent_at, '') IS NOT NULL) AS delai_reponse_j
              FROM blueseatra.quotes WHERE tenant_id = :tenant_id AND client_id = :id""", {"id": client_id}, un=True)
        k["taux_transformation"] = round(k["acceptes"] / k["conclus"], 3) if k["conclus"] else None
        k["delai_reponse_j"] = round(k["delai_reponse_j"], 1) if k["delai_reponse_j"] is not None else None
        k["prochaine_relance"] = await _q("""
            SELECT x.id, x.devis_id, x.echeance, x.canal, x.raison, q.number AS numero
              FROM blueseatra.relances x LEFT JOIN blueseatra.quotes q ON q.id = x.devis_id AND q.tenant_id = x.tenant_id
             WHERE x.tenant_id = :tenant_id AND x.client_id = :id AND x.statut IN ('prevue', 'reportee')
             ORDER BY x.echeance LIMIT 1""", {"id": client_id}, un=True)
        return k

    @r.get("/clients/{client_id}/devis")
    async def devis_du_client(client_id: str, cu=lecture):
        await lire_client(client_id)
        devis = await _q("""SELECT id, number, status, issue, total_ht, created_at, sent_at, valable_jusqu_au, object
                              FROM blueseatra.quotes WHERE tenant_id = :tenant_id
                               AND (client_id = :id OR client_final_id = :id) ORDER BY created_at DESC LIMIT 200""",
                         {"id": client_id})
        demandes = await _q("""SELECT id, title, status, created_at FROM blueseatra.requests
                                WHERE tenant_id = :tenant_id AND (client_id = :id OR client_final_id = :id)
                                ORDER BY created_at DESC LIMIT 200""", {"id": client_id})
        return {"devis": devis, "demandes": demandes}

    # --- Contacts ---------------------------------------------------------
    @r.get("/clients/{client_id}/contacts")
    async def contacts(client_id: str, cu=lecture):
        return await _q("""SELECT * FROM blueseatra.contacts WHERE tenant_id = :tenant_id AND client_id = :id
                           AND archive_le IS NULL ORDER BY principal DESC, nom""", {"id": client_id})

    async def _retirer_principal(client_id: str, sauf: str | None = None):
        await _q("""UPDATE blueseatra.contacts SET principal = false WHERE tenant_id = :tenant_id
                    AND client_id = :cid AND principal AND id <> coalesce(CAST(:sauf AS varchar), '')""",
                 {"cid": client_id, "sauf": sauf}, ecrit=True)

    @r.post("/clients/{client_id}/contacts")
    async def creer_contact(client_id: str, b: ContactIn, cu=ecriture):
        await lire_client(client_id)
        if b.principal:
            await _retirer_principal(client_id)
        d = b.model_dump() | {"id": _id(), "cid": client_id}
        row = await _q("""INSERT INTO blueseatra.contacts (id, tenant_id, client_id, civilite, prenom, nom, fonction,
                            email, telephone, mobile, langue, principal, accepte_relances)
                          VALUES (:id, :tenant_id, :cid, :civilite, :prenom, :nom, :fonction, :email, :telephone,
                                  :mobile, :langue, :principal, :accepte_relances) RETURNING *""", d, un=True, ecrit=True)
        await _audit_log(cu.email, "contact.create", row["id"], {"client_id": client_id})
        return row

    @r.patch("/contacts/{contact_id}")
    async def modifier_contact(contact_id: str, b: ContactIn, cu=ecriture):
        c = await _q("SELECT client_id, anonymise_le FROM blueseatra.contacts WHERE tenant_id = :tenant_id AND id = :id",
                     {"id": contact_id}, un=True)
        if not c:
            raise HTTPException(404, "Contact introuvable.")
        if c["anonymise_le"]:
            raise HTTPException(400, "Contact anonymisé : il ne peut plus être modifié.")
        if b.principal:
            await _retirer_principal(c["client_id"], contact_id)
        row = await _q("""UPDATE blueseatra.contacts SET civilite = :civilite, prenom = :prenom, nom = :nom,
                            fonction = :fonction, email = :email, telephone = :telephone, mobile = :mobile,
                            langue = :langue, principal = :principal, accepte_relances = :accepte_relances, maj_le = now()
                          WHERE tenant_id = :tenant_id AND id = :id RETURNING *""",
                       b.model_dump() | {"id": contact_id}, un=True, ecrit=True)
        if not b.accepte_relances:
            await annuler_relances(contact_id=contact_id, evenement="contact_oppose", garder_taches=True)
        return row

    @r.post("/contacts/{contact_id}/archiver")
    async def archiver_contact(contact_id: str, cu=gestion):
        await _q("UPDATE blueseatra.contacts SET archive_le = now(), principal = false WHERE tenant_id = :tenant_id AND id = :id",
                 {"id": contact_id}, ecrit=True)
        await _audit_log(cu.email, "contact.archive", contact_id)
        return {"ok": True}

    @r.post("/contacts/{contact_id}/anonymiser")
    async def anonymiser(contact_id: str, cu=gestion):
        row = await _q("""UPDATE blueseatra.contacts SET civilite = NULL, prenom = NULL, nom = 'Contact anonymisé',
                             fonction = NULL, email = NULL, telephone = NULL, mobile = NULL, principal = false,
                             accepte_relances = false, anonymise_le = now(), archive_le = coalesce(archive_le, now())
                           WHERE tenant_id = :tenant_id AND id = :id RETURNING id""", {"id": contact_id}, un=True, ecrit=True)
        if not row:
            raise HTTPException(404, "Contact introuvable.")
        await annuler_relances(contact_id=contact_id, evenement="contact_oppose")
        await _audit_log(cu.email, "contact.anonymize", contact_id)
        return {"ok": True}

    # --- Chantiers --------------------------------------------------------
    @r.get("/clients/{client_id}/chantiers")
    async def chantiers(client_id: str, cu=lecture):
        return await _q("""SELECT * FROM blueseatra.chantiers WHERE tenant_id = :tenant_id AND client_id = :id
                           AND archive_le IS NULL ORDER BY nom""", {"id": client_id})

    @r.post("/clients/{client_id}/chantiers")
    async def creer_chantier(client_id: str, b: ChantierIn, cu=ecriture):
        await lire_client(client_id)
        row = await _q("""INSERT INTO blueseatra.chantiers (id, tenant_id, client_id, nom, code_site, adresse, acces)
                          VALUES (:id, :tenant_id, :cid, :nom, :code_site, CAST(:adresse AS jsonb), :acces) RETURNING *""",
                       {"id": _id(), "cid": client_id, "nom": b.nom, "code_site": b.code_site,
                        "adresse": json.dumps(b.adresse.model_dump()), "acces": b.acces}, un=True, ecrit=True)
        await _audit_log(cu.email, "chantier.create", row["id"], {"client_id": client_id})
        return row

    @r.patch("/chantiers/{chantier_id}")
    async def modifier_chantier(chantier_id: str, b: ChantierIn, cu=ecriture):
        row = await _q("""UPDATE blueseatra.chantiers SET nom = :nom, code_site = :code_site,
                            adresse = CAST(:adresse AS jsonb), acces = :acces, maj_le = now()
                          WHERE tenant_id = :tenant_id AND id = :id RETURNING *""",
                       {"id": chantier_id, "nom": b.nom, "code_site": b.code_site,
                        "adresse": json.dumps(b.adresse.model_dump()), "acces": b.acces}, un=True, ecrit=True)
        if not row:
            raise HTTPException(404, "Chantier introuvable.")
        return row

    @r.post("/chantiers/{chantier_id}/archiver")
    async def archiver_chantier(chantier_id: str, cu=gestion):
        await _q("UPDATE blueseatra.chantiers SET archive_le = now() WHERE tenant_id = :tenant_id AND id = :id",
                 {"id": chantier_id}, ecrit=True)
        return {"ok": True}

    # --- Échanges ---------------------------------------------------------
    @r.get("/clients/{client_id}/echanges")
    async def echanges(client_id: str, limite: int = Query(100, ge=1, le=500), cu=lecture):
        return await _q("""SELECT * FROM blueseatra.echanges_clients WHERE tenant_id = :tenant_id AND client_id = :id
                           ORDER BY survenu_le DESC, id DESC LIMIT :limite""", {"id": client_id, "limite": limite})

    @r.post("/clients/{client_id}/echanges")
    async def ajouter_echange(client_id: str, b: EchangeIn, cu=ecriture):
        await lire_client(client_id)
        if b.type not in ("appel", "email", "visite", "note", "correction"):
            raise HTTPException(400, "Type d'échange inconnu.")
        if b.type == "correction" and not b.corrige_id:
            raise HTTPException(400, "Une correction doit désigner l'échange corrigé.")
        row = await _q("""INSERT INTO blueseatra.echanges_clients (tenant_id, client_id, contact_id, devis_id, chantier_id,
                             type, resume, corrige_id, auteur)
                          VALUES (:tenant_id, :cid, :contact_id, :devis_id, :chantier_id, :type, :resume, :corrige_id, :auteur)
                          RETURNING *""", b.model_dump() | {"cid": client_id, "auteur": cu.email}, un=True, ecrit=True)
        return row

    # --- Suggestions ------------------------------------------------------
    @r.get("/suggestions-clients")
    async def suggestions(demande_id: Optional[str] = None, cu=lecture):
        cond = "tenant_id = :tenant_id AND statut = 'a_valider'"
        p: dict = {}
        if demande_id:
            cond += " AND demande_id = :d"
            p["d"] = demande_id
        rows = await _q(f"""SELECT * FROM blueseatra.suggestions_clients WHERE {cond}
                            ORDER BY CASE force WHEN 'exacte' THEN 0 WHEN 'probable' THEN 1 ELSE 2 END, cree_le DESC
                            LIMIT 200""", p)
        auto = []
        if demande_id:
            auto = await _q("""SELECT * FROM blueseatra.suggestions_clients WHERE tenant_id = :tenant_id
                               AND demande_id = :d AND statut = 'acceptee' AND traite_par = 'automatique'""", {"d": demande_id})
        return {"a_valider": rows, "rattachements_auto": auto}

    @r.post("/suggestions-clients/{sid}/accepter")
    async def accepter(sid: str, body: dict | None = None, cu=ecriture):
        s = await _q("SELECT * FROM blueseatra.suggestions_clients WHERE tenant_id = :tenant_id AND id = :id",
                     {"id": sid}, un=True)
        if not s or s["statut"] != "a_valider":
            raise HTTPException(404, "Suggestion introuvable ou déjà traitée.")
        body = body or {}
        v = s["valeurs"] if isinstance(s["valeurs"], dict) else json.loads(s["valeurs"])
        cible = body.get("client_id") or s.get("cible_id")
        if s["type"] == "nouveau_client" and not body.get("client_id"):
            client = await creer_client(ClientIn(
                type=v.get("type") or ("enseigne" if s.get("role") == "client_final" else "entreprise"),
                raison_sociale=v.get("raison_sociale") or "Client sans nom",
                email=v.get("email"), telephone=v.get("telephone"), siret=_siret(v.get("siret")),
                adresse=Adresse(**(v.get("adresse") or {}))), cu.email, source="suggestion_ia")
            cible = client["id"]
        elif s["type"] == "nouveau_contact" and cible:
            await creer_contact(cible, ContactIn(nom=v.get("nom"), prenom=v.get("prenom"), email=v.get("email"),
                                                 telephone=v.get("telephone")), cu)
        elif s["type"] == "nouveau_chantier" and cible:
            await creer_chantier(cible, ChantierIn(nom=v.get("nom") or "Chantier",
                                                   adresse=Adresse(**(v.get("adresse") or {}))), cu)
        if cible and s.get("demande_id") and s["type"] in ("nouveau_client", "rattachement"):
            await lier_demande(s["demande_id"], cible, s.get("role"))
        if cible and v.get("source") == "devis_existant":
            await _q("""UPDATE blueseatra.quotes SET client_id = :c WHERE tenant_id = :tenant_id AND client_id IS NULL
                        AND trim(split_part(client, :nl, 1)) = :nom""",
                     {"c": cible, "nom": v.get("raison_sociale"), "nl": "\n"}, ecrit=True)
        await _q("""UPDATE blueseatra.suggestions_clients SET statut = 'acceptee', traite_par = :p, traite_le = now(),
                    cible_id = coalesce(CAST(:c AS varchar), cible_id) WHERE tenant_id = :tenant_id AND id = :id""",
                 {"id": sid, "p": cu.email, "c": cible}, ecrit=True)
        await _audit_log(cu.email, "suggestion.accept", sid, {"type": s["type"], "cible": cible})
        return {"ok": True, "client_id": cible}

    @r.post("/suggestions-clients/{sid}/rejeter")
    async def rejeter(sid: str, cu=ecriture):
        await _q("""UPDATE blueseatra.suggestions_clients SET statut = 'rejetee', traite_par = :p, traite_le = now()
                    WHERE tenant_id = :tenant_id AND id = :id AND statut = 'a_valider'""",
                 {"id": sid, "p": cu.email}, ecrit=True)
        return {"ok": True}

    @r.post("/suggestions-clients/{sid}/annuler-rattachement")
    async def annuler_auto(sid: str, cu=ecriture):
        s = await _q("SELECT * FROM blueseatra.suggestions_clients WHERE tenant_id = :tenant_id AND id = :id",
                     {"id": sid}, un=True)
        if not s or s["traite_par"] != "automatique":
            raise HTTPException(404, "Rattachement automatique introuvable.")
        col = "client_final_id" if s.get("role") == "client_final" else "client_id"
        await _q(f"UPDATE blueseatra.requests SET {col} = NULL WHERE tenant_id = :tenant_id AND id = :d",
                 {"d": s["demande_id"]}, ecrit=True)
        await _q("""UPDATE blueseatra.suggestions_clients SET statut = 'rejetee', traite_par = :p, traite_le = now()
                    WHERE tenant_id = :tenant_id AND id = :id""", {"id": sid, "p": cu.email}, ecrit=True)
        return {"ok": True}

    @r.post("/clients/reprise-devis-existants")
    async def reprise(cu=gestion):
        n = await reprendre_devis_existants()
        await _audit_log(cu.email, "clients.reprise", "", {"suggestions": n})
        return {"suggestions_creees": n}

    # --- Devis : liens, issue --------------------------------------------
    @r.post("/quotes/{quote_id}/client")
    async def lier_devis(quote_id: str, b: LierIn, cu=ecriture):
        q = await _q("SELECT id FROM blueseatra.quotes WHERE tenant_id = :tenant_id AND id = :id", {"id": quote_id}, un=True)
        if not q:
            raise HTTPException(404, "Devis introuvable.")
        for cid in (b.client_id, b.client_final_id):
            if cid:
                await lire_client(cid)
        await _q("""UPDATE blueseatra.quotes SET client_id = :client_id, client_final_id = :client_final_id,
                      chantier_id = :chantier_id, contact_id = :contact_id, valable_jusqu_au = :valable_jusqu_au
                    WHERE tenant_id = :tenant_id AND id = :id""", b.model_dump() | {"id": quote_id}, ecrit=True)
        return await devis_suivi(quote_id)

    @r.get("/quotes/{quote_id}/suivi")
    async def suivi(quote_id: str, cu=lecture):
        return await devis_suivi(quote_id)

    @r.post("/quotes/{quote_id}/issue")
    async def issue(quote_id: str, b: IssueIn, cu=ecriture):
        if b.issue not in ISSUES:
            raise HTTPException(400, "Issue inconnue.")
        q = await _q("SELECT id, status, client_id, number FROM blueseatra.quotes WHERE tenant_id = :tenant_id AND id = :id",
                     {"id": quote_id}, un=True)
        if not q:
            raise HTTPException(404, "Devis introuvable.")
        if b.issue != "en_attente" and q["status"] != "sent":
            raise HTTPException(400, "Seul un devis envoyé peut être accepté, refusé ou classé sans suite.")
        await enregistrer_issue(q, b.issue, b.motif, cu.email)
        return await devis_suivi(quote_id)

    # --- Relances ----------------------------------------------------------
    @r.get("/relances")
    async def relances(periode: str = "tout", cu=lecture):
        fin = {"retard": "(date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris')", "aujourdhui": "(date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris') + interval '1 day'",
               "semaine": "(date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris') + interval '7 days'"}.get(periode, "now() + interval '10 years'")
        rows = await _q(f"""
            SELECT x.*, q.number AS numero, q.total_ht, q.object, c.raison_sociale AS client,
                   k.prenom, k.nom AS contact_nom,
                   CASE WHEN coalesce(k.accepte_relances, true) THEN coalesce(k.email, c.email) END AS contact_email,
                   coalesce(k.telephone, c.telephone) AS contact_telephone, k.mobile AS contact_mobile,
                   CASE WHEN x.echeance < (date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris') THEN 'retard'
                        WHEN x.echeance < (date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris') + interval '1 day' THEN 'aujourdhui'
                        ELSE 'a_venir' END AS groupe
              FROM blueseatra.relances x
              LEFT JOIN blueseatra.quotes q ON q.tenant_id = x.tenant_id AND q.id = x.devis_id
              LEFT JOIN blueseatra.clients c ON c.tenant_id = x.tenant_id AND c.id = x.client_id
              LEFT JOIN blueseatra.contacts k ON k.tenant_id = x.tenant_id AND k.id = x.contact_id
             WHERE x.tenant_id = :tenant_id AND x.statut IN ('prevue', 'reportee') AND x.echeance < {fin}
             ORDER BY x.echeance LIMIT 300""", {})
        compte = await _q("""SELECT count(*) FILTER (WHERE echeance < (date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris')) AS retard,
                                    count(*) FILTER (WHERE echeance >= (date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris')
                                                     AND echeance < (date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris') + interval '1 day') AS aujourdhui,
                                    count(*) FILTER (WHERE echeance < (date_trunc('day', now() AT TIME ZONE 'Europe/Paris') AT TIME ZONE 'Europe/Paris') + interval '7 days') AS semaine
                               FROM blueseatra.relances WHERE tenant_id = :tenant_id AND statut IN ('prevue', 'reportee')""",
                             {}, un=True)
        return {"relances": rows, "compte": compte}

    async def _relance(rid: str) -> dict:
        x = await _q("SELECT * FROM blueseatra.relances WHERE tenant_id = :tenant_id AND id = :id", {"id": rid}, un=True)
        if not x:
            raise HTTPException(404, "Relance introuvable.")
        return x

    @r.post("/relances/{rid}/faite")
    async def faite(rid: str, b: FaiteIn, cu=ecriture):
        if b.resultat not in RESULTATS:
            raise HTTPException(400, "Résultat inconnu.")
        x = await _relance(rid)
        if x["statut"] not in ("prevue", "reportee"):
            raise HTTPException(400, "Relance déjà traitée.")
        await _q("""UPDATE blueseatra.relances SET statut = 'faite', resultat = :r, faite_par = :p, faite_le = now()
                    WHERE tenant_id = :tenant_id AND id = :id""", {"id": rid, "r": b.resultat, "p": cu.email}, ecrit=True)
        libelle = {"sans_reponse": "sans réponse", "a_rappeler": "à rappeler", "accepte": "devis accepté",
                   "refuse": "devis refusé", "en_reflexion": "en réflexion"}[b.resultat]
        if x.get("client_id"):
            await _echange(x["client_id"], "relance", f"Relance {x['rang']} ({x['canal']}) : {libelle}."
                           + (f" {b.note}" if b.note else ""), cu.email,
                           devis_id=x["devis_id"], contact_id=x.get("contact_id"), relance_id=rid)
        if b.resultat in ("accepte", "refuse"):
            q = await _q("SELECT id, status, client_id, number FROM blueseatra.quotes WHERE tenant_id = :tenant_id AND id = :id",
                         {"id": x["devis_id"]}, un=True)
            if q:
                await enregistrer_issue(q, b.resultat, b.note, cu.email)
        elif b.resultat == "a_rappeler":
            regles = await charger_regles()
            ech = rr.apres_resultat("a_rappeler", _maintenant(), regles)
            rang = await _prochain_rang_libre(x["devis_id"])
            if rang:
                await _q("""INSERT INTO blueseatra.relances (id, tenant_id, devis_id, client_id, contact_id, rang, echeance,
                               canal, raison, creee_par)
                             VALUES (:id, :tenant_id, :d, :c, :k, :rang, :e, 'appel', :raison, :p)""",
                         {"id": _id(), "d": x["devis_id"], "c": x.get("client_id"), "k": x.get("contact_id"),
                          "rang": rang, "e": ech, "p": cu.email,
                          "raison": f"Rappel demandé lors de la relance {x['rang']} du {_maintenant():%d/%m/%Y}."},
                         ecrit=True)
        return {"ok": True}

    @r.post("/relances/{rid}/reporter")
    async def reporter(rid: str, b: ReporterIn, cu=ecriture):
        x = await _relance(rid)
        if x["statut"] not in ("prevue", "reportee"):
            raise HTTPException(400, "Relance déjà traitée.")
        regles = await charger_regles()
        if b.date:
            j = b.date
        else:
            j = rr.ajouter_jours_ouvres(_maintenant().date(), b.jours_ouvres or 1)
        ech = datetime.combine(j, regles.heure_relance, tzinfo=rr.ZoneInfo(regles.fuseau))
        await _q("UPDATE blueseatra.relances SET statut = 'reportee', echeance = :e WHERE tenant_id = :tenant_id AND id = :id",
                 {"id": rid, "e": ech}, ecrit=True)
        return {"ok": True, "echeance": ech.isoformat()}

    @r.post("/relances/{rid}/annuler")
    async def annuler(rid: str, body: dict | None = None, cu=ecriture):
        await _relance(rid)
        await _q("""UPDATE blueseatra.relances SET statut = 'annulee', motif_annulation = :m
                    WHERE tenant_id = :tenant_id AND id = :id AND statut IN ('prevue', 'reportee')""",
                 {"id": rid, "m": ((body or {}).get("motif") or "Annulée par l'utilisateur")[:255]}, ecrit=True)
        return {"ok": True}

    @r.get("/regles-relance")
    async def lire_regles(cu=lecture):
        g = await charger_regles()
        return {"actif": g.actif, "delais_jours_ouvres": list(g.delais_jours_ouvres),
                "delais_urgent": list(g.delais_urgent), "max_relances": g.max_relances,
                "validite_devis_jours": g.validite_devis_jours, "rappel_avant_expiration_j": g.rappel_avant_expiration_j,
                "seuil_appel_ht": g.seuil_appel_ht, "heure_relance": g.heure_relance.strftime("%H:%M"), "fuseau": g.fuseau,
                "apercu": [{"rang": p.rang, "echeance": p.echeance.isoformat(), "canal": p.canal, "raison": p.raison}
                           for p in rr.planifier(rr.Devis("apercu", "D-EXEMPLE", _maintenant(), 2400,
                                                          contact_email="contact@exemple.fr",
                                                          valable_jusqu_au=_maintenant().date()
                                                          + timedelta(days=g.validite_devis_jours)), g)]}

    @r.put("/regles-relance")
    async def ecrire_regles(b: ReglesIn, cu=gestion):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", b.heure_relance):
            raise HTTPException(400, "Heure au format HH:MM.")
        for liste in (b.delais_jours_ouvres, b.delais_urgent):
            if not liste or any(not 1 <= d <= 60 for d in liste):
                raise HTTPException(400, "Délais entre 1 et 60 jours ouvrés.")
        await _q("""INSERT INTO blueseatra.regles_relance (tenant_id, actif, delais_jours_ouvres, delais_urgent, max_relances,
                        validite_devis_jours, rappel_avant_expiration_j, seuil_appel_ht, heure_relance, maj_par, maj_le)
                    VALUES (:tenant_id, :actif, :d, :u, :max_relances, :validite_devis_jours, :rappel_avant_expiration_j,
                            :seuil_appel_ht, :heure, :p, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET actif = EXCLUDED.actif, delais_jours_ouvres = EXCLUDED.delais_jours_ouvres,
                        delais_urgent = EXCLUDED.delais_urgent, max_relances = EXCLUDED.max_relances,
                        validite_devis_jours = EXCLUDED.validite_devis_jours,
                        rappel_avant_expiration_j = EXCLUDED.rappel_avant_expiration_j,
                        seuil_appel_ht = EXCLUDED.seuil_appel_ht, heure_relance = EXCLUDED.heure_relance,
                        maj_par = EXCLUDED.maj_par, maj_le = now()""",
                 b.model_dump() | {"d": b.delais_jours_ouvres[:6], "u": b.delais_urgent[:6], "p": cu.email,
                                   "heure": datetime.strptime(b.heure_relance, "%H:%M").time()}, ecrit=True)
        if not b.actif:
            await annuler_relances(evenement="regles_desactivees")
        await _audit_log(cu.email, "relances.rules_update", "")
        return await lire_regles(cu)

    # --- Import / export ---------------------------------------------------
    COLONNES = ("raison_sociale", "type", "siret", "email", "telephone", "adresse", "code_postal", "ville",
                "nom_commercial", "tva_intra", "site_web", "langue", "etiquettes", "notes")
    SYNONYMES = {"raison_sociale": ("raison sociale", "nom", "client", "societe", "société", "entreprise", "name", "company"),
                 "siret": ("siret",), "email": ("email", "e-mail", "mail", "courriel"),
                 "telephone": ("telephone", "téléphone", "tel", "tél", "phone"),
                 "adresse": ("adresse", "address", "rue"), "code_postal": ("code postal", "cp", "zip", "postal code"),
                 "ville": ("ville", "city", "commune"), "type": ("type",), "nom_commercial": ("nom commercial", "enseigne"),
                 "tva_intra": ("tva", "tva intra", "n° tva", "vat"), "site_web": ("site", "site web", "website"),
                 "langue": ("langue", "language"), "etiquettes": ("etiquettes", "étiquettes", "tags"), "notes": ("notes", "remarques")}

    def _lire_csv(contenu: bytes) -> tuple[list[str], list[dict]]:
        txt = contenu.decode("utf-8-sig", errors="replace")
        try:
            dialecte = csv.Sniffer().sniff(txt[:4000], delimiters=";,\t")
        except csv.Error:
            dialecte = csv.excel
            dialecte.delimiter = ";"
        lignes = list(csv.DictReader(io.StringIO(txt), dialect=dialecte))
        return (list(lignes[0].keys()) if lignes else []), lignes[:5000]

    def _mapping(entetes: list[str]) -> dict:
        m = {}
        for champ, noms in SYNONYMES.items():
            for e in entetes:
                if normaliser(e) in {normaliser(n) for n in noms} and champ not in m:
                    m[champ] = e
        return m

    @r.post("/clients/import/preview")
    async def import_apercu(file: UploadFile = File(...), cu=ecriture):
        contenu = await file.read()
        if len(contenu) > 5 * 1024 * 1024:
            raise HTTPException(413, "Fichier trop volumineux (5 Mo au maximum).")
        entetes, lignes = _lire_csv(contenu)
        return {"entetes": entetes, "mapping": _mapping(entetes), "apercu": lignes[:10], "lignes": len(lignes)}

    @r.post("/clients/import")
    async def importer(file: UploadFile = File(...), mapping: str = "", cu=ecriture):
        contenu = await file.read()
        if len(contenu) > 5 * 1024 * 1024:
            raise HTTPException(413, "Fichier trop volumineux (5 Mo au maximum).")
        entetes, lignes = _lire_csv(contenu)
        m = json.loads(mapping) if mapping else _mapping(entetes)
        if "raison_sociale" not in m:
            raise HTTPException(400, "Colonne du nom du client introuvable.")
        crees, doublons, erreurs = 0, [], []
        for i, l in enumerate(lignes, start=2):
            val = {k: (l.get(col) or "").strip() for k, col in m.items()}
            if not val.get("raison_sociale"):
                continue
            try:
                await creer_client(ClientIn(
                    raison_sociale=val["raison_sociale"],
                    type=val.get("type") if val.get("type") in TYPES_CLIENT else "entreprise",
                    siret=val.get("siret") or None, email=val.get("email") or None,
                    telephone=val.get("telephone") or None, nom_commercial=val.get("nom_commercial") or None,
                    tva_intra=val.get("tva_intra") or None, site_web=val.get("site_web") or None,
                    langue=val.get("langue") if val.get("langue") in ("fr", "en") else "fr",
                    etiquettes=[e for e in re.split(r"[,|]", val.get("etiquettes", "")) if e.strip()],
                    notes=val.get("notes") or None,
                    adresse=Adresse(ligne1=val.get("adresse") or None, code_postal=val.get("code_postal") or None,
                                    ville=val.get("ville") or None)), cu.email, source="import")
                crees += 1
            except HTTPException as e:
                (doublons if e.status_code == 409 else erreurs).append({"ligne": i, "message": e.detail})
            except Exception as e:  # noqa: BLE001
                erreurs.append({"ligne": i, "message": str(e)[:200]})
        await _audit_log(cu.email, "clients.import", "", {"crees": crees, "doublons": len(doublons), "erreurs": len(erreurs)})
        return {"crees": crees, "doublons": doublons[:100], "erreurs": erreurs[:100]}

    @r.get("/clients-export.csv")
    async def exporter(cu=gestion):
        rows = await _q("""SELECT raison_sociale, type, nom_commercial, siret, tva_intra, email, telephone,
                                  adresse->>'ligne1' AS adresse, adresse->>'code_postal' AS code_postal,
                                  adresse->>'ville' AS ville, langue, array_to_string(etiquettes, ',') AS etiquettes,
                                  cree_le, archive_le
                             FROM blueseatra.clients WHERE tenant_id = :tenant_id ORDER BY raison_sociale""", {})
        buf = io.StringIO()
        buf.write("\ufeff")
        w = csv.writer(buf, delimiter=";")
        w.writerow(list(rows[0].keys()) if rows else ["raison_sociale"])
        for x in rows:
            w.writerow(["" if v is None else v for v in x.values()])
        await _audit_log(cu.email, "clients.export", "", {"lignes": len(rows)})
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": "attachment; filename=clients-blueseatra.csv"})

    return r


# --- Fonctions utilisées par server.py ----------------------------------------

async def charger_regles() -> rr.Regles:
    g = await _q("SELECT * FROM blueseatra.regles_relance WHERE tenant_id = :tenant_id", {}, un=True)
    if not g:
        return rr.Regles()
    h = g["heure_relance"]
    heure = h if hasattr(h, "hour") else datetime.strptime(str(h)[:5], "%H:%M").time()
    return rr.Regles(actif=g["actif"], delais_jours_ouvres=tuple(g["delais_jours_ouvres"]),
                     delais_urgent=tuple(g["delais_urgent"]), max_relances=g["max_relances"],
                     validite_devis_jours=g["validite_devis_jours"],
                     rappel_avant_expiration_j=g["rappel_avant_expiration_j"],
                     seuil_appel_ht=float(g["seuil_appel_ht"]), heure_relance=heure, fuseau=g["fuseau"])


async def devis_suivi(quote_id: str) -> dict:
    q = await _q("""SELECT q.id, q.client_id, q.client_final_id, q.chantier_id, q.contact_id, q.issue, q.issue_le,
                           q.motif_issue, q.valable_jusqu_au, c.raison_sociale AS client_nom,
                           f.raison_sociale AS client_final_nom
                      FROM blueseatra.quotes q
                      LEFT JOIN blueseatra.clients c ON c.tenant_id = q.tenant_id AND c.id = q.client_id
                      LEFT JOIN blueseatra.clients f ON f.tenant_id = q.tenant_id AND f.id = q.client_final_id
                     WHERE q.tenant_id = :tenant_id AND q.id = :id""", {"id": quote_id}, un=True)
    if not q:
        raise HTTPException(404, "Devis introuvable.")
    q["relances"] = await _q("""SELECT id, rang, echeance, canal, raison, statut, resultat, motif_annulation
                                  FROM blueseatra.relances WHERE tenant_id = :tenant_id AND devis_id = :id ORDER BY rang""",
                             {"id": quote_id})
    return q


async def _prochain_rang_libre(devis_id: str) -> int | None:
    pris = {x["rang"] for x in await _q("""SELECT rang FROM blueseatra.relances WHERE tenant_id = :tenant_id
                                           AND devis_id = :d AND statut <> 'annulee'""", {"d": devis_id})}
    for rang in range(1, rr.RANG_EXPIRATION):
        if rang not in pris:
            return rang
    return None


async def annuler_relances(*, devis_id: str | None = None, client_id: str | None = None,
                           contact_id: str | None = None, evenement: str, garder_taches: bool = False) -> int:
    motif = rr.motif_arret(evenement)
    cond = ["tenant_id = :tenant_id", "statut IN ('prevue', 'reportee')"]
    p: dict = {"m": motif}
    if devis_id:
        cond.append("devis_id = :d")
        p["d"] = devis_id
    if client_id:
        cond.append("client_id = :c")
        p["c"] = client_id
    if contact_id:
        cond.append("contact_id = :k")
        p["k"] = contact_id
    if garder_taches:
        cond.append("canal = 'email'")
    rows = await _q(f"""UPDATE blueseatra.relances SET statut = 'annulee', motif_annulation = :m
                        WHERE {' AND '.join(cond)} RETURNING id""", p, ecrit=True)
    return len(rows)


async def enregistrer_issue(q: dict, issue: str, motif: str | None, acteur: str) -> None:
    await _q("""UPDATE blueseatra.quotes SET issue = :i, issue_le = :le,
                  motif_issue = :m WHERE tenant_id = :tenant_id AND id = :id""",
             {"id": q["id"], "i": issue, "m": (motif or None) and motif[:255],
              "le": None if issue == "en_attente" else _maintenant()}, ecrit=True)
    if issue in ("accepte", "refuse", "sans_suite"):
        await annuler_relances(devis_id=q["id"], evenement=issue)
        if q.get("client_id"):
            t = {"accepte": "devis_accepte", "refuse": "devis_refuse", "sans_suite": "note"}[issue]
            libelle = {"accepte": "accepté", "refuse": "refusé", "sans_suite": "classé sans suite"}[issue]
            await _echange(q["client_id"], t, f"Devis {q.get('number') or ''} {libelle}."
                           + (f" Motif : {motif}" if motif else ""), acteur, devis_id=q["id"])
    await _audit_log(acteur, "quote.issue", q["id"], {"issue": issue})


async def planifier_relances_devis(quote_id: str, acteur: str) -> int:
    """Appelée à l'envoi d'un devis. Idempotente (index unique par rang)."""
    q = await _q("""SELECT q.id, q.number, q.total_ht, q.sent_at, q.client_id, q.contact_id, q.valable_jusqu_au,
                           q.request_id, q.language, q.issue, r.extracted->>'urgency' AS urgence
                      FROM blueseatra.quotes q
                      LEFT JOIN blueseatra.requests r ON r.tenant_id = q.tenant_id AND r.id = q.request_id
                     WHERE q.tenant_id = :tenant_id AND q.id = :id""", {"id": quote_id}, un=True)
    if not q or (q.get("issue") and q["issue"] != "en_attente"):
        return 0
    regles = await charger_regles()
    if not q.get("valable_jusqu_au"):
        exp = (_maintenant() + timedelta(days=regles.validite_devis_jours)).date()
        await _q("UPDATE blueseatra.quotes SET valable_jusqu_au = :v, issue = coalesce(issue, 'en_attente') "
                 "WHERE tenant_id = :tenant_id AND id = :id", {"id": quote_id, "v": exp}, ecrit=True)
        q["valable_jusqu_au"] = exp.isoformat()
    else:
        await _q("UPDATE blueseatra.quotes SET issue = coalesce(issue, 'en_attente') WHERE tenant_id = :tenant_id AND id = :id",
                 {"id": quote_id}, ecrit=True)
    contact = None
    if q.get("contact_id"):
        contact = await _q("SELECT id, email, accepte_relances, langue FROM blueseatra.contacts "
                           "WHERE tenant_id = :tenant_id AND id = :id AND archive_le IS NULL", {"id": q["contact_id"]}, un=True)
    if not contact and q.get("client_id"):
        contact = await _q("""SELECT id, email, accepte_relances, langue FROM blueseatra.contacts
                              WHERE tenant_id = :tenant_id AND client_id = :c AND archive_le IS NULL
                              ORDER BY principal DESC, cree_le LIMIT 1""", {"c": q["client_id"]}, un=True)
    client_email = None
    if q.get("client_id"):
        cl = await _q("SELECT email, langue, archive_le FROM blueseatra.clients WHERE tenant_id = :tenant_id AND id = :id",
                      {"id": q["client_id"]}, un=True)
        if cl and cl.get("archive_le"):
            return 0
        client_email = cl and cl.get("email")
    envoye = datetime.fromisoformat(q["sent_at"].replace("Z", "+00:00")) if q.get("sent_at") else _maintenant()
    valable = q["valable_jusqu_au"]
    d = rr.Devis(id=q["id"], numero=q.get("number") or q["id"][:8], envoye_le=envoye,
                 total_ht=float(q.get("total_ht") or 0), urgent=(q.get("urgence") == "urgent"),
                 valable_jusqu_au=date.fromisoformat(valable) if isinstance(valable, str) else valable,
                 contact_email=(contact or {}).get("email") or client_email,
                 contact_accepte_relances=(contact or {}).get("accepte_relances", True),
                 langue=((contact or {}).get("langue") or q.get("language") or "fr")[:2])
    n = 0
    for p in rr.planifier(d, regles, ajd=_maintenant().date()):
        rows = await _q("""INSERT INTO blueseatra.relances (id, tenant_id, devis_id, client_id, contact_id, rang, echeance,
                               canal, raison, brouillon)
                           VALUES (:id, :tenant_id, :d, :c, :k, :rang, :e, :canal, :raison, :b)
                           ON CONFLICT DO NOTHING RETURNING id""",
                        {"id": _id(), "d": quote_id, "c": q.get("client_id"), "k": (contact or {}).get("id"),
                         "rang": p.rang, "e": p.echeance, "canal": p.canal, "raison": p.raison, "b": p.brouillon},
                        ecrit=True)
        n += len(rows)
    if q.get("client_id"):
        await _echange(q["client_id"], "devis_envoye", f"Devis {d.numero} envoyé ; {n} relance(s) prévue(s).",
                       acteur, devis_id=quote_id)
    return n


async def lier_demande(demande_id: str, client_id: str, role: str | None) -> None:
    col = "client_final_id" if role == "client_final" else "client_id"
    await _q(f"UPDATE blueseatra.requests SET {col} = :c WHERE tenant_id = :tenant_id AND id = :d",
             {"c": client_id, "d": demande_id}, ecrit=True)
    # Les devis issus de la demande héritent du rattachement s'ils n'en ont pas
    await _q(f"UPDATE blueseatra.quotes SET {col} = :c WHERE tenant_id = :tenant_id AND request_id = :d AND {col} IS NULL",
             {"c": client_id, "d": demande_id}, ecrit=True)


async def _clients_actifs() -> list[dict]:
    return await _q("""SELECT id, raison_sociale, nom_commercial, siret, lower(email) AS email, recherche_norm
                         FROM blueseatra.clients WHERE tenant_id = :tenant_id AND archive_le IS NULL LIMIT 20000""", {})


def _correspondance(nom: str, email: str | None, siret: str | None, clients: list[dict]) -> tuple[dict | None, str, int]:
    """Renvoie (client, force, score). Exacte : SIRET ou e-mail identiques."""
    email = (email or "").strip().lower() or None
    for c in clients:
        if siret and c.get("siret") == siret:
            return c, "exacte", 100
        if email and c.get("email") == email:
            return c, "exacte", 100
    n = normaliser(nom)
    meilleur, score = None, 0
    if n:
        for c in clients:
            s = fuzz.token_sort_ratio(n, normaliser(c["raison_sociale"], c.get("nom_commercial")))
            if s > score:
                meilleur, score = c, s
    domaine = email.split("@", 1)[1] if email and "@" in email else None
    if score >= 90:
        return meilleur, "probable", score
    if domaine and domaine not in ("gmail.com", "hotmail.com", "outlook.fr", "orange.fr", "free.fr", "yahoo.fr",
                                   "wanadoo.fr", "sfr.fr", "laposte.net", "outlook.com", "icloud.com"):
        for c in clients:
            if c.get("email", "") and c["email"].endswith("@" + domaine):
                return c, "probable", 90
    if score >= 75:
        return meilleur, "faible", score
    return None, "", score


def _preuve(texte: str, valeur: str) -> str:
    """Phrase du document qui contient la valeur, sinon la valeur seule."""
    if not texte or not valeur:
        return f"Extrait par l'IA : « {valeur} »"
    i = normaliser(texte).find(normaliser(valeur))
    brut = texte.replace("\n", " ")
    if i < 0:
        j = brut.lower().find(valeur.lower()[:20])
        if j < 0:
            return f"Extrait par l'IA : « {valeur} »"
        i = j
    debut = max(brut.rfind(".", 0, i) + 1, i - 120, 0)
    fin = brut.find(".", i + len(valeur))
    fin = min(fin if fin > 0 else len(brut), i + len(valeur) + 120)
    return f"« {brut[debut:fin].strip()} »"


async def _suggestion(demande_id: str, type_: str, role: str | None, valeurs: dict, preuve: str, force: str,
                      cible_id: str | None = None, statut: str = "a_valider", traite_par: str | None = None) -> str:
    sid = _id()
    await _q("""INSERT INTO blueseatra.suggestions_clients (id, tenant_id, demande_id, type, cible_id, role, valeurs,
                   preuve, force, statut, traite_par, traite_le)
                VALUES (:id, :tenant_id, :d, :t, :cible, :role, CAST(:v AS jsonb), :preuve, :force, :statut, :tp, :le)""",
             {"id": sid, "d": demande_id, "t": type_, "cible": cible_id, "role": role, "v": json.dumps(valeurs),
              "preuve": preuve[:1000], "force": force, "statut": statut, "tp": traite_par,
              "le": None if statut == "a_valider" else _maintenant()}, ecrit=True)
    return sid


async def suggerer_depuis_extraction(demande_id: str, extracted: dict, raw_text: str = "") -> int:
    """Crée les suggestions d'une demande extraite. Ne lève jamais : un échec
    ici ne doit pas faire échouer la demande."""
    try:
        existantes = await _q("SELECT count(*) AS n FROM blueseatra.suggestions_clients "
                              "WHERE tenant_id = :tenant_id AND demande_id = :d", {"d": demande_id}, un=True)
        if existantes and existantes["n"]:
            return 0                                   # déjà traitée (retraitement)
        ex = extracted or {}
        clients = await _clients_actifs()
        n = 0
        roles = [("donneur_ordre", ex.get("donneur_d_ordre"), ex.get("donneur_email"), ex.get("donneur_address"), None),
                 ("client_final", ex.get("client_final") or ex.get("client_name"), ex.get("client_email"),
                  ex.get("client_address"), ex.get("client_phone"))]
        vus = set()
        for role, nom, email, adresse, tel in roles:
            nom = (nom or "").strip()
            if not nom or normaliser(nom) in vus:
                continue
            vus.add(normaliser(nom))
            siret = _siret(ex.get("siret")) if role == "donneur_ordre" else None
            c, force, score = _correspondance(nom, email, siret, clients)
            preuve = _preuve(raw_text, nom)
            if c and force == "exacte":
                await lier_demande(demande_id, c["id"], role)
                await _suggestion(demande_id, "rattachement", role, {"raison_sociale": c["raison_sociale"],
                                  "motif": "SIRET identique" if siret and c.get("siret") == siret else "e-mail identique"},
                                  preuve, "exacte", c["id"], statut="acceptee", traite_par="automatique")
            elif c:
                await _suggestion(demande_id, "rattachement", role,
                                  {"raison_sociale": c["raison_sociale"], "nom_lu": nom, "score": score},
                                  preuve, force, c["id"])
                await _suggestion(demande_id, "nouveau_client", role,
                                  {"raison_sociale": nom, "email": email, "telephone": tel,
                                   "type": "enseigne" if role == "client_final" else "entreprise",
                                   "adresse": {"ligne1": adresse} if adresse else {}}, preuve, "faible")
            else:
                await _suggestion(demande_id, "nouveau_client", role,
                                  {"raison_sociale": nom, "email": email, "telephone": tel, "siret": siret,
                                   "type": "enseigne" if role == "client_final" else "entreprise",
                                   "adresse": {"ligne1": adresse} if adresse else {}}, preuve, "probable")
            n += 1
        return n
    except Exception:  # noqa: BLE001
        log.exception("suggestions clients impossibles pour la demande %s", demande_id)
        return 0


async def reprendre_devis_existants() -> int:
    """Crée des suggestions « nouveau client » (source devis existant) à
    partir des noms déjà saisis dans les devis, regroupés par nom normalisé."""
    rows = await _q("""SELECT client, count(*) AS n FROM blueseatra.quotes WHERE tenant_id = :tenant_id
                       AND client_id IS NULL AND coalesce(trim(client), '') <> '' GROUP BY client""", {})
    clients = await _clients_actifs()
    deja = {normaliser((s["valeurs"] or {}).get("raison_sociale") if isinstance(s["valeurs"], dict)
                       else json.loads(s["valeurs"]).get("raison_sociale"))
            for s in await _q("""SELECT valeurs FROM blueseatra.suggestions_clients WHERE tenant_id = :tenant_id
                                 AND statut = 'a_valider' AND type = 'nouveau_client'""", {})}
    groupes: dict[str, tuple[str, int]] = {}
    for r in rows:
        nom = r["client"].split("\n")[0].strip()[:255]
        k = normaliser(nom)
        if not k or k in deja:
            continue
        ancien = groupes.get(k)
        groupes[k] = (nom, (ancien[1] if ancien else 0) + int(r["n"]))
    n = 0
    for k, (nom, nb) in groupes.items():
        c, force, _ = _correspondance(nom, None, None, clients)
        if c and force in ("exacte", "probable"):
            continue
        await _suggestion(None, "nouveau_client", "donneur_ordre", {"raison_sociale": nom, "devis": nb,
                          "source": "devis_existant"}, f"Nom saisi dans {nb} devis existant(s)", "probable")
        n += 1
    return n
