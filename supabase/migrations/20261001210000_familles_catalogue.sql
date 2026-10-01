-- Liste des familles d'un catalogue, rapide (01/10/2026).
--
-- PROBLEME (mesure en production juste apres #141) : GET /fournisseurs/familles
-- prenait 75 s au premier appel. Pour chaque catalogue, la requete
--   SELECT raw_row->>'famille', count(*) ... WHERE tenant_id = ... AND version_id = ...
-- finissait en PARCOURS COMPLET de supplier_offers (2,5 Go) : l'index
-- idx_offers_tenant_version_famille porte sur une EXPRESSION (raw_row->>'famille'),
-- que PostgreSQL ne sait pas lire sans la fiche, et sous RLS l'operateur ->>
-- (non LEAKPROOF) ne peut pas servir de condition d'index.
--
-- CORRECTIF : blueseatra.familles_catalogue renvoie les familles DISTINCTES
-- d'une version par un parcours « en saut » de l'index (une lecture par
-- famille : 50 ms pour Rexel au lieu d'un parcours complet). Sans comptage :
-- compter exigerait de lire chaque fiche. SECURITY DEFINER, memes regles
-- que les autres fonctions de recherche : tenant courant ou catalogue commun
-- uniquement, portee precise obligatoire (version OU fournisseur historique).
-- Aucune table modifiee.

CREATE OR REPLACE FUNCTION blueseatra.familles_catalogue(
    p_tenant  text,
    p_version text,
    p_hist    text
)
RETURNS SETOF text
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $fonction$
BEGIN
    IF p_tenant IS NULL
       OR NOT (p_tenant = coalesce(blueseatra.current_tenant(), '')
               OR p_tenant = blueseatra.tenant_catalogue_commun())
       OR (p_version IS NULL) = (p_hist IS NULL) THEN
        RETURN;
    END IF;

    IF p_version IS NOT NULL THEN
        -- Parcours en saut de idx_offers_tenant_version_famille : chaque
        -- etape lit la premiere famille strictement superieure a la
        -- precedente. Borne a 5 000 familles par catalogue.
        RETURN QUERY
        WITH RECURSIVE f(famille, n) AS (
            (SELECT o.raw_row->>'famille', 1
               FROM blueseatra.supplier_offers o
              WHERE o.tenant_id = p_tenant AND o.version_id = p_version
                AND (o.raw_row->>'famille') IS NOT NULL
              ORDER BY o.raw_row->>'famille'
              LIMIT 1)
            UNION ALL
            SELECT (SELECT o.raw_row->>'famille'
                      FROM blueseatra.supplier_offers o
                     WHERE o.tenant_id = p_tenant AND o.version_id = p_version
                       AND (o.raw_row->>'famille') > f.famille
                     ORDER BY o.raw_row->>'famille'
                     LIMIT 1), f.n + 1
              FROM f
             WHERE f.famille IS NOT NULL AND f.n < 5000
        )
        SELECT f.famille FROM f WHERE f.famille IS NOT NULL AND f.famille <> '';
    ELSE
        -- Fournisseur sans catalogue versionne : offres de l'entreprise
        -- seulement (volumes faibles), meme regle que la navigation.
        RETURN QUERY
        SELECT DISTINCT o.raw_row->>'famille'
          FROM blueseatra.supplier_offers o
         WHERE o.tenant_id = p_tenant AND o.supplier_id = p_hist AND o.is_active
           AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = p_tenant))
           AND coalesce(o.raw_row->>'famille', '') <> ''
         LIMIT 5000;
    END IF;
END
$fonction$;

COMMENT ON FUNCTION blueseatra.familles_catalogue(text, text, text) IS
  'Familles distinctes d''un catalogue (parcours en saut de l''index), tenant courant/commun uniquement.';
REVOKE ALL ON FUNCTION blueseatra.familles_catalogue(text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.familles_catalogue(text, text, text) TO blueseatra_app;
