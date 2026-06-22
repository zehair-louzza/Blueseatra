# Blueseatra (FARM) — Development Plan (MVP)

## 1) Objectives (current status)
- ✅ Deliver a working multi-tenant B2B SaaS that converts unstructured requests (PDF/DOCX/images/raw text) into **structured JSON**, matches against **tenant pricing catalogs**, and generates **versioned quote drafts + PDF** (assisted validation).
- ✅ Enforce strict tenant isolation (MongoDB RLS-equivalent) + roles/permissions.
- ✅ Provide **multilingual AI extraction (any language)** and **UI i18n (FR/EN minimum)**.
- ✅ Add a **Configurable Integrations** layer: AI provider selector (OpenAI/Gemini/Anthropic/Oracle/**Emergent default**) + n8n webhook URL settings.
- ✅ Adapted to real incoming maintenance-broker documents (PRESTA/GMS) with domain-specific structured extraction and quote metadata.
- ✅ Produce quotes in a **professional French “DEVIS – FACTURE PRO FORMA”** layout consistent with the provided template, including company profile header/footer.
- ⏳ **NEW (next priority): Make catalog CSV import “open/dynamic”**:
  - Accept *any* CSV column set (no rigid schema requirements).
  - Auto-detect key fields from header synonyms.
  - Allow operator to override mapping in import wizard.
  - Preserve all original CSV columns per item (dynamic attributes) and render them in UI.
- ⏳ Defer Stripe billing (billing screen is a placeholder; subscriptions not implemented yet).

---

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

### Phase 3 — Adaptation to Real “Demande de devis / Ordre de mission” Formats + Pro Forma Template (COMPLETED ✅)
This phase replaces the previously planned Phase 3 (connectors/hardening) with the real-world adaptation work completed from supplied PDFs.

**Context (inputs analyzed)**
- ✅ Real incoming client documents:
  - “Demande de devis” from maintenance broker **PRESTA MAINTENANCE** (SFR/LA BELLE ILOISE…)
  - “Ordre de mission” from **GMS MAINTENANCE** (PROMOD…)

**User stories (delivered)**
1. ✅ Extraction enriched for broker formats: numbers, deadlines, contacts, deliverables, constraints, enriched line_items.
2. ✅ Quote mapping aligns to broker workflows (recipient = donneur d’ordre, client final referenced, meta stored).
3. ✅ Quote PDF pro forma style matched.
4. ✅ Company Profile configurable and rendered in PDF.

**Testing & validation (Phase 3)**
- ✅ Regression testing agent report:
  - Backend: **100% (28/28 regression tests passed)**
  - Frontend: **100%** (new fields verified; no UI regressions)

---

### Phase 4 — Dynamic / “Open” Catalog CSV Import (COMPLETED ✅)
**Goal**: Accept *any* CSV column format, preserve the dataset dynamically, and make Catalog UI + Quote picker resilient to flexible fields.

**User requirements confirmed**
- ✅ Auto-détection intelligente des colonnes clés **+** possibilité de corriger le mapping dans l’assistant.
- ✅ Toutes les colonnes non reconnues stockées et visibles (champ dynamique `attributes`).
- ✅ Affichage catalogue: tableau à colonnes dynamiques **et** option « détails » par ligne.
- ✅ Compatibilité avec l’ancien format: **non critique** (on peut simplifier et remplacer l’ancienne logique stricte).

**Input analyzed**
- New CSV (`catalogue_pme_btp_tce_maintenance_fiable_2026.csv`) detected as comma-delimited.
- Headers (13): `Famille, Article, Unité, Marque, Référence, Fournisseur_principal, Fournisseur_alternatif_1, Fournisseur_alternatif_2, TVA_%, Marge_%, Prix_achat_HT, Prix_vente_HT, Délai`.

#### Phase 4.A — Backend changes (FastAPI: `/app/backend/server.py`)
1. **Define standard fields + synonyms**
   - Add `STANDARD_FIELDS` (canonical fields used by app):
     - `item_label` (required), `item_code`, `family/category`, `unit`, `unit_price_ht`, `purchase_price_ht`, `vat_rate`, `margin`, `brand`, `reference`, `supplier_main`, `suppliers`, `currency`, `min_qty`, `notes`, `delay`, `is_active`.
   - For each standard field, define synonym lists (FR/EN + common variations):
     - e.g., label: `article`, `désignation`, `designation`, `libellé`, `libelle`, `item_label`, `label`, …
     - price: `prix_vente_ht`, `prix_ht`, `pu_ht`, `unit_price_ht`, …
     - vat: `tva`, `tva_%`, `vat`, `vat_rate`, …

2. **Auto-detection helper**
   - Implement `normalize_header()` and `suggest_mapping(columns)`:
     - normalize (lowercase, strip, remove accents, replace spaces/punctuations with `_`).
     - match by exact normalized synonym first; fallback to partial contains.

3. **Update `POST /api/catalogs/import/preview`**
   - Parse CSV with `pandas.read_csv(... dtype=str, keep_default_na=False)`.
   - Return:
     - `columns` (original), `preview` (first 5 rows), `total_rows`.
     - `suggested_mapping` (standard_field → CSV column or `null`).
     - `standard_fields` metadata for UI (label, required flag, description).
     - Replace the old `missing_required` logic: **only `item_label` must be mapped**.

4. **Update `POST /api/catalogs/import`**
   - Accept optional `mapping` as JSON string via `Form` (e.g., `mapping: str = Form(None)`).
   - Determine effective mapping:
     - Start from `suggested_mapping`, override with user-provided mapping.
   - Build each `pricing_items` document:
     - Standardized fields populated where mapped and parsable.
     - **Store every original CSV column into `attributes`** (verbatim string values), preserving all data.
     - Keep matching support by always computing:
       - `label_norm = normalize(item_label)`
       - `category` / `family` normalization if present.
   - Row validation:
     - Only fail a row if mapped `item_label` is empty.
     - Parse numbers with robust helper `_f()` (commas → dots, empty → default).
     - `item_code` if missing: generate stable fallback (e.g., `ROW-{rownum}` or hash of label+rownum).
   - Persist catalog version metadata:
     - Store `columns` (ordered list) and `mapping` on `catalog_versions`.
   - Remove/replace old strict “rich vs template” branching to fully generic path (compat not critical).

5. **Data model notes**
   - `pricing_items` gains:
     - `attributes: { [originalColumn: string]: string }`.
   - `catalog_versions` gains:
     - `columns: string[]`, `mapping: object`, optional `source_filename`.

#### Phase 4.B — Frontend changes (React)
1. **CatalogImport wizard (`/app/frontend/src/pages/CatalogImport.js`)**
   - Extend preview step to display mapping UI:
     - For each standard field, show a `<Select>` with available CSV columns.
     - Prefill using `suggested_mapping`.
     - Allow “(aucun)” for optional fields.
   - Update validation:
     - Block only if `item_label` not mapped.
     - Remove blocking on old `missing_required` list.
   - On import:
     - Send `mapping` JSON in `FormData` to `/catalogs/import`.
   - Add i18n strings in French for:
     - champs standards, aide, erreurs de mapping.

2. **Catalogs list/view (`/app/frontend/src/pages/Catalogs.js`)**
   - Update “view items” dialog to support dynamic columns:
     - Determine display columns:
       - core columns first (`item_code`, `item_label`, `family/category`, `unit`, `unit_price_ht`, `vat_rate`)
       - then **dynamic columns** from union of `attributes` keys.
     - Render horizontally scrollable table.
   - Add per-line “Détails”:
     - Collapsible panel or secondary dialog showing key/value list of `attributes`.
   - Keep table performant:
     - cap displayed columns or provide “Afficher tout” toggle if needed.

3. **Quote Editor catalog picker (`/app/frontend/src/pages/QuoteEditor.js`)**
   - Make selection robust to missing standard fields:
     - description falls back to label or best available attribute.
     - brand/reference shown if present via `item.brand` or `item.attributes?.Marque` / `Référence` equivalents.
   - Improve search indexing:
     - include `attributes` values in search string (bounded to avoid heavy CPU).

#### Phase 4.C — Testing & validation
1. **Backend testing agent**
   - Import the provided 2026 CSV and confirm:
     - no parse errors, rows imported, `attributes` populated.
     - mapping stored on `catalog_versions`.
   - Import an arbitrary CSV with non-standard headers and confirm it still imports.

2. **Frontend testing agent**
   - Wizard:
     - mapping UI appears, prefilled, override works.
     - import completes.
   - Catalog view:
     - dynamic columns render; details view shows all attributes.
   - Quote editor:
     - picker loads and adds a line without crashing even if some fields are missing.

**Success criteria (Phase 4)**
- ✅ Operator can import **any** CSV schema without rigid header requirements.
- ✅ All CSV columns are preserved and visible in catalog UI.
- ✅ Quote editor can pick and add items reliably from dynamic catalogs.

---

### Phase 5 — Hardening + Connectors + Better Matching (DEFERRED ⏳)
**User stories (planned / not yet implemented)**
1. As an admin, I can configure email/form/API connectors (via n8n webhook URLs) and see workflow run history.
2. As an operator, I can reprocess a request with full traceability (idempotency, retry history).
3. As an admin, I can enforce org-wide quote rules (default VAT, rounding, min labor, travel fees).
4. As an operator, I can see “suggested from history” matches based on past validated quotes.
5. As an admin, I can export audit logs and import job reports.
6. As an admin, I can upload a **company logo** and have it appear in PDFs.
7. As an operator/admin, I can override **payment schedules per quote** (instead of only tenant defaults).

**Steps (planned)**
- Connector endpoints + webhook handlers; store `workflow_runs` status/errors.
- Retry/reprocess improvements + idempotency keys.
- History-based matching improvements (store validated mappings; boost score).
- Performance: additional indexes and pagination for tables.
- Export/backup scripts (Mongo dump + stored files manifest).
- Logo upload + storage + PDF rendering.
- Per-quote payment schedule override + PDF rendering.

**Success criteria (planned)**
- Stable reprocessing + workflow observability.
- Improved match quality via tenant history.

---

### Phase 6+ — Billing (Stripe) + Advanced Admin (when keys provided) (DEFERRED ⏳)
**User stories (planned / not yet implemented)**
1. As an owner, I can subscribe to a plan and manage billing in Stripe portal.
2. As the system, I process Stripe webhooks to update subscription status.
3. As an admin, I can enforce feature limits by plan (requests/month, users, storage).
4. As finance, I can view invoices and subscription status in-app.
5. As an owner, I can cancel/reactivate without losing tenant data.

**Steps (planned)**
- Stripe Checkout + Customer Portal + webhook processing.
- Enforce plan gating and quotas.

---

## 3) Next Actions (immediate)
1. **Implement Phase 4 (open/dynamic CSV import)** end-to-end (backend + frontend).
2. Run backend + frontend testing agents for dynamic import flows.
3. (Optional next) Add pagination/virtualization for large catalogs after dynamic columns land.
4. Decide Stripe timeline and provide Stripe test keys when ready.

---

## 4) Success Criteria (overall MVP)
- ✅ A tenant can: import catalog → upload request (PDF/DOCX/image/text) → AI extracts multilingual structured JSON aligned to real broker documents → matching proposes explainable lines → draft quote editable → validate → PDF generated in pro forma template with:
  - pricing snapshot + audit trail
  - request references (N° demande, DI, client final, deadline)
  - required deliverables list
  - TVA legal mention (auto-liquidation or art.293B)
- ✅ Multi-tenant isolation + roles enforced on every endpoint.
- ✅ UI available in FR/EN; AI extraction robust across languages.
- ⏳ Catalog import supports **open/dynamic CSV schemas** with:
  - auto-detect + manual mapping override
  - full column preservation (`attributes`)
  - dynamic column rendering in catalog + quote picker resilience
- ⏳ Billing via Stripe planned for later phase.
