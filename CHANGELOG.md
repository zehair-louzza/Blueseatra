# Changelog

## 2026-08-15 — OVH + MCP + devis

Tout est sur `main` (PR #1 à #9). Smoke : ce commit.

### IA locale (OVH)
- Hermes / Ollama derrière Caddy (`HERMES_BASE_URL=https://ia.blueseatra.com`, `HERMES_API_KEY`)
- `extract_from_text` / `extract_from_image` / PDF / DOCX
- Modèles UI = ceux du VPS : `hermes-3`, `qwen3.6:27b`, `qwen2.5:14b`
- Mapping `client_name` / `location` → champs écran devis

### Devis
- Rapprochement catalogue (`description` + pluriels → Spot LED encastré)
- Marge % : `HT = qté × PU × (1 + marge/100)`
- Catalogue slim + cache 45 s + `GET /catalog/search`
- pandas chargé seulement à l’import CSV (boot Render plus court)

### MCP Perplexity Computer
- `POST /mcp` (Streamable HTTP)
- `MCP_TENANT_ID` = ANELEC Test `9171d808-f7ee-4d51-92f6-db60d93d8ecc`
- Outils : list_requests, get_request, list_quotes, search_catalog

### Infra
- Pooler Supabase : `prepared_statement_cache_size` et `statement_cache_size` à 0

### Hostinger (manuel)
Rebuild frontend pour voir marge / picker en direct :

```bash
cd frontend && yarn build
```

Uploader le contenu de `frontend/build/` vers `public_html/`.
