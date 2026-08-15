# ADR : moteur IA derrière ovh-ai-stack (plus de :11434 public)

## Statut
Accepté — 2026-08-15

## Décision
L'infra IA (Ollama, Hermes Agent, n8n, Caddy) vit dans le dépôt privé
`zehair-louzza/ovh-ai-stack`. Blueseatra n'appelle plus Ollama en clair.
Production : `HERMES_BASE_URL=https://…` + `HERMES_API_KEY` (en-tête `X-Api-Key`).

Oracle Cloud n'est plus l'hôte. OracleMind (produit MCP) n'est pas déprécié.
