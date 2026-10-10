-- Composition de mots dans la recherche (02/10/2026).
--
-- CONSTAT UTILISATEUR : chercher « porte-coupe-feu » en tapant les mots un
-- par un n'affinait pas visiblement le resultat, et les suggestions ne
-- proposaient que des mots isoles. Un chiffreur pense « porte coupe feu »,
-- « courbe c », « bloc porte » : en GROUPES de mots.
--
-- CE QUE CHANGE CETTE MIGRATION
-- 1. vocabulaire_recalculer : en plus des mots isoles, la table enregistre
--    les groupes de 2 et 3 mots CONSECUTIFS frequents, construits uniquement
--    sur des mots deja retenus comme mots courants (>= 5 offres) : pas de
--    groupes de references ou de coquilles. Un groupe est stocke avec un
--    espace : 'porte coupe feu'.
-- 2. vocabulaire_suggestions : le prefixe accepte desormais plusieurs mots
--    (avec ou sans espace final), ce qui permet de proposer les groupes qui
--    CONTINUENT ce qui est tape : « porte c » -> « porte coupe feu ».
--
-- Le remplissage existant doit etre refait apres cette migration :
--   SELECT blueseatra.vocabulaire_recalculer(tenant_id, version_id) ...

CREATE OR REPLACE FUNCTION blueseatra.vocabulaire_recalculer(p_tenant varchar, p_source varchar)
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
    v_hist    text;
BEGIN
    -- Appelant autorise : l'entreprise courante pour ses propres sources.
    -- Sans tenant courant, seul un role d'administration (connecteur,
    -- migration) peut recalculer -- jamais le role applicatif.
    IF p_tenant IS NULL OR p_source IS NULL OR p_source = '' THEN
        RETURN 0;
    END IF;
    IF v_courant IS NULL THEN
        -- session_user : connexion directe du role ; 'role' : SET ROLE
        -- (session_user reste alors celui de la connexion).
        IF session_user = 'blueseatra_app'
           OR current_setting('role', true) = 'blueseatra_app' THEN
            RAISE EXCEPTION 'vocabulaire_recalculer : tenant courant requis';
        END IF;
    ELSIF p_tenant <> v_courant THEN
        RAISE EXCEPTION 'vocabulaire_recalculer : tenant % different du tenant courant', p_tenant;
    END IF;

    DELETE FROM blueseatra.vocabulaire_recherche WHERE tenant_id = p_tenant AND source = p_source;

    v_hist := CASE WHEN p_source LIKE 'hist:%' THEN substr(p_source, 6) END;

    IF v_hist IS NULL THEN
        SELECT count(*) INTO v_total FROM blueseatra.supplier_offers o
         WHERE o.tenant_id = p_tenant AND o.version_id = p_source;
    ELSE
        SELECT count(*) INTO v_total FROM blueseatra.supplier_offers o
         WHERE o.tenant_id = p_tenant AND o.supplier_id = v_hist
           AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = p_tenant));
    END IF;
    -- Gros catalogues : un mot vu une seule fois est presque toujours une
    -- reference ou une coquille ; il resterait trouvable par la recherche.
    v_min     := CASE WHEN v_total > 20000 THEN 2  ELSE 1 END;
    v_min_bi  := CASE WHEN v_total > 20000 THEN 5  ELSE 2 END;
    v_min_tri := CASE WHEN v_total > 20000 THEN 3  ELSE 2 END;
    -- Un groupe n'est construit que sur des mots deja retenus comme mots
    -- courants ; dans une petite source, tout mot retenu vaut.
    v_mot     := CASE WHEN v_total > 20000 THEN 5  ELSE 1 END;

    -- Deux requetes distinctes plutot qu'un CASE dans le WHERE : un CASE
    -- empeche l'index (tenant_id, version_id) et ferait lire toutes les
    -- offres du tenant (970 000 pour le catalogue commun) a chaque source.
    IF v_hist IS NULL THEN
        -- Mots isoles
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.mot, count(*)::integer
          FROM blueseatra.supplier_offers o
          CROSS JOIN LATERAL (
                SELECT DISTINCT x AS mot
                  FROM unnest(string_to_array(o.recherche_norm, ' ')) AS u(x)
                 WHERE length(x) BETWEEN 2 AND 40 AND x ~ '[a-z]') m
         WHERE o.tenant_id = p_tenant AND o.version_id = p_source
         GROUP BY m.mot
        HAVING count(*) >= v_min;

        -- Groupes de 2 mots consecutifs, sur des mots courants seulement
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.gram, count(*)::integer
          FROM blueseatra.supplier_offers o
          CROSS JOIN LATERAL (
                SELECT w.arr[g.i] || ' ' || w.arr[g.i + 1] AS gram
                  FROM (SELECT string_to_array(o.recherche_norm, ' ') AS arr) w
                  CROSS JOIN generate_series(1, cardinality(w.arr) - 1) AS g(i)
                 WHERE length(w.arr[g.i]) BETWEEN 2 AND 40 AND w.arr[g.i] ~ '[a-z]'
                   AND length(w.arr[g.i + 1]) BETWEEN 2 AND 40 AND w.arr[g.i + 1] ~ '[a-z]') m
         WHERE o.tenant_id = p_tenant AND o.version_id = p_source
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 1) AND v.nb_offres >= v_mot)
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 2) AND v.nb_offres >= v_mot)
         GROUP BY m.gram
        HAVING count(*) >= v_min_bi;

        -- Groupes de 3 mots consecutifs, sur des mots courants seulement
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.gram, count(*)::integer
          FROM blueseatra.supplier_offers o
          CROSS JOIN LATERAL (
                SELECT w.arr[g.i] || ' ' || w.arr[g.i + 1] || ' ' || w.arr[g.i + 2] AS gram
                  FROM (SELECT string_to_array(o.recherche_norm, ' ') AS arr) w
                  CROSS JOIN generate_series(1, cardinality(w.arr) - 2) AS g(i)
                 WHERE length(w.arr[g.i]) BETWEEN 2 AND 40 AND w.arr[g.i] ~ '[a-z]'
                   AND length(w.arr[g.i + 1]) BETWEEN 2 AND 40 AND w.arr[g.i + 1] ~ '[a-z]'
                   AND length(w.arr[g.i + 2]) BETWEEN 2 AND 40 AND w.arr[g.i + 2] ~ '[a-z]') m
         WHERE o.tenant_id = p_tenant AND o.version_id = p_source
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 1) AND v.nb_offres >= v_mot)
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 2) AND v.nb_offres >= v_mot)
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 3) AND v.nb_offres >= v_mot)
         GROUP BY m.gram
        HAVING count(*) >= v_min_tri;
    ELSE
        -- Mots isoles (fournisseur sans catalogue versionne)
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.mot, count(*)::integer
          FROM blueseatra.supplier_offers o
          CROSS JOIN LATERAL (
                SELECT DISTINCT x AS mot
                  FROM unnest(string_to_array(o.recherche_norm, ' ')) AS u(x)
                 WHERE length(x) BETWEEN 2 AND 40 AND x ~ '[a-z]') m
         WHERE o.tenant_id = p_tenant AND o.supplier_id = v_hist
           AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = p_tenant))
         GROUP BY m.mot
        HAVING count(*) >= v_min;

        -- Groupes de 2 mots
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.gram, count(*)::integer
          FROM blueseatra.supplier_offers o
          CROSS JOIN LATERAL (
                SELECT w.arr[g.i] || ' ' || w.arr[g.i + 1] AS gram
                  FROM (SELECT string_to_array(o.recherche_norm, ' ') AS arr) w
                  CROSS JOIN generate_series(1, cardinality(w.arr) - 1) AS g(i)
                 WHERE length(w.arr[g.i]) BETWEEN 2 AND 40 AND w.arr[g.i] ~ '[a-z]'
                   AND length(w.arr[g.i + 1]) BETWEEN 2 AND 40 AND w.arr[g.i + 1] ~ '[a-z]') m
         WHERE o.tenant_id = p_tenant AND o.supplier_id = v_hist
           AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = p_tenant))
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 1) AND v.nb_offres >= v_mot)
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 2) AND v.nb_offres >= v_mot)
         GROUP BY m.gram
        HAVING count(*) >= v_min_bi;

        -- Groupes de 3 mots
        INSERT INTO blueseatra.vocabulaire_recherche (tenant_id, source, mot, nb_offres)
        SELECT p_tenant, p_source, m.gram, count(*)::integer
          FROM blueseatra.supplier_offers o
          CROSS JOIN LATERAL (
                SELECT w.arr[g.i] || ' ' || w.arr[g.i + 1] || ' ' || w.arr[g.i + 2] AS gram
                  FROM (SELECT string_to_array(o.recherche_norm, ' ') AS arr) w
                  CROSS JOIN generate_series(1, cardinality(w.arr) - 2) AS g(i)
                 WHERE length(w.arr[g.i]) BETWEEN 2 AND 40 AND w.arr[g.i] ~ '[a-z]'
                   AND length(w.arr[g.i + 1]) BETWEEN 2 AND 40 AND w.arr[g.i + 1] ~ '[a-z]'
                   AND length(w.arr[g.i + 2]) BETWEEN 2 AND 40 AND w.arr[g.i + 2] ~ '[a-z]') m
         WHERE o.tenant_id = p_tenant AND o.supplier_id = v_hist
           AND (o.catalog_id IS NULL OR o.catalog_id NOT IN (
                SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id = p_tenant))
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 1) AND v.nb_offres >= v_mot)
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 2) AND v.nb_offres >= v_mot)
           AND EXISTS (SELECT 1 FROM blueseatra.vocabulaire_recherche v
                       WHERE v.tenant_id = p_tenant AND v.source = p_source
                         AND v.mot = split_part(m.gram, ' ', 3) AND v.nb_offres >= v_mot)
         GROUP BY m.gram
        HAVING count(*) >= v_min_tri;
    END IF;
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN v_n;
END
$function$;


CREATE OR REPLACE FUNCTION blueseatra.vocabulaire_suggestions(
    p_tenants text[], p_sources text[], p_prefixe text, p_limite integer DEFAULT 8)
RETURNS TABLE(mot text, nb_offres bigint)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
    v_courant text := blueseatra.current_tenant();
    v_commun  text := blueseatra.tenant_catalogue_commun();
BEGIN
    -- Prefixe d'un a trois mots, espace final permis : « porte c » propose
    -- les groupes qui continuent (porte coupe feu), « porte » (espace final)
    -- propose les groupes qui commencent par porte.
    IF p_prefixe IS NULL OR length(p_prefixe) NOT BETWEEN 2 AND 80
       OR p_prefixe !~ '^[a-z0-9.+]+( [a-z0-9.+]+)* ?$' THEN
        RETURN;
    END IF;
    IF p_tenants IS NULL OR cardinality(p_tenants) NOT BETWEEN 1 AND 2
       OR p_sources IS NULL OR cardinality(p_sources) NOT BETWEEN 1 AND 200 THEN
        RETURN;
    END IF;
    -- Meme cloisonnement que offres_candidates : entreprise courante ou
    -- catalogue commun, rien d'autre.
    IF EXISTS (SELECT 1 FROM unnest(p_tenants) AS t(x)
               WHERE x IS NULL OR NOT (x = coalesce(v_courant, '') OR x = v_commun)) THEN
        RETURN;
    END IF;
    RETURN QUERY
        SELECT v.mot::text, sum(v.nb_offres)::bigint AS nb
          FROM blueseatra.vocabulaire_recherche v
         WHERE v.mot >= p_prefixe COLLATE "C"
           AND v.mot <  (p_prefixe || '~') COLLATE "C"
           AND v.tenant_id = ANY (p_tenants)
           AND v.source = ANY (p_sources)
         GROUP BY v.mot
         ORDER BY nb DESC, v.mot
         LIMIT least(greatest(coalesce(p_limite, 8), 1), 20);
END
$function$;

REVOKE ALL ON FUNCTION blueseatra.vocabulaire_recalculer(varchar, varchar) FROM PUBLIC;
REVOKE ALL ON FUNCTION blueseatra.vocabulaire_suggestions(text[], text[], text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.vocabulaire_recalculer(varchar, varchar) TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.vocabulaire_suggestions(text[], text[], text, integer) TO blueseatra_app;
