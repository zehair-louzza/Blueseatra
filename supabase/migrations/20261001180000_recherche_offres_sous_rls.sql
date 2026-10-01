-- Recherche d'offres fournisseurs rapide SOUS RLS (constat du 01/10/2026).
--
-- PROBLEME
--   Sous le role blueseatra_app, la RLS de supplier_offers interdit au
--   planificateur d'utiliser l'index trigramme idx_offers_recherche_trgm :
--   l'operateur LIKE (textlike) n'est pas LEAKPROOF, il ne peut donc pas
--   etre evalue avant les politiques. Chaque recherche filtrait ligne a
--   ligne : ~27 s pour le comparateur, > 30 s (command_timeout) pour le
--   selecteur d'articles du devis sur un terme courant ("prise").
--
-- CORRECTIF
--   Une fonction SECURITY DEFINER qui ne fait QUE la recherche trigramme et
--   ne renvoie que des colonnes de tri/filtrage (jamais la fiche complete) :
--   - elle refuse tout tenant qui n'est ni current_tenant() ni le catalogue
--     commun : un appelant ne peut pas lire une autre entreprise ;
--   - les motifs sont injectes via format(%L) (litteraux echappes) : aucun
--     texte utilisateur n'est concatene tel quel ;
--   - les fiches completes sont relues ENSUITE par id, toujours sous RLS :
--     meme si la fonction se trompait, la politique filtrerait les lignes.
--   Aucune table n'est modifiee ; aucune donnee n'est supprimee.
--
-- p_termes : tableau JSON de termes, combines en ET ; chaque terme est un
--   tableau d'ecritures combinees en OU : [[{"op":"like","v":"%prise%"}], ...]
--   op = "like" (LIKE) ou "regex" (~). Au plus 12 termes, 12 ecritures.
-- p_version  : restreint a une version de catalogue (selecteur du devis).
-- p_hist     : restreint a un fournisseur sans catalogue versionne.
-- p_versions_actives : n'accepte que les offres de la version active de
--   leur catalogue (ou sans catalogue), comme le comparateur.
-- p_tri_prix : renvoie les p_limite offres les moins cheres (sinon, les
--   p_limite premieres trouvees, plus rapide). Chemin choisi selon le
--   nombre ESTIME de correspondances (<= 3000 : trigramme puis tri ;
--   au-dela : index par prix, arret a p_limite). Les deux chemins
--   renvoient exactement les memes lignes ; seul le temps differe.

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
    v_terme    jsonb;
    v_alt      jsonb;
    v_ou       text;
    v_cond     text := '';
    v_portee   text;
    v_limite   integer := least(greatest(coalesce(p_limite, 200), 1), 5000);
    v_sql      text;
    v_seuil    constant integer := 3000;
    v_nb       numeric;
    v_plan     json;
    v_t        text;
BEGIN
    -- 1. Cloisonnement : chaque tenant demande doit etre l'entreprise
    --    courante ou le catalogue commun. Sinon : aucune ligne.
    IF p_tenants IS NULL OR cardinality(p_tenants) = 0 OR cardinality(p_tenants) > 2 THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(p_tenants) AS t(x)
               WHERE x IS NULL OR NOT (x = coalesce(v_courant, '') OR x = v_commun)) THEN
        RETURN;
    END IF;

    -- 2. Conditions de recherche : ET entre termes, OU entre ecritures.
    IF p_termes IS NULL OR jsonb_typeof(p_termes) <> 'array'
       OR jsonb_array_length(p_termes) NOT BETWEEN 1 AND 12 THEN
        RETURN;
    END IF;
    FOR v_terme IN SELECT e FROM jsonb_array_elements(p_termes) AS a(e) LOOP
        IF jsonb_typeof(v_terme) <> 'array' OR jsonb_array_length(v_terme) NOT BETWEEN 1 AND 12 THEN
            RETURN;
        END IF;
        v_ou := '';
        FOR v_alt IN SELECT e FROM jsonb_array_elements(v_terme) AS a(e) LOOP
            IF coalesce(v_alt->>'v', '') = '' THEN
                RETURN;
            ELSIF v_alt->>'op' = 'like' THEN
                v_ou := v_ou || CASE WHEN v_ou = '' THEN '' ELSE ' OR ' END
                        || format('o.recherche_norm LIKE %L', v_alt->>'v');
            ELSIF v_alt->>'op' = 'regex' THEN
                v_ou := v_ou || CASE WHEN v_ou = '' THEN '' ELSE ' OR ' END
                        || format('o.recherche_norm ~ %L', v_alt->>'v');
            ELSE
                RETURN;
            END IF;
        END LOOP;
        v_cond := v_cond || ' AND (' || v_ou || ')';
    END LOOP;

    -- 3. Portee : tenants autorises, offre active, et restriction eventuelle.
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

    -- 4. Execution.
    IF NOT p_tri_prix THEN
        -- Selecteur d'articles : les p_limite premieres offres trouvees
        -- par l'index trigramme suffisent (le tri se fait ensuite).
        v_sql := format(
            'SELECT o.id, o.tenant_id, o.supplier_id, o.version_id, o.price_ht, o.recherche_norm'
            ' FROM blueseatra.supplier_offers o WHERE %s%s LIMIT %s',
            v_portee, v_cond, v_limite);
    ELSE
        -- Comparateur : les p_limite offres les MOINS CHERES. Le bon chemin
        -- depend du nombre de correspondances. On lit l'ESTIMATION du
        -- planificateur (EXPLAIN, sans lecture de donnees) : un vrai
        -- comptage lirait des milliers de pages a froid (mesure : 3 a 6 s).
        EXECUTE format('EXPLAIN (FORMAT JSON) SELECT 1 FROM blueseatra.supplier_offers o'
                       ' WHERE %s%s', v_portee, v_cond)
           INTO v_plan;
        v_nb := coalesce((v_plan->0->'Plan'->>'Plan Rows')::numeric, 0);
        IF v_nb <= v_seuil THEN
            -- Peu de correspondances : index trigramme puis tri. Le CTE
            -- MATERIALIZED empeche le planificateur de parcourir l'index
            -- par prix en filtrant ligne a ligne (cause du #133).
            v_sql := format(
                'WITH m AS MATERIALIZED ('
                ' SELECT o.id, o.tenant_id, o.supplier_id, o.version_id, o.price_ht, o.recherche_norm'
                ' FROM blueseatra.supplier_offers o WHERE %s%s)'
                ' SELECT * FROM m ORDER BY m.price_ht ASC NULLS LAST, m.id LIMIT %s',
                v_portee, v_cond, v_limite);
        ELSE
            -- Terme courant : parcours de idx_offers_recherche_prix_v2 dans
            -- l'ordre des prix (index-only : il inclut recherche_norm), une
            -- branche par tenant pour garder l'ordre de l'index ; arret des
            -- que p_limite offres correspondent.
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
