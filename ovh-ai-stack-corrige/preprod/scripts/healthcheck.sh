#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod." >&2
  exit 1
fi

status=0
for service in postgres redis; do
  health=$(docker compose --env-file .env.preprod ps --format json "$service" 2>/dev/null | grep -o '"Health":"[^"]*"' | head -n 1 | cut -d '"' -f 4 || true)
  if [ "$health" != "healthy" ]; then
    echo "$service is not healthy (status: ${health:-unknown})" >&2
    status=1
  else
    echo "$service is healthy"
  fi
done

exit "$status"
