-- ============================================================================
-- Journal d'audit en ajout seul (audit_logs)
-- ============================================================================
-- Constat du 1er octobre 2026 : la documentation présente audit_logs comme
-- un journal en ajout seul, mais la base ne l'imposait pas. Le rôle
-- applicatif blueseatra_app disposait encore des droits UPDATE et DELETE
-- (GRANT global de l'étape 4 du durcissement RLS) et aucun trigger ne
-- protégeait la table, contrairement à registre_consommation et
-- echanges_clients.
--
-- Correctif, sur le modèle de blueseatra.registre_ajout_seul() :
--   1. retrait des droits UPDATE, DELETE et TRUNCATE au rôle applicatif ;
--   2. trigger BEFORE UPDATE OR DELETE (par ligne) et BEFORE TRUNCATE
--      (par instruction) qui refuse l'opération pour tous les rôles ;
--   3. une seule exception, réservée à la maintenance (bases de test,
--      purge réglementaire décidée par écrit) : un rôle d'administration,
--      jamais blueseatra_app, positionne pour SA transaction
--        SET LOCAL blueseatra.maintenance_audit = 'on';
--
-- Aucun chemin de l'application ne modifie ni ne supprime une ligne du
-- journal (vérifié dans backend/ : seules des insertions). L'export RGPD
-- (observabilite.TABLES_EXPORT) ne fait que lire la table.
--
-- Idempotente : peut être rejouée sans effet de bord.
-- ============================================================================

CREATE OR REPLACE FUNCTION blueseatra.audit_ajout_seul() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_user <> 'blueseatra_app'
       AND coalesce(current_setting('blueseatra.maintenance_audit', true), '') = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSIF TG_OP = 'UPDATE' THEN
            RETURN NEW;
        END IF;
        RETURN NULL;   -- TRUNCATE (trigger par instruction)
    END IF;
    RAISE EXCEPTION 'audit_logs est en ajout seul : % refusé.', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;

DROP TRIGGER IF EXISTS audit_ajout_seul ON blueseatra.audit_logs;
CREATE TRIGGER audit_ajout_seul
    BEFORE UPDATE OR DELETE ON blueseatra.audit_logs
    FOR EACH ROW EXECUTE FUNCTION blueseatra.audit_ajout_seul();

DROP TRIGGER IF EXISTS audit_ajout_seul_truncate ON blueseatra.audit_logs;
CREATE TRIGGER audit_ajout_seul_truncate
    BEFORE TRUNCATE ON blueseatra.audit_logs
    FOR EACH STATEMENT EXECUTE FUNCTION blueseatra.audit_ajout_seul();

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app') THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON blueseatra.audit_logs FROM blueseatra_app;
        GRANT SELECT, INSERT ON blueseatra.audit_logs TO blueseatra_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON blueseatra.audit_logs FROM authenticated;
    END IF;
END $$;

COMMENT ON TABLE blueseatra.audit_logs IS
    'Journal d''audit en ajout seul : UPDATE, DELETE et TRUNCATE refusés par trigger '
    '(blueseatra.audit_ajout_seul) et par retrait des droits du rôle applicatif.';
