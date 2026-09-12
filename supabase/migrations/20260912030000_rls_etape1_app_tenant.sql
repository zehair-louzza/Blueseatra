-- ============================================================================
-- Durcissement RLS -- ETAPE 1 / 3
-- current_tenant() accepte un reglage de session en repli
--
-- PROBLEME (audit du 12/09/2026)
-- -----------------------------
-- RLS est activee sur les 14 tables de `blueseatra` avec des politiques
-- correctement cloisonnees :
--
--     (tenant_id)::text = blueseatra.current_tenant()
--
-- Mais la fonction ne lit que `request.jwt.claims`, renseigne par PostgREST
-- (l'API REST auto-generee de Supabase). Sur la connexion asyncpg DIRECTE du
-- backend -- le seul chemin reellement utilise en production -- ce reglage
-- n'existe pas et la fonction renvoie NULL. Aucune politique ne peut donc
-- jamais correspondre.
--
-- RLS n'est pas une seconde ligne de defense : c'est une ligne de defense
-- INACTIVE sur le chemin qui compte.
--
-- CE QUE FAIT CETTE MIGRATION
-- ---------------------------
-- Ajoute `app.tenant_id` comme source de repli. Le backend l'emet desormais
-- par transaction via set_config('app.tenant_id', ..., true)
-- (voir backend/database.py, tenant_session()).
--
-- ORDRE DES ETAPES -- A RESPECTER IMPERATIVEMENT
-- ----------------------------------------------
--   ETAPE 1 (ce fichier)  : current_tenant() accepte app.tenant_id
--   ETAPE 2 (code, PR)    : le backend emet la valeur a chaque transaction
--   ETAPE 3 (a venir)     : role non-proprietaire + FORCE ROW LEVEL SECURITY
--
-- Appliquer l'etape 3 avant 1 et 2 COUPE LA PRODUCTION : les politiques
-- deviendraient actives alors que current_tenant() vaut encore NULL, donc
-- toutes les requetes metier renverraient zero ligne.
--
-- RISQUE DE CETTE MIGRATION : QUASI NUL
-- -------------------------------------
-- Le changement est purement ADDITIF (coalesce). L'ancien comportement
-- (lecture de request.jwt.claims) reste prioritaire et inchange. Et comme le
-- role du backend contourne encore RLS (relforcerowsecurity = false), aucune
-- politique ne s'applique de toute facon aujourd'hui sur ce chemin.
--
-- Reversible par la definition d'origine, conservee en commentaire en fin de
-- fichier.
-- ============================================================================

CREATE OR REPLACE FUNCTION blueseatra.current_tenant()
RETURNS text
LANGUAGE sql
STABLE
-- search_path vide : la fonction ne doit dependre d'aucun schema resolu
-- dynamiquement. Protection classique contre le detournement de fonction
-- par un schema place en tete du search_path de l'appelant.
SET search_path TO ''
AS $function$
  SELECT coalesce(
    -- 1. Chemin PostgREST / API REST Supabase (comportement d'origine,
    --    conserve en priorite pour ne rien casser).
    NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', ''),
    -- 2. Chemin backend : connexion asyncpg directe. Emis par transaction
    --    avec set_config(..., is_local => true).
    NULLIF(current_setting('app.tenant_id', true), '')
  )
$function$;

COMMENT ON FUNCTION blueseatra.current_tenant() IS
  'Tenant de la session courante, pour les politiques RLS. Deux sources, '
  'dans l''ordre : request.jwt.claims->>tenant_id (PostgREST) puis '
  'app.tenant_id (backend, via set_config is_local => true, par '
  'transaction). Etape 1/3 du durcissement RLS du 12/09/2026. Ne JAMAIS '
  'utiliser un SET global pour app.tenant_id : avec un pool de connexions, '
  'le tenant fuirait d''une requete vers la suivante.';


-- ============================================================================
-- Verification post-migration
-- ============================================================================
-- Hors de toute transaction applicative, les deux reglages sont absents et la
-- fonction doit renvoyer NULL. Avec un app.tenant_id local, elle doit le
-- renvoyer -- et l'oublier au commit.
--
--   SELECT blueseatra.current_tenant() IS NULL;      -- attendu : true
--
--   BEGIN;
--     SELECT set_config('app.tenant_id', 'test-123', true);
--     SELECT blueseatra.current_tenant();             -- attendu : test-123
--   ROLLBACK;
--
--   SELECT blueseatra.current_tenant() IS NULL;      -- attendu : true
--                                                    -- (portee transaction)
-- ============================================================================


-- ============================================================================
-- RETOUR ARRIERE
-- ============================================================================
-- CREATE OR REPLACE FUNCTION blueseatra.current_tenant()
-- RETURNS text LANGUAGE sql STABLE SET search_path TO '' AS $$
--   SELECT NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', '')
-- $$;
-- ============================================================================
