#!/usr/bin/env bash
# À LANCER SUR LE VPS OVH (ssh ubuntu@vps-b377201e...) — item "Modèles VPS".
# Tire les petits modèles adaptés au CPU puis mesure une extraction de tableau.
set -euo pipefail

echo "=== 1) Pull des modèles (une fois, ~5 Go + 6 Go) ==="
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull qwen2.5vl:7b
docker compose exec ollama ollama list

echo ""
echo "=== 2) Chauffe (premier chargement en RAM) ==="
docker compose exec ollama ollama run qwen2.5:7b "OK" >/dev/null || true

echo ""
echo "=== 3) Mesure : extraction d'un tableau de devis (JSON strict) ==="
read -r -d '' PROMPT <<'EOF' || true
Structure cette demande en JSON (sans prix, ignore les colonnes € / P.U. / Total) :
| Désignation | Qté | Unité | P.U. HT | Total HT |
| Pose de spots LED 230V | 12 | u | 24,50 | 294,00 |
| Remplacement tableau électrique | 1 | ens | 680,00 | 680,00 |
| Câble R2V 3G2.5 | 80 | ml | 1,90 | 152,00 |
Réponds uniquement en JSON: {"requested_items":[{"designation":...,"quantite":...,"unite":...}]}
EOF

START=$(date +%s.%N)
docker compose exec ollama ollama run qwen2.5:7b "$PROMPT"
END=$(date +%s.%N)

echo ""
echo "=== Durée extraction tableau : $(echo "$END - $START" | bc) s ==="
echo "(attendu : quelques secondes sur 8 vCPU — vs 80s-11min avec gemma4:26b)"
echo ""
echo "Contrôle RAM :"
docker stats --no-stream ovh-ai-stack-ollama-1 2>/dev/null || docker stats --no-stream
