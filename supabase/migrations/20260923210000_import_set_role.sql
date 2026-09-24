-- Appliquee en production le 23/09/2026 (accord explicite du proprietaire).
-- Sur PG16+, postgres avait ADMIN sur blueseatra_app mais pas SET : le script
-- d'import (SET ROLE blueseatra_app, pour rester sous RLS) etait refuse.
-- Aucune donnee ni table modifiee. Retour arriere :
--   REVOKE SET OPTION FOR blueseatra_app FROM postgres;
--
-- Garde : la preproduction (CI, VPS) n'a pas forcement de role `postgres`
-- (utilisateur applicatif dedie) et peut tourner sous PG < 16, ou l'option
-- WITH SET n'existe pas. Sans ces gardes, la migration faisait echouer la
-- CI « migrations » de la PR #101.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres')
     AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'blueseatra_app') THEN
    IF current_setting('server_version_num')::int >= 160000 THEN
      EXECUTE 'GRANT blueseatra_app TO postgres WITH SET TRUE';
    ELSE
      EXECUTE 'GRANT blueseatra_app TO postgres';
    END IF;
  END IF;
END
$$;
