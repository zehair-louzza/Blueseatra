-- =====================================================================
-- Etape 4b -- retirer a blueseatra_app l'appartenance au role
--             `authenticated`, qui lui donnait des droits herites
--             sur tenants et tenant_users.
-- =====================================================================
--
-- LA FAILLE
-- ---------
-- La migration 20260912050000 affirmait en commentaire :
--
--     "Aucun GRANT sur users / tenants / tenant_users : c'est
--      deliberement..."
--
-- C'etait FAUX. La meme migration executait :
--
--     GRANT authenticated TO blueseatra_app;
--
-- pour que les politiques RLS existantes (toutes definies TO
-- authenticated) s'appliquent au nouveau role sans devoir les reecrire.
-- Mais le role `authenticated` de Supabase porte aussi ses propres
-- GRANT de table :
--
--     tenants       -> authenticated=r/postgres        (SELECT)
--     tenant_users  -> authenticated=arwd/postgres     (SELECT+INSERT+
--                                                       UPDATE+DELETE)
--
-- blueseatra_app, cree avec INHERIT, heritait donc de tout cela.
--
-- Concretement, le chemin metier pouvait lire la liste des tenants et
-- ECRIRE dans tenant_users -- la table qui associe un utilisateur a un
-- tenant. C'est un chemin d'elevation de privileges : une injection sur
-- le chemin metier pouvait s'octroyer l'acces a un autre tenant.
--
-- POURQUOI L'AUDIT PRECEDENT NE L'A PAS VU
-- -----------------------------------------
-- Il interrogeait information_schema.role_table_grants avec
-- grantee = 'blueseatra_app', qui ne liste que les GRANT DIRECTS. Les
-- droits herites d'un role parent n'y figurent pas.
--
-- La bonne fonction est has_table_privilege(), qui resout l'heritage :
--
--     select has_table_privilege('blueseatra_app',
--                                'blueseatra.tenant_users', 'INSERT');
--     -- renvoyait true
--
-- Detecte par le script de pre-vol, qui tentait reellement la lecture
-- au lieu de se fier a une table de metadonnees.
--
-- LE CORRECTIF
-- ------------
-- On ne peut pas retirer les GRANT de `authenticated` sur tenants et
-- tenant_users : ils sont legitimes pour le vrai chemin Supabase (un
-- utilisateur authentifie via JWT, cote PostgREST).
--
-- On ajoute donc blueseatra_app comme role CIBLE des 11 politiques
-- metier, puis on retire l'appartenance a `authenticated`. Le role
-- conserve ses GRANT directs (poses par 20260912050000) et reste
-- couvert par les politiques, sans plus rien heriter.
--
-- SANS RISQUE MAINTENANT
-- ----------------------
-- La production tourne en repli : le chemin metier utilise `postgres`,
-- personne ne se connecte encore avec blueseatra_app. Modifier ses
-- droits n'a donc aucun effet sur le trafic en cours. C'est exactement
-- la fenetre pour le faire.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Ajouter blueseatra_app comme cible des politiques metier
-- ---------------------------------------------------------------------
-- Boucle plutot que 11 ALTER POLICY ecrits a la main : evite une faute
-- de frappe sur un nom de politique, et couvre automatiquement toute
-- politique future sur ces tables.
--
-- ALTER POLICY ... TO remplace la liste de roles, il ne l'etend pas :
-- on reconstruit donc la liste existante + blueseatra_app, en repartant
-- de pg_policies pour ne rien perdre.

DO $$
DECLARE
  pol   record;
  roles text;
BEGIN
  FOR pol IN
    SELECT p.schemaname, p.tablename, p.policyname, p.roles
    FROM pg_policies p
    WHERE p.schemaname = 'blueseatra'
      AND p.tablename NOT IN ('users', 'tenants', 'tenant_users')
  LOOP
    -- pol.roles est un name[] : on le transforme en liste SQL en
    -- ajoutant blueseatra_app s'il n'y est pas deja.
    SELECT string_agg(quote_ident(r), ', ')
      INTO roles
      FROM (
        SELECT unnest(pol.roles::text[]) AS r
        UNION
        SELECT 'blueseatra_app'
      ) s
      WHERE r <> '-';  -- '-' = PUBLIC, ne doit pas etre requalifie

    IF roles IS NULL THEN
      -- politique ciblant PUBLIC : ne pas la restreindre par erreur
      RAISE NOTICE 'Politique %.% ciblant PUBLIC, laissee inchangee',
                   pol.tablename, pol.policyname;
      CONTINUE;
    END IF;

    EXECUTE format('ALTER POLICY %I ON %I.%I TO %s',
                   pol.policyname, pol.schemaname, pol.tablename, roles);
    RAISE NOTICE 'Politique %.% -> %', pol.tablename, pol.policyname, roles;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 2. Retirer l'appartenance a `authenticated`
-- ---------------------------------------------------------------------
REVOKE authenticated FROM blueseatra_app;

-- ---------------------------------------------------------------------
-- 3. Ceinture et bretelles : revoquer explicitement tout residu
-- ---------------------------------------------------------------------
-- Sans effet si l'etape 2 a suffi, mais protege contre un GRANT direct
-- qui aurait ete pose entre-temps.
REVOKE ALL PRIVILEGES ON blueseatra.users        FROM blueseatra_app;
REVOKE ALL PRIVILEGES ON blueseatra.tenants      FROM blueseatra_app;
REVOKE ALL PRIVILEGES ON blueseatra.tenant_users FROM blueseatra_app;

-- ---------------------------------------------------------------------
-- 4. Verification bloquante -- la migration echoue si la faille subsiste
-- ---------------------------------------------------------------------
-- has_table_privilege() et non information_schema : c'est justement la
-- difference qui avait masque le probleme.
DO $$
DECLARE
  t       text;
  priv    text;
  fuites  text := '';
BEGIN
  FOREACH t IN ARRAY ARRAY['users', 'tenants', 'tenant_users'] LOOP
    FOREACH priv IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE'] LOOP
      IF has_table_privilege('blueseatra_app', 'blueseatra.' || t, priv) THEN
        fuites := fuites || format('  %s sur %s%s', priv, t, chr(10));
      END IF;
    END LOOP;
  END LOOP;

  IF fuites <> '' THEN
    RAISE EXCEPTION
      'ECHEC : blueseatra_app conserve des droits sur les tables '
      'd''authentification :%s%sVerifier les appartenances de role '
      '(pg_auth_members) et les GRANT a PUBLIC.',
      chr(10), fuites;
  END IF;

  -- Symetrie : le role doit CONSERVER ses droits metier.
  FOREACH t IN ARRAY ARRAY['quotes', 'pricing_items', 'catalogs',
                           'requests', 'audit_logs'] LOOP
    IF NOT has_table_privilege('blueseatra_app', 'blueseatra.' || t, 'SELECT') THEN
      RAISE EXCEPTION
        'ECHEC : blueseatra_app a PERDU l''acces a %, le chemin metier '
        'serait casse. Migration annulee.', t;
    END IF;
  END LOOP;

  RAISE NOTICE 'OK : aucun droit sur users/tenants/tenant_users, '
               'droits metier intacts.';
END $$;

COMMIT;

-- =====================================================================
-- RETOUR ARRIERE
-- =====================================================================
--   GRANT authenticated TO blueseatra_app;
--
-- Suffit a restaurer l'etat precedent : les politiques ciblent
-- desormais blueseatra_app EN PLUS de authenticated, donc rien ne
-- depend du retrait. Retirer blueseatra_app des politiques n'est pas
-- necessaire et serait contre-productif.
-- =====================================================================
