-- ===========================================================================
-- Sources fournisseurs du chiffrage (feature du 01/10/2026)
-- ===========================================================================
-- Permet a une entreprise d'ACTIVER ou de DESACTIVER, pour le chiffrage de
-- ses devis, les catalogues fournisseurs visibles par elle (les siens + le
-- catalogue commun). Un catalogue desactive n'est jamais supprime : son
-- contenu reste intact et il peut etre reactive a tout moment.
--
-- Modele : une ligne par (entreprise, catalogue fournisseur). La cle `cle`
-- est l'identifiant de version du catalogue fournisseur (UUID) ou
-- `hist:<supplier_id>` pour les offres historiques -- exactement la cle
-- utilisee par le parcours /fournisseurs/catalogue, resolue cote serveur
-- parmi les fournisseurs visibles : jamais crue telle quelle.
--
-- Les articles eux-memes ne sont PAS copies : le chiffrage les lit en SQL
-- dans supplier_offers au moment de la recherche (index trigramme
-- recherche_norm, migration 20260912070000). Aucune duplication de donnees.
--
-- Securite : RLS comme catalogue_commun_masque -- chaque entreprise ne
-- voit et n'ecrit que ses propres lignes (tenant_id = current_tenant()).
--
-- Idempotente. Retour arriere : section ROLLBACK en fin de fichier.
-- ===========================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS blueseatra.chiffrage_sources (
    tenant_id  varchar(36)  NOT NULL,
    cle        varchar(80)  NOT NULL,
    actif      boolean      NOT NULL DEFAULT true,
    cree_le    varchar(40),
    maj_le     varchar(40),
    par        varchar(255),
    PRIMARY KEY (tenant_id, cle)
);

ALTER TABLE blueseatra.chiffrage_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chiffrage_sources_all ON blueseatra.chiffrage_sources;
CREATE POLICY chiffrage_sources_all ON blueseatra.chiffrage_sources
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());

GRANT SELECT, INSERT, UPDATE, DELETE ON blueseatra.chiffrage_sources TO blueseatra_app;

COMMIT;

-- ===========================================================================
-- ROLLBACK (a executer manuellement si necessaire)
-- ---------------------------------------------------------------------------
-- BEGIN;
-- DROP POLICY IF EXISTS chiffrage_sources_all ON blueseatra.chiffrage_sources;
-- DROP TABLE IF EXISTS blueseatra.chiffrage_sources;
-- COMMIT;
-- ===========================================================================
