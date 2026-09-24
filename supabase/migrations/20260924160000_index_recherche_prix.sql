-- =====================================================================
-- Index compact de recherche triee par prix (Catalogue fournisseurs et
-- Comparer les prix)
-- =====================================================================
--
-- Mesure en production (24/09/2026) : « disjoncteur » dans Rexel > 60 s.
-- Le trigramme trouve vite les lignes, mais le tri par prix oblige a lire
-- toutes les fiches correspondantes dans une table de 1,1 Go (~1,1 ko par
-- ligne) alors que la memoire partagee ne fait que 224 Mo.
--
-- Cet index range les offres par entreprise puis par prix et embarque le
-- texte de recherche : PostgreSQL parcourt les offres les moins cheres en
-- lisant uniquement l'index (index-only scan, ~200 Mo) et s'arrete des que
-- la page est remplie. Aucune donnee n'est modifiee.
--
-- CONCURRENTLY : ne bloque ni lecture ni ecriture. A executer hors
-- transaction (pas de BEGIN/COMMIT). L'index-only scan suppose une table
-- videe (VACUUM) pour que la carte de visibilite soit a jour.
-- =====================================================================

-- catalog_id et supplier_id sont inclus : le filtre de version active et
-- le nom du fournisseur de Comparer les prix restent ainsi dans l'index.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_recherche_prix_v2
    ON blueseatra.supplier_offers (tenant_id, price_ht, id)
    INCLUDE (version_id, catalog_id, supplier_id, is_active, recherche_norm);

-- Premiere version (sans catalog_id ni supplier_id), remplacee par la v2.
DROP INDEX CONCURRENTLY IF EXISTS blueseatra.idx_offers_recherche_prix;
