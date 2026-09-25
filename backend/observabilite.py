"""Observabilité et RGPD (ticket #93).

1. Journaux structurés JSON, corrélés par `request_id` et par entreprise
   pseudonymisée. Les e-mails sont masqués dans tous les messages.
2. Mesures en mémoire par route (volume, erreurs 5xx, latence p50/p95) pour
   suivre les SLO ; lecture protégée par un jeton d'exploitation.
3. RGPD par entreprise : export complet des données, anonymisation d'une
   personne par son e-mail, liste des anonymisations arrivées à échéance.
   Chaque opération est tracée dans `audit_logs`. Aucune suppression.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import time
import uuid
import zipfile
from collections import defaultdict, deque
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from database import get_current_tenant, tenant_session

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def pseudo(valeur: str | None) -> str:
    """Empreinte courte et stable (non réversible) pour les journaux."""
    if not valeur:
        return "-"
    sel = os.environ.get("LOG_PSEUDO_SEL", "blueseatra")
    return hashlib.sha256(f"{sel}:{valeur}".encode()).hexdigest()[:10]


def masquer(texte: str) -> str:
    return _EMAIL.sub(lambda m: f"<email:{pseudo(m.group(0).lower())}>", texte)


class FormatJSON(logging.Formatter):
    def format(self, rec: logging.LogRecord) -> str:
        doc = {
            "ts": datetime.fromtimestamp(rec.created, timezone.utc).isoformat(timespec="milliseconds"),
            "niveau": rec.levelname, "module": rec.name,
            "message": masquer(rec.getMessage()),
            "request_id": request_id_var.get(),
            "tenant": pseudo(_tenant_courant()),
        }
        for k in ("route", "methode", "statut", "duree_ms"):
            if hasattr(rec, k):
                doc[k] = getattr(rec, k)
        if rec.exc_info:
            doc["exception"] = masquer(self.formatException(rec.exc_info))
        return json.dumps(doc, ensure_ascii=False)


class FiltreMasquage(logging.Filter):
    """En format texte aussi, aucun e-mail en clair."""
    def filter(self, rec: logging.LogRecord) -> bool:
        # Masquer sans aplatir : certains formateurs (uvicorn.access) relisent
        # rec.args comme un tuple positionnel.
        if isinstance(rec.msg, str):
            rec.msg = masquer(rec.msg)
        if isinstance(rec.args, tuple):
            rec.args = tuple(masquer(a) if isinstance(a, str) else a for a in rec.args)
        elif isinstance(rec.args, dict):
            rec.args = {k: masquer(v) if isinstance(v, str) else v for k, v in rec.args.items()}
        if rec.exc_info and not rec.exc_text:
            rec.exc_text = masquer(logging.Formatter().formatException(rec.exc_info))
        return True


def _tenant_courant():
    try:
        return get_current_tenant()
    except Exception:
        return None


def configurer_journaux() -> None:
    """JSON si LOG_FORMAT=json, ou par défaut sur Render (variable RENDER)."""
    fmt = os.environ.get("LOG_FORMAT") or ("json" if os.environ.get("RENDER") else "texte")
    # Racine et journaux d'uvicorn (qui ne remontent pas à la racine) : les
    # traces d'exception d'uvicorn.error peuvent contenir des e-mails.
    for nom in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        for h in logging.getLogger(nom).handlers:
            if fmt == "json":
                h.setFormatter(FormatJSON())
            if not any(isinstance(f, FiltreMasquage) for f in h.filters):
                h.addFilter(FiltreMasquage())


# --- Mesures et SLO ------------------------------------------------------------
SLO = {"disponibilite_pct": 99.5, "latence_p95_ms": 1500, "taux_5xx_pct": 1.0}
_FENETRE = 2000
_mesures: dict[str, deque] = defaultdict(lambda: deque(maxlen=_FENETRE))
_demarrage = time.time()
_ID_SUR = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_log_acces = logging.getLogger("blueseatra.acces")


_SEGMENT_ID = re.compile(r"/(?:[0-9a-fA-F-]{20,}|\d+|verif-[\w-]+)(?=/|$)")


def _gabarit(request: Request) -> str:
    """Gabarit de route (/api/quotes/{quote_id}) ; à défaut, chemin dont les identifiants
    sont remplacés par {id}, pour ne jamais créer une série de mesures par objet."""
    route = request.scope.get("route")
    p = getattr(route, "path", None)
    if p and "{" in p or (p and p == request.url.path):
        return p
    return _SEGMENT_ID.sub("/{id}", request.url.path)


async def intergiciel(request: Request, call_next):
    rid = request.headers.get("x-request-id", "")
    rid = rid if _ID_SUR.match(rid) else uuid.uuid4().hex[:16]
    jeton = request_id_var.set(rid)
    t0 = time.perf_counter()
    statut = 500
    try:
        reponse = await call_next(request)
        statut = reponse.status_code
        reponse.headers["X-Request-ID"] = rid
        return reponse
    finally:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        g = _gabarit(request)
        if g.startswith("/api"):
            _mesures[g].append((time.time(), statut, ms))
        if statut >= 500 or ms > 3000:
            _log_acces.warning("requête %s %s -> %s en %s ms", request.method, g, statut, ms,
                               extra={"route": g, "methode": request.method, "statut": statut, "duree_ms": ms})
        request_id_var.reset(jeton)


def _centile(valeurs, p):
    if not valeurs:
        return None
    v = sorted(valeurs)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def instantane_mesures() -> dict:
    routes, tout = {}, []
    for g, d in _mesures.items():
        pts = list(d)
        tout += pts
        lat = [p[2] for p in pts]
        routes[g] = {"appels": len(pts), "erreurs_5xx": sum(1 for p in pts if p[1] >= 500),
                     "p50_ms": _centile(lat, 50), "p95_ms": _centile(lat, 95)}
    lat = [p[2] for p in tout]
    n5 = sum(1 for p in tout if p[1] >= 500)
    glob = {"appels": len(tout), "erreurs_5xx": n5,
            "taux_5xx_pct": round(100 * n5 / len(tout), 2) if tout else 0.0,
            "p95_ms": _centile(lat, 95)}
    etat = {"latence_p95": glob["p95_ms"] is None or glob["p95_ms"] <= SLO["latence_p95_ms"],
            "taux_5xx": glob["taux_5xx_pct"] <= SLO["taux_5xx_pct"]}
    return {"depuis": datetime.fromtimestamp(_demarrage, timezone.utc).isoformat(), "fenetre_par_route": _FENETRE,
            "slo": SLO, "global": glob, "respect_slo": etat,
            "routes": dict(sorted(routes.items(), key=lambda kv: -kv[1]["appels"]))}


# --- RGPD ----------------------------------------------------------------------
TABLES_EXPORT = {
    # table: colonnes exclues (secrets, contenus binaires)
    "company_profiles": {"logo_b64"}, "tenant_users": set(), "abonnements": set(),
    "clients": set(), "contacts": set(), "chantiers": set(), "echanges_clients": set(),
    "suggestions_clients": set(), "regles_relance": set(), "relances": set(),
    "requests": {"file_b64"}, "quotes": set(), "quote_versions": set(),
    "catalogs": set(), "catalog_versions": set(), "import_jobs": set(),
    "registre_consommation": set(), "audit_logs": set(), "settings_integrations": {"ai_key"},
}
DUREE_CONSERVATION_ANS = 3   # contacts d'un client archivé depuis plus de 3 ans


class PersonneIn(BaseModel):
    email: EmailStr
    motif: str = "Demande d'effacement (article 17 RGPD)"


def _json_defaut(o):
    if isinstance(o, (datetime,)):
        return o.isoformat()
    return str(o)


async def _lire(s, sql, params):
    r = await s.execute(text(sql), params)
    return [dict(x) for x in r.mappings().all()]


async def _audit(s, tenant, acteur, action, cible, meta):
    # INSERT : le tenant_id est fourni explicitement (celui de l'utilisateur authentifié).
    await _lire(s, """INSERT INTO blueseatra.audit_logs (id, tenant_id, actor, action, target, meta, created_at)
                            VALUES (:id, :tenant_id, :a, :ac, :c, CAST(:m AS jsonb), :at) RETURNING id""",
                    {"id": str(uuid.uuid4()), "tenant_id": tenant, "a": acteur, "ac": action, "c": cible,
                     "m": json.dumps(meta, default=_json_defaut), "at": datetime.now(timezone.utc).isoformat()})


def build_router(get_current, require_role) -> APIRouter:
    r = APIRouter(prefix="/api")
    gestion = Depends(require_role("owner", "admin"))

    @r.get("/exploitation/mesures")
    async def mesures(x_metrics_token: str | None = Header(default=None)):
        attendu = os.environ.get("BLUESEATRA_METRICS_TOKEN")
        if not attendu:
            raise HTTPException(404, "Not Found")
        if not x_metrics_token or not hashlib.sha256(x_metrics_token.encode()).digest() == hashlib.sha256(attendu.encode()).digest():
            raise HTTPException(401, "Jeton d'exploitation invalide")
        return instantane_mesures()

    @r.get("/rgpd/export")
    async def export(cu=gestion):
        """Toutes les données de l'entreprise, une table par fichier JSON, dans un zip."""
        tampon, compte = io.BytesIO(), {}
        async with tenant_session() as s:
            with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
                for table, exclues in TABLES_EXPORT.items():
                    try:
                        async with s.begin_nested():
                            lignes = await _lire(s, f"SELECT * FROM blueseatra.{table} WHERE tenant_id = :tenant_id", {"tenant_id": cu.tenant_id})
                    except Exception:
                        continue   # table absente sur cette base : ignorée
                    lignes = [{k: v for k, v in l.items() if k not in exclues} for l in lignes]
                    compte[table] = len(lignes)
                    z.writestr(f"{table}.json", json.dumps(lignes, ensure_ascii=False, indent=1, default=_json_defaut))
                membres = await _lire(s, """SELECT u.id, u.email, u.name, tu.role FROM blueseatra.tenant_users tu
                                             JOIN blueseatra.users u ON u.id = tu.user_id WHERE tu.tenant_id = :tenant_id""",
                                      {"tenant_id": cu.tenant_id})
                z.writestr("membres.json", json.dumps(membres, ensure_ascii=False, indent=1, default=_json_defaut))
                z.writestr("LISEZMOI.txt", (
                    "Export RGPD Blueseatra\n"
                    f"Entreprise : {cu.tenant_id}\nDate : {datetime.now(timezone.utc).isoformat()}\n"
                    f"Demandé par : {cu.email}\n\nUne table par fichier JSON. Exclus : mots de passe, clé IA, "
                    "fichiers binaires (logo, documents importés).\n"))
            await _audit(s, cu.tenant_id, cu.email, "rgpd.export", cu.tenant_id, {"tables": compte})
            await s.commit()
        tampon.seek(0)
        nom = f"blueseatra-export-{datetime.now(timezone.utc):%Y%m%d-%H%M}.zip"
        return StreamingResponse(tampon, media_type="application/zip",
                                 headers={"Content-Disposition": f'attachment; filename="{nom}"'})

    @r.post("/rgpd/personnes/anonymiser")
    async def anonymiser_personne(b: PersonneIn, cu=gestion):
        """Efface l'identité d'une personne (contacts et e-mail de fiche client) ; l'historique chiffré reste."""
        email = b.email.lower()
        async with tenant_session() as s:
            contacts = await _lire(s, """UPDATE blueseatra.contacts SET civilite = NULL, prenom = NULL, nom = 'Contact anonymisé',
                                              fonction = NULL, email = NULL, telephone = NULL, mobile = NULL, principal = false,
                                              accepte_relances = false, anonymise_le = now(), archive_le = coalesce(archive_le, now())
                                          WHERE tenant_id = :tenant_id AND lower(email) = :e RETURNING id""", {"tenant_id": cu.tenant_id, "e": email})
            clients = await _lire(s, """UPDATE blueseatra.clients SET email = NULL, maj_le = now()
                                         WHERE tenant_id = :tenant_id AND lower(email) = :e RETURNING id""", {"tenant_id": cu.tenant_id, "e": email})
            ids = [c["id"] for c in contacts]
            annulees = []
            if ids:
                annulees = await _lire(s, """UPDATE blueseatra.relances SET statut = 'annulee', motif_annulation = 'Anonymisation RGPD'
                                              WHERE tenant_id = :tenant_id AND contact_id = ANY(:ids) AND statut IN ('prevue', 'reportee')
                                              RETURNING id""", {"tenant_id": cu.tenant_id, "ids": ids})
            await _audit(s, cu.tenant_id, cu.email, "rgpd.anonymisation", pseudo(email),
                         {"motif": b.motif, "contacts": len(ids), "clients": len(clients), "relances_annulees": len(annulees)})
            await s.commit()
        return {"ok": True, "contacts_anonymises": len(ids), "fiches_client_modifiees": len(clients),
                "relances_annulees": len(annulees)}

    @r.get("/rgpd/echeances")
    async def echeances(cu=gestion):
        """Contacts de clients archivés depuis plus de DUREE_CONSERVATION_ANS, pas encore anonymisés."""
        async with tenant_session() as s:
            rows = await _lire(s, f"""SELECT ct.id, ct.client_id, cl.raison_sociale, cl.archive_le
                                     FROM blueseatra.contacts ct JOIN blueseatra.clients cl
                                       ON cl.id = ct.client_id AND cl.tenant_id = ct.tenant_id
                                     WHERE ct.tenant_id = :tenant_id AND ct.anonymise_le IS NULL
                                       AND cl.archive_le < now() - interval '{int(DUREE_CONSERVATION_ANS)} years'
                                     ORDER BY cl.archive_le""", {"tenant_id": cu.tenant_id})
        return {"duree_conservation_ans": DUREE_CONSERVATION_ANS, "a_anonymiser": rows}

    return r
