-- Amorce minimale d'une base PostgreSQL JETABLE pour les tests SQL (CI).
-- Reproduit ce que Supabase fournit déjà : schéma, rôles et current_tenant().
CREATE SCHEMA IF NOT EXISTS blueseatra;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app') THEN CREATE ROLE blueseatra_app NOLOGIN; END IF;
END $$;
GRANT USAGE ON SCHEMA blueseatra TO blueseatra_app, authenticated;
CREATE OR REPLACE FUNCTION blueseatra.current_tenant() RETURNS text
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.tenant_id', true), '') $$;
GRANT EXECUTE ON FUNCTION blueseatra.current_tenant() TO blueseatra_app, authenticated;
