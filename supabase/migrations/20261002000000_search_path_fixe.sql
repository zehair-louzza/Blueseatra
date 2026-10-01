-- search_path fixé sur les 10 fonctions signalées par le Security Advisor
-- de Supabase (avertissement « Function Search Path Mutable », 02/10/2026).
--
-- Risque corrigé
-- --------------
-- Une fonction sans search_path résout ses noms non qualifiés avec le
-- search_path de l'appelant. Quiconque pourrait créer un objet dans un schéma
-- placé avant pg_catalog ou blueseatra dans ce chemin pourrait détourner un
-- appel. Constaté en production : aucune de ces fonctions n'est SECURITY
-- DEFINER, et seuls postgres et dashboard_user peuvent créer dans public ou
-- extensions. Le risque est donc faible, mais la correction ne coûte rien.
--
-- Vérifications faites avant d'écrire cette migration
-- ---------------------------------------------------
-- * Les 9 fonctions passées à search_path = '' qualifient toutes leurs tables
--   (blueseatra.xxx) et n'appellent que des fonctions de pg_catalog (now,
--   greatest, hashtext, pg_advisory_xact_lock…), toujours résolues.
-- * normalise_recherche appelle unaccent('unaccent', …) sans schéma, et
--   unaccent est installée dans public : elle reçoit search_path = public,
--   pg_temp. Elle calcule la colonne générée supplier_offers.recherche_norm.
--   Mesuré sur 200 000 lignes : résultat identique (0 différence) et
--   +3 % de temps d'import (une fonction avec SET n'est plus « inlinée »).
--
-- Les 2 avertissements « Extension in Public » (unaccent, pg_trgm) ne sont
-- PAS traités ici. Les deux extensions appartiennent à supabase_admin :
-- postgres ne peut pas faire ALTER EXTENSION … SET SCHEMA, et un DROP / CREATE
-- supprimerait les index trigrammes de 967 563 offres pendant leur
-- reconstruction.
--
-- Les migrations d'origine portent désormais le même SET search_path : les
-- rejouer (CREATE OR REPLACE) ne ramène pas l'avertissement.
-- Idempotente, sans verrou long : ALTER FUNCTION ne touche aucune donnée.

DO $$
DECLARE
    f regprocedure;
BEGIN
    FOR f IN
        SELECT p.oid::regprocedure
          FROM pg_proc p
         WHERE p.pronamespace = 'blueseatra'::regnamespace
           AND p.proname IN ('tenant_catalogue_commun', 'registre_ajout_seul',
                             'echanges_ajout_seul', 'quota_garde_tenant',
                             'quota_abonnement', 'quota_periode', 'quota_reserver',
                             'quota_annuler', 'quota_crediter_recharge')
    LOOP
        EXECUTE format('ALTER FUNCTION %s SET search_path = %L', f, '');
    END LOOP;

    FOR f IN
        SELECT p.oid::regprocedure
          FROM pg_proc p
         WHERE p.pronamespace = 'blueseatra'::regnamespace
           AND p.proname = 'normalise_recherche'
    LOOP
        EXECUTE format('ALTER FUNCTION %s SET search_path = public, pg_temp', f);
    END LOOP;
END $$;

-- Contrôle : plus aucune fonction du schéma blueseatra sans search_path fixe.
-- Toute nouvelle fonction devra le déclarer, sinon cette vérification échoue
-- au prochain passage de la migration.
DO $$
DECLARE
    restantes text;
BEGIN
    SELECT string_agg(p.oid::regprocedure::text, ', ' ORDER BY p.proname)
      INTO restantes
      FROM pg_proc p
     WHERE p.pronamespace = 'blueseatra'::regnamespace
       AND p.prokind IN ('f', 'p')
       AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
       AND NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig, '{}')) c
                        WHERE c LIKE 'search_path=%');
    IF restantes IS NOT NULL THEN
        RAISE EXCEPTION 'Fonctions sans search_path fixe : %', restantes;
    END IF;

    -- normalise_recherche doit toujours trouver unaccent (accents retirés).
    -- Pas d'exposant dans l'exemple : le dictionnaire unaccent standard ne
    -- convertit pas « ² », Supabase et la préproduction si.
    IF blueseatra.normalise_recherche('Câble R2V 3G2,5 — Disjoncteur 16A')
       <> 'cable r2v 3g2.5 disjoncteur 16a' THEN
        RAISE EXCEPTION 'normalise_recherche ne renvoie plus le même résultat';
    END IF;
END $$;
