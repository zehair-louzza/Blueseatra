#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod. Copy .env.preprod.example and set unique secrets first." >&2
  exit 1
fi

chmod 600 .env.preprod

# Refuse placeholders and production-looking secrets before starting anything.
./scripts/validate-env.sh

# Infrastructure only (postgres, redis). The api/worker services belong
# to the "app" profile and are started after migrations are applied.
docker compose --env-file .env.preprod up -d
docker compose --env-file .env.preprod ps
