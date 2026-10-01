-- Recherche par mot A L'INTERIEUR d'un catalogue, rapide sous RLS.
--
-- PROBLEME (mesure en production le 01/10/2026, catalogue Rexel 747 771
-- offres, ecran « Afficher le catalogue ») : meme cause que la migration
-- 20261001180000. Sous blueseatra_app, LIKE n'est pas LEAKPROOF : l'index
-- trigramme est inutilisable et la version est parcourue ligne a ligne.
-- « disjoncteur 16a courbe c » 26,6 s ; terme rare 43,9 s ; mot + famille :
-- delai depasse (erreur).
--
-- CORRECTIF
--   1. blueseatra.recherche_conditions(jsonb) : traduction des termes en
--      clause SQL, partagee par les deux fonctions de recherche (une seule
--      implementation des regles de securite : operateurs limites a LIKE et
--      ~, motifs en litteraux echappes via format(%L), bornes de taille).
--   2. blueseatra.offres_candidates : meme signature, meme comportement,
--      reecrite pour utiliser recherche_conditions.
--   3. blueseatra.catalogue_page : une page triee par prix d'UNE version
--      (ou d'un fournisseur sans catalogue), avec un total plafonne. Ne
--      renvoie que des identifiants ; les fiches sont relues sous RLS.
--   Aucune table modifiee, aucune donnee touchee.

-- 1. Termes -> clause SQL ----------------------------------------------------
-- p_termes : [[{"op":"like","v":"%prise%"}, ...], ...] ; ET entre termes,
-- OU entre ecritures. Renvoie NULL si l'entree est invalide.
CREATE OR REPLACE FUNCTION blueseatra.recherche_conditions(p_termes jsonb)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
SET search_path = ''
AS $fonction$
DECLARE
    v_terme jsonb;
    v_alt   jsonb;
    v_ou    text;
    v_cond  text := '';
BEGIN
    IF p_termes IS NULL OR jsonb_typeof(p_termes) <> 'array'
       OR jsonb_array_length(p_termes) NOT BETWEEN 1 AND 12 THEN
        RETURN NULL;
    END IF;
    FOR v_terme IN SELECT e FROM jsonb_array_elements(p_termes) AS a(e) LOOP
        IF jsonb_typeof(v_terme) <> 'array' OR jsonb_array_length(v_terme) NOT BETWEEN 1 AND 12 THEN
            RETURN NULL;
        END IF;
        v_ou := '';
        FOR v_alt IN SELECT e FROM jsonb_array_elements(v_terme) AS a(e) LOOP
            IF jsonb_typeof(v_alt) <> 'object' OR coalesce(v_alt->>'v', '') = ''
               OR length(v_alt->>'v') > 200 THEN
                RETURN NULL;
            ELSIF v_alt->>'op' = 'like' THEN
                v_ou := v_ou || CASE WHEN v_ou = '' THEN '' ELSE ' OR ' END
                        || format('o.recherche_norm LIKE %L', v_alt->>'v');
            ELSIF v_alt->>'op' = 'regex' THEN
                v_ou := v_ou || CASE WHEN v_ou = '' THEN '' ELSE ' OR ' END
                        || format('o.recherche_norm ~ %L', v_alt->>'v');
            ELSE
                RETURN NULL;
            END IF;
        END LOOP;
        v_cond := v_cond || ' AND (' || v_ou || ')';
    END LOOP;
    RETURN v_cond;
END
$fonction$;

REVOKE ALL ON FUNCTION blueseatra.recherche_conditions(jsonb) FROM PUBLIC;

-- 2. offres_candidates, reecrite sur recherche_conditions ----------------------
CREATE OR REPLACE FUNCTION blueseatra.offres_candidates(
    p_tenants          text[],
    p_termes           jsonb,
    p_limite           integer DEFAULT 200,
    p_version          text    DEFAULT NULL,
    p_hist             text    DEFAULT NULL,
    p_versions_actives boolean DEFAULT false,
    p_tri_prix         boolean DEFAULT false
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
        IF v_nb <= v_seuil THEN
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

COMMENT ON FUNCTION blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean) IS
  'Recherche trigramme des offres fournisseurs utilisable sous RLS. Ne renvoie que les tenants courant/commun ; fiches relues ensuite sous RLS.';
REVOKE ALL ON FUNCTION blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.offres_candidates(text[], jsonb, integer, text, text, boolean, boolean) TO blueseatra_app;

-- 3. Une page de recherche dans un catalogue -----------------------------------
-- p_tenant    : entreprise courante ou catalogue commun (sinon : vide).
-- p_version   : version du catalogue ; OU p_hist : fournisseur sans catalogue.
-- p_famille   : filtre facultatif sur raw_row->>'famille'.
-- p_limite / p_decalage : la page (tri prix croissant, puis id).
-- p_plafond   : le total est compte jusqu'a p_plafond lignes au plus.
-- Renvoie {"ids": [...dans l'ordre...], "total": n}.
CREATE OR REPLACE FUNCTION blueseatra.catalogue_page(
    p_tenant   text,
    p_version  text,
    p_hist     text,
    p_termes   jsonb,
    p_famille  text,
    p_limite   integer,
    p_decalage integer,
    p_plafond  integer
)
RETURNS jsonb
LANGUAGE plpgsql
VOLATILE  -- EXPLAIN interdit dans une fonction STABLE ; lecture seule de fait
SECURITY DEFINER
SET search_path = ''
AS $fonction$
DECLARE
    v_vide     constant jsonb := '{"ids": [], "total": 0}';
    v_cond     text;
    v_portee   text;
    v_limite   integer := least(greatest(coalesce(p_limite, 50), 1), 201);
    v_decalage integer := greatest(coalesce(p_decalage, 0), 0);
    v_plafond  integer := least(greatest(coalesce(p_plafond, 1001), 1), 10001);
    v_ids      jsonb;
    v_total    integer;
    v_plan     json;
    v_trigramme boolean := false;
    v_seuil_famille constant integer := 60000;
BEGIN
    -- Cloisonnement : uniquement l'entreprise courante ou le catalogue commun,
    -- et toujours une portee precise (version OU fournisseur historique).
    IF p_tenant IS NULL
       OR NOT (p_tenant = coalesce(blueseatra.current_tenant(), '')
               OR p_tenant = blueseatra.tenant_catalogue_commun())
       OR (p_version IS NULL) = (p_hist IS NULL) THEN
        RETURN v_vide;
    END IF;

    v_cond := blueseatra.recherche_conditions(p_termes);
    IF v_cond IS NULL THEN
        RETURN v_vide;
    END IF;

    v_portee := format('o.tenant_id = %L AND o.is_active', p_tenant);
    IF p_version IS NOT NULL THEN
        v_portee := v_portee || format(' AND o.version_id = %L', p_version);
    ELSE
        v_portee := v_portee || format(
            ' AND o.supplier_id = %L AND (o.catalog_id IS NULL OR o.catalog_id NOT IN ('
            'SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = %L))',
            p_hist, p_tenant);
    END IF;
    IF coalesce(p_famille, '') <> '' THEN
        v_portee := v_portee || format(' AND (o.raw_row->>''famille'') = %L', p_famille);
    END IF;

    -- Total plafonne : s'arrete des p_plafond correspondances.
    EXECUTE format('SELECT count(*) FROM (SELECT 1 FROM blueseatra.supplier_offers o'
                   ' WHERE %s%s LIMIT %s) s', v_portee, v_cond, v_plafond)
       INTO v_total;
    IF v_total = 0 THEN
        RETURN v_vide;
    END IF;

    -- Avec une famille, un mot courant peut y etre rare (« prise » dans
    -- Eclairage) : le parcours par prix lirait alors des centaines de milliers
    -- de fiches (famille hors index). Si le mot est assez selectif dans toute
    -- la table (ESTIMATION du planificateur, sans lecture), l'index trigramme
    -- est plus sur.
    IF v_total >= v_plafond AND coalesce(p_famille, '') <> '' THEN
        EXECUTE format('EXPLAIN (FORMAT JSON) SELECT 1 FROM blueseatra.supplier_offers o WHERE true%s',
                       v_cond) INTO v_plan;
        v_trigramme := coalesce((v_plan->0->'Plan'->>'Plan Rows')::numeric, 0) <= v_seuil_famille;
    END IF;

    IF v_total < v_plafond OR v_trigramme THEN
        -- Peu de correspondances (toutes comptees, < p_plafond) : index trigramme, puis
        -- tri des seuls id/prix (le CTE empeche le parcours par prix).
        EXECUTE format(
            'WITH m AS MATERIALIZED (SELECT o.id, o.price_ht FROM blueseatra.supplier_offers o WHERE %s%s)'
            ' SELECT coalesce(jsonb_agg(p.id ORDER BY p.price_ht ASC NULLS LAST, p.id), ''[]'')'
            ' FROM (SELECT m.id, m.price_ht FROM m ORDER BY m.price_ht ASC NULLS LAST, m.id'
            '       LIMIT %s OFFSET %s) p',
            v_portee, v_cond, v_limite, v_decalage)
           INTO v_ids;
    ELSE
        -- Terme courant (au moins p_plafond correspondances) : parcours de
        -- l'index par prix dans la portee, arret des que la page est pleine.
        EXECUTE format(
            'SELECT coalesce(jsonb_agg(p.id ORDER BY p.price_ht ASC NULLS LAST, p.id), ''[]'')'
            ' FROM (SELECT o.id, o.price_ht FROM blueseatra.supplier_offers o WHERE %s%s'
            '       ORDER BY o.price_ht ASC NULLS LAST, o.id LIMIT %s OFFSET %s) p',
            v_portee, v_cond, v_limite, v_decalage)
           INTO v_ids;
    END IF;
    RETURN jsonb_build_object('ids', v_ids, 'total', v_total);
END
$fonction$;

COMMENT ON FUNCTION blueseatra.catalogue_page(text, text, text, jsonb, text, integer, integer, integer) IS
  'Page de recherche par mot dans un catalogue, utilisable sous RLS. Tenant courant/commun uniquement ; fiches relues ensuite sous RLS.';
REVOKE ALL ON FUNCTION blueseatra.catalogue_page(text, text, text, jsonb, text, integer, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.catalogue_page(text, text, text, jsonb, text, integer, integer, integer) TO blueseatra_app;
