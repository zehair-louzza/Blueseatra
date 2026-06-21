# Blueseatra (FARM) — Development Plan (MVP)

## 1) Objectives (current status)
- ✅ Deliver a working multi-tenant B2B SaaS that converts unstructured requests (PDF/DOCX/images/raw text) into **structured JSON**, matches against **tenant CSV pricing catalogs**, and generates **versioned quote drafts + PDF** (assisted validation).
- ✅ Enforce strict tenant isolation (MongoDB RLS-equivalent) + roles/permissions.
- ✅ Provide **multilingual AI extraction (any language)** and **UI i18n (FR/EN minimum)**.
- ✅ Add a **Configurable Integrations** layer: AI provider selector (OpenAI/Gemini/Anthropic/Oracle/**Emergent default**) + n8n webhook URL settings.
- ⏳ Defer Stripe billing (billing screen is a placeholder; subscriptions not implemented yet).

## 2) Implementation Steps

### Phase 1 — Core POC (Isolation) (COMPLETED ✅)
**User stories (validated)**
1. ✅ As an operator, I can paste raw text in any language and get a structured “request JSON” with confidence/metadata.
2. ✅ As an operator, I can upload an image/photo and the system extracts the same structured JSON.
3. ✅ As an operator, I can upload a PDF and the system extracts text (or falls back to vision) and produces structured JSON.
4. ✅ As an operator, I can import a CSV catalog and see normalized pricing items ready for matching.
5. ✅ As an operator, I can run matching and get explainable scored matches + “to confirm” flags under threshold.

**Delivered**
- `/app/backend/poc_core.py` proving:
  - Multilingual extraction:
    - FR PDF (text extraction)
    - EN image (vision)
    - ES raw text
  - Strict JSON output schema (language, client/site, urgency, line_items, confidence)
  - Explainable matching (score + reasons)
  - Deterministic quote totals (HT/TVA/TTC) from catalog only

**Success criteria results**
- ✅ Valid structured JSON returned for text + image + PDF, with language detection.
- ✅ Matching outputs include score + explanation; thresholding works.
- ✅ Quote totals compute deterministically from catalog (AI never sets prices).

---

### Phase 2 — V1 Full App (Build around proven core) (COMPLETED ✅)
**User stories (delivered)**
1. ✅ As a user, I can sign up/login and create my first tenant, then switch tenants if I belong to multiple.
2. ✅ As an admin, I can add teammates and assign roles (owner/admin/operator/viewer/billing_admin).
3. ✅ As an operator, I can create a request by uploading PDF/DOCX/image or pasting text, and see extracted fields + processing status.
4. ✅ As an operator, I can import a pricing catalog CSV, review errors, activate a version, and know which version is active.
5. ✅ As an operator, I can generate a quote draft from a request, edit/confirm lines, and validate to produce a versioned quote + downloadable PDF.

**Backend (FastAPI + MongoDB) — delivered**
- Data model implemented as MongoDB collections (all include `tenant_id`) with strict isolation enforced on every query.
- Auth:
  - Email/password (bcrypt)
  - JWT includes `user_id`, `tenant_id`, role
  - Tenant switching endpoint
- Requests module:
  - Create request from raw text or upload PDF/DOCX/image
  - Async AI processing (background task)
  - Stores extracted JSON + language + confidence + status pipeline
  - Reprocess endpoint
- Catalog module:
  - CSV template download
  - Import preview + import + versioning + error log
  - Activate catalog version
  - Demo catalog auto-seeded at signup for immediate usability
- Quote module:
  - Draft generation from processed request
  - Explainable matching engine
  - Editable quote draft (PATCH recomputes totals)
  - Quote versions snapshot on validate
  - Validate + send status lifecycle
  - PDF generation + download
  - Embedded pricing snapshot metadata for reproducibility/auditability
- Integrations settings:
  - Provider/model selector (Emergent/OpenAI/Gemini/Anthropic/Oracle)
  - Optional API key storage (never returned to client; only `ai_key_set` flag)
  - n8n webhook URL config
  - Default works with built-in Emergent engine (gpt-5.4)
- Audit logging:
  - Requests, catalog import/activate, quote create/edit/validate/send, settings updates
- Dashboard endpoint with KPIs and recent activity

**Frontend (React + Tailwind + shadcn/ui) — delivered**
- Public portal (landing) + authenticated console.
- i18n (FR/EN) with language toggle.
- Screens implemented:
  - Landing
  - Login / Signup
  - AppShell (tenant switcher, navigation)
  - Dashboard
  - Requests list + create dialog + request detail (extracted fields)
  - Catalogs list + item viewer + CSV import wizard + error display
  - Quotes list + quote editor + validate/send + PDF download
  - Members + role management
  - Audit log timeline
  - Settings / Integrations
  - Billing placeholder

**Testing & validation (end of Phase 2)**
- ✅ Testing agent report:
  - Backend: **100% (40/40 tests passed)**
  - Frontend: **100% pass** for all core flows
- ✅ Verified explicitly:
  - Multi-tenancy isolation across two tenants
  - Multilingual AI extraction (FR/EN) in app flows
  - Full quote workflow: request → draft → edit → validate → send → PDF download
  - Role enforcement (viewer blocked from sensitive actions)

**Success criteria results**
- ✅ Strict tenant isolation verified.
- ✅ End-to-end quote generation works with real uploads and deterministic totals + PDF.
- ✅ UI works in FR/EN; AI extraction works across multiple languages.
- ✅ Integrations settings support provider/model selection and optional key entry.

---

### Phase 3 — Hardening + Connectors + Better Matching (DEFERRED ⏳)
**User stories (planned / not yet implemented)**
1. As an admin, I can configure email/form/API connectors (via n8n webhook URLs) and see workflow run history.
2. As an operator, I can reprocess a request with full traceability (idempotency, retry history).
3. As an admin, I can enforce org-wide quote rules (default VAT, rounding, min labor, travel fees).
4. As an operator, I can see “suggested from history” matches based on past validated quotes.
5. As an admin, I can export audit logs and import job reports.

**Steps (planned)**
- Connector endpoints + webhook handlers; store `workflow_runs` status/errors.
- Retry/reprocess improvements + idempotency keys.
- History-based matching improvements (store validated mappings; boost score).
- Performance: additional indexes and pagination for tables.
- Export/backup scripts (Mongo dump + stored files manifest).

**Success criteria (planned)**
- Stable reprocessing + workflow observability.
- Improved match quality via tenant history.

---

### Phase 4+ — Billing (Stripe) + Advanced Admin (when keys provided) (DEFERRED ⏳)
**User stories (planned / not yet implemented)**
1. As an owner, I can subscribe to a plan and manage billing in Stripe portal.
2. As the system, I process Stripe webhooks to update subscription status.
3. As an admin, I can enforce feature limits by plan (requests/month, users, storage).
4. As finance, I can view invoices and subscription status in-app.
5. As an owner, I can cancel/reactivate without losing tenant data.

**Steps (planned)**
- Stripe Checkout + Customer Portal + webhook processing.
- Enforce plan gating and quotas.

## 3) Next Actions (immediate)
1. Decide if/when to implement Phase 3 connectors (n8n/ZimaBoard integration) and provide webhook URL conventions.
2. Decide on Stripe timeline and provide Stripe test keys when ready.
3. (Optional) Provide preferred AI provider/model defaults per tenant and API keys when you want to switch away from the built-in engine.

## 4) Success Criteria (overall MVP)
- ✅ A tenant can: import catalog → upload request (PDF/DOCX/image/text) → AI extracts multilingual structured JSON → matching proposes explainable lines → draft quote editable → validate → PDF generated with embedded pricing snapshot + audit trail.
- ✅ Multi-tenant isolation + roles enforced on every endpoint.
- ✅ UI available in FR/EN; AI extraction robust across languages.
- ✅ Integrations settings support provider/model selection and optional key entry; default works without user keys.
- ⏳ Billing via Stripe planned for Phase 4.
