"""Blueseatra backend — multi-tenant B2B quoting SaaS (FastAPI + MongoDB)."""
import os
import io
import csv
import json
import uuid
import logging
import asyncio
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import jwt
import bcrypt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

import ai_service
import matching as match_engine
import quote_scenarios
import pdf_service
import mcp_bridge
from pg_adapter import PGDatabase

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Database: Supabase PostgreSQL via a motor-compatible adapter (SQLAlchemy/asyncpg).
db = PGDatabase()

JWT_SECRET = os.environ.get('JWT_SECRET')
_WEAK_SECRETS = {'', 'blueseatra-dev-secret', 'blueseatra-dev-secret-change-in-prod',
                 'change-me', 'secret', 'changeme'}
if not JWT_SECRET or JWT_SECRET in _WEAK_SECRETS or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET is missing, weak or default. Set a strong random value "
        "(e.g. `python -c \"import secrets;print(secrets.token_urlsafe(48))\"`) in backend/.env."
    )
JWT_ALGO = 'HS256'

# Encryption-at-rest for sensitive secrets (e.g. tenant-provided AI provider keys).
from cryptography.fernet import Fernet, InvalidToken  # noqa: E402

_enc_key = os.environ.get('APP_ENCRYPTION_KEY')
_fernet = Fernet(_enc_key.encode()) if _enc_key else None
_ENC_PREFIX = "enc::"


def encrypt_secret(value: str) -> str:
    if not value or not _fernet:
        return value or ""
    return _ENC_PREFIX + _fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value or not isinstance(value, str) or not value.startswith(_ENC_PREFIX):
        return value or ""
    if not _fernet:
        return ""
    try:
        return _fernet.decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except (InvalidToken, ValueError):
        return ""

app = FastAPI(title="Blueseatra API")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("blueseatra")

ROLES = ["owner", "admin", "operator", "viewer", "billing_admin"]

# Max upload size (bytes) for request documents and CSV catalog imports.
MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', str(15 * 1024 * 1024)))  # 15 MB


def _check_size(content: bytes):
    if content and len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"Fichier trop volumineux (max {MAX_UPLOAD_SIZE // (1024 * 1024)} Mo).")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user_id: str, tenant_id: str, role: str) -> str:
    payload = {
        "user_id": user_id, "tenant_id": tenant_id, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def audit(tenant_id, actor, action, target=None, meta=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "tenant_id": tenant_id, "actor": actor,
        "action": action, "target": target, "meta": meta or {}, "created_at": now_iso(),
    })


class CurrentUser(BaseModel):
    user_id: str
    email: str
    name: str
    tenant_id: str
    role: str


async def get_current(creds: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    tu = await db.tenant_users.find_one(
        {"tenant_id": payload["tenant_id"], "user_id": payload["user_id"]}, {"_id": 0})
    if not tu:
        raise HTTPException(403, "No access to tenant")
    return CurrentUser(user_id=user["id"], email=user["email"], name=user.get("name", ""),
                       tenant_id=payload["tenant_id"], role=tu["role"])


def require_role(*allowed):
    async def checker(cu: CurrentUser = Depends(get_current)):
        if cu.role not in allowed:
            raise HTTPException(403, f"Requires role: {', '.join(allowed)}")
        return cu
    return checker


DEMO_ITEMS = [
    ("DEP-001", "Deplacement technicien", "deplacement", "u", 45.00, 20, 1),
    ("MO-001", "Main d'oeuvre qualifiee", "main_oeuvre", "hr", 38.50, 20, 1),
    ("PEINT-001", "Peinture murale deux couches", "peinture", "m2", 12.50, 10, 5),
    ("PROT-001", "Protection chantier", "protection", "ens", 85.00, 20, 1),
    ("PLACO-001", "Pose placo BA13", "placo", "m2", 28.00, 10, 2),
    ("FIBRE-001", "Tirage fibre optique", "fibre", "ml", 6.20, 20, 1),
    ("MAINT-001", "Maintenance porte automatique", "maintenance", "u", 150.00, 20, 1),
    ("CONSO-001", "Consommables divers", "consommables", "ens", 25.00, 20, 1),
]


async def seed_demo_catalog(tenant_id, user_email):
    cat_id = new_id()
    ver_id = new_id()
    await db.catalogs.insert_one({
        "id": cat_id, "tenant_id": tenant_id, "name": "Catalogue de demonstration",
        "client_code": "DEMO", "created_at": now_iso(), "active_version_id": ver_id,
    })
    await db.catalog_versions.insert_one({
        "id": ver_id, "tenant_id": tenant_id, "catalog_id": cat_id, "version_number": 1,
        "status": "active", "item_count": len(DEMO_ITEMS), "error_count": 0,
        "created_at": now_iso(), "activated_at": now_iso(),
    })
    docs = []
    for code, label, cat, unit, price, vat, minq in DEMO_ITEMS:
        docs.append({
            "id": new_id(), "tenant_id": tenant_id, "catalog_id": cat_id, "version_id": ver_id,
            "item_code": code, "item_label": label, "label_norm": match_engine.normalize(label),
            "category": cat, "unit": unit, "unit_price_ht": price, "currency": "EUR",
            "vat_rate": vat, "min_qty": minq, "is_active": True, "notes": "",
        })
    await db.pricing_items.insert_many(docs)
    await audit(tenant_id, user_email, "catalog.seed", cat_id, {"items": len(docs)})


# ===========================================================================
# AUTH
# ===========================================================================
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    company: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@api.post("/auth/signup")
async def signup(body: SignupIn):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    user_id = new_id()
    tenant_id = new_id()
    await db.users.insert_one({
        "id": user_id, "email": body.email.lower(), "name": body.name,
        "password_hash": hash_pw(body.password), "created_at": now_iso(),
    })
    await db.tenants.insert_one({
        "id": tenant_id, "name": body.company, "plan": "starter", "created_at": now_iso(),
    })
    await db.tenant_users.insert_one({
        "id": new_id(), "tenant_id": tenant_id, "user_id": user_id, "role": "owner",
        "created_at": now_iso(),
    })
    await seed_demo_catalog(tenant_id, body.email.lower())
    await audit(tenant_id, body.email.lower(), "auth.signup", user_id)
    token = make_token(user_id, tenant_id, "owner")
    return {"token": token, "user": {"id": user_id, "email": body.email.lower(), "name": body.name},
            "tenant": {"id": tenant_id, "name": body.company, "role": "owner"}}


@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    tu = await db.tenant_users.find_one({"user_id": user["id"]}, {"_id": 0})
    if not tu:
        raise HTTPException(403, "User has no tenant")
    tenant = await db.tenants.find_one({"id": tu["tenant_id"]}, {"_id": 0})
    token = make_token(user["id"], tu["tenant_id"], tu["role"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name", "")},
            "tenant": {"id": tenant["id"], "name": tenant["name"], "role": tu["role"]}}


@api.get("/auth/me")
async def me(cu: CurrentUser = Depends(get_current)):
    memberships = await db.tenant_users.find({"user_id": cu.user_id}, {"_id": 0}).to_list(100)
    tenant_ids = [m["tenant_id"] for m in memberships]
    tdocs = await db.tenants.find({"id": {"$in": tenant_ids}}, {"_id": 0}).to_list(100) if tenant_ids else []
    tmap = {t["id"]: t for t in tdocs}
    tenants = [{"id": t["id"], "name": t["name"], "role": m["role"]}
               for m in memberships if (t := tmap.get(m["tenant_id"]))]
    active = await db.tenants.find_one({"id": cu.tenant_id}, {"_id": 0})
    return {
        "user": {"id": cu.user_id, "email": cu.email, "name": cu.name},
        "tenant": {"id": cu.tenant_id, "name": active["name"] if active else "", "role": cu.role},
        "tenants": tenants,
    }


@api.post("/auth/switch-tenant/{tenant_id}")
async def switch_tenant(tenant_id: str, cu: CurrentUser = Depends(get_current)):
    tu = await db.tenant_users.find_one({"tenant_id": tenant_id, "user_id": cu.user_id}, {"_id": 0})
    if not tu:
        raise HTTPException(403, "No access to tenant")
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    token = make_token(cu.user_id, tenant_id, tu["role"])
    return {"token": token, "tenant": {"id": tenant_id, "name": tenant["name"], "role": tu["role"]}}


# ===========================================================================
# MEMBERS
# ===========================================================================
class InviteIn(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=6)
    role: str = "operator"


@api.get("/members")
async def list_members(cu: CurrentUser = Depends(get_current)):
    members = await db.tenant_users.find({"tenant_id": cu.tenant_id}, {"_id": 0}).to_list(500)
    user_ids = [m["user_id"] for m in members]
    udocs = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0}).to_list(500) if user_ids else []
    umap = {u["id"]: u for u in udocs}
    out = [{"user_id": u["id"], "email": u["email"], "name": u.get("name", ""), "role": m["role"]}
           for m in members if (u := umap.get(m["user_id"]))]
    return out


@api.post("/members")
async def add_member(body: InviteIn, cu: CurrentUser = Depends(require_role("owner", "admin"))):
    if body.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        user_id = new_id()
        await db.users.insert_one({
            "id": user_id, "email": body.email.lower(), "name": body.name,
            "password_hash": hash_pw(body.password), "created_at": now_iso(),
        })
    else:
        user_id = user["id"]
        existing = await db.tenant_users.find_one({"tenant_id": cu.tenant_id, "user_id": user_id})
        if existing:
            raise HTTPException(400, "User already a member")
    await db.tenant_users.insert_one({
        "id": new_id(), "tenant_id": cu.tenant_id, "user_id": user_id, "role": body.role,
        "created_at": now_iso(),
    })
    await audit(cu.tenant_id, cu.email, "member.add", user_id, {"role": body.role})
    return {"ok": True, "user_id": user_id}


class RoleUpdate(BaseModel):
    role: str


@api.patch("/members/{user_id}")
async def update_member(user_id: str, body: RoleUpdate,
                        cu: CurrentUser = Depends(require_role("owner", "admin"))):
    if body.role not in ROLES:
        raise HTTPException(400, "Invalid role")
    res = await db.tenant_users.update_one(
        {"tenant_id": cu.tenant_id, "user_id": user_id}, {"$set": {"role": body.role}})
    if res.matched_count == 0:
        raise HTTPException(404, "Member not found")
    await audit(cu.tenant_id, cu.email, "member.role_update", user_id, {"role": body.role})
    return {"ok": True}


# ===========================================================================
# SETTINGS / INTEGRATIONS
# ===========================================================================
class IntegrationSettings(BaseModel):
    ai_provider: str = "hermes"
    ai_model: Optional[str] = None
    ai_key: Optional[str] = None
    n8n_webhook_url: Optional[str] = None


PROVIDER_MODELS = {
    
    "openai": ["gpt-5.4", "gpt-5.4-mini", "gpt-4o", "gpt-4.1"],
    "gemini": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash"],
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"],
    # Noms réels sur le VPS OVH (ovh-ai-stack / ollama list)
    "hermes": ["hermes-3", "qwen3.6:27b", "qwen2.5:14b"],
}


@api.get("/settings/integrations")
async def get_settings(cu: CurrentUser = Depends(get_current)):
    s = await db.settings_integrations.find_one({"tenant_id": cu.tenant_id}, {"_id": 0})
    if not s:
        s = {"tenant_id": cu.tenant_id, "ai_provider": "hermes", "ai_model": "hermes-3",
             "n8n_webhook_url": None}
    s = dict(s)
    s["ai_key_set"] = bool(s.get("ai_key"))
    s.pop("ai_key", None)
    return {"settings": s, "provider_models": PROVIDER_MODELS}


@api.put("/settings/integrations")
async def update_settings(body: IntegrationSettings,
                          cu: CurrentUser = Depends(require_role("owner", "admin"))):
    doc = {"tenant_id": cu.tenant_id, "ai_provider": body.ai_provider,
           "ai_model": body.ai_model, "n8n_webhook_url": body.n8n_webhook_url, "updated_at": now_iso()}
    if body.ai_key:
        doc["ai_key"] = encrypt_secret(body.ai_key)
    await db.settings_integrations.update_one({"tenant_id": cu.tenant_id}, {"$set": doc}, upsert=True)
    await audit(cu.tenant_id, cu.email, "settings.update", None,
                {"ai_provider": body.ai_provider, "ai_model": body.ai_model})
    return {"ok": True}


async def get_tenant_ai_settings(tenant_id):
    s = await db.settings_integrations.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not s:
        return {}
    if s.get("ai_key"):
        s["ai_key"] = decrypt_secret(s["ai_key"])
    return s


# ===========================================================================
# COMPANY PROFILE (for quote / pro forma PDF header & footer)
# ===========================================================================
class CompanyProfile(BaseModel):
    company_name: Optional[str] = None
    subtitle: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    country: Optional[str] = "France"
    phone: Optional[str] = None
    email: Optional[str] = None
    siret: Optional[str] = None
    tva_intra: Optional[str] = None
    capital: Optional[str] = None
    ape: Optional[str] = None
    assurance: Optional[str] = None
    iban: Optional[str] = None
    validity: Optional[str] = "3 mois"
    payment_terms: Optional[str] = None
    acceptance_text: Optional[str] = None
    logo_url: Optional[str] = None
    logo_b64: Optional[str] = None


def _intitule_with_di(obj, di_number) -> str:
    title = match_engine.short_title(obj or "", 140)
    raw = str(di_number or "").strip()
    if not raw:
        return title
    di_num = raw[2:].lstrip(" \t:-") if raw.upper().startswith("DI") else raw
    if not di_num:
        return title
    prefix = f"DI {di_num}"
    rest = title
    for start in (prefix, di_num, raw):
        if rest.upper().startswith(start.upper()):
            rest = rest[len(start):].strip()
            break
    return f"{prefix} {rest}".strip()


async def get_company_profile(tenant_id):
    p = await db.company_profiles.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not p:
        tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
        p = {"company_name": tenant["name"] if tenant else "Blueseatra", "validity": "3 mois"}
    return p


@api.get("/company-profile")
async def company_profile_get(cu: CurrentUser = Depends(get_current)):
    return await get_company_profile(cu.tenant_id)


@api.put("/company-profile")
async def company_profile_put(body: CompanyProfile,
                              cu: CurrentUser = Depends(require_role("owner", "admin"))):
    doc = {k: v for k, v in body.model_dump().items()}
    doc["tenant_id"] = cu.tenant_id
    doc["updated_at"] = now_iso()
    await db.company_profiles.update_one({"tenant_id": cu.tenant_id}, {"$set": doc}, upsert=True)
    await audit(cu.tenant_id, cu.email, "company_profile.update")
    return {"ok": True}


# ===========================================================================
# REQUESTS
# ===========================================================================
async def process_request(request_id: str, tenant_id: str, vision_pages: list | None = None):
    """vision_pages : liste d'images (une par page rendue, jamais empilees
    — voir ai_service.extract_from_pdf_pages) transmise directement en
    memoire par create_request pour les cas ou aucun fichier n'est persiste
    (PDF au calque texte illisible). Jamais lue depuis la base ou le disque
    dans ce cas — uniquement l'argument en memoire de cet appel."""
    req = await db.requests.find_one({"id": request_id, "tenant_id": tenant_id}, {"_id": 0})
    if not req:
        return
    await db.requests.update_one({"id": request_id}, {"$set": {"status": "processing"}})
    try:
        settings = await get_tenant_ai_settings(tenant_id)
        text = req.get("raw_text") or ""
        stype = req.get("source_type")
        if stype == "pdf_ocr" and vision_pages:
            extracted = await ai_service.extract_from_pdf_pages(vision_pages, settings, session_id=request_id)
            extracted["_warning"] = (
                (extracted.get("_warning") + " ") if extracted.get("_warning") else ""
            ) + "Calque texte du PDF illisible : extraction par lecture visuelle des pages (fichier non conserve)."
        elif stype == "pdf_ocr":
            # Le PDF original n'est jamais persiste (voir create_request) : le
            # rendu visuel n'existe que le temps de la tache d'arriere-plan
            # lancee a la creation. Un "retraiter" plus tard sur une demande
            # deja resolue en pdf_ocr ne peut pas relire le fichier disparu.
            raise ValueError(
                "Ce PDF a un calque texte illisible et n'est pas conserve par le SaaS : "
                "reimportez le fichier pour relancer une extraction visuelle.")
        elif stype == "image" and req.get("file_b64"):
            import base64
            extracted = await ai_service.extract_from_image(
                base64.b64decode(req["file_b64"]), settings, session_id=request_id)
        elif text.strip():
            # Gemma (role="file", raisonnement actif) est le moteur d'extraction
            # par defaut pour tout fichier importe (PDF, DOCX, XLSX, CSV, TXT),
            # tableaux inclus — decision produit du 2026-08-18. qwen2.5:14b ne
            # sert plus qu'au texte colle manuellement (source_type == "text").
            extracted = await ai_service.extract_from_text(
                text, settings, session_id=request_id, from_file=(stype != "text"))
        else:
            raise ValueError("No content to process")
        if extracted.get("_error"):
            raise RuntimeError(extracted["_error"])
        status = "needs_review" if (extracted.get("confidence") or 0) < 0.6 else "done"
        await db.requests.update_one({"id": request_id}, {"$set": {
            "status": status, "extracted": extracted,
            "language": extracted.get("language"), "confidence": extracted.get("confidence"),
            "error": extracted.get("_error"),
        }})
        await audit(tenant_id, req.get("created_by"), "request.processed", request_id,
                    {"items": len(extracted.get("line_items", [])), "lang": extracted.get("language")})
    except Exception as e:
        logger.exception("process_request failed")
        await db.requests.update_one({"id": request_id}, {"$set": {"status": "failed", "error": str(e)}})


@api.post("/requests")
async def create_request(
    background: BackgroundTasks,
    cu: CurrentUser = Depends(get_current),
    title: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    req_id = new_id()
    raw_text = text or ""
    source_type = "text"
    filename = None
    file_b64 = None
    # Rendu visuel (PDF au calque texte illisible) : les octets ne sont
    # JAMAIS ecrits en base ni sur disque. Ils ne vivent qu'en memoire, portes
    # par l'argument de la tache d'arriere-plan ci-dessous, le temps de
    # l'extraction IA — jamais dans la reponse HTTP ni dans un champ persiste.
    vision_bytes = None
    if file is not None:
        filename = file.filename
        content = await file.read()
        _check_size(content)
        lower = (filename or "").lower()
        if lower.endswith(".pdf"):
            source_type = "pdf"
            raw_text = ai_service.extract_pdf_text(content)
            # Certains PDF (police subset sans table ToUnicode, export tableau
            # vectoriel, scan) ont un calque texte illisible meme si la page
            # se lit tres bien a l'oeil. On rend alors les pages en image et on
            # extrait par vision en arriere-plan (l'appel au modele peut
            # prendre largement plus longtemps que le delai d'attente du
            # navigateur), sans jamais persister le PDF ni son rendu.
            if ai_service.pdf_needs_vision_fallback(raw_text):
                source_type = "pdf_ocr"
                # Chaque page est rendue et traitee INDIVIDUELLEMENT (jamais
                # empilee en une seule image composite) : evite les echecs
                # observes de certains modeles OCR sur des images composites
                # multi-pages (decision du 2026-08-19, voir
                # ai_service.extract_from_pdf_pages).
                vision_bytes = ai_service.render_pdf_pages_to_images(content)
        elif lower.endswith(".docx"):
            source_type = "docx"
            raw_text = ai_service.extract_docx_text(content)
        elif lower.endswith((".xlsx", ".xlsm")):
            source_type = "xlsx"
            raw_text = ai_service.extract_xlsx_text(content)
        elif lower.endswith((".csv", ".tsv")):
            source_type = "csv"
            raw_text = ai_service.extract_csv_text(content)
        elif lower.endswith(".txt"):
            source_type = "text_file"
            raw_text = ai_service.extract_plain_text(content)
        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            source_type = "image"
            import base64
            file_b64 = base64.b64encode(content).decode()
        else:
            raise HTTPException(400, "Unsupported file type")
    if not raw_text.strip() and source_type not in ("image", "pdf_ocr"):
        raise HTTPException(400, "No text or supported file provided")
    doc = {
        "id": req_id, "tenant_id": cu.tenant_id, "title": title, "source_type": source_type,
        "status": "received", "raw_text": raw_text, "filename": filename, "file_b64": file_b64,
        "extracted": None, "language": None, "confidence": None,
        "created_by": cu.email, "created_at": now_iso(),
    }
    await db.requests.insert_one(doc)
    await audit(cu.tenant_id, cu.email, "request.create", req_id, {"source": source_type})
    background.add_task(process_request, req_id, cu.tenant_id, vision_bytes)
    return {"id": req_id, "status": "received"}


@api.get("/requests")
async def list_requests(cu: CurrentUser = Depends(get_current)):
    return await db.requests.find({"tenant_id": cu.tenant_id}, {"_id": 0, "file_b64": 0}) \
        .sort("created_at", -1).to_list(500)


@api.get("/requests/{request_id}")
async def get_request(request_id: str, cu: CurrentUser = Depends(get_current)):
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id}, {"_id": 0, "file_b64": 0})
    if not r:
        raise HTTPException(404, "Request not found")
    return r


@api.get("/requests/{request_id}/file")
async def get_request_file(request_id: str, cu: CurrentUser = Depends(get_current)):
    """Renvoie le fichier original pour affichage direct dans le SaaS, UNIQUEMENT
    pour les images (deja necessaires en base pour l'extraction par vision).
    Les PDF ne sont jamais persistes (voir create_request) : leur aperçu se
    fait cote client au moment de l'import, sans passer par le serveur.
    Content-Disposition inline pour que le navigateur l'ouvre plutot que de
    le telecharger."""
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Request not found")
    if r.get("source_type") != "image" or not r.get("file_b64"):
        raise HTTPException(404, "No viewable original file for this request")
    import base64
    content = base64.b64decode(r["file_b64"])
    lower = (r.get("filename") or "").lower()
    if lower.endswith(".png"):
        media_type, ext = "image/png", "png"
    elif lower.endswith(".webp"):
        media_type, ext = "image/webp", "webp"
    else:
        media_type, ext = "image/jpeg", "jpg"
    safe_name = (r.get("filename") or f"document.{ext}").replace('"', "")
    return StreamingResponse(io.BytesIO(content), media_type=media_type,
                             headers={"Content-Disposition": f'inline; filename="{safe_name}"'})


@api.post("/requests/{request_id}/process")
async def reprocess_request(request_id: str, background: BackgroundTasks,
                            cu: CurrentUser = Depends(get_current)):
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id})
    if not r:
        raise HTTPException(404, "Request not found")
    background.add_task(process_request, request_id, cu.tenant_id)
    return {"ok": True, "status": "processing"}


async def _run_deep_vision(request_id: str, tenant_id: str, image_bytes: bytes):
    """Tache d'arriere-plan : appel synchrone HTTP evite ici car Phi-4-
    reasoning-vision-15B prend ~10-15 min mesure, largement au-dela du
    timeout du proxy HTTP de Render. Meme pattern que process_request :
    statut ecrit en base, le frontend interroge par polling."""
    settings = await get_tenant_ai_settings(tenant_id)
    await db.requests.update_one({"id": request_id}, {"$set": {"deep_vision_status": "processing"}})
    try:
        deep_result = await ai_service.escalate_to_deep_vision(image_bytes, settings)
        await db.requests.update_one({"id": request_id}, {"$set": {
            "deep_vision_result": deep_result, "deep_vision_status": "done",
        }})
        await audit(tenant_id, None, "request.deep_vision", request_id, {"engine": deep_result.get("engine")})
    except Exception as e:
        await db.requests.update_one({"id": request_id}, {"$set": {
            "deep_vision_status": "failed",
            "deep_vision_error": f"{type(e).__name__}: {e or repr(e)}",
        }})


@api.post("/requests/{request_id}/deep-vision")
async def deep_vision_escalation(request_id: str, background: BackgroundTasks,
                                 cu: CurrentUser = Depends(get_current)):
    """Escalade manuelle explicite vers Phi-4-reasoning-vision-15B (jamais
    automatique dans process_request — voir ai_service.escalate_to_deep_vision).
    Uniquement disponible pour les photos (source_type == "image") : ce sont
    les seuls fichiers dont l'octet original reste en base (file_b64). Les
    PDF ne sont jamais persistes (voir create_request), donc aucune image
    n'est disponible pour relancer une analyse apres la requete initiale.
    Tres lent (~10-15 min mesure) : traite en arriere-plan (voir
    _run_deep_vision), le frontend interroge GET /requests/{id} pour suivre
    deep_vision_status."""
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id})
    if not r:
        raise HTTPException(404, "Request not found")
    if r.get("source_type") != "image" or not r.get("file_b64"):
        raise HTTPException(
            400,
            "Analyse approfondie disponible uniquement pour les photos importees "
            "(le fichier original n'est pas conserve pour les autres types).",
        )
    import base64
    image_bytes = base64.b64decode(r["file_b64"])
    background.add_task(_run_deep_vision, request_id, cu.tenant_id, image_bytes)
    return {"ok": True, "status": "processing"}


# ===========================================================================
# CATALOGS + CSV IMPORT
# ===========================================================================
CSV_COLUMNS = ["client_code", "item_code", "item_label", "category", "unit",
               "unit_price_ht", "currency", "vat_rate", "min_qty", "is_active", "notes"]

# --- Open / dynamic CSV import -------------------------------------------------
# Canonical fields the app understands, each with a French label, whether it is
# required, a numeric flag and the list of header synonyms used for auto-detection.
STANDARD_FIELDS = [
    {"key": "item_label", "label": "Libellé / Désignation", "required": True, "numeric": False,
     "syn": ["article", "designation", "libelle", "label", "item_label", "nom", "produit",
             "description", "intitule", "prestation", "designation_article"]},
    {"key": "item_code", "label": "Code / Référence", "required": False, "numeric": False,
     "syn": ["reference", "ref", "code", "item_code", "sku", "code_article", "ref_article",
             "reference_article", "code_produit"]},
    {"key": "family", "label": "Famille / Catégorie", "required": False, "numeric": False,
     "syn": ["famille", "categorie", "category", "groupe", "group", "rubrique", "type",
             "famille_article", "lot"]},
    {"key": "unit", "label": "Unité", "required": False, "numeric": False,
     "syn": ["unite", "unit", "u", "unite_de_vente", "uv", "conditionnement"]},
    {"key": "unit_price_ht", "label": "Prix de vente HT", "required": False, "numeric": True,
     "syn": ["prix_vente_ht", "prix_vente", "prix_ht", "pu_ht", "pu", "prix", "unit_price_ht",
             "unit_price", "tarif", "tarif_ht", "pv_ht", "pvht", "prix_unitaire", "prix_unitaire_ht"]},
    {"key": "purchase_price_ht", "label": "Prix d'achat HT", "required": False, "numeric": True,
     "syn": ["prix_achat_ht", "prix_achat", "pa_ht", "pa", "cout", "cost", "purchase_price",
             "prix_revient", "paht"]},
    {"key": "vat_rate", "label": "TVA (%)", "required": False, "numeric": True,
     "syn": ["tva", "tva_%", "tva_pct", "vat", "vat_rate", "taux_tva", "tva_taux"]},
    {"key": "margin", "label": "Marge (%)", "required": False, "numeric": True,
     "syn": ["marge", "marge_%", "marge_pct", "margin", "taux_marge", "marge_taux"]},
    {"key": "brand", "label": "Marque", "required": False, "numeric": False,
     "syn": ["marque", "brand", "fabricant", "manufacturer"]},
    {"key": "supplier_main", "label": "Fournisseur principal", "required": False, "numeric": False,
     "syn": ["fournisseur_principal", "fournisseur", "supplier", "fournisseur_1", "vendor"]},
    {"key": "supplier_alt_1", "label": "Fournisseur alternatif 1", "required": False, "numeric": False,
     "syn": ["fournisseur_alternatif_1", "fournisseur_alt_1", "fournisseur_2", "supplier_alt_1",
             "fournisseur_secondaire"]},
    {"key": "supplier_alt_2", "label": "Fournisseur alternatif 2", "required": False, "numeric": False,
     "syn": ["fournisseur_alternatif_2", "fournisseur_alt_2", "fournisseur_3", "supplier_alt_2"]},
    {"key": "delay", "label": "Délai", "required": False, "numeric": False,
     "syn": ["delai", "delay", "lead_time", "delai_livraison", "disponibilite"]},
    {"key": "min_qty", "label": "Quantité min.", "required": False, "numeric": True,
     "syn": ["min_qty", "qte_min", "quantite_min", "qty_min", "minimum"]},
    {"key": "currency", "label": "Devise", "required": False, "numeric": False,
     "syn": ["currency", "devise", "monnaie"]},
    {"key": "notes", "label": "Notes", "required": False, "numeric": False,
     "syn": ["notes", "note", "commentaire", "comment", "remarque", "observations"]},
]


def normalize_header(h: str) -> str:
    """Lowercase, strip accents and collapse non-alphanumerics to single underscores."""
    s = unicodedata.normalize("NFKD", str(h or "")).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def suggest_mapping(columns):
    """Auto-detect a {standard_field: csv_column or None} mapping from header synonyms."""
    norm = {col: normalize_header(col) for col in columns}
    used = set()
    mapping = {}
    # Pass 1: exact synonym match. Pass 2: partial (contains) match.
    for field in STANDARD_FIELDS:
        chosen = None
        for col in columns:
            if col in used:
                continue
            if norm[col] in field["syn"]:
                chosen = col
                break
        if not chosen:
            for col in columns:
                if col in used:
                    continue
                ncol = norm[col]
                if any(ncol == s or ncol.startswith(s + "_") or s in ncol.split("_") for s in field["syn"]):
                    chosen = col
                    break
        if chosen:
            mapping[field["key"]] = chosen
            used.add(chosen)
        else:
            mapping[field["key"]] = None
    return mapping


def _num(v, default=0.0):
    """Robust numeric parse: handles commas, %, spaces, empty -> default."""
    try:
        s = str(v).strip().replace("%", "").replace(" ", "").replace(",", ".")
        if s in ("", "nan", "none"):
            return default
        return float(s)
    except (TypeError, ValueError):
        return default


@api.get("/catalogs")
async def list_catalogs(cu: CurrentUser = Depends(get_current)):
    cats = await db.catalogs.find({"tenant_id": cu.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    cat_ids = [c["id"] for c in cats]
    versions = await db.catalog_versions.find(
        {"tenant_id": cu.tenant_id, "catalog_id": {"$in": cat_ids}}, {"_id": 0}
    ).sort("version_number", -1).to_list(10000) if cat_ids else []
    vmap = {}
    for v in versions:
        vmap.setdefault(v["catalog_id"], []).append(v)
    for c in cats:
        c["versions"] = vmap.get(c["id"], [])
    return cats


@api.get("/catalogs/{catalog_id}/items")
async def catalog_items(catalog_id: str, cu: CurrentUser = Depends(get_current)):
    cat = await db.catalogs.find_one({"id": catalog_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not cat:
        raise HTTPException(404, "Catalog not found")
    items = await db.pricing_items.find(
        {"tenant_id": cu.tenant_id, "version_id": cat.get("active_version_id")}, {"_id": 0}).to_list(2000)
    ver = await db.catalog_versions.find_one(
        {"id": cat.get("active_version_id"), "tenant_id": cu.tenant_id}, {"_id": 0}) or {}
    return {"catalog": cat, "items": items, "columns": ver.get("columns", []), "mapping": ver.get("mapping", {})}


def _read_csv_robust(content: bytes):
    """Parse a CSV with any delimiter/encoding. Returns all columns as strings."""
    import pandas as pd
    for kwargs in ({"sep": None, "engine": "python"}, {"sep": ";"}, {"sep": ","}, {"sep": "\t"}):
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False,
                                 encoding=enc, **kwargs)
                if len(df.columns) >= 1 and not (len(df.columns) == 1 and (";" in df.columns[0] or "\t" in df.columns[0])):
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
            except Exception:
                continue
    raise HTTPException(400, "Impossible de lire le fichier CSV (format ou encodage non reconnu).")


@api.get("/catalog-template.csv")
async def catalog_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Famille", "Article", "Unité", "Marque", "Référence", "Fournisseur_principal",
                "Fournisseur_alternatif_1", "TVA_%", "Marge_%", "Prix_achat_HT", "Prix_vente_HT", "Délai"])
    w.writerow(["Gros œuvre", "Ciment CPJ 25 kg", "sac", "Knauf", "RF400000",
                "La Plateforme du Bâtiment", "Point.P", "20", "18.7", "8.66", "10.1", "2-5 j"])
    buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=blueseatra_catalog_template.csv"})


@api.post("/catalogs/import/preview")
async def import_preview(cu: CurrentUser = Depends(require_role("owner", "admin", "operator")),
                         file: UploadFile = File(...)):
    content = await file.read()
    _check_size(content)
    df = _read_csv_robust(content)
    columns = list(df.columns)
    mapping = suggest_mapping(columns)
    return {
        "columns": columns,
        "preview": df.head(5).fillna("").astype(str).to_dict(orient="records"),
        "total_rows": len(df),
        "suggested_mapping": mapping,
        "standard_fields": [{"key": f["key"], "label": f["label"], "required": f["required"]}
                            for f in STANDARD_FIELDS],
    }


@api.post("/catalogs/import")
async def import_catalog(cu: CurrentUser = Depends(require_role("owner", "admin", "operator")),
                         file: UploadFile = File(...),
                         catalog_name: str = Form(...),
                         mapping: str = Form(None),
                         activate: str = Form("true")):
    content = await file.read()
    _check_size(content)
    df = _read_csv_robust(content)
    columns = list(df.columns)

    # Effective mapping: start from auto-detection, override with user-provided mapping.
    eff = suggest_mapping(columns)
    if mapping:
        try:
            user_map = json.loads(mapping)
            for k, v in (user_map or {}).items():
                eff[k] = (v or None) if (v in columns or v in (None, "")) else eff.get(k)
        except (ValueError, TypeError):
            pass

    if not eff.get("item_label"):
        raise HTTPException(400, "Aucune colonne 'Libellé / Désignation' détectée. "
                                 "Veuillez associer une colonne au champ libellé.")

    numeric_keys = {f["key"] for f in STANDARD_FIELDS if f["numeric"]}

    def mget(row, key):
        col = eff.get(key)
        return (str(row.get(col)).strip() if col and row.get(col) is not None else "")

    cat_id = new_id()
    ver_id = new_id()
    job_id = new_id()

    existing_cat = await db.catalogs.find_one({"tenant_id": cu.tenant_id, "name": catalog_name})
    if existing_cat:
        cat_id = existing_cat["id"]
        last = await db.catalog_versions.find({"tenant_id": cu.tenant_id, "catalog_id": cat_id}) \
            .sort("version_number", -1).to_list(1)
        version_number = (last[0]["version_number"] + 1) if last else 1
    else:
        version_number = 1
        await db.catalogs.insert_one({
            "id": cat_id, "tenant_id": cu.tenant_id, "name": catalog_name,
            "client_code": "N/A", "created_at": now_iso(), "active_version_id": None,
        })

    items, errors = [], []
    for idx, row in df.iterrows():
        rownum = int(idx) + 2
        try:
            label = mget(row, "item_label")
            if not label:
                raise ValueError("Le libellé / la désignation est obligatoire")
            family = mget(row, "family")
            code = mget(row, "item_code") or f"ART-{rownum}"
            suppliers = [s for s in [mget(row, "supplier_main"),
                                     mget(row, "supplier_alt_1"),
                                     mget(row, "supplier_alt_2")] if s]
            # Preserve EVERY original CSV column verbatim.
            attributes = {col: (str(row.get(col)).strip() if row.get(col) is not None else "")
                          for col in columns}
            items.append({
                "id": new_id(), "tenant_id": cu.tenant_id, "catalog_id": cat_id, "version_id": ver_id,
                "item_code": code, "item_label": label, "label_norm": match_engine.normalize(label),
                "category": match_engine.normalize(family), "family": family,
                "unit": (mget(row, "unit") or "u").lower(),
                "brand": mget(row, "brand"),
                "reference": mget(row, "item_code"),
                "supplier_main": suppliers[0] if suppliers else "",
                "suppliers": suppliers,
                "vat_rate": _num(mget(row, "vat_rate"), 20),
                "margin": _num(mget(row, "margin"), 0),
                "purchase_price_ht": _num(mget(row, "purchase_price_ht")),
                "unit_price_ht": _num(mget(row, "unit_price_ht")),
                "currency": mget(row, "currency") or "EUR",
                "min_qty": _num(mget(row, "min_qty"), 1) or 1.0,
                "is_active": True,
                "delay": mget(row, "delay"),
                "notes": mget(row, "notes"),
                "attributes": attributes,
            })
        except Exception as e:
            errors.append({"id": new_id(), "tenant_id": cu.tenant_id, "job_id": job_id,
                           "row_number": rownum, "message": str(e),
                           "raw": {k: str(v) for k, v in row.to_dict().items()}})

    await db.catalog_versions.insert_one({
        "id": ver_id, "tenant_id": cu.tenant_id, "catalog_id": cat_id, "version_number": version_number,
        "status": "draft", "item_count": len(items), "error_count": len(errors),
        "columns": columns, "mapping": eff, "source_filename": file.filename,
        "created_at": now_iso(), "activated_at": None,
    })
    if items:
        await db.pricing_items.insert_many(items)
    if errors:
        await db.import_errors.insert_many(errors)
    await db.import_jobs.insert_one({
        "id": job_id, "tenant_id": cu.tenant_id, "catalog_id": cat_id, "version_id": ver_id,
        "filename": file.filename, "total_rows": len(df), "success_rows": len(items),
        "error_rows": len(errors), "status": "completed", "created_at": now_iso(),
    })

    activated = False
    if activate.lower() == "true" and items:
        await db.catalog_versions.update_many(
            {"tenant_id": cu.tenant_id, "catalog_id": cat_id}, {"$set": {"status": "archived"}})
        await db.catalog_versions.update_one({"id": ver_id}, {"$set": {"status": "active", "activated_at": now_iso()}})
        await db.catalogs.update_one({"id": cat_id}, {"$set": {"active_version_id": ver_id}})
        activated = True

    _evict_catalog_cache(cu.tenant_id)
    await audit(cu.tenant_id, cu.email, "catalog.import", cat_id,
                {"version": version_number, "success": len(items), "errors": len(errors), "activated": activated})
    return {"catalog_id": cat_id, "version_id": ver_id, "version_number": version_number,
            "job_id": job_id, "success_rows": len(items), "error_rows": len(errors), "activated": activated}


@api.get("/import-jobs/{job_id}/errors")
async def import_errors(job_id: str, cu: CurrentUser = Depends(get_current)):
    return await db.import_errors.find({"tenant_id": cu.tenant_id, "job_id": job_id}, {"_id": 0}).to_list(2000)


@api.post("/catalogs/{catalog_id}/activate/{version_id}")
async def activate_version(catalog_id: str, version_id: str,
                           cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    ver = await db.catalog_versions.find_one(
        {"id": version_id, "catalog_id": catalog_id, "tenant_id": cu.tenant_id})
    if not ver:
        raise HTTPException(404, "Version not found")
    await db.catalog_versions.update_many(
        {"tenant_id": cu.tenant_id, "catalog_id": catalog_id}, {"$set": {"status": "archived"}})
    await db.catalog_versions.update_one({"id": version_id}, {"$set": {"status": "active", "activated_at": now_iso()}})
    await db.catalogs.update_one({"id": catalog_id}, {"$set": {"active_version_id": version_id}})
    _evict_catalog_cache(cu.tenant_id)
    await audit(cu.tenant_id, cu.email, "catalog.activate", catalog_id, {"version_id": version_id})
    return {"ok": True}


@api.patch("/catalogs/{catalog_id}")
async def update_catalog(catalog_id: str, body: dict,
                         cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    cat = await db.catalogs.find_one({"id": catalog_id, "tenant_id": cu.tenant_id})
    if not cat:
        raise HTTPException(404, "Catalog not found")
    updates = {}
    if "client_code" in body:
        updates["client_code"] = (str(body.get("client_code") or "").strip() or "N/A")
    if "name" in body and str(body.get("name") or "").strip():
        updates["name"] = str(body["name"]).strip()
    if updates:
        await db.catalogs.update_one({"id": catalog_id, "tenant_id": cu.tenant_id}, {"$set": updates})
        _evict_catalog_cache(cu.tenant_id)
        await audit(cu.tenant_id, cu.email, "catalog.update", catalog_id, updates)
    return {"ok": True, **updates}


@api.post("/catalogs/{catalog_id}/deactivate")
async def deactivate_catalog(catalog_id: str,
                             cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    cat = await db.catalogs.find_one({"id": catalog_id, "tenant_id": cu.tenant_id})
    if not cat:
        raise HTTPException(404, "Catalog not found")
    await db.catalog_versions.update_many(
        {"tenant_id": cu.tenant_id, "catalog_id": catalog_id}, {"$set": {"status": "archived"}})
    await db.catalogs.update_one({"id": catalog_id}, {"$set": {"active_version_id": None}})
    _evict_catalog_cache(cu.tenant_id)
    await audit(cu.tenant_id, cu.email, "catalog.deactivate", catalog_id, {})
    return {"ok": True}


@api.delete("/catalogs/{catalog_id}")
async def delete_catalog(catalog_id: str,
                         cu: CurrentUser = Depends(require_role("owner", "admin"))):
    cat = await db.catalogs.find_one({"id": catalog_id, "tenant_id": cu.tenant_id})
    if not cat:
        raise HTTPException(404, "Catalog not found")
    flt = {"tenant_id": cu.tenant_id, "catalog_id": catalog_id}
    jobs = await db.import_jobs.find(flt, {"id": 1}).to_list(1000)
    if jobs:
        await db.import_errors.delete_many({"tenant_id": cu.tenant_id, "job_id": {"$in": [j["id"] for j in jobs]}})
    await db.pricing_items.delete_many(flt)
    await db.catalog_versions.delete_many(flt)
    await db.import_jobs.delete_many(flt)
    await db.catalogs.delete_one({"id": catalog_id, "tenant_id": cu.tenant_id})
    _evict_catalog_cache(cu.tenant_id)
    await audit(cu.tenant_id, cu.email, "catalog.delete", catalog_id, {"name": cat.get("name")})
    return {"ok": True}


_CATALOG_CACHE: dict = {}
_CATALOG_TTL_S = 45
_SLIM_ITEM_KEYS = (
    "id", "item_code", "item_label", "label_norm", "category", "family",
    "unit", "brand", "supplier_main", "suppliers", "unit_price_ht", "vat_rate",
    "margin", "min_qty", "currency", "is_active",
)


def _slim_item(item: dict) -> dict:
    return {k: item.get(k) for k in _SLIM_ITEM_KEYS}


def _evict_catalog_cache(tenant_id):
    """Invalide le cache catalogue du tenant après toute mutation (import/activate/
    deactivate/delete) pour ne jamais chiffrer un devis avec d'anciens prix."""
    _CATALOG_CACHE.pop(tenant_id, None)


async def get_active_catalog(tenant_id):
    now = datetime.now(timezone.utc).timestamp()
    hit = _CATALOG_CACHE.get(tenant_id)
    if hit and now - hit[0] < _CATALOG_TTL_S:
        return hit[1], hit[2]
    cat = await db.catalogs.find_one(
        {"tenant_id": tenant_id, "active_version_id": {"$ne": None}}, {"_id": 0}, sort=[("created_at", -1)])
    if not cat:
        return None, []
    raw = await db.pricing_items.find(
        {"tenant_id": tenant_id, "version_id": cat["active_version_id"]}, {"_id": 0}).to_list(5000)
    seen = set()
    items = []
    for it in raw:
        if it.get("is_active") is False:
            continue
        code = it.get("item_code") or it.get("id")
        if code in seen:
            continue
        seen.add(code)
        items.append(_slim_item(it))
    _CATALOG_CACHE[tenant_id] = (now, cat, items)
    return cat, items


@api.get("/catalog/active")
async def catalog_active(cu: CurrentUser = Depends(get_current)):
    cat, items = await get_active_catalog(cu.tenant_id)
    return {"catalog": cat, "items": items}


@api.get("/catalog/search")
async def catalog_search(q: str = Query(""), limit: int = Query(40, ge=1, le=80),
                         cu: CurrentUser = Depends(get_current)):
    cat, items = await get_active_catalog(cu.tenant_id)
    if not cat:
        return {"catalog": None, "items": []}
    needle = (q or "").strip().lower()
    if not needle:
        return {"catalog": {"name": cat.get("name"), "id": cat.get("id")}, "items": items[:limit]}
    hits = []
    for it in items:
        blob = " ".join(str(it.get(k) or "") for k in ("item_label", "item_code", "category", "family", "brand")).lower()
        if needle in blob:
            hits.append(it)
        if len(hits) >= limit:
            break
    return {"catalog": {"name": cat.get("name"), "id": cat.get("id")}, "items": hits}


# ===========================================================================
# QUOTES
# ===========================================================================
@api.post("/quotes/draft")
async def create_quote_draft(body: dict, cu: CurrentUser = Depends(get_current)):
    request_id = body.get("request_id")
    req = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id}, {"_id": 0, "file_b64": 0})
    if not req:
        raise HTTPException(404, "Request not found")
    if not req.get("extracted"):
        raise HTTPException(400, "Request not yet processed")
    cat, items = await get_active_catalog(cu.tenant_id)
    if not cat:
        raise HTTPException(400, "No active pricing catalog. Import and activate one first.")
    ver = await db.catalog_versions.find_one({"id": cat["active_version_id"]}, {"_id": 0})

    extracted0 = ai_service._normalize_extracted(dict(req["extracted"] or {}))
    settings = await get_tenant_ai_settings(cu.tenant_id)
    labels = [it.get("item_label") for it in items if it.get("item_label")]
    scenarios = quote_scenarios.split_quote_scenarios(extracted0, req.get("raw_text") or "")
    count = await db.quotes.count_documents({"tenant_id": cu.tenant_id})
    ex = req["extracted"] or {}
    client_recipient = ex.get("donneur_d_ordre") or ex.get("client_final") or ex.get("client_name") or ex.get("client")
    site_val = match_engine.clean_text(
        ex.get("intervention_address") or ex.get("intervention_site") or ex.get("location") or ex.get("site") or ""
    )
    n_opt = len(scenarios)
    created = []
    for i, extracted in enumerate(scenarios, 1):
        # Multi-option drafts already have scoped line_items. Do not block on Ollama
        # (Hermes 404 / cold start caused a 90s browser timeout on "Générer un devis").
        if n_opt == 1:
            try:
                extracted = await asyncio.wait_for(
                    ai_service.expand_work_into_materials(extracted, settings, labels),
                    timeout=15,
                )
            except Exception:
                logger.warning("expand_work_into_materials skipped for request %s", request_id)
        lines, total_ht, total_vat = match_engine.build_quote_lines(extracted, items)
        works_description = match_engine.build_works_description(extracted)
        quote_id = new_id()
        opt_label = extracted.get("option_label") or extracted.get("description") or ""
        obj_src = f"Option {i}/{n_opt} — {opt_label}" if n_opt > 1 else (ex.get("description") or opt_label)
        quote = {
            "id": quote_id, "tenant_id": cu.tenant_id, "request_id": request_id,
            "number": f"BS-{datetime.now().year}-{count + i:04d}",
            "status": "draft", "version": 1,
            "client": client_recipient, "site": site_val,
            "client_final": ex.get("client_final"),
            "object": _intitule_with_di(obj_src, ex.get("di_number")),
            "language": req.get("language"),
            "meta": {
                "doc_type": ex.get("doc_type"),
                "request_number": ex.get("request_number"),
                "di_number": ex.get("di_number"),
                "followup_number": ex.get("followup_number"),
                "response_deadline": ex.get("response_deadline"),
                "donneur_d_ordre": ex.get("donneur_d_ordre"),
                "client_final": ex.get("client_final"),
                "intervention_site": ex.get("intervention_site"),
                "required_deliverables": ex.get("required_deliverables") or [],
                "works_description": works_description,
                "option_index": i,
                "option_count": n_opt,
                "option_label": extracted.get("option_label"),
            },
            "lines": lines, "total_ht": total_ht, "total_vat": total_vat,
            "total_ttc": round(total_ht + total_vat, 2),
            "currency": items[0]["currency"] if items else "EUR",
            "pricing_snapshot": {
                "catalog_id": cat["id"], "catalog_name": cat["name"],
                "version_id": cat["active_version_id"],
                "version_number": ver["version_number"] if ver else 1, "snapshot_at": now_iso(),
            },
            "created_by": cu.email, "created_at": now_iso(),
        }
        await db.quotes.insert_one(quote)
        await audit(cu.tenant_id, cu.email, "quote.draft", quote_id,
                    {"request_id": request_id, "option": i, "options": n_opt})
        quote.pop("_id", None)
        created.append(quote)
    first = created[0]
    first["sibling_quotes"] = [{"id": q["id"], "number": q["number"], "object": q["object"]} for q in created[1:]]
    first["option_count"] = n_opt
    return first


@api.get("/quotes")
async def list_quotes(cu: CurrentUser = Depends(get_current)):
    return await db.quotes.find({"tenant_id": cu.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.get("/quotes/{quote_id}")
async def get_quote(quote_id: str, cu: CurrentUser = Depends(get_current)):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    return q


@api.patch("/quotes/{quote_id}")
async def update_quote(quote_id: str, body: dict, cu: CurrentUser = Depends(get_current)):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    if q["status"] != "draft":
        raise HTTPException(400, "Only draft quotes can be edited")

    def _num(v):
        if v in (None, ""):
            return None
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    raw_lines = body.get("lines", q.get("lines", []))
    lines = []
    for l in raw_lines:
        ltype = l.get("line_type") or "generic"
        base = {
            "line_type": ltype,
            "description": (l.get("description") or "").strip(),
            "category": l.get("category"),
            "matched_item_code": l.get("matched_item_code"),
            "matched_label": l.get("matched_label"),
            "brand": l.get("brand"),
            "supplier": l.get("supplier"),
            "margin": _num(l.get("margin")),
            "score": l.get("score", 0),
            "reasons": l.get("reasons") or [],
        }
        if ltype in ("note", "page_break", "lot", "sublot"):
            base.update({
                "qty": None, "unit": None, "unit_price_ht": None, "vat_rate": None,
                "line_ht": None, "status": ltype, "lot_number": l.get("lot_number"),
            })
            lines.append(base)
            continue
        qty = _num(l.get("qty"))
        price = _num(l.get("unit_price_ht"))
        vat = _num(l.get("vat_rate"))
        base.update({"qty": qty, "unit": (l.get("unit") or None), "unit_price_ht": price, "vat_rate": vat})
        if qty is not None and price is not None:
            base["line_ht"] = match_engine.line_amount_ht(qty, price, base.get("margin"))
            prev = l.get("status")
            base["status"] = prev if prev in ("matched", "proposed", "confirmed") else "confirmed"
        else:
            base["line_ht"] = None
            base["status"] = "to_confirm"
        lines.append(base)

    total_ht, total_vat, total_ttc = match_engine.recompute_totals(lines)
    update = {"lines": lines, "total_ht": total_ht, "total_vat": total_vat, "total_ttc": total_ttc}
    for f in ("client", "site", "object", "client_final"):
        if f in body:
            update[f] = body[f]
    if "works_description" in body:
        meta = dict(q.get("meta") or {})
        meta["works_description"] = body["works_description"]
        update["meta"] = meta
    await db.quotes.update_one({"id": quote_id}, {"$set": update})
    await audit(cu.tenant_id, cu.email, "quote.edit", quote_id)
    q.update(update)
    return q


@api.post("/quotes/{quote_id}/validate")
async def validate_quote(quote_id: str, cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    await db.quote_versions.insert_one({
        "id": new_id(), "tenant_id": cu.tenant_id, "quote_id": quote_id,
        "version": q.get("version", 1), "snapshot": q, "created_at": now_iso(),
    })
    await db.quotes.update_one({"id": quote_id}, {"$set": {"status": "validated", "validated_at": now_iso()}})
    await audit(cu.tenant_id, cu.email, "quote.validate", quote_id)
    return {"ok": True, "status": "validated"}


@api.post("/quotes/{quote_id}/send")
async def send_quote(quote_id: str, cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    await db.quotes.update_one({"id": quote_id}, {"$set": {"status": "sent", "sent_at": now_iso()}})
    await audit(cu.tenant_id, cu.email, "quote.send", quote_id)
    return {"ok": True, "status": "sent"}


@api.post("/quotes/{quote_id}/reopen")
async def reopen_quote(quote_id: str, cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    if q.get("status") not in ("validated", "sent"):
        raise HTTPException(400, "Only validated or sent quotes can be reopened")
    await db.quotes.update_one(
        {"id": quote_id},
        {"$set": {"status": "draft", "validated_at": None, "sent_at": None}},
    )
    await audit(cu.tenant_id, cu.email, "quote.reopen", quote_id)
    q["status"] = "draft"
    return q


@api.post("/quotes/{quote_id}/duplicate")
async def duplicate_quote(quote_id: str, cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    count = await db.quotes.count_documents({"tenant_id": cu.tenant_id})
    clone = dict(q)
    clone["id"] = new_id()
    clone["number"] = f"BS-{datetime.now().year}-{count + 1:04d}"
    clone["status"] = "draft"
    clone["version"] = 1
    clone["created_at"] = now_iso()
    clone["created_by"] = cu.email
    clone["validated_at"] = None
    clone["sent_at"] = None
    await db.quotes.insert_one(clone)
    await audit(cu.tenant_id, cu.email, "quote.duplicate", clone["id"], {"from": quote_id})
    clone.pop("_id", None)
    return clone


@api.post("/quotes/{quote_id}/rematch")
async def rematch_quote(quote_id: str, cu: CurrentUser = Depends(require_role("owner", "admin", "operator"))):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    if q.get("status") != "draft":
        raise HTTPException(400, "Reopen the quote before rematching")
    req = None
    if q.get("request_id"):
        req = await db.requests.find_one(
            {"id": q["request_id"], "tenant_id": cu.tenant_id}, {"_id": 0, "file_b64": 0})
    if not req or not req.get("extracted"):
        raise HTTPException(400, "No extracted request to rematch")
    cat, items = await get_active_catalog(cu.tenant_id)
    if not cat:
        raise HTTPException(400, "No active pricing catalog")
    extracted = ai_service._normalize_extracted(dict(req["extracted"] or {}))
    settings = await get_tenant_ai_settings(cu.tenant_id)
    labels = [it.get("item_label") for it in items if it.get("item_label")]
    extracted = await ai_service.expand_work_into_materials(extracted, settings, labels)
    if extracted.get("_expanded"):
        await db.requests.update_one({"id": req["id"]}, {"$set": {"extracted": extracted}})
    lines, total_ht, total_vat = match_engine.build_quote_lines(extracted, items)
    old_mat = sum(float(l.get("unit_price_ht") or 0) for l in (q.get("lines") or []) if l.get("line_type") == "material")
    new_mat = sum(float(l.get("unit_price_ht") or 0) for l in lines if l.get("line_type") == "material")
    if old_mat > 0 and new_mat <= 0:
        raise HTTPException(400, "Aucun article catalogue correspondant. Les prix du brouillon sont conservés.")
    meta = dict(q.get("meta") or {})
    meta["works_description"] = match_engine.build_works_description(extracted)
    if extracted.get("di_number"):
        meta["di_number"] = extracted.get("di_number")
    update = {
        "lines": lines, "total_ht": total_ht, "total_vat": total_vat,
        "total_ttc": round(total_ht + (total_vat or 0), 2),
        "meta": meta,
        "object": _intitule_with_di(q.get("object") or extracted.get("description"), meta.get("di_number")),
    }
    await db.quotes.update_one({"id": quote_id}, {"$set": update})
    await audit(cu.tenant_id, cu.email, "quote.rematch", quote_id)
    q.update(update)
    return q


@api.delete("/quotes/{quote_id}")
async def delete_quote(quote_id: str, cu: CurrentUser = Depends(require_role("owner", "admin"))):
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    try:
        await db.quote_versions.delete_many({"tenant_id": cu.tenant_id, "quote_id": quote_id})
        await db.quotes.delete_one({"id": quote_id, "tenant_id": cu.tenant_id})
    except Exception as e:
        logger.exception("delete_quote failed")
        raise HTTPException(500, f"Suppression impossible ({type(e).__name__}).")
    await audit(cu.tenant_id, cu.email, "quote.delete", quote_id, {"number": q.get("number")})
    return {"ok": True}


@api.patch("/requests/{request_id}")
async def update_request(request_id: str, body: dict, cu: CurrentUser = Depends(get_current)):
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id}, {"_id": 0, "file_b64": 0})
    if not r:
        raise HTTPException(404, "Request not found")
    update = {}
    if "title" in body and str(body.get("title") or "").strip():
        update["title"] = str(body["title"]).strip()
    if "raw_text" in body:
        update["raw_text"] = str(body.get("raw_text") or "")
    if not update:
        return r
    await db.requests.update_one({"id": request_id}, {"$set": update})
    await audit(cu.tenant_id, cu.email, "request.edit", request_id)
    r.update(update)
    return r


@api.delete("/requests/{request_id}")
async def delete_request(request_id: str, cu: CurrentUser = Depends(require_role("owner", "admin"))):
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Request not found")
    try:
        await db.requests.delete_one({"id": request_id, "tenant_id": cu.tenant_id})
    except Exception as e:
        logger.exception("delete_request failed")
        raise HTTPException(500, f"Suppression impossible ({type(e).__name__}).")
    await audit(cu.tenant_id, cu.email, "request.delete", request_id, {"title": r.get("title")})
    return {"ok": True}


@api.get("/quotes/{quote_id}/pdf")
async def quote_pdf(quote_id: str, token: Optional[str] = None,
                    creds: HTTPAuthorizationCredentials = Depends(security)):
    raw = creds.credentials if creds else token
    if not raw:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    tenant_id = payload["tenant_id"]
    q = await db.quotes.find_one({"id": quote_id, "tenant_id": tenant_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Quote not found")
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    profile = await get_company_profile(tenant_id)
    pdf_bytes = pdf_service.generate_quote_pdf(q, tenant["name"] if tenant else "Blueseatra", profile)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=devis_{q['number']}.pdf"})


# ===========================================================================
# DASHBOARD + AUDIT
# ===========================================================================
@api.get("/dashboard")
async def dashboard(cu: CurrentUser = Depends(get_current)):
    t = cu.tenant_id
    cat, items = await get_active_catalog(t)
    quote_proj = {"_id": 0, "lines": 0, "pricing_snapshot": 0, "extracted": 0}
    quotes = await db.quotes.find({"tenant_id": t}, quote_proj).sort("created_at", -1).to_list(800)
    req_proj = {"_id": 0, "file_b64": 0, "raw_text": 0, "extracted": 0}
    requests = await db.requests.find({"tenant_id": t}, req_proj).sort("created_at", -1).to_list(400)

    def _ht(q):
        try:
            return float(q.get("total_ht") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _month(iso):
        s = str(iso or "")
        return s[:7] if len(s) >= 7 and s[0:4].isdigit() else None

    now = datetime.now()
    months = []
    y, m = now.year, now.month
    for _ in range(11, -1, -1):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12

    by_status = {}
    monthly = {k: {"draft_ht": 0.0, "won_ht": 0.0, "count": 0} for k in months}
    for q in quotes:
        st = q.get("status") or "draft"
        bucket = by_status.setdefault(st, {"status": st, "count": 0, "ht": 0.0})
        bucket["count"] += 1
        bucket["ht"] = round(bucket["ht"] + _ht(q), 2)
        mk = _month(q.get("created_at") or q.get("updated_at"))
        if mk in monthly:
            monthly[mk]["count"] += 1
            if st == "draft":
                monthly[mk]["draft_ht"] = round(monthly[mk]["draft_ht"] + _ht(q), 2)
            elif st in ("validated", "sent"):
                monthly[mk]["won_ht"] = round(monthly[mk]["won_ht"] + _ht(q), 2)

    req_by = {}
    for r in requests:
        st = r.get("status") or "received"
        req_by[st] = req_by.get(st, 0) + 1

    drafts = by_status.get("draft", {}).get("count", 0)
    validated = by_status.get("validated", {}).get("count", 0)
    sent = by_status.get("sent", {}).get("count", 0)
    draft_ht = by_status.get("draft", {}).get("ht", 0)
    won_ht = round(
        (by_status.get("validated") or {}).get("ht", 0) + (by_status.get("sent") or {}).get("ht", 0),
        2,
    )
    slim_q = [
        {
            "id": q.get("id"),
            "number": q.get("number"),
            "status": q.get("status"),
            "client_name": q.get("client_name") or q.get("client"),
            "total_ht": q.get("total_ht"),
            "total_ttc": q.get("total_ttc"),
            "currency": q.get("currency") or "EUR",
            "created_at": q.get("created_at"),
        }
        for q in quotes[:8]
    ]
    slim_r = [
        {
            "id": r.get("id"),
            "title": r.get("title") or r.get("filename") or "Demande",
            "status": r.get("status"),
            "created_at": r.get("created_at"),
        }
        for r in requests[:8]
    ]
    awaiting_quotes = [q for q in slim_q if q.get("status") == "draft"][:6]
    awaiting_requests = [r for r in slim_r if r.get("status") in ("needs_review", "failed", "received")][:6]

    clients = {}
    for q in quotes:
        name = (q.get("client_name") or q.get("client") or "").strip() or "—"
        row = clients.setdefault(name, {"name": name, "count": 0, "ht": 0.0})
        row["count"] += 1
        row["ht"] = round(row["ht"] + _ht(q), 2)
    top_clients = sorted(clients.values(), key=lambda x: -x["ht"])[:5]

    aging = []
    for q in quotes:
        if q.get("status") != "draft":
            continue
        created = str(q.get("created_at") or "")
        aging.append({
            "id": q.get("id"),
            "number": q.get("number"),
            "client_name": q.get("client_name") or q.get("client"),
            "total_ht": q.get("total_ht"),
            "created_at": created,
        })
    aging = aging[:8]

    return {
        "kpis": {
            "requests": len(requests),
            "drafts": drafts,
            "validated": validated + sent,
            "sent": sent,
            "active_catalog_items": len(items),
            "active_catalog_name": cat["name"] if cat else None,
            "pipeline_draft_ht": draft_ht,
            "pipeline_won_ht": won_ht,
            "requests_review": req_by.get("needs_review", 0),
            "requests_failed": req_by.get("failed", 0),
            "requests_done": req_by.get("done", 0),
        },
        "pipeline": sorted(by_status.values(), key=lambda x: -x["count"]),
        "request_status": [{"status": k, "count": v} for k, v in sorted(req_by.items())],
        "monthly": [{"month": k, **monthly[k]} for k in months],
        "funnel": [
            {"key": "requests", "count": len(requests)},
            {"key": "drafts", "count": drafts},
            {"key": "validated", "count": validated},
            {"key": "sent", "count": sent},
        ],
        "awaiting_quotes": awaiting_quotes,
        "awaiting_requests": awaiting_requests,
        "recent_requests": slim_r,
        "recent_quotes": slim_q,
        "top_clients": top_clients,
        "aging_drafts": aging,
    }


@api.get("/audit")
async def audit_logs(cu: CurrentUser = Depends(get_current)):
    return await db.audit_logs.find({"tenant_id": cu.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(300)


@api.get("/")
async def root():
    return {"service": "Blueseatra API", "status": "ok"}


@api.get("/health")
async def health():
    """Lightweight liveness probe (used by Render health checks)."""
    return {"status": "healthy"}


app.include_router(api)
app.include_router(mcp_bridge.router)
# Auth uses Bearer tokens (Authorization header), not cookies. The combination
# allow_credentials=True + wildcard origin is invalid/insecure, so credentials are
# only enabled when explicit origins are configured via CORS_ORIGINS.
_cors_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '*').split(',') if o.strip()]
_allow_credentials = _cors_origins != ['*'] and '*' not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_credentials=_allow_credentials,
    allow_origins=_cors_origins or ['*'],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.tenant_users.create_index([("tenant_id", 1), ("user_id", 1)])
        for col in ["requests", "catalogs", "catalog_versions", "pricing_items", "quotes", "audit_logs"]:
            await db[col].create_index("tenant_id")
    except Exception as e:
        logger.warning(f"index creation: {e}")
    logger.info("Blueseatra API started")


@app.on_event("shutdown")
async def shutdown():
    await db.dispose()
