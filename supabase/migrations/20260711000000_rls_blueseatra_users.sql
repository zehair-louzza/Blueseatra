-- ============================================================
-- Migration : RLS Policies pour blueseatra.users
-- Date      : 2026-07-11
-- Auteur    : zehair-louzza
-- Context   : La table blueseatra.users utilise un systeme
--             d'auth custom (FastAPI + JWT sur Render).
--             Le backend utilise la cle service_role Supabase
--             qui bypasse RLS nativement.
--             Ces politiques bloquent tout acces direct
--             non autorise via anon ou authenticated.
-- ============================================================

-- Activer RLS si pas encore fait (idempotent)
ALTER TABLE blueseatra.users ENABLE ROW LEVEL SECURITY;

-- Supprimer les politiques existantes si elles existent (idempotent)
DROP POLICY IF EXISTS "users_select_service_only" ON blueseatra.users;
DROP POLICY IF EXISTS "users_insert_service_only" ON blueseatra.users;
DROP POLICY IF EXISTS "users_update_service_only" ON blueseatra.users;
DROP POLICY IF EXISTS "users_delete_service_only" ON blueseatra.users;

-- 1. SELECT : Seul le service_role (backend FastAPI) peut lire
CREATE POLICY "users_select_service_only"
  ON blueseatra.users
  FOR SELECT
  TO service_role
  USING (true);

-- 2. INSERT : Seul le service_role peut creer des users
--    (inscription via /api/auth/register)
CREATE POLICY "users_insert_service_only"
  ON blueseatra.users
  FOR INSERT
  TO service_role
  WITH CHECK (true);

-- 3. UPDATE : Seul le service_role peut modifier les users
CREATE POLICY "users_update_service_only"
  ON blueseatra.users
  FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- 4. DELETE : Seul le service_role peut supprimer des users
CREATE POLICY "users_delete_service_only"
  ON blueseatra.users
  FOR DELETE
  TO service_role
  USING (true);

-- Verification : lister les politiques creees
-- SELECT policyname, cmd, roles FROM pg_policies
-- WHERE schemaname = 'blueseatra' AND tablename = 'users';
