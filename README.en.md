<div align="center">

<img src="docs/assets/banniere.jpg" alt="Blueseatra" width="100%">

<br>

**AI-assisted quoting software for building-services, maintenance and fit-out contractors.**

<br>

[![CI infra](https://github.com/zehair-louzza/Blueseatra/actions/workflows/ci-infra.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/ci-infra.yml)
[![Security](https://github.com/zehair-louzza/Blueseatra/actions/workflows/securite.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/securite.yml)
[![Business tests](https://github.com/zehair-louzza/Blueseatra/actions/workflows/tests-metier.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/tests-metier.yml)
[![Production](https://img.shields.io/badge/production-live-2EA043)](https://blueseatra.com)
[![Licence](https://img.shields.io/badge/licence-proprietary-555)](./LICENSE)

![Python](https://img.shields.io/badge/Python-3.11-1B3F73?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-1B3F73?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-1B3F73?logo=react&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-3AAFB9?logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-RLS-3AAFB9?logo=supabase&logoColor=white)
![Ollama](https://img.shields.io/badge/AI-Ollama%20%C2%B7%20OVH-3AAFB9?logo=ollama&logoColor=white)

[**Website**](https://blueseatra.com) · [**Documentation (FR)**](./docs/README.md) · [**User manual (FR)**](./docs/manuel-utilisateur.md) · [**API**](./docs/reference-api.md) · [**Français**](./README.md)

</div>

---

## What it does

1. **Read.** Emails, PDFs and site photos are read by a self-hosted AI. It extracts the principal, the end client, the site, the urgency and the work items, then organises them into trade packages.
2. **Price.** Each line is matched against your own catalogue and about 967,000 references from 9 French distributors. Margins, discounts and French construction VAT are computed by fixed rules. The AI never sets a price.
3. **Follow up.** Validated quotes are exported as Pro Forma PDFs. Follow-ups are scheduled in French working days, and each outcome (accepted, declined, no follow-up) is tracked per client.

## Features

- AI extraction with an OCR cascade and a sequential queue.
- Quote editor with packages, labour, travel and notes, and 20 / 10 / 5.5 / 0 % VAT.
- Custom catalogue import from any CSV layout, with versioning.
- Shared supplier catalogue and price comparison.
- Clients module: records, contacts, sites, activity log, AI suggestions with evidence, follow-ups, GDPR opt-out and anonymisation.
- Multi-tenant roles with PostgreSQL row-level security.
- Plans and usage metering.
- French and English interface.

## Stack

React 18 and Tailwind CSS on Hostinger · FastAPI (Python 3.11) on Render · PostgreSQL 17 on Supabase with RLS · Ollama on an OVH VPS. See [architecture](./docs/architecture.md).

The detailed documentation is written in French.

---

<div align="center"><sub>© 2025-2026 Blueseatra. Proprietary code, all rights reserved.</sub></div>
