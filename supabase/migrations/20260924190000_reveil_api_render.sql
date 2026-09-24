-- =====================================================================
-- Réveil automatique de l'API Render (offre gratuite)
-- =====================================================================
--
-- POURQUOI
-- L'offre gratuite de Render endort l'API après 15 minutes sans requête.
-- Le premier appel suivant attendait alors environ 50 secondes. Un appel à
-- /api/health toutes les 13 minutes garde l'API éveillée ; environ 730 h
-- par mois, dans la limite des 750 h gratuites pour un seul service.
--
-- ÉTAT DE LA PRODUCTION
-- Tâche créée à la main le 24/09/2026 (jobid 1, nom « reveil-api-render »).
-- Ce fichier la trace dans le dépôt pour qu'elle puisse être recréée à
-- l'identique si la base était reconstruite.
--
-- SÛRETÉ
-- - Idempotent : cron.schedule() met à jour une tâche de même nom au lieu
--   d'en créer une seconde.
-- - Sans effet là où pg_cron / pg_net n'existent pas (PostgreSQL de la CI,
--   préproduction OVH) : rien n'est créé.
-- - Aucune table métier n'est lue ni modifiée ; la tâche ne fait qu'un GET.
--
-- ARRÊT
--   SELECT cron.unschedule('reveil-api-render');
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron')
       OR NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_net') THEN
        RAISE NOTICE 'pg_cron ou pg_net indisponible : réveil de l''API non planifié.';
        RETURN;
    END IF;

    CREATE EXTENSION IF NOT EXISTS pg_cron;
    CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

    PERFORM cron.schedule(
        'reveil-api-render',
        '*/13 * * * *',
        $job$SELECT net.http_get(
                url := 'https://blueseatra-api.onrender.com/api/health',
                timeout_milliseconds := 60000)$job$
    );
END
$$;
