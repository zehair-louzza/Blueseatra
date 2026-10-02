-- Vocabulaire de recherche : les mots qui existent vraiment dans les catalogues.
--
-- POURQUOI (02/10/2026)
-- La recherche d'articles partait a chaque pause de frappe sur 970 000
-- offres : ~35 ms d'index trigramme par source et par mot long (9 sources,
-- « disjoncteur » ~530 ms). Pendant la frappe, l'utilisateur n'a besoin que
-- de savoir QUELS MOTS existent : « disj » -> disjoncteur (27 637 offres).
-- Cette table repond en quelques millisecondes ; la recherche lourde ne part
-- plus que sur un mot complet choisi.
--
-- CONTENU
-- Une ligne par (entreprise, source, mot) : nombre d'offres de la source qui
-- contiennent le mot. La source est la cle de version (version_id), ou
-- 'hist:<supplier_id>' pour les offres sans catalogue versionne -- les memes
-- cles que catalogue_chiffrage / catalogue_navigation, pour filtrer sur les
-- sources actives ou visibles de l'entreprise.
--
-- CLOISONNEMENT
-- Les mots d'un catalogue prive sont des donnees de l'entreprise (references,
-- marques negociees) : jamais proposes a une autre. La lecture passe par
-- vocabulaire_suggestions(), qui refuse tout tenant autre que l'entreprise
-- courante ou le catalogue commun (meme regle que offres_candidates). RLS
-- activee en defense supplementaire.
--
-- MISE A JOUR
-- vocabulaire_recalculer(tenant, source) apres chaque import (script
-- import_catalogue_lourd.py). Une version importee ne change plus ensuite.

CREATE TABLE IF NOT EXISTS blueseatra.vocabulaire_recherche (
    tenant_id  varchar NOT NULL,
    source     varchar NOT NULL,
    mot        text COLLATE "C" NOT NULL,
    nb_offres  integer NOT NULL,
    PRIMARY KEY (tenant_id, source, mot)
);

-- Recherche par prefixe : intervalle [prefixe, prefixe || '~') en collation C.
-- Les mots ne contiennent que [a-z0-9.+] (normalise_recherche), tous < '~'.
CREATE INDEX IF NOT EXISTS idx_vocabulaire_mot
    ON blueseatra.vocabulaire_recherche (mot, tenant_id, source) INCLUDE (nb_offres);

ALTER TABLE blueseatra.vocabulaire_recherche ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS vocabulaire_tenant ON blueseatra.vocabulaire_recherche;
CREATE POLICY vocabulaire_tenant ON blueseatra.vocabulaire_recherche FOR SELECT TO blueseatra_app
    USING (tenant_id = blueseatra.current_tenant());
DROP POLICY IF EXISTS vocabulaire_commun ON blueseatra.vocabulaire_recherche;
CREATE POLICY vocabulaire_commun ON blueseatra.vocabulaire_recherche FOR SELECT TO blueseatra_app
    USING (tenant_id = blueseatra.tenant_catalogue_commun());
-- Ecriture uniquement par vocabulaire_recalculer() (SECURITY DEFINER).
GRANT SELECT ON blueseatra.vocabulaire_recherche TO blueseatra_app;


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
    v_min := CASE WHEN v_total > 20000 THEN 2 ELSE 1 END;

    -- Deux requetes distinctes plutot qu'un CASE dans le WHERE : un CASE
    -- empeche l'index (tenant_id, version_id) et ferait lire toutes les
    -- offres du tenant (970 000 pour le catalogue commun) a chaque source.
    IF v_hist IS NULL THEN
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
    ELSE
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
    IF p_prefixe IS NULL OR length(p_prefixe) NOT BETWEEN 2 AND 40
       OR p_prefixe !~ '^[a-z0-9.+]+$' THEN
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

COMMENT ON TABLE blueseatra.vocabulaire_recherche IS
  'Mots presents dans les offres, par entreprise et par source (version ou hist:fournisseur). '
  'Alimente par vocabulaire_recalculer() ; lu par vocabulaire_suggestions().';

-- Le remplissage des catalogues existants se fait HORS migration, source par
-- source (le catalogue commun compte 970 000 offres) :
--   SELECT blueseatra.vocabulaire_recalculer(tenant_id, version_id)
--     FROM (SELECT DISTINCT tenant_id, version_id FROM blueseatra.supplier_offers
--            WHERE version_id IS NOT NULL) s;
