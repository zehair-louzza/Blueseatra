# Blueseatra OVH preproduction

Isolated Docker Compose stack for Blueseatra preproduction on the OVH VPS.
It deliberately does not alter the existing OVH AI stack, does not touch the
Supabase production project, and never requires a paid Supabase branch.

## Services

| Service  | Role | Profile |
|----------|------|---------|
| postgres | PostgreSQL 17, TLS on (private self-signed certificate generated on start), schema `blueseatra`, Supabase-compatible roles | default |
| redis    | Redis 7, AOF + password | default |
| api      | Blueseatra FastAPI backend (`backend/server.py`) | `app` |
| worker   | RQ extraction worker (`backend/extraction_worker.py`) | `app` |

All services live on the internal `blueseatra_preprod_internal` network. No
database or Redis port is published. The API is bound to `127.0.0.1`
on the VPS by default — reach it through an SSH tunnel or the existing
reverse proxy, never expose it directly.

## First start

```bash
cd ovh-ai-stack-corrige/preprod
cp .env.preprod.example .env.preprod
chmod 600 .env.preprod
# Fill every placeholder in .env.preprod (see comments inside).
chmod +x scripts/*.sh
./scripts/bootstrap.sh     # validates .env.preprod, then starts postgres/redis
./scripts/healthcheck.sh
```

## Migrations (mandatory before starting the app)

```bash
./scripts/migrate.sh         # dry-run on a throwaway database, nothing persistent
./scripts/migrate.sh --apply # only after a passing dry-run
```

What the script does, in order:

1. (dry-run only) creates and later drops the `blueseatra_migrate_dryrun` database;
2. ensures the `authenticated` / `service_role` group roles and the `blueseatra` schema exist;
3. creates the base tables from the backend SQLAlchemy models (`init_schema.py` in the api image);
4. applies `supabase/migrations/*.sql` in filename order, with `ON_ERROR_STOP=1`;
5. sets the password of the restricted `blueseatra_app` role from `PREPROD_APP_DB_PASSWORD`.

Applied files are recorded in `blueseatra._preprod_applied_migrations` and
skipped on re-run, so a failed run can simply be re-run.

Excluded on purpose: `20260912040000_rls_etape3_force_NON_APPLIQUEE.sql` —
its own header states it is a plan, not a runnable migration, and that
applying it breaks authentication.

### Preprod-specific adaptations (documented gaps)

The repo migration history is partial relative to the production database.
Three things existed in production before the migrations that reference
them, so `migrate.sh` recreates them first:

- the `blueseatra_app` role (GRANTed by `module_fournisseur` before its own
  `CREATE ROLE` migration);
- the `blueseatra.current_tenant()` function (same situation, exact same
  definition as migration `20260912030000`);
- table privileges on the fournisseur tables, which Supabase grants by
default to `authenticated` but a vanilla PostgreSQL does not. Only the
fournisseur tables are granted — the authentication tables stay out of
reach of `blueseatra_app`, mirroring production posture.

The `unaccent` dictionary is also patched (superscripts `² ³ ¹`) to match
Supabase's rules file, which migration `20260912070000` self-checks.

### RLS posture reproduced faithfully

With these migrations, RLS is active on `users` and the fournisseur tables
(`suppliers`, `supplier_offers`, ...), and deliberately NOT on the other
business tables — that is exactly the current production state, since the
FORCE step (etape 3) is the non-applied plan file. Verified on this stack:
`blueseatra_app` with `app.tenant_id` sees only its tenant's fournisseur
rows, cross-tenant inserts are refused, and `tenants`/`users` are
inaccessible to it.

## Start the application

```bash
docker compose --env-file .env.preprod --profile app up -d
```

The api and worker containers share the image `blueseatra-backend:preprod`,
built from `Dockerfile.backend` with the repository root as build context.
The API listens on `127.0.0.1:8080` (override with `API_BIND`), e.g.:

```bash
ssh -L 8080:127.0.0.1:8080 vps
curl http://127.0.0.1:8080/health
```

### Database roles (mirrors production RLS)

- `DATABASE_URL` — privileged path, used for authentication tables. In
  preprod this is the local `blueseatra_preprod` superuser.
- `DATABASE_URL_APP` — restricted `blueseatra_app` role for the business
  path, so RLS behaviour is exercised the same way as in production.
  See `backend/database.py` for why the auth path must stay on `DATABASE_URL`.

## Commands

```bash
docker compose --env-file .env.preprod ps
docker compose --env-file .env.preprod logs -f api
docker compose --env-file .env.preprod --profile app logs -f worker
docker compose --env-file .env.preprod down                 # infra only
docker compose --env-file .env.preprod --profile app down   # everything
```

## Reset

`./scripts/reset.sh` permanently deletes the configured preproduction
PostgreSQL and Redis volumes. It asks for the exact confirmation value
`RESET-PREPROD`. If a MinIO volume exists from the old stack, it is left
untouched and must be handled separately after a data inventory.
Never run it against production resources.

## Security boundaries

- Keep `.env.preprod` out of Git and at permissions `0600`.
- `scripts/validate-env.sh` (run by bootstrap) refuses placeholder values and
  production-looking secrets: `supabase.co` hosts, `sb_secret_`, `sk_live_`,
  `whsec_`, and the production Hermes gateway.
- Use synthetic or irreversibly anonymized data only.
- Never point `HERMES_BASE_URL` at the production gateway; use a preprod
  Hermes instance with a test budget.
- This plain PostgreSQL instance does not provide Supabase Auth, Storage API,
  Realtime or Edge Functions — it validates schema, RLS roles and application
  behaviour, which is exactly its purpose.
- Add any future container to `preprod_internal`; publish it through the VPS
  reverse proxy only after authentication and TLS are configured.
