-- Recherche par famille dans le comparateur de prix (01/10/2026).
--
-- blueseatra.offres_candidates recoit un filtre facultatif p_famille
-- (raw_row->>'famille'). La liste des familles proposees au chiffreur vient
-- de l'index (tenant_id, version_id, famille, ...) deja en place, par
-- catalogue et mise en cache (catalogue_navigation.familles).
--
-- La signature change (8e parametre) : DROP puis
-- CREATE dans la meme transaction. p_famille vaut NULL par defaut, donc les
-- appels a 7 arguments du code deja deploye restent valides pendant la
-- bascule. Memes regles de cloisonnement qu'avant (voir 20261001180000).
-- Aucune table modifiee.

DROP FUNCTION IF EXISTS blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean);
DROP FUNCTION IF EXISTS blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean, text);

CREATE FUNCTION blueseatra.offres_candidates(
    p_tenants          text[],
    p_termes           jsonb,
    p_limite           integer DEFAULT 200,
    p_version          text    DEFAULT NULL,
    p_hist             text    DEFAULT NULL,
    p_versions_actives boolean DEFAULT false,
    p_tri_prix         boolean DEFAULT false,
    p_famille          text    DEFAULT NULL
)
RETURNS TABLE (
    id             varchar,
    tenant_id      varchar,
    supplier_id    varchar,
    version_id     varchar,
    price_ht       double precision,
    recherche_norm text
)
LANGUAGE plpgsql
VOLATILE  -- EXPLAIN interdit dans une fonction STABLE ; lecture seule de fait
SECURITY DEFINER
SET search_path = ''
AS $fonction$
DECLARE
    v_courant  text := blueseatra.current_tenant();
    v_commun   text := blueseatra.tenant_catalogue_commun();
    v_cond     text;
    v_portee   text;
    v_limite   integer := least(greatest(coalesce(p_limite, 200), 1), 5000);
    v_sql      text;
    v_seuil    constant integer := 3000;
    v_nb       numeric;
    v_plan     json;
    v_t        text;
    v_trigramme boolean := false;
    v_seuil_famille constant integer := 60000;
BEGIN
    -- Cloisonnement : chaque tenant demande doit etre l'entreprise courante
    -- ou le catalogue commun. Sinon : aucune ligne.
    IF p_tenants IS NULL OR cardinality(p_tenants) = 0 OR cardinality(p_tenants) > 2 THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(p_tenants) AS t(x)
               WHERE x IS NULL OR NOT (x = coalesce(v_courant, '') OR x = v_commun)) THEN
        RETURN;
    END IF;

    v_cond := blueseatra.recherche_conditions(p_termes);
    IF v_cond IS NULL THEN
        RETURN;
    END IF;

    v_portee := format('o.tenant_id = ANY (%L::varchar[]) AND o.is_active', p_tenants);
    IF p_version IS NOT NULL THEN
        v_portee := v_portee || format(' AND o.version_id = %L', p_version);
    ELSIF p_hist IS NOT NULL THEN
        v_portee := v_portee || format(
            ' AND o.supplier_id = %L AND (o.catalog_id IS NULL OR o.catalog_id NOT IN ('
            'SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = ANY (%L::varchar[])))',
            p_hist, p_tenants);
    END IF;
    IF p_versions_actives THEN
        v_portee := v_portee || format(
            ' AND (o.catalog_id IS NULL'
            ' OR o.version_id IN (SELECT c.active_version_id FROM blueseatra.catalogs c'
            '   WHERE c.tenant_id = ANY (%1$L::varchar[]) AND c.active_version_id IS NOT NULL)'
            ' OR o.catalog_id NOT IN (SELECT c.id FROM blueseatra.catalogs c'
            '   WHERE c.tenant_id = ANY (%1$L::varchar[])))',
            p_tenants);
    END IF;

    IF coalesce(p_famille, '') <> '' THEN
        v_portee := v_portee || format(' AND (o.raw_row->>''famille'') = %L', p_famille);
    END IF;

    IF NOT p_tri_prix THEN
        v_sql := format(
            'SELECT o.id, o.tenant_id, o.supplier_id, o.version_id, o.price_ht, o.recherche_norm'
            ' FROM blueseatra.supplier_offers o WHERE %s%s LIMIT %s',
            v_portee, v_cond, v_limite);
    ELSE
        -- Chemin choisi selon l'ESTIMATION du planificateur (EXPLAIN, sans
        -- lecture de donnees) : un vrai comptage coute 3 a 6 s a froid.
        EXECUTE format('EXPLAIN (FORMAT JSON) SELECT 1 FROM blueseatra.supplier_offers o'
                       ' WHERE %s%s', v_portee, v_cond)
           INTO v_plan;
        v_nb := coalesce((v_plan->0->'Plan'->>'Plan Rows')::numeric, 0);
        -- Avec une famille (hors index par prix), un mot courant peut y etre
        -- rare : si le mot est assez selectif dans toute la table, l'index
        -- trigramme evite de lire des centaines de milliers de fiches.
        IF v_nb > v_seuil AND coalesce(p_famille, '') <> '' THEN
            EXECUTE format('EXPLAIN (FORMAT JSON) SELECT 1 FROM blueseatra.supplier_offers o WHERE true%s',
                           v_cond) INTO v_plan;
            v_trigramme := coalesce((v_plan->0->'Plan'->>'Plan Rows')::numeric, 0) <= v_seuil_famille;
        END IF;
        IF v_nb <= v_seuil OR v_trigramme THEN
            v_sql := format(
                'WITH m AS MATERIALIZED ('
                ' SELECT o.id, o.tenant_id, o.supplier_id, o.version_id, o.price_ht, o.recherche_norm'
                ' FROM blueseatra.supplier_offers o WHERE %s%s)'
                ' SELECT * FROM m ORDER BY m.price_ht ASC NULLS LAST, m.id LIMIT %s',
                v_portee, v_cond, v_limite);
        ELSE
            v_sql := '';
            FOREACH v_t IN ARRAY p_tenants LOOP
                v_sql := v_sql || CASE WHEN v_sql = '' THEN '' ELSE ' UNION ALL ' END || format(
                    '(SELECT o.id, o.tenant_id, o.supplier_id, o.version_id, o.price_ht, o.recherche_norm'
                    ' FROM blueseatra.supplier_offers o WHERE %s AND o.tenant_id = %L%s'
                    ' ORDER BY o.price_ht ASC NULLS LAST, o.id LIMIT %s)',
                    v_portee, v_t, v_cond, v_limite);
            END LOOP;
            v_sql := format('SELECT * FROM (%s) u ORDER BY u.price_ht ASC NULLS LAST, u.id LIMIT %s',
                            v_sql, v_limite);
        END IF;
    END IF;
    RETURN QUERY EXECUTE v_sql;
END
$fonction$;

COMMENT ON FUNCTION blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean, text) IS
  'Recherche trigramme des offres fournisseurs utilisable sous RLS. Ne renvoie que les tenants courant/commun ; fiches relues ensuite sous RLS.';
REVOKE ALL ON FUNCTION blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean, text) TO blueseatra_app;
