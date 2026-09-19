# Roles and schema required by the Blueseatra Supabase migrations.
#
# The SQL migrations under supabase/migrations/ reference Supabase-managed
# group roles (`authenticated`, `service_role`, and later `blueseatra_app`).
# On the plain PostgreSQL preproduction instance we create them as group
# roles so the exact same migration files apply without modification.
#
# `blueseatra_app` is created here as NOLOGIN: migration
# 20260912050000_rls_etape4_role_blueseatra_app.sql references it in GRANTs
# that run earlier in module_fournisseur, and its own CREATE ROLE only runs
# if the role does not already exist. scripts/migrate.sh gives it LOGIN and
# a password at the end (PREPROD_APP_DB_PASSWORD).
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
