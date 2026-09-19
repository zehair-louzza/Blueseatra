# Blueseatra preprod backups (3-2-1)

## Strategy

- **1st copy**: the live PostgreSQL data on the VPS (`postgres_preprod_data` volume).
- **2nd copy (local, different medium)**: encrypted dumps in `ovh-ai-stack-corrige/preprod/backups/`, produced by `scripts/backup-preprod.sh`.
- **3rd copy (offsite)**: manually or automatically copy the `.enc` + `.sha256` files out of the VPS after each backup — to a MinIO/S3-compatible bucket, another machine, or an encrypted local download. This repository does not provision offsite storage; pick one and document the exact destination here once chosen.

## One-time setup

```bash
cd ovh-ai-stack-corrige/preprod
echo "BACKUP_ENCRYPTION_PASSPHRASE=$(openssl rand -hex 32)" >> .env.preprod
echo "BACKUP_RETENTION_DAYS=30" >> .env.preprod
chmod 600 .env.preprod
chmod +x scripts/backup-preprod.sh scripts/restore-preprod.sh
```

Store `BACKUP_ENCRYPTION_PASSPHRASE` in a password manager. Losing it makes every backup permanently unreadable.

## Running a backup

```bash
./scripts/backup-preprod.sh
```

Produces `backups/blueseatra-preprod-<UTC timestamp>.dump.enc` plus a `.sha256` checksum, verifies the checksum immediately, and purges files older than `BACKUP_RETENTION_DAYS`.

## Scheduling (systemd timer)

Create `/etc/systemd/system/blueseatra-preprod-backup.service`:

```ini
[Unit]
Description=Blueseatra preprod encrypted backup

[Service]
Type=oneshot
WorkingDirectory=/path/to/Blueseatra/ovh-ai-stack-corrige/preprod
ExecStart=/path/to/Blueseatra/ovh-ai-stack-corrige/preprod/scripts/backup-preprod.sh
```

And `/etc/systemd/system/blueseatra-preprod-backup.timer`:

```ini
[Unit]
Description=Daily Blueseatra preprod backup

[Timer]
OnCalendar=03:30
Persistent=true

[Install]
WantedBy=timers.target
```

Then: `systemctl enable --now blueseatra-preprod-backup.timer`.

## Restoring

```bash
# Safe: restores into a throwaway database, verifies row counts, drops it
./scripts/restore-preprod.sh backups/blueseatra-preprod-<timestamp>.dump.enc

# Destructive: overwrites the real preprod database, requires typing RESTORE-PREPROD
./scripts/restore-preprod.sh backups/blueseatra-preprod-<timestamp>.dump.enc --apply
```

## Restore test log

Record every real restore test here, as required by issue #96's acceptance criteria ("un test de restauration réel effectué et tracé"):

| Date (UTC) | Backup file | Result | Operator |
|---|---|---|---|
| _pending_ | _pending_ | _pending — run `restore-preprod.sh` without `--apply` on the VPS and log the result here_ | _pending_ |

This table is intentionally empty until a human operator runs the verification restore on the actual VPS and fills it in — a restore that has never actually been executed must not be reported as tested.

## Secrets

`backup-preprod.sh` and `restore-preprod.sh` never write `BACKUP_ENCRYPTION_PASSPHRASE`, `POSTGRES_PASSWORD`, or any other secret to disk outside `.env.preprod`. Encryption uses AES-256-CBC with PBKDF2 (200000 iterations) via OpenSSL, matching the tooling already used elsewhere in this stack (`validate-env.sh`, `bootstrap.sh`).
