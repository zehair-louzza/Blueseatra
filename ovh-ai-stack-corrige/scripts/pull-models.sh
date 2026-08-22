#!/usr/bin/env bash
# Télécharge UNIQUEMENT les petits modèles adaptés au VPS CPU (8 vCPU / 22 Go).
# Fini gemma4:26b / qwen3.6:27b (17-18 Go, 80s-11min/doc sur CPU) dans le chemin chaud.
# Vérif noms : https://ollama.com/library/qwen2.5  https://ollama.com/library/qwen2.5vl
set -euo pipefail

echo "=== Structuration texte -> JSON (défaut, rapide) ==="
docker compose exec ollama ollama pull qwen2.5:7b

echo "=== Vision : photos / PDF scanné (calque illisible) ==="
docker compose exec ollama ollama pull qwen2.5vl:7b

# Compat backend Blueseatra historique (alias hermes-3).
echo "=== Compat HERMES_DEFAULT_MODEL (léger, 4.7 Go) ==="
docker compose exec ollama ollama pull hermes3
docker compose exec ollama ollama cp hermes3 hermes-3 || true

# OCR spécialisés déjà validés côté SaaS (petits, gardés) — décommentez si utilisés.
# docker compose exec ollama ollama pull qwen2.5vl:7b

echo "=== Modèles installés ==="
docker compose exec ollama ollama list

echo ""
echo "Contrôle vitesse (doit répondre en quelques secondes, pas en minutes) :"
echo "  docker compose exec ollama ollama run qwen2.5:7b 'réponds juste OK'"
