# Blueseatra (FARM) — Development Plan (MVP)

## 1) Objectives
- Deliver a working multi-tenant B2B SaaS that converts unstructured requests (PDF/DOCX/images/raw text) into **structured JSON**, matches against **tenant CSV pricing catalogs**, and generates **versioned quote drafts + PDF** (assisted validation).
- Enforce strict tenant isolation (MongoDB RLS-equivalent) + roles/permissions.
- Provide **multilingual AI extraction (any language)** and **UI i18n (FR/EN minimum)**.
- Add a **Configurable Integrations** layer: AI provider selector (OpenAI/Gemini/Claude/Oracle/Emergent default) + n8n webhook URL settings.
- Defer Stripe billing (show plan page only).

## 2) Implementation Steps

### Phase 1 — Core POC (Isolation) (do not proceed until green)
**User stories**
1. As an operator, I can paste raw text in any language and get a structured “request JSON” with confidence/metadata.
2. As an operator, I can upload an image/photo and the system extracts the same structured JSON.
3. As an operator, I can upload a PDF and the system extracts text (or falls back to vision) and produces structured JSON.
4. As an operator, I can import a CSV catalog and see normalized pricing items ready for matching.
5. As an operator, I can run matching and get explainable scored matches + “to confirm” flags under threshold.

**Steps**
- Websearch best practices: (a) PDF OCR vs text extraction fallback strategy, (b) explainable matching scoring + thresholds for catalog matching.
- Create `/app/backend/poc_core.py`:
  - Load sample CSV (official template) via pandas → normalize units/currency/vat → in-memory “staging + items”.
  - Parse inputs:
    - PDF: `pdfplumber` text extraction; if too little text → render/page image or treat as scanned and use vision.
    - DOCX: `python-docx`.
    - Image: Pillow → base64 (per `/app/image_testing.md`).
  - AI extraction using `emergentintegrations.LlmChat` (default Emergent key + **openai/gpt-5.4**), prompt outputs strict JSON schema:
    - client/site/description/line_items[{label, category, qty, unit, dimensions, notes}], urgency, constraints, keywords, language, confidence.
  - Matching engine:
    - exact `item_code`, exact normalized label, fuzzy label (`rapidfuzz`), category + unit compatibility, thresholding, produce explanations + scores.
  - Quote calculation:
    - apply min_qty, unit_price_ht, vat_rate → totals HT/TVA/TTC; mark lines missing match as “unpriced/to confirm”.
- Run the POC with **real** sample files (at least: 1 PDF, 1 image, 1 non-FR text) and confirm outputs are valid JSON and totals compute.

**Success criteria**
- POC reliably returns valid structured JSON for text + image + PDF (with fallback) and identifies language.
- Matching outputs include score + explanation, with a configurable threshold.
- Quote totals (HT/TVA/TTC) compute deterministically from catalog (AI never sets price).

---

### Phase 2 — V1 Full App (Build around proven core)
**User stories**
1. As a user, I can sign up/login and create my first tenant, then switch tenants if I belong to multiple.
2. As an admin, I can invite a teammate and assign roles (owner/admin/operator/viewer/billing_admin).
3. As an operator, I can create a request by uploading PDF/DOCX/image or pasting text, and see extracted fields + processing status.
4. As an operator, I can import a pricing catalog CSV, review errors, activate a version, and know which version is active.
5. As an operator, I can generate a quote draft from a request, edit/confirm matches, and validate to produce a versioned quote + downloadable PDF.

**Backend (FastAPI + MongoDB)**
- Data model (collections; all include `tenant_id`): tenants, users, tenant_users, requests, request_documents, request_extracted_fields, catalogs, catalog_versions, pricing_items, import_jobs, import_errors, quote_drafts, quote_lines, quote_versions, audit_logs, workflow_runs, settings_integrations.
- Auth:
  - Email/password (bcrypt), JWT includes `user_id`, `active_tenant_id`, `role`.
  - Dependency guard: every query filtered by `tenant_id` (RLS-equivalent).
- Core services:
  - Document ingestion + storage (Mongo GridFS or filesystem path + metadata; store original + extracted text + hashes).
  - Extraction pipeline endpoints: create request → background task process → store extracted JSON + confidence + language.
  - Catalog import wizard backend:
    - upload → detect delimiter/encoding → preview → (optional) mapping → staging → normalize → upsert → errors → create version → activate.
  - Matching + quote engine:
    - produce explainable matches, create draft, embed `pricing_snapshot` (catalog_version + item data used).
    - versioning on validate; immutable quote_version records.
  - Audit logging for sensitive actions (imports, activation, quote validate, etc.).
- Integrations settings:
  - AI provider selector (Emergent/OpenAI/Gemini/Anthropic/Oracle) + model + key (optional) stored per-tenant; env fallback to Emergent.
  - n8n webhook URL settings (stored; exposed for later connector callbacks).
- REST API under `/api` per blueprint (plus `/settings/integrations`).

**Frontend (React + Tailwind + shadcn/ui)**
- App shell: public portal + authenticated console.
- Screens (MVP): login/signup, tenant switcher, dashboard, requests list/detail (upload + status + extracted fields), catalogs list, CSV import wizard + errors, quote drafts list, quote editor/detail, PDF download, admin members/roles, audit logs, settings/integrations, billing placeholder.
- i18n: react-i18next with FR/EN dictionaries (extensible), language toggle.
- UX: clear wizard steps, data tables, empty states, error handling, explainable match UI (score + reason + confirm).

**Testing & validation (end of Phase 2)**
- Call testing agent for 1 full E2E pass: signup→create tenant→import CSV→create request (PDF/image/text)→process→generate draft→confirm lines→validate→download PDF.

**Success criteria**
- Strict tenant isolation verified (no cross-tenant access via API).
- End-to-end quote generation works with real uploads and produces correct deterministic totals + PDF.
- UI works in FR/EN; AI extraction handles at least 2 languages in testing.
- Integrations settings page lets user pick provider/model and save (key optional).

---

### Phase 3 — Hardening + Connectors + Better Matching
**User stories**
1. As an admin, I can configure email/form/API connectors (via n8n webhook URLs) and see workflow run history.
2. As an operator, I can reprocess a request (retry extraction/matching) with full traceability.
3. As an admin, I can enforce org-wide quote rules (default VAT, rounding, min labor, travel fees).
4. As an operator, I can see “suggested from history” matches based on past validated quotes.
5. As an admin, I can export audit logs and import job reports.

**Steps**
- Connector stubs + webhook endpoints; store `workflow_runs` with status/errors.
- Add retry/reprocess + idempotency keys.
- Improve matching: store validated mappings; boost score with tenant history.
- Performance: indexes on `tenant_id`, request status, catalog_version.
- Add backup/export scripts (Mongo dump + stored files manifests).

**Success criteria**
- Stable reprocessing + workflow observability.
- Improved match quality via history.

---

### Phase 4+ — Billing (Stripe) + Advanced Admin (when keys provided)
**User stories**
1. As an owner, I can subscribe to a plan and manage billing in Stripe portal.
2. As the system, I process Stripe webhooks to update subscription status.
3. As an admin, I can enforce feature limits by plan (requests/month, users, storage).
4. As finance, I can view invoices and subscription status in-app.
5. As an owner, I can cancel/reactivate without losing tenant data.

**Steps**
- Stripe Checkout + Customer Portal + webhooks; enforce plan gating.

## 3) Next Actions (immediate)
1. Implement and run Phase 1 POC script (`poc_core.py`) using Emergent default AI (gpt-5.4) with real sample files.
2. Freeze the JSON schema for extracted request + quote draft line objects.
3. Once POC is green, scaffold Phase 2 collections + API skeleton and build end-to-end flow screens.

## 4) Success Criteria (overall MVP)
- A real tenant can: import catalog → upload request (PDF/DOCX/image/text) → AI extracts multilingual structured JSON → matching proposes explainable lines → draft quote editable → validate → PDF generated with embedded pricing snapshot + audit trail.
- Multi-tenant isolation + roles enforced on every endpoint.
- UI available in FR/EN; AI extraction robust across languages.
- Integrations settings support provider/model selection and optional key entry; default works without user keys.
