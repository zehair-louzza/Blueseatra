-- ============================================================================
-- Durcissement RLS -- ETAPE 4 / 9 du runbook
-- Creation du role applicatif blueseatra_app
--
--   /!\  CE FICHIER NE CONTIENT PAS DE MOT DE PASSE  /!\
--
-- Etape 1 (fait, 12/09)    : current_tenant() accepte app.tenant_id
-- Etape 2 (fait, PR #72)   : le backend emet app.tenant_id par transaction
-- Etape 3 (fait, PR #73)   : moteur AUTH + routage par table dans le code
-- Etape 4 (CE FICHIER)     : creer le role blueseatra_app
-- Etape 5 (runbook Render) : basculer le moteur metier sur ce role
-- Etape 6 (sans objet)     : les WITH CHECK existent deja, verifie le 12/09
-- Etape 7 (a venir)        : FORCE ROW LEVEL SECURITY, table par table
-- Etape 8 (a venir)        : sondage croise A/B en conditions reelles
-- Etape 9 (a venir)        : verifier rolbypassrls = false sur blueseatra_app
--
-- ETAT CONSTATE LE 12/09/2026 avant cette migration
-- ---------------------------------------------------
--   - blueseatra_app n'existe pas encore (verifie sur pg_roles)
--   - les 14 tables de blueseatra appartiennent toutes a `postgres`
--   - `postgres` a rolbypassrls = true
--
-- CE QUE FAIT CE FICHIER
-- -----------------------
--   1. Cree le role blueseatra_app SANS mot de passe (a definir a la main,
--      juste apres, via une commande separee -- voir la note en fin de
--      fichier).
--   2. Le rend membre de `authenticated`, pour que les politiques RLS
--      existantes (TO authenticated) s'appliquent sans devoir toutes les
--      reecrire pour un nouveau role.
--   3. Accorde les droits sur les 11 tables METIER, PAS sur users /
--      tenants / tenant_users -- ces trois restent reservees au role
--      privilegie (moteur AUTH), voir pg_adapter.TABLES_AUTH.
--   4. Applique ALTER DEFAULT PRIVILEGES pour que les futures tables du
--      module fournisseur (suppliers, canonical_products, supplier_offers)
--      recoivent automatiquement les memes droits sans migration
--      supplementaire.
--
-- CE QUE CE FICHIER NE FAIT PAS (volontairement)
-- ------------------------------------------------
--   - PAS de mot de passe : un secret ne doit jamais transiter par un
--     fichier commit ni par une conversation.
--   - PAS de FORCE ROW LEVEL SECURITY : c'est l'etape 7, apres avoir
--     verifie que blueseatra_app fonctionne correctement sans elle. Ordre
--     imperatif -- voir le runbook.
--   - PAS de changement de proprietaire des tables : blueseatra_app n'a
--     pas besoin d'etre proprietaire, seulement d'avoir les DROITS
--     d'usage. Rester non-proprietaire est en fait LE point : FORCE RLS
--     n'a d'effet que sur un role non-proprietaire.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. Le role, sans mot de passe
-- ----------------------------------------------------------------------------
-- NOBYPASSRLS explicite, meme si c'est la valeur par defaut de CREATE ROLE :
-- explicite vaut mieux qu'implicite sur exactement le point qui a rendu RLS
-- inerte jusqu'ici (le role `postgres` a rolbypassrls = true).
--
-- LOGIN : necessaire, c'est le role sous lequel le backend se connecte.
-- INHERIT : le role herite automatiquement des droits de `authenticated`
--   sans avoir a faire SET ROLE a chaque transaction -- ce qui couterait
--   un aller-retour reseau supplementaire par requete.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app') THEN
    CREATE ROLE blueseatra_app
      LOGIN
      NOSUPERUSER
      NOCREATEDB
      NOCREATEROLE
      NOBYPASSRLS
      INHERIT
      CONNECTION LIMIT -1;
  END IF;
END
$$;

COMMENT ON ROLE blueseatra_app IS
  'Role applicatif du backend Blueseatra pour le chemin METIER (etape 3-5 '
  'du durcissement RLS, 12/09/2026). NOBYPASSRLS et non proprietaire des '
  'tables : ce sont les deux conditions pour que FORCE ROW LEVEL SECURITY '
  'ait un effet reel. Les tables d''authentification (users, tenants, '
  'tenant_users) restent hors de portee de ce role -- voir '
  'pg_adapter.TABLES_AUTH cote code.';


-- ----------------------------------------------------------------------------
-- 2. Membre de `authenticated`, pour reutiliser les politiques existantes
-- ----------------------------------------------------------------------------
GRANT authenticated TO blueseatra_app;


-- ----------------------------------------------------------------------------
-- 3. Droits sur les tables METIER uniquement
-- ----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA blueseatra TO blueseatra_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON
  blueseatra.catalogs,
  blueseatra.catalog_versions,
  blueseatra.pricing_items,
  blueseatra.requests,
  blueseatra.quotes,
  blueseatra.quote_versions,
  blueseatra.import_jobs,
  blueseatra.import_errors,
  blueseatra.audit_logs,
  blueseatra.settings_integrations,
  blueseatra.company_profiles
TO blueseatra_app;

-- Necessaire pour toute colonne generee via une sequence (aucune ici a ce
-- jour -- les identifiants sont des varchar(36) generes cote application --
-- mais couvre sans risque une evolution future du schema).
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA blueseatra TO blueseatra_app;

-- Aucun GRANT sur users / tenants / tenant_users : c'est deliberement
-- absent. blueseatra_app ne doit JAMAIS pouvoir les lire, meme si un bug
-- cote code tentait de les atteindre par ce role -- la base refuserait
-- l'acces independamment du code applicatif.


-- ----------------------------------------------------------------------------
-- 4. Droits par defaut pour les futures tables (module fournisseur)
-- ----------------------------------------------------------------------------
-- Portee volontairement globale au schema : les 5 tables du module
-- fournisseur (suppliers, canonical_products, supplier_offers,
-- product_match_rules, unit_conversions -- voir
-- 20260912020000_module_fournisseur.sql) recevront automatiquement ces
-- droits sans migration supplementaire.
--
-- Ne cree AUCUN risque pour product_match_rules / unit_conversions : ces
-- deux tables sont volontairement globales et deja regies par leurs
-- propres politiques (lecture pour authenticated, ecriture pour
-- service_role seul). Les GRANT de table restent necessaires en plus des
-- politiques RLS -- RLS filtre les LIGNES, GRANT autorise les OPERATIONS ;
-- les deux sont independants et l'un ne remplace jamais l'autre.
ALTER DEFAULT PRIVILEGES IN SCHEMA blueseatra
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO blueseatra_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA blueseatra
  GRANT USAGE, SELECT ON SEQUENCES TO blueseatra_app;


-- ============================================================================
-- VERIFICATION POST-MIGRATION -- a executer et LIRE le resultat
-- ============================================================================
SELECT
  rolname,
  rolcanlogin  AS peut_se_connecter,
  rolbypassrls AS contourne_rls,          -- DOIT etre false
  rolsuper     AS est_superuser           -- DOIT etre false
FROM pg_roles
WHERE rolname = 'blueseatra_app';

-- Doit renvoyer exactement 11 lignes (les tables metier), 0 pour
-- users/tenants/tenant_users.
SELECT count(*) AS tables_accessibles
FROM information_schema.table_privileges
WHERE grantee = 'blueseatra_app'
  AND table_schema = 'blueseatra'
  AND privilege_type = 'SELECT';

-- Doit renvoyer 0 ligne : confirmation que users/tenants/tenant_users sont
-- hors de portee.
SELECT table_name
FROM information_schema.table_privileges
WHERE grantee = 'blueseatra_app'
  AND table_schema = 'blueseatra'
  AND table_name IN ('users', 'tenants', 'tenant_users');


-- ============================================================================
-- RETOUR ARRIERE -- piege verifie le 12/09/2026 lors du test a blanc
-- ============================================================================
-- `DROP ROLE blueseatra_app` echouera avec l'erreur 2BP01 si on a seulement
-- fait REVOKE ALL PRIVILEGES ... FROM blueseatra_app : les entrees issues
-- de ALTER DEFAULT PRIVILEGES (section 4) sont un mecanisme SEPARE et ne
-- sont PAS retirees par un REVOKE ordinaire. Ordre verifie qui fonctionne,
-- teste sur un role jetable avant d'ecrire ce fichier :
--
--   ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA blueseatra
--     REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM blueseatra_app;
--   ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA blueseatra
--     REVOKE USAGE, SELECT ON SEQUENCES FROM blueseatra_app;
--   REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA blueseatra FROM blueseatra_app;
--   REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA blueseatra FROM blueseatra_app;
--   REVOKE ALL PRIVILEGES ON SCHEMA blueseatra FROM blueseatra_app;
--   REVOKE authenticated FROM blueseatra_app;
--   DROP ROLE IF EXISTS blueseatra_app;
-- ============================================================================


-- ============================================================================
-- MOT DE PASSE -- A FAIRE SEPAREMENT, JAMAIS DANS UN FICHIER COMMIT
-- ============================================================================
-- Deux facons de le definir, au choix. Ni l'une ni l'autre ne doit
-- transiter par une conversation, un fichier versionne, ou un log.
--
-- OPTION A -- Supabase Dashboard (recommandee, aucune commande a taper)
--   1. https://supabase.com/dashboard/project/xmsxlochasjauhnxarvc/database/roles
--   2. Trouver `blueseatra_app` dans la liste des roles
--   3. Reset password -> laisser Supabase generer une valeur forte
--   4. Copier IMMEDIATEMENT la valeur affichee (elle ne sera plus visible
--      apres fermeture de la boite de dialogue) et la coller directement
--      dans Render (voir le runbook DATABASE_URL_AUTH), sans passer par un
--      fichier ou un presse-papier partage.
--
-- OPTION B -- SQL, si le dashboard n'est pas accessible
--   Executer, dans le SQL Editor de Supabase (jamais via ce fichier de
--   migration versionne) :
--
--     ALTER ROLE blueseatra_app WITH PASSWORD 'COLLER_ICI_UNE_VALEUR_FORTE';
--
--   Generer la valeur AVANT, localement et hors de toute conversation,
--   par exemple :
--     python3 -c "import secrets; print(secrets.token_urlsafe(32))"
--   Executer la commande ALTER ROLE, puis fermer immediatement l'onglet
--   SQL Editor -- l'historique de requetes de Supabase la conserverait
--   sinon en clair.
-- ============================================================================
