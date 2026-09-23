-- Appliquee en production le 23/09/2026 (accord explicite du proprietaire).
-- Sur PG16+, postgres avait ADMIN sur blueseatra_app mais pas SET : le script
-- d'import (SET ROLE blueseatra_app, pour rester sous RLS) etait refuse.
-- Aucune donnee ni table modifiee. Retour arriere :
--   REVOKE SET OPTION FOR blueseatra_app FROM postgres;
GRANT blueseatra_app TO postgres WITH SET TRUE;
