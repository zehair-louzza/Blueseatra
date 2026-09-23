-- ===========================================================================
-- Catalogue fournisseurs COMMUN a toutes les entreprises
-- ===========================================================================
-- 1. CORRECTIF constate en production le 23/09/2026 (lecture de pg_policies) :
--    supplier_offers_all et suppliers_all ne visent que le role
--    `authenticated`. Pour `blueseatra_app` (NOBYPASSRLS), RLS est active
--    SANS politique -> zero ligne en lecture, ecriture refusee. Les autres
--    tables (catalogs, catalog_versions, quotes...) visent deja les deux
--    roles. Le site n'est pas touche aujourd'hui (mode repli `postgres`),
--    mais la bascule DATABASE_URL_APP casserait la recherche fournisseurs,
--    et le script d'import (SET ROLE blueseatra_app) serait refuse.
--
-- 2. Tenant systeme du catalogue commun (aucun utilisateur ne s'y rattache).
-- 3. Masquage par entreprise, et masquage global (compte Blueseatra).
--    Le catalogue commun n'est JAMAIS supprime depuis le site.
-- 4. LECTURE SEULE du catalogue commun pour blueseatra_app. Politiques
--    permissives FOR SELECT : elles s'ajoutent (OR) aux politiques
--    existantes pour la lecture uniquement. Ecriture inchangee :
--    tenant_id = current_tenant().
--
-- Idempotente. Retour arriere : section ROLLBACK en fin de fichier.
-- ===========================================================================
BEGIN;

-- 1. Correctif des roles --------------------------------------------------
ALTER POLICY supplier_offers_all ON blueseatra.supplier_offers TO authenticated, blueseatra_app;
ALTER POLICY suppliers_all       ON blueseatra.suppliers       TO authenticated, blueseatra_app;

-- 2. Tenant systeme -------------------------------------------------------
CREATE OR REPLACE FUNCTION blueseatra.tenant_catalogue_commun()
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT '00000000-0000-4000-8000-000000000c0d'::text $$;

INSERT INTO blueseatra.tenants (id, name, plan, created_at)
SELECT blueseatra.tenant_catalogue_commun(), 'Catalogue commun Blueseatra', 'systeme',
       to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
WHERE NOT EXISTS (SELECT 1 FROM blueseatra.tenants WHERE id = blueseatra.tenant_catalogue_commun());

-- 3. Masquage par entreprise ----------------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.catalogue_commun_masque (
    tenant_id  varchar PRIMARY KEY,
    masque_le  varchar NOT NULL,
    masque_par varchar
);
ALTER TABLE blueseatra.catalogue_commun_masque ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS catalogue_commun_masque_all ON blueseatra.catalogue_commun_masque;
CREATE POLICY catalogue_commun_masque_all ON blueseatra.catalogue_commun_masque
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
-- La ligne tenant_id = tenant commun signifie "masque pour TOUTES les
-- entreprises" (posee par le compte Blueseatra) : lisible par tous.
DROP POLICY IF EXISTS lecture_masquage_global ON blueseatra.catalogue_commun_masque;
CREATE POLICY lecture_masquage_global ON blueseatra.catalogue_commun_masque
    FOR SELECT TO blueseatra_app
    USING ((tenant_id)::text = blueseatra.tenant_catalogue_commun());
GRANT SELECT, INSERT, DELETE ON blueseatra.catalogue_commun_masque TO blueseatra_app;

-- 4. Lecture seule du catalogue commun ------------------------------------
DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.supplier_offers;
CREATE POLICY lecture_catalogue_commun ON blueseatra.supplier_offers
    FOR SELECT TO blueseatra_app
    USING ((tenant_id)::text = blueseatra.tenant_catalogue_commun());

DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.suppliers;
CREATE POLICY lecture_catalogue_commun ON blueseatra.suppliers
    FOR SELECT TO blueseatra_app
    USING ((tenant_id)::text = blueseatra.tenant_catalogue_commun());

DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.catalogs;
CREATE POLICY lecture_catalogue_commun ON blueseatra.catalogs
    FOR SELECT TO blueseatra_app
    USING ((tenant_id)::text = blueseatra.tenant_catalogue_commun());

DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.catalog_versions;
CREATE POLICY lecture_catalogue_commun ON blueseatra.catalog_versions
    FOR SELECT TO blueseatra_app
    USING ((tenant_id)::text = blueseatra.tenant_catalogue_commun());

COMMIT;

-- ===========================================================================
-- ROLLBACK (a executer manuellement si necessaire)
-- ---------------------------------------------------------------------------
-- BEGIN;
-- DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.supplier_offers;
-- DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.suppliers;
-- DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.catalogs;
-- DROP POLICY IF EXISTS lecture_catalogue_commun ON blueseatra.catalog_versions;
-- DROP POLICY IF EXISTS lecture_masquage_global ON blueseatra.catalogue_commun_masque;
-- DROP TABLE IF EXISTS blueseatra.catalogue_commun_masque;
-- ALTER POLICY supplier_offers_all ON blueseatra.supplier_offers TO authenticated;
-- ALTER POLICY suppliers_all       ON blueseatra.suppliers       TO authenticated;
-- -- les lignes du tenant commun doivent etre supprimees AVANT :
-- DELETE FROM blueseatra.tenants WHERE id = blueseatra.tenant_catalogue_commun();
-- DROP FUNCTION IF EXISTS blueseatra.tenant_catalogue_commun();
-- COMMIT;
-- ===========================================================================
