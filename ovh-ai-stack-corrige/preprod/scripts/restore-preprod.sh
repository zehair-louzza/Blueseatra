#!/usr/bin/env sh
# Restore a Blueseatra preprod backup produced by backup-preprod.sh.
#
#   ./scripts/restore-preprod.sh <file.dump.enc>              restore into a throwaway db (default, safe)
#   ./scripts/restore-preprod.sh <file.dump.enc> --apply      restore into the persistent preprod db (destructive)

set -eu
umask 077
cd "$(dirname "$0")/.."

ENC_FILE="${1:-}"
MODE="${2:-}"

[ -n "$ENC_FILE" ] || { echo "Usage: $0 <file.dump.enc> [--apply]" >&2; exit 1; }
[ -f "$ENC_FILE" ] || { echo "File not found: $ENC_FILE" >&2; exit 1; }
[ -f "${ENC_FILE}.sha256" ] && { sha256sum -c "${ENC_FILE}.sha256" || { echo "Checksum mismatch, refusing to restore." >&2; exit 1; }; } \
  || echo "No checksum file found next to ${ENC_FILE}, skipping integrity check." >&2

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod." >&2
  exit 1
fi
set -a
. ./.env.preprod
set +a

[ -n "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ] || { echo "BACKUP_ENCRYPTION_PASSPHRASE missing in .env.preprod." >&2; exit 1; }

DB_USER="${POSTGRES_USER:-blueseatra_preprod}"
DB_NAME="${POSTGRES_DB:-blueseatra_preprod}"
DECRYPTED="$(mktemp)"
trap 'rm -f "$DECRYPTED"' EXIT

echo "==> Decrypting ${ENC_FILE}"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  -in "$ENC_FILE" -out "$DECRYPTED"

if [ "$MODE" = "--apply" ]; then
  echo "==> DESTRUCTIVE restore into the persistent database '${DB_NAME}'."
  printf '%s' "Type RESTORE-PREPROD to continue: "
  read -r confirmation
  [ "$confirmation" = "RESTORE-PREPROD" ] || { echo "Restore cancelled."; exit 1; }
  docker compose --env-file .env.preprod exec -T postgres \
    dropdb -U "$DB_USER" --if-exists "$DB_NAME"
  docker compose --env-file .env.preprod exec -T postgres \
    createdb -U "$DB_USER" "$DB_NAME"
  docker compose --env-file .env.preprod exec -T postgres \
    pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner < "$DECRYPTED"
  echo "Restore applied to ${DB_NAME}."
else
  TMP_DB="blueseatra_restore_check_$(date +%s)"
  echo "==> Verification restore into throwaway database ${TMP_DB} (nothing persistent)"
  docker compose --env-file .env.preprod exec -T postgres \
    createdb -U "$DB_USER" "$TMP_DB"
  docker compose --env-file .env.preprod exec -T postgres \
    pg_restore -U "$DB_USER" -d "$TMP_DB" --no-owner < "$DECRYPTED" \
    || { echo "Restore into throwaway database failed." >&2; docker compose --env-file .env.preprod exec -T postgres dropdb -U "$DB_USER" --if-exists "$TMP_DB"; exit 1; }
  docker compose --env-file .env.preprod exec -T postgres \
    psql -U "$DB_USER" -d "$TMP_DB" -c "SELECT count(*) AS restored_rows FROM blueseatra.users;"
  docker compose --env-file .env.preprod exec -T postgres \
    dropdb -U "$DB_USER" "$TMP_DB"
  echo "Verification restore succeeded and throwaway database was dropped."
  echo "Run with --apply only when you intend to overwrite the persistent preprod database."
fi
