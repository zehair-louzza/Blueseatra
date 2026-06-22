"""Blueseatra backend — multi-tenant B2B quoting SaaS (FastAPI + MongoDB)."""
import os
import io
import csv
import json
import uuid
import logging
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import jwt
import bcrypt
import pandas as pd
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

import ai_service
import matching as match_engine
import pdf_service

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
    ai_provider: str = "emergent"
    ai_model: Optional[str] = None
    ai_key: Optional[str] = None
    n8n_webhook_url: Optional[str] = None


PROVIDER_MODELS = {
    "emergent": ["gpt-5.4", "gemini-3-flash-preview", "claude-sonnet-4-6"],
    "openai": ["gpt-5.4", "gpt-5.4-mini", "gpt-4o", "gpt-4.1"],
    "gemini": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash"],
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"],
    "oracle": ["oci-vision"],
}


@api.get("/settings/integrations")
async def get_settings(cu: CurrentUser = Depends(get_current)):
    s = await db.settings_integrations.find_one({"tenant_id": cu.tenant_id}, {"_id": 0})
    if not s:
        s = {"tenant_id": cu.tenant_id, "ai_provider": "emergent", "ai_model": "gpt-5.4",
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
async def process_request(request_id: str, tenant_id: str):
    req = await db.requests.find_one({"id": request_id, "tenant_id": tenant_id}, {"_id": 0})
    if not req:
        return
    await db.requests.update_one({"id": request_id}, {"$set": {"status": "processing"}})
    try:
        settings = await get_tenant_ai_settings(tenant_id)
        text = req.get("raw_text") or ""
        if req.get("source_type") == "image" and req.get("file_b64"):
            import base64
            extracted = await ai_service.extract_from_image(
                base64.b64decode(req["file_b64"]), settings, session_id=request_id)
        elif text.strip():
            extracted = await ai_service.extract_from_text(text, settings, session_id=request_id)
        else:
            raise ValueError("No content to process")
        status = "needs_review" if (extracted.get("confidence") or 0) < 0.6 else "done"
        await db.requests.update_one({"id": request_id}, {"$set": {
            "status": status, "extracted": extracted,
            "language": extracted.get("language"), "confidence": extracted.get("confidence"),
            "processed_at": now_iso(),
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
    if file is not None:
        filename = file.filename
        content = await file.read()
        _check_size(content)
        lower = (filename or "").lower()
        if lower.endswith(".pdf"):
            source_type = "pdf"
            raw_text = ai_service.extract_pdf_text(content)
        elif lower.endswith(".docx"):
            source_type = "docx"
            raw_text = ai_service.extract_docx_text(content)
        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            source_type = "image"
            import base64
            file_b64 = base64.b64encode(content).decode()
        else:
            raise HTTPException(400, "Unsupported file type")
    if not raw_text.strip() and source_type != "image":
        raise HTTPException(400, "No text or supported file provided")
    doc = {
        "id": req_id, "tenant_id": cu.tenant_id, "title": title, "source_type": source_type,
        "status": "received", "raw_text": raw_text, "filename": filename, "file_b64": file_b64,
        "extracted": None, "language": None, "confidence": None,
        "created_by": cu.email, "created_at": now_iso(),
    }
    await db.requests.insert_one(doc)
    await audit(cu.tenant_id, cu.email, "request.create", req_id, {"source": source_type})
    background.add_task(process_request, req_id, cu.tenant_id)
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


@api.post("/requests/{request_id}/process")
async def reprocess_request(request_id: str, background: BackgroundTasks,
                            cu: CurrentUser = Depends(get_current)):
    r = await db.requests.find_one({"id": request_id, "tenant_id": cu.tenant_id})
    if not r:
        raise HTTPException(404, "Request not found")
    background.add_task(process_request, request_id, cu.tenant_id)
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


def _read_csv_robust(content: bytes) -> pd.DataFrame:
    """Parse a CSV with any delimiter/encoding. Returns all columns as strings."""
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
    await audit(cu.tenant_id, cu.email, "catalog.delete", catalog_id, {"name": cat.get("name")})
    return {"ok": True}


async def get_active_catalog(tenant_id):
    cat = await db.catalogs.find_one(
        {"tenant_id": tenant_id, "active_version_id": {"$ne": None}}, {"_id": 0}, sort=[("created_at", -1)])
    if not cat:
        return None, []
    items = await db.pricing_items.find(
        {"tenant_id": tenant_id, "version_id": cat["active_version_id"]}, {"_id": 0}).to_list(5000)
    return cat, items


@api.get("/catalog/active")
async def catalog_active(cu: CurrentUser = Depends(get_current)):
    cat, items = await get_active_catalog(cu.tenant_id)
    return {"catalog": cat, "items": items}


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

    lines, total_ht, total_vat = match_engine.build_quote_lines(req["extracted"], items)
    count = await db.quotes.count_documents({"tenant_id": cu.tenant_id})
    quote_id = new_id()
    ex = req["extracted"]
    client_recipient = ex.get("donneur_d_ordre") or ex.get("client_final") or ex.get("client")
    site_val = ex.get("intervention_address") or ex.get("intervention_site") or ex.get("site")
    quote = {
        "id": quote_id, "tenant_id": cu.tenant_id, "request_id": request_id,
        "number": f"BS-{datetime.now().year}-{count + 1:04d}",
        "status": "draft", "version": 1,
        "client": client_recipient, "site": site_val,
        "client_final": ex.get("client_final"),
        "object": ex.get("description"),
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
    await audit(cu.tenant_id, cu.email, "quote.draft", quote_id, {"request_id": request_id})
    quote.pop("_id", None)
    return quote


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
        if ltype in ("note", "page_break"):
            base.update({"qty": None, "unit": None, "unit_price_ht": None, "vat_rate": None,
                         "line_ht": None, "status": ltype})
            lines.append(base)
            continue
        qty = _num(l.get("qty"))
        price = _num(l.get("unit_price_ht"))
        vat = _num(l.get("vat_rate"))
        base.update({"qty": qty, "unit": (l.get("unit") or None), "unit_price_ht": price, "vat_rate": vat})
        if qty is not None and price is not None:
            base["line_ht"] = round(qty * price, 2)
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
    requests_count = await db.requests.count_documents({"tenant_id": t})
    drafts = await db.quotes.count_documents({"tenant_id": t, "status": "draft"})
    validated = await db.quotes.count_documents({"tenant_id": t, "status": {"$in": ["validated", "sent"]}})
    cat, items = await get_active_catalog(t)
    recent_requests = await db.requests.find({"tenant_id": t}, {"_id": 0, "file_b64": 0}).sort("created_at", -1).to_list(5)
    recent_quotes = await db.quotes.find({"tenant_id": t}, {"_id": 0}).sort("created_at", -1).to_list(5)
    return {
        "kpis": {"requests": requests_count, "drafts": drafts, "validated": validated,
                 "active_catalog_items": len(items),
                 "active_catalog_name": cat["name"] if cat else None},
        "recent_requests": recent_requests, "recent_quotes": recent_quotes,
    }


@api.get("/audit")
async def audit_logs(cu: CurrentUser = Depends(get_current)):
    return await db.audit_logs.find({"tenant_id": cu.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(300)


@api.get("/")
async def root():
    return {"service": "Blueseatra API", "status": "ok"}


app.include_router(api)
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
    client.close()
