-- Recalcul du vocabulaire pour les TRES gros catalogues : par lots (02/10/2026).
--
-- CONSTAT : sur le catalogue Rexel (747 000 offres), la version
-- 20261002060000 agrégeait ~7,5 millions de paires et de triples d'un coup.
-- Deux murs ont été mesurés en production :
--   1. l'agrégat déborde de work_mem (600 Mo et plus) : la passe a tourné
--      plus de 75 minutes sans finir ;
--   2. le planificateur APALAT la sous-requête lateral
--      (string_to_array(...) AS arr) et recalcule la découpe de la
--      désignation à CHAQUE référence — six découpes par paire, des
--      millions de fois (constaté par EXPLAIN : Group Key sur
--      string_to_array(lot.recherche_norm), et non sur arr).
--
-- MÉTHODE :
--   - la découpe de la désignation est faite UNE fois par offre, dans une
--     CTE MATERIALIZED (jamais aplatissable) ;
--   - la source est découpée par plages d'identifiants (bornes
--     précalculées en un seul balayage ; chaque lot est ensuite lu par
--     tranche de clé primaire) ;
--   - chaque lot agrège peu de lignes, tient dans work_mem, et ACCUMULE ses
--     comptes par upsert : ON CONFLICT ... nb_offres = nb_offres + EXCLUDED ;
--   - les seuils (mots rares, groupes peu fréquents) sont appliqués en
--     nettoyage une fois chaque passe terminée.
--
-- Le résultat est identique à vocabulaire_recalculer : mêmes lignes, mêmes
-- comptes. Vérifié par test de substitution sur la base jetable avec des
-- lots de 2 lignes (nombreuses tranches) et comparaison exacte avec la
-- fonction de référence.
--
-- Les sources 'hist:' sont déléguées à vocabulaire_recalculer : elles sont
-- historiquement petites, le chemin versionné suffit ici.

CREATE OR REPLACE FUNCTION blueseatra.vocabulaire_recalculer_lourd(
    p_tenant varchar, p_source varchar, p_taille integer DEFAULT 75000)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
    v_courant text := blueseatra.current_tenant();
    v_taille  integer := least(greatest(coalesce(p_taille, 75000), 100), 200000);
    v_bornes  varchar[];
    v_bas     varchar;
    v_haut    varchar;
    v_i       integer;
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

    DELETE FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source;

    -- Bornes : un identifiant tous les v_taille offres, en un seul balayage.
    SELECT coalesce(array_agg(id ORDER BY id), '{}') INTO v_bornes
      FROM (SELECT o.id, row_number() OVER (ORDER BY o.id) AS rn
              FROM blueseatra.supplier_offers o
             WHERE o.tenant_id = p_tenant AND o.version_id = p_source) t
     WHERE rn % v_taille = 0;

    ------------------------------------------------------------------
    -- Passe 1 : mots isoles, accumules par upsert.
    ------------------------------------------------------------------
    v_bas := '';
    FOR v_i IN 1 .. coalesce(array_length(v_bornes, 1), 0) LOOP
        v_haut := v_bornes[v_i];
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.mot, count(*)::integer
          FROM (SELECT lot.recherche_norm
                  FROM blueseatra.supplier_offers lot
                 WHERE lot.tenant_id = p_tenant AND lot.version_id = p_source
                   AND lot.id > v_bas AND lot.id <= v_haut) o
          CROSS JOIN LATERAL (
                SELECT DISTINCT x AS mot
                  FROM unnest(string_to_array(o.recherche_norm, ' ')) AS u(x)
                 WHERE length(x) BETWEEN 2 AND 40 AND x ~ '[a-z]') m
         GROUP BY m.mot
        ON CONFLICT (tenant_id, source, mot)
          DO UPDATE SET nb_offres = blueseatra.vocabulaire_recherche.nb_offres
                        + EXCLUDED.nb_offres;
        v_bas := v_haut;
    END LOOP;
    -- Derniere tranche (jusqu'au bout de la source).
    INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
    SELECT p_tenant, p_source, m.mot, count(*)::integer
      FROM (SELECT lot.recherche_norm
              FROM blueseatra.supplier_offers lot
             WHERE lot.tenant_id = p_tenant AND lot.version_id = p_source
               AND lot.id > v_bas) o
      CROSS JOIN LATERAL (
            SELECT DISTINCT x AS mot
              FROM unnest(string_to_array(o.recherche_norm, ' ')) AS u(x)
             WHERE length(x) BETWEEN 2 AND 40 AND x ~ '[a-z]') m
     GROUP BY m.mot
    ON CONFLICT (tenant_id, source, mot)
      DO UPDATE SET nb_offres = blueseatra.vocabulaire_recherche.nb_offres
                    + EXCLUDED.nb_offres;

    DELETE FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source
       AND mot !~ ' ' AND nb_offres < v_min;

    ------------------------------------------------------------------
    -- Passe 2 : groupes de 2 mots consecutifs courants.
    -- La decoupe est faite UNE fois par offre (CTE MATERIALIZED) : le
    -- planificateur ne peut pas aplatir la CTE et recycler la decoupe.
    ------------------------------------------------------------------
    v_bas := '';
    FOR v_i IN 1 .. coalesce(array_length(v_bornes, 1), 0) LOOP
        v_haut := v_bornes[v_i];
        WITH arrs AS MATERIALIZED (
          SELECT string_to_array(lot.recherche_norm, ' ') AS arr
            FROM blueseatra.supplier_offers lot
           WHERE lot.tenant_id = p_tenant AND lot.version_id = p_source
             AND lot.id > v_bas AND lot.id <= v_haut)
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, a.arr[g.i] || ' ' || a.arr[g.i + 1], count(*)::integer
          FROM arrs a
          CROSS JOIN LATERAL generate_series(1, cardinality(a.arr) - 1) g(i)
          JOIN blueseatra.vocabulaire_recherche c1
            ON c1.tenant_id = p_tenant AND c1.source = p_source
           AND c1.mot = a.arr[g.i] AND c1.nb_offres >= v_mot AND c1.mot !~ ' '
          JOIN blueseatra.vocabulaire_recherche c2
            ON c2.tenant_id = p_tenant AND c2.source = p_source
           AND c2.mot = a.arr[g.i + 1] AND c2.nb_offres >= v_mot AND c2.mot !~ ' '
         WHERE length(a.arr[g.i]) BETWEEN 2 AND 40 AND a.arr[g.i] ~ '[a-z]'
           AND length(a.arr[g.i + 1]) BETWEEN 2 AND 40 AND a.arr[g.i + 1] ~ '[a-z]'
         GROUP BY a.arr[g.i], a.arr[g.i + 1]
        ON CONFLICT (tenant_id, source, mot)
          DO UPDATE SET nb_offres = blueseatra.vocabulaire_recherche.nb_offres
                        + EXCLUDED.nb_offres;
        v_bas := v_haut;
    END LOOP;
    WITH arrs AS MATERIALIZED (
      SELECT string_to_array(lot.recherche_norm, ' ') AS arr
        FROM blueseatra.supplier_offers lot
       WHERE lot.tenant_id = p_tenant AND lot.version_id = p_source
         AND lot.id > v_bas)
    INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
    SELECT p_tenant, p_source, a.arr[g.i] || ' ' || a.arr[g.i + 1], count(*)::integer
      FROM arrs a
      CROSS JOIN LATERAL generate_series(1, cardinality(a.arr) - 1) g(i)
      JOIN blueseatra.vocabulaire_recherche c1
        ON c1.tenant_id = p_tenant AND c1.source = p_source
       AND c1.mot = a.arr[g.i] AND c1.nb_offres >= v_mot AND c1.mot !~ ' '
      JOIN blueseatra.vocabulaire_recherche c2
        ON c2.tenant_id = p_tenant AND c2.source = p_source
       AND c2.mot = a.arr[g.i + 1] AND c2.nb_offres >= v_mot AND c2.mot !~ ' '
     WHERE length(a.arr[g.i]) BETWEEN 2 AND 40 AND a.arr[g.i] ~ '[a-z]'
       AND length(a.arr[g.i + 1]) BETWEEN 2 AND 40 AND a.arr[g.i + 1] ~ '[a-z]'
     GROUP BY a.arr[g.i], a.arr[g.i + 1]
    ON CONFLICT (tenant_id, source, mot)
      DO UPDATE SET nb_offres = blueseatra.vocabulaire_recherche.nb_offres
                    + EXCLUDED.nb_offres;

    DELETE FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source
       AND mot ~ ' '
       AND array_length(string_to_array(mot, ' '), 1) = 2
       AND nb_offres < v_min_bi;

    ------------------------------------------------------------------
    -- Passe 3 : groupes de 3 mots consecutifs courants.
    ------------------------------------------------------------------
    v_bas := '';
    FOR v_i IN 1 .. coalesce(array_length(v_bornes, 1), 0) LOOP
        v_haut := v_bornes[v_i];
        WITH arrs AS MATERIALIZED (
          SELECT string_to_array(lot.recherche_norm, ' ') AS arr
            FROM blueseatra.supplier_offers lot
           WHERE lot.tenant_id = p_tenant AND lot.version_id = p_source
             AND lot.id > v_bas AND lot.id <= v_haut)
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source,
               a.arr[g.i] || ' ' || a.arr[g.i + 1] || ' ' || a.arr[g.i + 2],
               count(*)::integer
          FROM arrs a
          CROSS JOIN LATERAL generate_series(1, cardinality(a.arr) - 2) g(i)
          JOIN blueseatra.vocabulaire_recherche c1
            ON c1.tenant_id = p_tenant AND c1.source = p_source
           AND c1.mot = a.arr[g.i] AND c1.nb_offres >= v_mot AND c1.mot !~ ' '
          JOIN blueseatra.vocabulaire_recherche c2
            ON c2.tenant_id = p_tenant AND c2.source = p_source
           AND c2.mot = a.arr[g.i + 1] AND c2.nb_offres >= v_mot AND c2.mot !~ ' '
          JOIN blueseatra.vocabulaire_recherche c3
            ON c3.tenant_id = p_tenant AND c3.source = p_source
           AND c3.mot = a.arr[g.i + 2] AND c3.nb_offres >= v_mot AND c3.mot !~ ' '
         WHERE length(a.arr[g.i]) BETWEEN 2 AND 40 AND a.arr[g.i] ~ '[a-z]'
           AND length(a.arr[g.i + 1]) BETWEEN 2 AND 40 AND a.arr[g.i + 1] ~ '[a-z]'
           AND length(a.arr[g.i + 2]) BETWEEN 2 AND 40 AND a.arr[g.i + 2] ~ '[a-z]'
         GROUP BY a.arr[g.i], a.arr[g.i + 1], a.arr[g.i + 2]
        ON CONFLICT (tenant_id, source, mot)
          DO UPDATE SET nb_offres = blueseatra.vocabulaire_recherche.nb_offres
                        + EXCLUDED.nb_offres;
        v_bas := v_haut;
    END LOOP;
    WITH arrs AS MATERIALIZED (
      SELECT string_to_array(lot.recherche_norm, ' ') AS arr
        FROM blueseatra.supplier_offers lot
       WHERE lot.tenant_id = p_tenant AND lot.version_id = p_source
         AND lot.id > v_bas)
    INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
    SELECT p_tenant, p_source,
           a.arr[g.i] || ' ' || a.arr[g.i + 1] || ' ' || a.arr[g.i + 2],
           count(*)::integer
      FROM arrs a
      CROSS JOIN LATERAL generate_series(1, cardinality(a.arr) - 2) g(i)
      JOIN blueseatra.vocabulaire_recherche c1
        ON c1.tenant_id = p_tenant AND c1.source = p_source
       AND c1.mot = a.arr[g.i] AND c1.nb_offres >= v_mot AND c1.mot !~ ' '
      JOIN blueseatra.vocabulaire_recherche c2
        ON c2.tenant_id = p_tenant AND c2.source = p_source
       AND c2.mot = a.arr[g.i + 1] AND c2.nb_offres >= v_mot AND c2.mot !~ ' '
      JOIN blueseatra.vocabulaire_recherche c3
        ON c3.tenant_id = p_tenant AND c3.source = p_source
       AND c3.mot = a.arr[g.i + 2] AND c3.nb_offres >= v_mot AND c3.mot !~ ' '
     WHERE length(a.arr[g.i]) BETWEEN 2 AND 40 AND a.arr[g.i] ~ '[a-z]'
       AND length(a.arr[g.i + 1]) BETWEEN 2 AND 40 AND a.arr[g.i + 1] ~ '[a-z]'
       AND length(a.arr[g.i + 2]) BETWEEN 2 AND 40 AND a.arr[g.i + 2] ~ '[a-z]'
     GROUP BY a.arr[g.i], a.arr[g.i + 1], a.arr[g.i + 2]
    ON CONFLICT (tenant_id, source, mot)
      DO UPDATE SET nb_offres = blueseatra.vocabulaire_recherche.nb_offres
                    + EXCLUDED.nb_offres;

    DELETE FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source
       AND mot ~ ' '
       AND array_length(string_to_array(mot, ' '), 1) = 3
       AND nb_offres < v_min_tri;

    SELECT count(*) INTO v_n
      FROM blueseatra.vocabulaire_recherche
     WHERE tenant_id = p_tenant AND source = p_source;
    RETURN v_n;
END
$function$;

REVOKE ALL ON FUNCTION blueseatra.vocabulaire_recalculer_lourd(varchar, varchar, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.vocabulaire_recalculer_lourd(varchar, varchar, integer) TO blueseatra_app;
