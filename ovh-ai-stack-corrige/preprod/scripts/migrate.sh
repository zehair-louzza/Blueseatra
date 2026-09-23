#!/usr/bin/env sh
# Apply the Blueseatra Supabase migrations to the preproduction PostgreSQL.
#
#   ./scripts/migrate.sh             DRY-RUN on a throwaway database
#   ./scripts/migrate.sh --apply     apply to the persistent preprod database
#
# The dry-run is the default and is mandatory before --apply: it replays the
# whole chain (roles + schema + SQLAlchemy models + SQL migrations) on a
# temporary database that is dropped at the end, so the persistent preprod
# database is never touched by an unvalidated migration.
#
# Idempotence: applied files are recorded in blueseatra._preprod_applied_migrations
# and skipped on re-run, so a partial failure can simply be re-run.
#
# Prerequisite: the infrastructure stack must be up (./scripts/bootstrap.sh).
set -eu

cd "$(dirname "$0")/.."

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod. Copy .env.preprod.example and fill it first." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
. ./.env.preprod
set +a

MODE="dryrun"
if [ "${1:-}" = "--apply" ]; then
  MODE="apply"
elif [ -n "${1:-}" ]; then
  echo "Usage: $0 [--apply]" >&2
  exit 1
fi

DB_NAME="${POSTGRES_DB:-blueseatra_preprod}"
DB_USER="${POSTGRES_USER:-blueseatra_preprod}"
if [ "$MODE" = "apply" ]; then
  TARGET_DB="$DB_NAME"
else
  TARGET_DB="blueseatra_migrate_dryrun"
fi

MIGRATIONS_DIR="../../supabase/migrations"
COMPOSE="docker compose --env-file .env.preprod --profile app"

# Migration deliberately NEVER applied by this script:
# 20260912040000_rls_etape3_force_NON_APPLIQUEE.sql is a documented PLAN, not
# a runnable migration — its own header states that applying it breaks
# authentication. It must stay excluded here and in production tooling.
EXCLUDED="20260912040000_rls_etape3_force_NON_APPLIQUEE.sql"
migration_tmp=""
trap '[ -z "$migration_tmp" ] || rm -f "$migration_tmp"' EXIT

echo "==> migrate.sh — mode: $MODE (target database: $TARGET_DB)"

# ---------------------------------------------------------------------------
# 0. Fresh throwaway database for the dry-run
# ---------------------------------------------------------------------------
if [ "$MODE" != "apply" ]; then
  echo "==> Recreating throwaway dry-run database"
  $COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $TARGET_DB" >/dev/null
  $COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres \
    -c "CREATE DATABASE $TARGET_DB" >/dev/null
fi

# ---------------------------------------------------------------------------
# 1. Roles + schema + current_tenant() + extensions + tracking table
# ---------------------------------------------------------------------------
# Two preprod-specific adaptations, both documented:
#  - `blueseatra_app` is pre-created because module_fournisseur GRANTs to it
#    before its own CREATE ROLE migration runs (in production the role
#    already existed before module_fournisseur was applied).
#  - `current_tenant()` is pre-created because module_fournisseur policies
#    reference it, while the repo migration that defines it (etape 1) is
#    dated later; in production the function already existed.
#  - unaccent rules are patched (superscripts) to match Supabase's
#    dictionary, required by 20260912070000's normalization self-check.
echo "==> Ensuring roles, schema, current_tenant(), extensions, tracking table"

# 1a. unaccent superscript rules (² -> 2, ³ -> 3, ¹ -> 1), idempotent
$COMPOSE exec -u root -T postgres sh /docker-entrypoint-initdb.d/03-unaccent-superscripts.sh

$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$TARGET_DB" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app') THEN
    CREATE ROLE blueseatra_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT;
  END IF;
END
$$;
CREATE SCHEMA IF NOT EXISTS blueseatra;

-- Same definition as 20260912030000 (which will CREATE OR REPLACE it later).
CREATE OR REPLACE FUNCTION blueseatra.current_tenant()
RETURNS text
LANGUAGE sql
STABLE
SET search_path TO ''
AS $function$
  SELECT coalesce(
    NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', ''),
    NULLIF(current_setting('app.tenant_id', true), '')
  )
$function$;

-- Reload the unaccent dictionary from the patched rules file. If objects
-- already depend on it (re-run after a full apply), keep it as is.
DO $$
BEGIN
  BEGIN
    DROP EXTENSION IF EXISTS unaccent;
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'unaccent kept: %', SQLERRM;
  END;
  CREATE EXTENSION IF NOT EXISTS unaccent;
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
END
$$;

CREATE TABLE IF NOT EXISTS blueseatra._preprod_applied_migrations (
  filename   text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
SQL

unaccent_check=$($COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$TARGET_DB" \
  -tAc "SELECT unaccent('unaccent', 'mm²')" | tr -d '[:space:]')
if [ "$unaccent_check" != "mm2" ]; then
  echo "ERROR: active PostgreSQL unaccent dictionary maps mm² to '$unaccent_check' (expected mm2)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Base tables from the backend SQLAlchemy models
# ---------------------------------------------------------------------------
echo "==> Creating base tables from backend models (api image)"
DB_URL="postgresql://$DB_USER:$POSTGRES_PASSWORD@postgres:5432/$TARGET_DB"
$COMPOSE run --rm -e DATABASE_URL="$DB_URL" -e DATABASE_URL_APP="" \
  api python /preprod-scripts/init_schema.py

# ---------------------------------------------------------------------------
# 3. SQL migrations, in filename order
# ---------------------------------------------------------------------------
echo "==> Applying SQL migrations"
failures=0
for file in $(ls "$MIGRATIONS_DIR" | sort); do
  case "$file" in
    "$EXCLUDED")
      echo "    SKIP (documented as non-runnable): $file"
      continue
      ;;
  esac

  already=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$TARGET_DB" -tAc \
    "SELECT 1 FROM blueseatra._preprod_applied_migrations WHERE filename = '$file'" \
    | tr -d '[:space:]')
  if [ "$already" = "1" ]; then
    echo "    already applied: $file"
    continue
  fi

  echo "    applying: $file"
  migration_input="$MIGRATIONS_DIR/$file"
  if [ "$file" = "20260912070000_recherche_fournisseur_index.sql" ]; then
    # Local-only compatibility: vanilla PostgreSQL may drop superscripts;
    # pg_restore also clears search_path, so qualify both the extension
    # function and dictionary for generated columns restored from a dump.
    # Never rewrite the already-applied Supabase migration in the repository.
    source_line="lower(unaccent('unaccent', coalesce(txt, ''))),"
    if [ "$(grep -Fc "$source_line" "$migration_input")" != "1" ]; then
      echo "ERROR: normalization source line changed; refusing compatibility rewrite." >&2
      exit 1
    fi
    migration_tmp=$(mktemp)
    sed "s#lower(unaccent('unaccent', coalesce(txt, ''))),#lower(public.unaccent('public.unaccent', translate(coalesce(txt, ''), '²³¹', '231'))),#" \
      "$migration_input" > "$migration_tmp"
    if ! grep -Fq "lower(public.unaccent('public.unaccent', translate(coalesce(txt, ''), '²³¹', '231')))," "$migration_tmp"; then
      echo "ERROR: compatibility rewrite failed; refusing empty or unmodified SQL." >&2
      exit 1
    fi
    migration_input="$migration_tmp"
    echo "    preprod compatibility: explicit ²/³/¹ translation (Supabase SQL unchanged)"
  fi
  $COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -q \
    -U "$DB_USER" -d "$TARGET_DB" < "$migration_input" && applied=1 || applied=0
  [ -z "$migration_tmp" ] || rm -f "$migration_tmp"
  migration_tmp=""
  if [ "$applied" -eq 1 ]; then
    $COMPOSE exec -T postgres psql -U "$DB_USER" -d "$TARGET_DB" -tAc \
      "INSERT INTO blueseatra._preprod_applied_migrations (filename) VALUES ('$file')" >/dev/null
  else
    failures=$((failures + 1))
    echo "    FAILED:  $file"
    if [ "$MODE" = "apply" ]; then
      echo "" >&2
      echo "Aborting --apply. The persistent database is left partially migrated;" >&2
      echo "already-applied files are skipped on re-run, so you can fix and re-run." >&2
      exit 1
    fi
  fi
done

# ---------------------------------------------------------------------------
# 4. Fournisseur table privileges for blueseatra_app
# ---------------------------------------------------------------------------
# On Supabase, the platform grants default table privileges to `authenticated`
# (and blueseatra_app is a member of it). A vanilla PostgreSQL has no such
# default, so module_fournisseur policies would be unreachable. We replicate
# the grants on the fournisseur tables ONLY — the authentication tables
# (users / tenants / tenant_users) deliberately stay out of reach of
# blueseatra_app, exactly as migration 20260912050000 requires.
echo "==> Granting fournisseur table privileges to blueseatra_app"
$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$TARGET_DB" <<'SQL'
GRANT USAGE ON SCHEMA blueseatra TO blueseatra_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  blueseatra.suppliers,
  blueseatra.canonical_products,
  blueseatra.supplier_offers,
  blueseatra.product_match_rules,
  blueseatra.unit_conversions
TO blueseatra_app;
SQL

# ---------------------------------------------------------------------------
# 5. Password for the restricted blueseatra_app role (business/RLS path)
# ---------------------------------------------------------------------------
has_role=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$TARGET_DB" -tAc \
  "SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app'" | tr -d '[:space:]')
if [ "$has_role" = "1" ]; then
  echo "==> Setting password on role blueseatra_app"
  # NB: psql -c does not interpolate :'var' — the statement must go through stdin.
  $COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$TARGET_DB" \
    -v app_pw="$PREPROD_APP_DB_PASSWORD" <<'SQL'
ALTER ROLE blueseatra_app LOGIN PASSWORD :'app_pw';
SQL
else
  echo "==> WARNING: role blueseatra_app was not created (migration 20260912050000 missing or failed)" >&2
  failures=$((failures + 1))
fi

# ---------------------------------------------------------------------------
# 6. Cleanup / result
# ---------------------------------------------------------------------------
if [ "$MODE" != "apply" ]; then
  echo "==> Dropping throwaway dry-run database"
  $COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $TARGET_DB" >/dev/null
  if [ "$failures" -gt 0 ]; then
    echo "RESULT: DRY-RUN FAILED — $failures error(s) above must be fixed before --apply." >&2
    exit 1
  fi
  echo "RESULT: DRY-RUN PASSED — the full migration chain is validated."
  echo "To apply to the persistent preprod database, run: $0 --apply"
else
  if [ "$failures" -gt 0 ]; then
    echo "RESULT: APPLY FINISHED WITH $failures ERROR(S) — see messages above." >&2
    exit 1
  fi
  echo "RESULT: APPLY DONE — preprod database '$DB_NAME' is up to date."
fi
