#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

printf '%s' "This permanently deletes all Blueseatra preproduction data. Type RESET-PREPROD to continue: "
read -r confirmation

if [ "$confirmation" != "RESET-PREPROD" ]; then
  echo "Reset cancelled."
  exit 1
fi

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod." >&2
  exit 1
fi

docker compose --env-file .env.preprod down -v --remove-orphans
echo "Blueseatra preproduction volumes were deleted."
