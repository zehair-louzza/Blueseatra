#!/usr/bin/env sh
# Encrypted, integrity-checked PostgreSQL backup for Blueseatra preprod.
# Local half of the 3-2-1 strategy documented in BACKUP.md.
#
#   ./scripts/backup-preprod.sh
#
# Requires BACKUP_ENCRYPTION_PASSPHRASE (>=32 chars) in .env.preprod.
# Add it yourself, it is not in .env.preprod.example by default:
#   echo "BACKUP_ENCRYPTION_PASSPHRASE=$(openssl rand -hex 32)" >> .env.preprod

set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod. Run bootstrap.sh first." >&2
  exit 1
fi

. ./.env.preprod

if [ -z "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ] || [ ${#BACKUP_ENCRYPTION_PASSPHRASE} -lt 32 ]; then
  echo "BACKUP_ENCRYPTION_PASSPHRASE missing or shorter than 32 chars in .env.preprod." >&2
  echo "Generate one with: echo \"BACKUP_ENCRYPTION_PASSPHRASE=\$(openssl rand -hex 32)\" >> .env.preprod" >&2
  exit 1
fi

DB_USER="${POSTGRES_USER:-blueseatra_preprod}"
DB_NAME="${POSTGRES_DB:-blueseatra_preprod}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_DIR="$(pwd)/backups"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DUMP_FILE="${BACKUP_DIR}/blueseatra-preprod-${STAMP}.dump"
ENC_FILE="${DUMP_FILE}.enc"
SUM_FILE="${ENC_FILE}.sha256"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

echo "==> Dumping ${DB_NAME} (custom format)"
docker compose --env-file .env.preprod exec -T postgres \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$DUMP_FILE"

[ -s "$DUMP_FILE" ] || { echo "Dump is empty, aborting." >&2; rm -f "$DUMP_FILE"; exit 1; }

echo "==> Encrypting backup (AES-256-CBC, PBKDF2)"
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  -in "$DUMP_FILE" -out "$ENC_FILE"
rm -f "$DUMP_FILE"

echo "==> Writing integrity checksum"
sha256sum "$ENC_FILE" > "$SUM_FILE"

echo "==> Verifying checksum"
sha256sum -c "$SUM_FILE" >/dev/null || { echo "Checksum verification failed, backup is corrupt." >&2; exit 1; }

echo "==> Purging backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -maxdepth 1 -type f -name '*.enc' -mtime "+${RETENTION_DAYS}" -print -delete
find "$BACKUP_DIR" -maxdepth 1 -type f -name '*.sha256' -mtime "+${RETENTION_DAYS}" -print -delete

echo "Backup complete: ${ENC_FILE}"
echo "Remember to copy this file off the VPS (see BACKUP.md, 3-2-1 offsite step)."
