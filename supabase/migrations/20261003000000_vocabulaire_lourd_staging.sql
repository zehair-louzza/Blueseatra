-- Recalcul du vocabulaire, version TABLES DE TRAVAIL (03/10/2026).
--
-- CONSTATS DE PRODUCTION (catalogue Rexel, 747 000 offres) :
--   1. La version monobloc (20261002060000) agrégeait ~7,5 millions de paires
--      d'un coup : débordement de work_mem, passe interrompue à 75 minutes.
--   2. La version par lots avec upserts accumulés (20261002070000)
--      s'effondrait à partir de la 6e tranche : les upserts invalident la
--      carte de visibilité de la table cible, les Index Only Scan sur
--      idx_vocabulaire_mot redeviennent des lectures de table (52 000 heap
--      fetches mesurés), l'index gonfle, les statistiques prennent du
--      retard. Passe interrompue à 47 minutes.
--
-- ARCHITECTURE (conseil du modèle relecteur, 03/10/2026) :
--   supplier_offers -> table temp. de tableaux (découpe UNE fois par offre)
--   -> table temp. de mots isolés -> tables temp. de paires et de triples
--   -> REMPLACEMENT final en une seule écriture.
--
--   - Aucune écriture dans la table cible pendant l'agrégation : plus
--     d'ON CONFLICT, plus de lectures d'index contre une table en mutation.
--   - Les jointures « mots courants » se font contre la table temporaire
--     des mots isolés, petite et propre.
--   - Les tableaux sont matérialisés une fois : le planificateur ne peut
--     pas recalculer string_to_array (constat : 6 découpes par paire dans
--     la version lateral, aplatie par le planificateur).
--   - Les seuils de la version de référence (vocabulaire_recalculer) sont
--     conservés : mêmes lignes, mêmes comptes.
--
-- Les sources 'hist:' restent déléguées à vocabulaire_recalculer.

CREATE OR REPLACE FUNCTION blueseatra.vocabulaire_recalculer_lourd(
    p_tenant varchar, p_source varchar)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
    v_courant text := blueseatra.current_tenant();
    v_total   bigint;
    v_min     integer;
    v_min_bi  integer;
    v_min_tri integer;
    v_mot     integer;
    v_n       integer;
BEGIN
    -- Memes gardes que vocabulaire_recalculer.
    IF p_tenant IS NULL OR p_source IS NULL OR p_source = '' THEN
        RETURN 0;
    END IF;
    IF v_courant IS NULL THEN
        IF session_user = 'blueseatra_app'
           OR current_setting('role', true) = 'blueseatra_app' THEN
            RAISE EXCEPTION 'vocabulaire_recalculer_lourd : tenant courant requis';
        END IF;
    ELSIF p_tenant <> v_courant THEN
        RAISE EXCEPTION 'vocabulaire_recalculer_lourd : tenant % different du tenant courant', p_tenant;
    END IF;
    IF p_source LIKE 'hist:%' THEN
        RETURN blueseatra.vocabulaire_recalculer(p_tenant, p_source);
    END IF;

    SELECT count(*) INTO v_total
      FROM blueseatra.supplier_offers o
     WHERE o.tenant_id = p_tenant AND o.version_id = p_source;
    v_min     := CASE WHEN v_total > 20000 THEN 2  ELSE 1 END;
    v_min_bi  := CASE WHEN v_total > 20000 THEN 5  ELSE 2 END;
    v_min_tri := CASE WHEN v_total > 20000 THEN 3  ELSE 2 END;
    v_mot     := CASE WHEN v_total > 20000 THEN 5  ELSE 1 END;

    ------------------------------------------------------------------
    -- Etape 1 : les tableaux de mots, decoupes UNE fois par offre.
    ------------------------------------------------------------------
    DROP TABLE IF EXISTS pg_temp.vocab_arrs;
    CREATE TEMP TABLE vocab_arrs AS
    SELECT string_to_array(o.recherche_norm, ' ') AS arr
      FROM blueseatra.supplier_offers o
     WHERE o.tenant_id = p_tenant AND o.version_id = p_source;
    ANALYZE vocab_arrs;

    ------------------------------------------------------------------
    -- Etape 2 : mots isoles (un mot vu 2 fois dans une designation
    -- compte UNE fois : DISTINCT par offre).
    ------------------------------------------------------------------
    DROP TABLE IF EXISTS pg_temp.vocab_singles;
    CREATE TEMP TABLE vocab_singles AS
    SELECT d.mot, count(*)::integer AS nb_offres
      FROM vocab_arrs a
      CROSS JOIN LATERAL (
            SELECT DISTINCT x AS mot
              FROM unnest(a.arr) AS u(x)
             WHERE length(x) BETWEEN 2 AND 40 AND x ~ '[a-z]') d
     GROUP BY d.mot
    HAVING count(*) >= v_min;

    CREATE UNIQUE INDEX vocab_singles_mot ON vocab_singles (mot);
    ANALYZE vocab_singles;

    ------------------------------------------------------------------
    -- Etape 3 : paires de mots consecutifs, sur mots courants.
    -- Jointure contre la table TEMPORAIRE (pas la table cible).
    ------------------------------------------------------------------
    DROP TABLE IF EXISTS pg_temp.vocab_paires;
    CREATE TEMP TABLE vocab_paires AS
    SELECT p.w1 || ' ' || p.w2 AS mot, count(*)::integer AS nb_offres
      FROM (SELECT a.arr[g.i] AS w1, a.arr[g.i + 1] AS w2
              FROM vocab_arrs a
              CROSS JOIN LATERAL generate_series(1, cardinality(a.arr) - 1) g(i)
              JOIN vocab_singles s1 ON s1.mot = a.arr[g.i]      AND s1.nb_offres >= v_mot
              JOIN vocab_singles s2 ON s2.mot = a.arr[g.i + 1]  AND s2.nb_offres >= v_mot
             WHERE length(a.arr[g.i]) BETWEEN 2 AND 40 AND a.arr[g.i] ~ '[a-z]'
               AND length(a.arr[g.i + 1]) BETWEEN 2 AND 40 AND a.arr[g.i + 1] ~ '[a-z]') p
     GROUP BY p.w1, p.w2
    HAVING count(*) >= v_min_bi;
    ANALYZE vocab_paires;

    ------------------------------------------------------------------
    -- Etape 4 : triples de mots consecutifs, sur mots courants.
    ------------------------------------------------------------------
    DROP TABLE IF EXISTS pg_temp.vocab_triples;
    CREATE TEMP TABLE vocab_triples AS
    SELECT p.w1 || ' ' || p.w2 || ' ' || p.w3 AS mot, count(*)::integer AS nb_offres
      FROM (SELECT a.arr[g.i] AS w1, a.arr[g.i + 1] AS w2, a.arr[g.i + 2] AS w3
              FROM vocab_arrs a
              CROSS JOIN LATERAL generate_series(1, cardinality(a.arr) - 2) g(i)
              JOIN vocab_singles s1 ON s1.mot = a.arr[g.i]      AND s1.nb_offres >= v_mot
              JOIN vocab_singles s2 ON s2.mot = a.arr[g.i + 1]  AND s2.nb_offres >= v_mot
              JOIN vocab_singles s3 ON s3.mot = a.arr[g.i + 2] AND s3.nb_offres >= v_mot
             WHERE length(a.arr[g.i]) BETWEEN 2 AND 40 AND a.arr[g.i] ~ '[a-z]'
               AND length(a.arr[g.i + 1]) BETWEEN 2 AND 40 AND a.arr[g.i + 1] ~ '[a-z]'
               AND length(a.arr[g.i + 2]) BETWEEN 2 AND 40 AND a.arr[g.i + 2] ~ '[a-z]') p
     GROUP BY p.w1, p.w2, p.w3
    HAVING count(*) >= v_min_tri;
    ANALYZE vocab_triples;

    ------------------------------------------------------------------
    -- Etape 5 : remplacement, en une seule ecriture.
    ------------------------------------------------------------------
    DELETE FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source;

    INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
    SELECT p_tenant, p_source, mot, nb_offres FROM vocab_singles
    UNION ALL
    SELECT p_tenant, p_source, mot, nb_offres FROM vocab_paires
    UNION ALL
    SELECT p_tenant, p_source, mot, nb_offres FROM vocab_triples;

    DROP TABLE IF EXISTS pg_temp.vocab_arrs, pg_temp.vocab_singles,
                        pg_temp.vocab_paires, pg_temp.vocab_triples;

    SELECT count(*) INTO v_n
      FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source;
    RETURN v_n;
END
$function$;

REVOKE ALL ON FUNCTION blueseatra.vocabulaire_recalculer_lourd(varchar, varchar) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.vocabulaire_recalculer_lourd(varchar, varchar) TO blueseatra_app;

-- L'ancienne signature a 3 arguments (20261002070000) est retiree.
DROP FUNCTION IF EXISTS blueseatra.vocabulaire_recalculer_lourd(varchar, varchar, integer);
