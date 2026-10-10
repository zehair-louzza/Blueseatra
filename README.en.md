<div align="center">

<img src="docs/assets/banniere.jpg" alt="Blueseatra: from raw requests to validated quotes, on your prices" width="100%">

<br>

**AI-assisted quoting software for building-services, maintenance and fit-out contractors.**

<br>

[![CI infra](https://github.com/zehair-louzza/Blueseatra/actions/workflows/ci-infra.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/ci-infra.yml)
[![Security](https://github.com/zehair-louzza/Blueseatra/actions/workflows/securite.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/securite.yml)
[![Business tests](https://github.com/zehair-louzza/Blueseatra/actions/workflows/tests-metier.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/tests-metier.yml)
[![Production](https://img.shields.io/badge/production-live-1A7F37?labelColor=2D333B)](https://blueseatra.com)
[![Version](https://img.shields.io/badge/version-2026.10.01-0969DA?labelColor=2D333B&logo=semver&logoColor=white)](./CHANGELOG.md)
[![Licence](https://img.shields.io/badge/licence-proprietary-8250DF?labelColor=2D333B)](./LICENSE)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?labelColor=2D333B&logo=python&logoColor=FFD43B)
![FastAPI](https://img.shields.io/badge/FastAPI-API-00796B?labelColor=2D333B&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-087EA4?labelColor=2D333B&logo=react&logoColor=61DAFB)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-0369A1?labelColor=2D333B&logo=tailwindcss&logoColor=38BDF8)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?labelColor=2D333B&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-RLS-18794E?labelColor=2D333B&logo=supabase&logoColor=3ECF8E)
![Render](https://img.shields.io/badge/API-Render-6D28D9?labelColor=2D333B&logo=render&logoColor=white)
![Vercel](https://img.shields.io/badge/Site-Vercel-000000?labelColor=2D333B&logo=vercel&logoColor=white)
![Ollama](https://img.shields.io/badge/AI-Ollama%20%C2%B7%20OVH-000E9C?labelColor=2D333B&logo=ollama&logoColor=white)

![API routes](https://img.shields.io/badge/API%20routes-124-0969DA?labelColor=2D333B&logo=openapiinitiative&logoColor=white)
![Migrations](https://img.shields.io/badge/migrations-35-8250DF?labelColor=2D333B&logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/automated%20tests-690-1A7F37?labelColor=2D333B&logo=pytest&logoColor=white)
![Isolation](https://img.shields.io/badge/isolation-RLS%20per%20company-BC4C00?labelColor=2D333B&logo=supabase&logoColor=white)
![GDPR](https://img.shields.io/badge/GDPR-anonymisation%20%C2%B7%20opt--out-BF3989?labelColor=2D333B)
![Languages](https://img.shields.io/badge/languages-FR%20%C2%B7%20EN-0E7490?labelColor=2D333B&logo=googletranslate&logoColor=white)

[**Website**](https://blueseatra.com) ·
[**User manual (FR)**](./docs/manuel-utilisateur.md) ·
[**Documentation (FR)**](./docs/README.md) ·
[**Architecture (FR)**](./docs/architecture.md) ·
[**API**](./docs/reference-api.md) ·
[**Changelog (FR)**](./CHANGELOG.md) ·
[**Licence**](./LICENSE) ·
[**Français**](./README.md)

</div>

---

## Why Blueseatra

An estimator spends hours retyping work orders, looking up prices and chasing clients. Blueseatra automates the reading and the formatting, and never lets the AI decide a price.

<table>
<tr>
<td width="33%" valign="top">

### Read
An email, a PDF, a site photo: the AI identifies the principal, the end client, the site, the urgency and the work, then sorts the work into **trade packages**.

</td>
<td width="33%" valign="top">

### Price
Lines are matched against **your catalogue** and about **967,000 references** from 9 French distributors. Margins, discounts and French construction VAT are computed by fixed rules.

</td>
<td width="33%" valign="top">

### Follow up
The validated quote goes out as a Pro Forma PDF; **follow-ups in working days** and the commercial outcome are then tracked client by client.

</td>
</tr>
</table>

## Overview

<table>
<tr>
<td width="50%"><img src="docs/assets/manuel-en/03-demande-detail.jpg" alt="A request read by the AI"><br><sub><b>Request read by the AI</b>: extracted data, source text and detected clients with their evidence</sub></td>
<td width="50%"><img src="docs/assets/manuel-en/05-editeur-devis.jpg" alt="Quote editor"><br><sub><b>Quote editor</b>: numbered packages, labour, travel, frozen price source</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/manuel-en/08-fiche-client.jpg" alt="Client record"><br><sub><b>Client record</b>: contacts, sites, requests and quotes, activity, follow-ups</sub></td>
<td width="50%"><img src="docs/assets/manuel-en/01-tableau-de-bord.jpg" alt="Dashboard"><br><sub><b>Dashboard</b>: quotes waiting for validation, requests needing attention</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/manuel-en/06-catalogues.jpg" alt="Catalogues"><br><sub><b>Catalogues</b>: your price catalogue and the supplier catalogues you switch on for quoting</sub></td>
<td width="50%"><img src="docs/assets/manuel-en/10-offre-consommation.jpg" alt="Plan and usage"><br><sub><b>Plan and usage</b>: only automated work is counted</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/manuel-en/15c-comparateur-produits-identiques.jpg" alt="Identical products at several suppliers"><br><sub><b>Price comparison</b>: the same product at several suppliers, whatever their description, compared per base unit</sub></td>
<td width="50%"><img src="docs/assets/manuel-en/09-catalogue-fournisseurs.jpg" alt="Supplier catalogue"><br><sub><b>Supplier catalogue</b>: shared supplier catalogues, each switched on or off for quoting</sub></td>
</tr>
</table>

<sub>English interface. Personal data is masked. Product descriptions, families and sample queries stay in French: they come from, and must match, French supplier catalogues.</sub>

## Features

| Area | What is delivered | Status |
|---|---|:---:|
| **AI reading** | PDF, DOCX, XLSX, CSV, TXT, images; OCR cascade; sequential extraction queue; confidence score; draft generated automatically | ✅ |
| **Quotes** | Packages and sub-packages, materials, labour, travel, notes; 20 / 10 / 5.5 / 0 % VAT; hidden margin; variants; Pro Forma PDF | ✅ |
| **Custom catalogues** | CSV or Excel (.xlsx, .xls) import in any layout, sheet and header row detected, macro workbooks refused, column mapping, versions, atomic activation, large files | ✅ |
| **Supplier catalogue** | Rexel, Prolians, Point.P, YESSS, La Plateforme du Bâtiment, Au Forum du Bâtiment, SFIC, Chausson, Icilux; shared, can be hidden, never deleted; search by word and by family inside each catalogue | ✅ |
| **Quoting on activatable sources** | Each supplier catalogue can be switched on or off for quoting (toggle, content kept); without an internal catalogue, activated sources generate the quote; fast search under RLS (trigram index through secured functions) | ✅ |
| **Price comparison** | Cheapest offer per supplier, criteria isolated, equivalent terms recognised ("courbe c", "2p", "ph+n"…), filter by product family | ✅ |
| **Identical products across suppliers** | The same item recognised at several suppliers (EAN, or brand + manufacturer reference) even when descriptions differ; prices brought back to the base unit (a 100 m pack compared per metre); anomalies flagged | ✅ |
| **Single catalogue format** | 971,676 offers from 9 suppliers cleaned into one common format: checked GTIN, canonical brand, base unit, price per unit; source data never modified | ✅ |
| **Clients** | Records, contacts, sites, activity log, CSV import and export, indicators | ✅ |
| **AI suggestions** | Principal and end client proposed with the source sentence; automatic linking only on an identical SIRET or email | ✅ |
| **Follow-ups** | Working days and public holidays, urgency, expiry reminder, phone call above a threshold, GDPR opt-out, FR / EN texts | ✅ |
| **Multi-company** | Roles owner, admin, operator, viewer, billing_admin; company switcher; PostgreSQL RLS | ✅ |
| **Plans and quotas** | Découverte, Initial, Pilotage, Performance, Signature; append-only usage ledger; blocking can be switched on (`BLUESEATRA_QUOTAS_APPLIQUES`) | ✅ |
| **Email follow-ups** | Sent from the company mailbox (SMTP 465 / 587): by click after review, or automatically when due; editable text, never sent twice, opted-out contacts never emailed | ✅ |
| **G3 item suggestions** | From a request: supplies extracted by AI, chosen among 20 real candidates (internal catalogue and enabled supplier catalogues), always to be validated | ✅ |
| **GDPR masking** | Every AI call receives masked text (addresses, names, people, identifiers), restored server-side; no image leaves the VPS | ✅ |
| **Integrations** | n8n webhook per company, MCP bridge, choice of AI engine (VPS, Mistral, OpenCode Free) | ✅ |
| **Contact** | `contact@blueseatra.com` with a pre-filled subject per topic (services, plans, company, help) | ✅ |
| **Online payment** | Stripe | 🔜 ticket #90 |

## Quick start

```bash
git clone https://github.com/zehair-louzza/Blueseatra.git && cd Blueseatra

# API
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set DATABASE_URL, JWT_SECRET, APP_ENCRYPTION_KEY, HERMES_BASE_URL
uvicorn server:app --port 8001 --reload

# Website
cd ../frontend && npm install --legacy-peer-deps
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

Details (variables, local database, tests) are in the [developer guide (FR)](./docs/guide-developpeur.md).

## Architecture

<img src="docs/assets/schema-architecture-en.png" alt="Blueseatra architecture: Vercel, Render, Supabase, Hermès gateway and OVH VPS" width="100%">

<img src="docs/assets/schema-parcours-complet-en.png" alt="Full quote journey, from intake to the final PDF: who acts, who reacts" width="100%">

The ten phases in detail, Supabase and Render views: [Infrastructure and full quote journey](./docs/infrastructure.en.md).

<img src="docs/assets/schema-chiffrage-en.png" alt="Quoting on activatable sources" width="100%">

<img src="docs/assets/schema-recherche-rls-en.png" alt="Supplier search under RLS: secured functions, then records read back under RLS" width="100%">


<details>
<summary>Text view (Mermaid)</summary>

```mermaid
flowchart LR
    U[Browser] -->|HTTPS| V[Vercel<br>React site]
    U -->|/api| R[Render<br>FastAPI API]
    R -->|blueseatra_app role + RLS| S[(Supabase<br>PostgreSQL 17)]
    R -->|HTTPS + key| O[OVH VPS<br>Ollama]
    R -.-> N[n8n]
```

</details>

<img src="docs/assets/schema-routage.png" alt="AI routing through the Hermès gateway" width="100%">

**Principles**
- The AI never sets a price.
- Each company is isolated in the code and in the database; the few functions that bypass RLS (search) check the company themselves.
- Nothing is deleted silently.
- A quote only goes out after human validation.

Details: [architecture.md (FR)](./docs/architecture.md).

## All diagrams

Click a diagram to open the document that explains it. Diagrams are generated by [`scripts/docs/generer_schemas.py`](./scripts/docs/generer_schemas.py); English versions are used where they exist.

<table>
<tr>
<td width="50%" valign="top"><a href="./docs/architecture.md"><img src="./docs/assets/schema-architecture-en.png" alt="Architecture"></a><br><sub><b>Architecture</b>: Vercel, Render, Supabase, Hermès gateway, OVH VPS</sub></td>
<td width="50%" valign="top"><a href="./docs/infrastructure.md"><img src="./docs/assets/schema-parcours-complet-en.png" alt="Full quote journey"></a><br><sub><b>Full quote journey</b>: ten phases, who acts and who reacts</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/manuel-utilisateur.md"><img src="./docs/assets/schema-parcours.png" alt="Request journey"></a><br><sub><b>Request journey</b>: from email to validated quote</sub></td>
<td width="50%" valign="top"><a href="./docs/architecture.md"><img src="./docs/assets/schema-routage.png" alt="AI routing"></a><br><sub><b>AI routing</b>: Hermès gateway, Ollama, Mistral, OpenCode Free</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/rgpd-masquage-ia-externe.md"><img src="./docs/assets/schema-masquage-rgpd.png" alt="GDPR masking"></a><br><sub><b>GDPR masking</b>: placeholders before every AI call, restored server-side</sub></td>
<td width="50%" valign="top"><a href="./docs/rgpd-masquage-ia-externe.md"><img src="./docs/assets/schema-g3.png" alt="G3 item suggestions"></a><br><sub><b>G3 item suggestions</b>: real candidates, AI choice, human validation</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/manuel-utilisateur.md"><img src="./docs/assets/schema-chiffrage-en.png" alt="Pricing on switchable sources"></a><br><sub><b>Pricing on switchable sources</b>: internal and supplier catalogues</sub></td>
<td width="50%" valign="top"><a href="./docs/architecture.md"><img src="./docs/assets/schema-recherche-rls-en.png" alt="Supplier search under RLS"></a><br><sub><b>Supplier search under RLS</b>: secured functions, before and after timings</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/manuel-utilisateur.md"><img src="./docs/assets/schema-import-catalogue.png" alt="Catalogue import"></a><br><sub><b>Catalogue import</b>: five steps and check verdict</sub></td>
<td width="50%" valign="top"><a href="./docs/manuel-utilisateur.md"><img src="./docs/assets/schema-cycle-devis.png" alt="Quote lifecycle"></a><br><sub><b>Quote lifecycle</b>: statuses, follow-ups, stop</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/specs/module-clients.md"><img src="./docs/assets/schema-relances-email.png" alt="Email follow-ups"></a><br><sub><b>Email follow-ups</b>: click or automatic, company mailbox</sub></td>
<td width="50%" valign="top"><a href="./docs/tarification-2026-09.md"><img src="./docs/assets/schema-quotas.png" alt="Quotas"></a><br><sub><b>Quotas</b>: reservation, refund, what is never counted</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/audit-isolation-tenants-2026-09-12.md"><img src="./docs/assets/schema-isolation.png" alt="Company isolation"></a><br><sub><b>Company isolation</b>: code filter and PostgreSQL RLS</sub></td>
<td width="50%" valign="top"><a href="./docs/conformite-rgpd.md"><img src="./docs/assets/schema-rgpd.png" alt="GDPR rights"></a><br><sub><b>GDPR rights</b>: export, anonymisation, objection</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/exploitation.md"><img src="./docs/assets/schema-livraison.png" alt="Delivery pipeline"></a><br><sub><b>Delivery pipeline</b>: PR, checks, deployment, rollback</sub></td>
<td width="50%" valign="top"><a href="./docs/runbook-incident.md"><img src="./docs/assets/schema-incident.png" alt="Incident flow"></a><br><sub><b>Incident flow</b>: detect, contain, fix, verify</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="./docs/infrastructure.md"><img src="./docs/assets/vue-supabase-en.png" alt="Supabase view"></a><br><sub><b>Supabase view</b>: blueseatra schema, roles and RLS</sub></td>
<td width="50%" valign="top"><a href="./docs/infrastructure.md"><img src="./docs/assets/vue-render-en.png" alt="Render view"></a><br><sub><b>Render view</b>: services, variables, deployment</sub></td>
</tr>
</table>

## Screenshots

<details>
<summary><b>All 31 application screens</b> (click to expand)</summary>

<table>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/01-tableau-de-bord.jpg" alt="Dashboard"><br><sub><b>Dashboard</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/02-demandes.jpg" alt="Requests"><br><sub><b>Requests</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/02b-boite-reception.jpg" alt="Sorted inbox"><br><sub><b>Sorted inbox</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/03-demande-detail.jpg" alt="Request read by AI"><br><sub><b>Request read by AI</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/03b-demande-lignes.jpg" alt="Extracted work lines"><br><sub><b>Extracted work lines</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/04-devis-liste.jpg" alt="Quote list"><br><sub><b>Quote list</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/05-editeur-devis.jpg" alt="Quote editor"><br><sub><b>Quote editor</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/05b-versions-devis.jpg" alt="Quote versions"><br><sub><b>Quote versions</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/16-pdf-devis.jpg" alt="Pro forma PDF"><br><sub><b>Pro forma PDF</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/06-catalogues.jpg" alt="Catalogues"><br><sub><b>Catalogues</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/06b-controle-import.jpg" alt="Pre-activation check"><br><sub><b>Pre-activation check</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/06c-afficher-catalogue-fournisseur.jpg" alt="Supplier catalogue"><br><sub><b>Supplier catalogue</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel/06d-sources-chiffrage.jpg" alt="Pricing sources"><br><sub><b>Pricing sources</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/screens/catalogue-fournisseurs.jpg" alt="Supplier catalogue"><br><sub><b>Supplier catalogue</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/15-comparateur-prix.jpg" alt="Price comparison"><br><sub><b>Price comparison</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel/15b-comparateur-resultats.jpg" alt="Cheapest per supplier"><br><sub><b>Cheapest per supplier</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/15c-comparateur-produits-identiques.jpg" alt="Identical products"><br><sub><b>Identical products</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/07-clients.jpg" alt="Clients"><br><sub><b>Clients</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/08-fiche-client.jpg" alt="Client record"><br><sub><b>Client record</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/09-relances.jpg" alt="Follow-ups"><br><sub><b>Follow-ups</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel-en/10-offre-consommation.jpg" alt="Plan and usage"><br><sub><b>Plan and usage</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel/11-membres.jpg" alt="Members and roles"><br><sub><b>Members and roles</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/12-parametres.jpg" alt="Settings"><br><sub><b>Settings</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/12b-societe-pdf.jpg" alt="Company and PDF"><br><sub><b>Company and PDF</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/manuel/13-donnees-personnelles.jpg" alt="Personal data"><br><sub><b>Personal data</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/manuel/14-journal-audit.jpg" alt="Audit log"><br><sub><b>Audit log</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/screens/accueil.jpg" alt="Home page"><br><sub><b>Home page</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/screens/tarifs.jpg" alt="Plans"><br><sub><b>Plans</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/screens/valeurs.jpg" alt="Values"><br><sub><b>Values</b></sub></td>
<td width="33%" valign="top"><img src="./docs/assets/screens/connexion.jpg" alt="Sign-in"><br><sub><b>Sign-in</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="./docs/assets/screens/ollama-config.jpg" alt="AI engine settings"><br><sub><b>AI engine settings</b></sub></td>
</tr>
</table>

Each screen is explained step by step in the [user manual (FR)](./docs/manuel-utilisateur.md).

</details>

## Documentation

The detailed documentation is written in French.

| For | Document |
|---|---|
| Using the application | [User manual](./docs/manuel-utilisateur.md) |
| Understanding the system | [Architecture](./docs/architecture.md) · [Infrastructure and full quote journey](./docs/infrastructure.en.md) · [Decisions (ADR)](./docs/decisions) |
| Developing | [Developer guide](./docs/guide-developpeur.md) · [API reference](./docs/reference-api.md) · [Contributing](./CONTRIBUTING.md) |
| Running in production | [Operations](./docs/exploitation.md) · [DEPLOIEMENT.md](./DEPLOIEMENT.md) |
| Plans and pricing | [Pricing](./docs/tarification-2026-09.md) |
| Clients module | [Specification](./docs/specs/module-clients.md) |
| Security | [SECURITY.md](./SECURITY.md) · [Isolation audit](./docs/audit-isolation-tenants-2026-09-12.md) |
| Everything else | [Documentation index](./docs/README.md) |

## Quality and security

| Check | Where |
|---|---|
| Isolation between companies (static and live) | `backend/tests_security`, workflow `securite.yml` |
| Search functions under RLS: isolation, injection, permissions, exactness (disposable database) | `backend/tests_security/test_offres_candidates_sql.py`, workflow `tests-metier.yml` |
| Follow-up rules, quotas, Clients migration on PostgreSQL 17 | `backend/tests_clients`, `backend/tests_quotas`, workflow `tests-metier.yml` |
| Lint, migration consistency, secret scanning | workflow `ci-infra.yml` |
| Mandatory review of sensitive areas | [`CODEOWNERS`](./.github/CODEOWNERS) |
| Companies' AI secrets encrypted (Fernet), bcrypt passwords, JWT | `backend/server.py` |

## Ecosystem

| Repository | Role |
|---|---|
| **Blueseatra** (this repository) | Application: API, website, database |
| [ovh-ai-stack](https://github.com/zehair-louzza/ovh-ai-stack) | Self-hosted AI engine (Ollama, Caddy, monitoring) |
| [Fournisseur-Blueseatra](https://github.com/zehair-louzza/Fournisseur-Blueseatra) | Collection and normalisation of supplier price lists |

## Roadmap

- [x] Shared supplier catalogue and price comparison
- [x] Visual redesign and pricing
- [x] Usage counters (observation mode)
- [x] Clients module and follow-ups
- [x] Ledger and quotas ([#89](https://github.com/zehair-louzza/Blueseatra/issues/89)), blocking can be switched on
- [x] Fast supplier search under RLS, filter by family
- [ ] Stripe payment and top-ups ([#90](https://github.com/zehair-louzza/Blueseatra/issues/90))
- [x] Sending follow-ups by email from Blueseatra
- [x] GDPR masking of every AI call and G3 item suggestions

## Licence

**Proprietary** software. Rights holder: **Zehair Louzza**, trading as "Blueseatra". The binding text is the [LICENSE](./LICENSE) file (version 2.0, 10 October 2026). Its French version prevails.

| Topic | In practice |
|---|---|
| What is protected | Code, documentation, diagrams, screenshots, name and logo, databases and normalised catalogues |
| What publishing on GitHub allows | Viewing the repository and forking it on GitHub, as GitHub's terms require. Nothing else |
| What is prohibited without written consent | Copying, running, modifying, redistributing, offering as SaaS, building a competing product, extracting the catalogues |
| Artificial intelligence | Text and data mining is opted out (French IP Code, art. L.122-5-3): no model training on this repository |
| Third-party components | They remain under their own licences. Distributor brands and prices belong to their owners |
| Contributions | Accepted only with an assignment of rights to the holder |
| Governing law | French law, courts within the jurisdiction of the Paris Court of Appeal |

Permission requests (evaluation, partnership, commercial licence): `contact@blueseatra.com`. Report security issues privately as described in [SECURITY.md](./SECURITY.md).

---

<div align="center">
<sub>© 2025-2026 Zehair Louzza, trading as "Blueseatra". Proprietary software, all rights reserved. See <a href="./LICENSE">LICENSE</a>.</sub>
</div>
