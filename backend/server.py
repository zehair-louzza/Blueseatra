"""Blueseatra backend — multi-tenant B2B quoting SaaS (FastAPI + MongoDB)."""
import os
import io
import csv
import uuid
import logging
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

JWT_SECRET = os.environ.get('JWT_SECRET', 'blueseatra-dev-secret')
JWT_ALGO = 'HS256'

app = FastAPI(title="Blueseatra API")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("blueseatra")

ROLES = ["owner", "admin", "operator", "viewer", "billing_admin"]


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
    tenants = []
    for m in memberships:
        t = await db.tenants.find_one({"id": m["tenant_id"]}, {"_id": 0})
        if t:
            tenants.append({"id": t["id"], "name": t["name"], "role": m["role"]})
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
    out = []
    for m in members:
        u = await db.users.find_one({"id": m["user_id"]}, {"_id": 0})
        if u:
            out.append({"user_id": u["id"], "email": u["email"], "name": u.get("name", ""), "role": m["role"]})
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
        doc["ai_key"] = body.ai_key
    await db.settings_integrations.update_one({"tenant_id": cu.tenant_id}, {"$set": doc}, upsert=True)
    await audit(cu.tenant_id, cu.email, "settings.update", None,
                {"ai_provider": body.ai_provider, "ai_model": body.ai_model})
    return {"ok": True}


async def get_tenant_ai_settings(tenant_id):
    s = await db.settings_integrations.find_one({"tenant_id": tenant_id}, {"_id": 0})
    return s or {}


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


@api.get("/catalogs")
async def list_catalogs(cu: CurrentUser = Depends(get_current)):
    cats = await db.catalogs.find({"tenant_id": cu.tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for c in cats:
        c["versions"] = await db.catalog_versions.find(
            {"tenant_id": cu.tenant_id, "catalog_id": c["id"]}, {"_id": 0}).sort("version_number", -1).to_list(100)
    return cats


@api.get("/catalogs/{catalog_id}/items")
async def catalog_items(catalog_id: str, cu: CurrentUser = Depends(get_current)):
    cat = await db.catalogs.find_one({"id": catalog_id, "tenant_id": cu.tenant_id}, {"_id": 0})
    if not cat:
        raise HTTPException(404, "Catalog not found")
    items = await db.pricing_items.find(
        {"tenant_id": cu.tenant_id, "version_id": cat.get("active_version_id")}, {"_id": 0}).to_list(2000)
    return {"catalog": cat, "items": items}


@api.get("/catalog-template.csv")
async def catalog_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    w.writerow(["ACME", "PEINT-001", "Peinture murale deux couches", "peinture", "m2",
                "12.50", "EUR", "10", "5", "true", "Inclut sous-couche"])
    buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=blueseatra_catalog_template.csv"})


@api.post("/catalogs/import/preview")
async def import_preview(cu: CurrentUser = Depends(require_role("owner", "admin", "operator")),
                         file: UploadFile = File(...)):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as e:
        raise HTTPException(400, f"Cannot parse CSV: {e}")
    columns = list(df.columns)
    missing = [c for c in ["item_code", "item_label", "unit_price_ht"] if c not in columns]
    return {"columns": columns, "preview": df.head(5).to_dict(orient="records"),
            "total_rows": len(df), "missing_required": missing, "expected_columns": CSV_COLUMNS}


@api.post("/catalogs/import")
async def import_catalog(cu: CurrentUser = Depends(require_role("owner", "admin", "operator")),
                         file: UploadFile = File(...),
                         catalog_name: str = Form(...),
                         activate: str = Form("true")):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as e:
        raise HTTPException(400, f"Cannot parse CSV: {e}")

    cat_id = new_id()
    ver_id = new_id()
    job_id = new_id()
    client_code = (df["client_code"].iloc[0] if "client_code" in df.columns and len(df) else "") or "N/A"

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
            "client_code": client_code, "created_at": now_iso(), "active_version_id": None,
        })

    items, errors = [], []
    for idx, row in df.iterrows():
        rownum = int(idx) + 2
        try:
            code = (row.get("item_code") or "").strip()
            label = (row.get("item_label") or "").strip()
            if not code or not label:
                raise ValueError("item_code and item_label are required")
            price = float(str(row.get("unit_price_ht")).replace(",", "."))
            vat = float(str(row.get("vat_rate") or 0).replace(",", ".") or 0)
            minq = float(str(row.get("min_qty") or 0).replace(",", ".") or 0)
            is_active = str(row.get("is_active") or "true").strip().lower() in ("true", "1", "yes", "oui")
            items.append({
                "id": new_id(), "tenant_id": cu.tenant_id, "catalog_id": cat_id, "version_id": ver_id,
                "item_code": code, "item_label": label, "label_norm": match_engine.normalize(label),
                "category": (row.get("category") or "").strip().lower(),
                "unit": (row.get("unit") or "u").strip().lower(),
                "unit_price_ht": price, "currency": (row.get("currency") or "EUR").strip(),
                "vat_rate": vat, "min_qty": minq, "is_active": is_active,
                "notes": (row.get("notes") or "").strip(),
            })
        except Exception as e:
            errors.append({"id": new_id(), "tenant_id": cu.tenant_id, "job_id": job_id,
                           "row_number": rownum, "message": str(e),
                           "raw": {k: str(v) for k, v in row.to_dict().items()}})

    await db.catalog_versions.insert_one({
        "id": ver_id, "tenant_id": cu.tenant_id, "catalog_id": cat_id, "version_number": version_number,
        "status": "draft", "item_count": len(items), "error_count": len(errors),
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


async def get_active_catalog(tenant_id):
    cat = await db.catalogs.find_one(
        {"tenant_id": tenant_id, "active_version_id": {"$ne": None}}, {"_id": 0}, sort=[("created_at", -1)])
    if not cat:
        return None, []
    items = await db.pricing_items.find(
        {"tenant_id": tenant_id, "version_id": cat["active_version_id"]}, {"_id": 0}).to_list(5000)
    return cat, items


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
    quote = {
        "id": quote_id, "tenant_id": cu.tenant_id, "request_id": request_id,
        "number": f"BS-{datetime.now().year}-{count + 1:04d}",
        "status": "draft", "version": 1,
        "client": req["extracted"].get("client"), "site": req["extracted"].get("site"),
        "object": req["extracted"].get("description"),
        "language": req.get("language"),
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
    lines = body.get("lines", q["lines"])
    for l in lines:
        if l.get("unit_price_ht") is not None and l.get("qty") is not None:
            try:
                l["line_ht"] = round(float(l["qty"]) * float(l["unit_price_ht"]), 2)
            except (TypeError, ValueError):
                pass
    total_ht, total_vat, total_ttc = match_engine.recompute_totals(lines)
    update = {"lines": lines, "total_ht": total_ht, "total_vat": total_vat, "total_ttc": total_ttc}
    if "client" in body:
        update["client"] = body["client"]
    if "site" in body:
        update["site"] = body["site"]
    if "object" in body:
        update["object"] = body["object"]
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
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
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
