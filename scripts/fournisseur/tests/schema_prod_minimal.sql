-- Reproduction MINIMALE du schema de production (releve le 23/09/2026 via
-- information_schema) pour tester import_catalogue_lourd.py hors Supabase.
-- Attention : en production source_date, created_at et activated_at sont
-- des varchar, contrairement a la migration 20260912020000.
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS blueseatra;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='blueseatra_app') THEN
    CREATE ROLE blueseatra_app NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
END $$;
GRANT USAGE ON SCHEMA blueseatra TO blueseatra_app;

CREATE OR REPLACE FUNCTION blueseatra.current_tenant() RETURNS text
LANGUAGE sql STABLE SET search_path TO '' AS $f$
  SELECT coalesce(
    NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', ''),
    NULLIF(current_setting('app.tenant_id', true), ''))
$f$;

CREATE TABLE blueseatra.tenants (id varchar(36) PRIMARY KEY, name varchar(200) NOT NULL,
  plan varchar(40) DEFAULT 'starter', created_at varchar(40));
CREATE TABLE blueseatra.catalogs (
  id varchar(36) PRIMARY KEY, tenant_id varchar(36) NOT NULL, name varchar(200) NOT NULL,
  client_code varchar(60) DEFAULT 'N/A', active_version_id varchar(36), created_at varchar(40));
CREATE TABLE blueseatra.catalog_versions (
  id varchar(36) PRIMARY KEY, tenant_id varchar(36) NOT NULL, catalog_id varchar(36) NOT NULL,
  version_number integer DEFAULT 1, status varchar(20) DEFAULT 'draft', item_count integer DEFAULT 0,
  error_count integer DEFAULT 0, columns jsonb, mapping jsonb, source_filename varchar(255),
  created_at varchar(40), activated_at varchar(40));
CREATE TABLE blueseatra.suppliers (
  id varchar(36) PRIMARY KEY, tenant_id varchar(36) NOT NULL, name varchar(200) NOT NULL,
  slug varchar(120), website text, franco_ht double precision, shipping_cost_ht double precision,
  discount_rules jsonb NOT NULL DEFAULT '{}', default_delay varchar(60), agencies jsonb NOT NULL DEFAULT '[]',
  notes text, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT suppliers_tenant_name_uniq UNIQUE (tenant_id, name));
CREATE TABLE blueseatra.supplier_offers (
  id varchar(36) PRIMARY KEY, tenant_id varchar(36) NOT NULL, supplier_id varchar(36) NOT NULL
    REFERENCES blueseatra.suppliers(id) ON DELETE CASCADE,
  catalog_id varchar(36), version_id varchar(36), raw_label text NOT NULL, raw_reference varchar(160),
  raw_unit varchar(60), raw_row jsonb, label_norm text, brand varchar(120), manufacturer_ref varchar(120),
  ean varchar(20), unit_canonical varchar(40), packaging_qty double precision NOT NULL DEFAULT 1,
  min_qty double precision, price_ht double precision, price_ht_per_unit double precision,
  currency varchar(8) NOT NULL DEFAULT 'EUR', vat_rate double precision, discount_applied double precision,
  delay varchar(60), availability varchar(60), product_url text, source_date varchar(40), source_filename text,
  canonical_product_id varchar(36), match_status varchar(20) NOT NULL DEFAULT 'orphan', match_confidence integer,
  match_rule_id varchar(36), match_reasons jsonb NOT NULL DEFAULT '[]', matched_at timestamptz, matched_by varchar(120),
  is_active boolean NOT NULL DEFAULT true,
  created_at varchar(40) DEFAULT to_char((now() AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
  designation_courte text, type_produit varchar(60), calibre varchar(20), courbe varchar(10), poles varchar(20),
  pouvoir_coupure varchar(20), sensibilite varchar(20), section varchar(20), puissance varchar(20),
  temperature varchar(20), conditionnement_lot integer, est_accessoire boolean DEFAULT false,
  est_courant_continu boolean DEFAULT false,
  CONSTRAINT supplier_offers_packaging_chk CHECK (packaging_qty > 0));
CREATE OR REPLACE FUNCTION blueseatra.normalise_recherche(txt text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
  SELECT trim(regexp_replace(
    -- 3. tout ce qui n'est ni lettre, ni chiffre, ni point, ni plus
    --    devient une espace ; les espaces multiples sont reduits
    regexp_replace(
      -- 2. minuscules, sans accents
      lower(unaccent('unaccent', coalesce(txt, ''))),
      -- 1. protege les decimales : "2,5" -> "2.5" AVANT le nettoyage,
      --    sinon la virgule serait remplacee par une espace
      '(\d)[.,](\d)', '\1.\2', 'g'
    ),
    '[^a-z0-9.+]+', ' ', 'g'
  ));
$$;

ALTER TABLE blueseatra.supplier_offers ADD COLUMN recherche_norm text GENERATED ALWAYS AS (
  blueseatra.normalise_recherche(coalesce(raw_label,'')||' '||coalesce(brand,'')||' '||
  coalesce(raw_reference,'')||' '||coalesce(manufacturer_ref,'')||' '||coalesce(ean,''))) STORED;
CREATE INDEX idx_offers_tenant ON blueseatra.supplier_offers (tenant_id);
CREATE INDEX idx_offers_tenant_supplier ON blueseatra.supplier_offers (tenant_id, supplier_id);
CREATE INDEX idx_offers_tenant_version ON blueseatra.supplier_offers (tenant_id, version_id);
CREATE INDEX idx_offers_tenant_prix ON blueseatra.supplier_offers (tenant_id, price_ht ASC NULLS LAST);
CREATE INDEX idx_offers_recherche_trgm ON blueseatra.supplier_offers USING gin (recherche_norm gin_trgm_ops);

GRANT SELECT, INSERT, UPDATE, DELETE ON blueseatra.suppliers, blueseatra.catalogs,
  blueseatra.catalog_versions, blueseatra.supplier_offers TO blueseatra_app;
-- Politiques TELLES QUE RELEVEES EN PRODUCTION (pg_policies, 23/09/2026) :
-- supplier_offers_all et suppliers_all ne visent QUE `authenticated`
-- (corrige par la migration 20260923200000). blueseatra_app n'a aucun
-- droit sur tenants.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['suppliers','catalogs','catalog_versions','supplier_offers'] LOOP
    EXECUTE format('ALTER TABLE blueseatra.%I ENABLE ROW LEVEL SECURITY', t);
  END LOOP; END $$;
CREATE POLICY supplier_offers_all ON blueseatra.supplier_offers FOR ALL TO authenticated
  USING ((tenant_id)::text = blueseatra.current_tenant()) WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
CREATE POLICY suppliers_all ON blueseatra.suppliers FOR ALL TO authenticated
  USING ((tenant_id)::text = blueseatra.current_tenant()) WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
CREATE POLICY catalogs_all ON blueseatra.catalogs FOR ALL TO authenticated, blueseatra_app
  USING ((tenant_id)::text = blueseatra.current_tenant()) WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
CREATE POLICY cv_all ON blueseatra.catalog_versions FOR ALL TO authenticated, blueseatra_app
  USING ((tenant_id)::text = blueseatra.current_tenant()) WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
