-- =====================================================================
-- Compteurs et quotas par entreprise (ticket #89)
-- =====================================================================
--
-- Ce qui est compté (grille validée le 24/09/2026)
--   devis_ia : une demande lue et structurée par l'IA (un devis assisté)
--   page_lue : une page lue sur photo ou scan (PDF sans calque texte, image)
-- Les devis manuels, les PDF, les catalogues et le catalogue commun ne
-- sont jamais comptés.
--
-- Principes
--   - Registre en ajout seul : aucune ligne n'est modifiée ni supprimée
--     (déclencheur + droits). Une correction est une nouvelle ligne inverse.
--   - Le solde affiché est toujours la somme des lignes du registre : il se
--     recalcule à l'identique en rejouant le registre.
--   - Chaque entreprise ne voit que ses lignes (RLS sur current_tenant()),
--     et toutes les fonctions refusent un tenant différent du tenant courant.
--   - Réservation atomique : verrou par entreprise, dotation du mois créée
--     à la première consommation, forfait consommé avant les recharges.
--   - Rien n'est bloqué par cette migration : le blocage n'a lieu que si le
--     serveur est lancé avec BLUESEATRA_QUOTAS_APPLIQUES=1. Sinon, mode
--     observation : tout est compté, rien n'est refusé.
--
-- Additive et idempotente : aucune table existante n'est modifiée.
-- =====================================================================

-- 1. Offres (référentiel en lecture seule) -----------------------------
CREATE TABLE IF NOT EXISTS blueseatra.offres (
    code                  varchar PRIMARY KEY,
    nom                   varchar NOT NULL,
    prix_mensuel_ht_cents integer,          -- NULL : sur devis ou non facturée
    sieges                integer,          -- NULL : illimité / contrat
    devis_ia              integer,          -- par période ; NULL : illimité
    pages_lues            integer,          -- par période ; NULL : illimité
    import_mo             integer,
    essai_jours           integer,          -- non NULL : offre d'essai, période unique
    visible               boolean NOT NULL DEFAULT true,
    ordre                 integer NOT NULL DEFAULT 0
);

INSERT INTO blueseatra.offres
    (code, nom, prix_mensuel_ht_cents, sieges, devis_ia, pages_lues, import_mo, essai_jours, visible, ordre)
VALUES
    ('decouverte',  'Découverte',  0,     1,    10,   30,   25,   14,   true,  1),
    ('initial',     'Initial',     5900,  1,    60,   150,  100,  NULL, true,  2),
    ('pilotage',    'Pilotage',    14900, 3,    250,  750,  300,  NULL, true,  3),
    ('performance', 'Performance', 39900, 10,   1000, 3000, 1024, NULL, true,  4),
    ('signature',   'Signature',   NULL,  NULL, NULL, NULL, NULL, NULL, true,  5),
    ('interne',     'Interne (non facturé)', NULL, NULL, NULL, NULL, NULL, NULL, false, 9)
ON CONFLICT (code) DO UPDATE SET
    nom = EXCLUDED.nom, prix_mensuel_ht_cents = EXCLUDED.prix_mensuel_ht_cents,
    sieges = EXCLUDED.sieges, devis_ia = EXCLUDED.devis_ia, pages_lues = EXCLUDED.pages_lues,
    import_mo = EXCLUDED.import_mo, essai_jours = EXCLUDED.essai_jours,
    visible = EXCLUDED.visible, ordre = EXCLUDED.ordre;

ALTER TABLE blueseatra.offres ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS offres_lecture ON blueseatra.offres;
CREATE POLICY offres_lecture ON blueseatra.offres FOR SELECT TO blueseatra_app USING (true);
GRANT SELECT ON blueseatra.offres TO blueseatra_app;

-- 2. Abonnement de chaque entreprise ------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.abonnements (
    tenant_id              varchar PRIMARY KEY,
    offre_code             varchar NOT NULL REFERENCES blueseatra.offres(code),
    statut                 varchar NOT NULL
                           CHECK (statut IN ('essai', 'actif', 'lecture_seule', 'suspendu')),
    periode_debut          timestamptz NOT NULL DEFAULT now(),
    essai_fin_le           timestamptz,
    sieges_supplementaires integer NOT NULL DEFAULT 0 CHECK (sieges_supplementaires >= 0),
    cree_le                timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE blueseatra.abonnements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS abonnements_tenant ON blueseatra.abonnements;
CREATE POLICY abonnements_tenant ON blueseatra.abonnements
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
-- L'application crée l'essai d'une entreprise mais ne change jamais une
-- offre : un changement d'offre passe par la plateforme (plus tard Stripe).
GRANT SELECT, INSERT ON blueseatra.abonnements TO blueseatra_app;

-- 3. Registre de consommation (ajout seul) ------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.registre_consommation (
    id            bigserial PRIMARY KEY,
    tenant_id     varchar NOT NULL,
    cree_le       timestamptz NOT NULL DEFAULT clock_timestamp(),
    unite         varchar NOT NULL CHECK (unite IN ('devis_ia', 'page_lue')),
    quantite      integer NOT NULL CHECK (quantite <> 0),
    nature        varchar NOT NULL
                  CHECK (nature IN ('dotation', 'consommation', 'annulation', 'recharge', 'ajustement')),
    reserve       varchar NOT NULL CHECK (reserve IN ('forfait', 'recharge')),
    periode_debut timestamptz,
    demande_id    varchar,
    annule_id     bigint REFERENCES blueseatra.registre_consommation(id),
    acteur        varchar,
    motif         varchar,
    CHECK (nature <> 'consommation' OR quantite < 0),
    CHECK (nature NOT IN ('dotation', 'recharge', 'annulation') OR quantite > 0),
    CHECK (nature <> 'annulation' OR annule_id IS NOT NULL),
    CHECK (reserve <> 'forfait' OR periode_debut IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS registre_une_dotation_par_periode
    ON blueseatra.registre_consommation (tenant_id, unite, periode_debut)
    WHERE nature = 'dotation';
CREATE UNIQUE INDEX IF NOT EXISTS registre_une_annulation_par_ligne
    ON blueseatra.registre_consommation (annule_id) WHERE nature = 'annulation';
CREATE INDEX IF NOT EXISTS registre_tenant_unite
    ON blueseatra.registre_consommation (tenant_id, unite, reserve, periode_debut);
CREATE INDEX IF NOT EXISTS registre_tenant_demande
    ON blueseatra.registre_consommation (tenant_id, demande_id) WHERE demande_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS registre_tenant_date
    ON blueseatra.registre_consommation (tenant_id, cree_le DESC);

CREATE OR REPLACE FUNCTION blueseatra.registre_ajout_seul() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'registre_consommation est en ajout seul : % refusé. Corriger par une ligne inverse.', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS registre_ajout_seul ON blueseatra.registre_consommation;
CREATE TRIGGER registre_ajout_seul
    BEFORE UPDATE OR DELETE ON blueseatra.registre_consommation
    FOR EACH ROW EXECUTE FUNCTION blueseatra.registre_ajout_seul();
DROP TRIGGER IF EXISTS registre_ajout_seul_truncate ON blueseatra.registre_consommation;
CREATE TRIGGER registre_ajout_seul_truncate
    BEFORE TRUNCATE ON blueseatra.registre_consommation
    FOR EACH STATEMENT EXECUTE FUNCTION blueseatra.registre_ajout_seul();

ALTER TABLE blueseatra.registre_consommation ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS registre_tenant ON blueseatra.registre_consommation;
CREATE POLICY registre_tenant ON blueseatra.registre_consommation
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());
GRANT SELECT, INSERT ON blueseatra.registre_consommation TO blueseatra_app;
GRANT USAGE ON SEQUENCE blueseatra.registre_consommation_id_seq TO blueseatra_app;

-- 4. Fonctions ----------------------------------------------------------

-- Garde commune : le tenant passé doit être le tenant courant quand il est
-- défini (chemin métier). Sans tenant courant, seul un rôle BYPASSRLS
-- (tâche système) peut appeler ; RLS bloque sinon toute écriture.
CREATE OR REPLACE FUNCTION blueseatra.quota_garde_tenant(p_tenant varchar) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF p_tenant IS NULL OR p_tenant = '' THEN
        RAISE EXCEPTION 'tenant manquant';
    END IF;
    IF blueseatra.current_tenant() IS NOT NULL AND blueseatra.current_tenant() <> p_tenant THEN
        RAISE EXCEPTION 'tenant % différent du tenant courant', p_tenant
            USING ERRCODE = 'insufficient_privilege';
    END IF;
END $$;

-- Abonnement de l'entreprise ; crée l'essai Découverte au premier usage.
CREATE OR REPLACE FUNCTION blueseatra.quota_abonnement(p_tenant varchar)
RETURNS blueseatra.abonnements
LANGUAGE plpgsql AS $$
DECLARE a blueseatra.abonnements;
BEGIN
    PERFORM blueseatra.quota_garde_tenant(p_tenant);
    SELECT * INTO a FROM blueseatra.abonnements WHERE tenant_id = p_tenant;
    IF NOT FOUND THEN
        INSERT INTO blueseatra.abonnements (tenant_id, offre_code, statut, periode_debut, essai_fin_le)
        VALUES (p_tenant, 'decouverte', 'essai', now(), now() + interval '14 days')
        ON CONFLICT (tenant_id) DO NOTHING;
        SELECT * INTO a FROM blueseatra.abonnements WHERE tenant_id = p_tenant;
    END IF;
    RETURN a;
END $$;

-- Début de la période en cours : période unique pour un essai, sinon mois
-- glissant à partir de periode_debut.
CREATE OR REPLACE FUNCTION blueseatra.quota_periode(a blueseatra.abonnements, o blueseatra.offres,
                                                    p_maintenant timestamptz DEFAULT now())
RETURNS timestamptz
LANGUAGE plpgsql STABLE AS $$
DECLARE n integer;
BEGIN
    IF o.essai_jours IS NOT NULL THEN
        RETURN a.periode_debut;
    END IF;
    n := (extract(year FROM age(p_maintenant, a.periode_debut)) * 12
          + extract(month FROM age(p_maintenant, a.periode_debut)))::integer;
    RETURN a.periode_debut + make_interval(months => greatest(n, 0));
END $$;

-- Réserve des unités pour une demande, de façon atomique.
--   p_devis  : 1 pour une nouvelle demande IA, 0 pour une relecture seule
--   p_pages  : pages lues sur photo ou scan (0 pour un texte ou un PDF lisible)
--   p_bloquer: true = refuser au-delà du quota ; false = mode observation
-- Idempotent : une demande dont le devis IA est déjà compté (et non annulé)
-- n'est pas recomptée, ni ses pages.
CREATE OR REPLACE FUNCTION blueseatra.quota_reserver(
    p_tenant varchar, p_demande varchar, p_devis integer, p_pages integer,
    p_acteur varchar, p_bloquer boolean)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    a blueseatra.abonnements;
    o blueseatra.offres;
    v_periode timestamptz;
    v_motif text := NULL;
    v_deja boolean := false;
    v_unite text;
    v_besoin integer;
    v_inclus integer;
    v_forfait integer;
    v_recharge integer;
    v_pris integer;
    v_depasse boolean := false;
BEGIN
    PERFORM blueseatra.quota_garde_tenant(p_tenant);
    IF coalesce(p_devis, 0) < 0 OR coalesce(p_pages, 0) < 0 THEN
        RAISE EXCEPTION 'quantités négatives refusées';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('blueseatra.quota:' || p_tenant));

    a := blueseatra.quota_abonnement(p_tenant);
    SELECT * INTO o FROM blueseatra.offres WHERE code = a.offre_code;
    v_periode := blueseatra.quota_periode(a, o);

    IF p_demande IS NOT NULL AND coalesce(p_devis, 0) > 0 THEN
        SELECT EXISTS (
            SELECT 1 FROM blueseatra.registre_consommation c
            WHERE c.tenant_id = p_tenant AND c.demande_id = p_demande
              AND c.unite = 'devis_ia' AND c.nature = 'consommation'
              AND NOT EXISTS (SELECT 1 FROM blueseatra.registre_consommation x
                              WHERE x.tenant_id = p_tenant AND x.annule_id = c.id))
        INTO v_deja;
        IF v_deja THEN
            RETURN jsonb_build_object('autorise', true, 'deja_compte', true);
        END IF;
    END IF;

    IF a.statut IN ('lecture_seule', 'suspendu') THEN
        v_motif := a.statut;
    ELSIF o.essai_jours IS NOT NULL AND a.essai_fin_le IS NOT NULL AND now() > a.essai_fin_le THEN
        v_motif := 'essai_termine';
    END IF;

    -- Dotations de la période (créées une seule fois grâce à l'index unique)
    FOREACH v_unite IN ARRAY ARRAY['devis_ia', 'page_lue'] LOOP
        v_inclus := CASE v_unite WHEN 'devis_ia' THEN o.devis_ia ELSE o.pages_lues END;
        IF v_inclus IS NOT NULL AND v_inclus > 0 THEN
            INSERT INTO blueseatra.registre_consommation
                (tenant_id, unite, quantite, nature, reserve, periode_debut, acteur, motif)
            VALUES (p_tenant, v_unite, v_inclus, 'dotation', 'forfait', v_periode, 'systeme',
                    'Dotation ' || o.nom)
            ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;

    -- Contrôle des soldes avant toute consommation
    FOREACH v_unite IN ARRAY ARRAY['devis_ia', 'page_lue'] LOOP
        v_besoin := CASE v_unite WHEN 'devis_ia' THEN coalesce(p_devis, 0) ELSE coalesce(p_pages, 0) END;
        CONTINUE WHEN v_besoin = 0;
        v_inclus := CASE v_unite WHEN 'devis_ia' THEN o.devis_ia ELSE o.pages_lues END;
        CONTINUE WHEN v_inclus IS NULL;   -- illimité (Signature, Interne)
        SELECT coalesce(sum(quantite) FILTER (WHERE reserve = 'forfait' AND periode_debut = v_periode), 0),
               coalesce(sum(quantite) FILTER (WHERE reserve = 'recharge'), 0)
          INTO v_forfait, v_recharge
          FROM blueseatra.registre_consommation
         WHERE tenant_id = p_tenant AND unite = v_unite;
        IF greatest(v_forfait, 0) + greatest(v_recharge, 0) < v_besoin THEN
            v_motif := coalesce(v_motif, 'quota_atteint_' || v_unite);
        END IF;
    END LOOP;

    IF v_motif IS NOT NULL AND p_bloquer THEN
        RETURN jsonb_build_object('autorise', false, 'motif', v_motif, 'offre', o.code);
    END IF;
    v_depasse := v_motif IS NOT NULL;

    -- Consommation : forfait d'abord, puis recharges ; en observation, le
    -- dépassement est imputé au forfait (solde négatif visible).
    FOREACH v_unite IN ARRAY ARRAY['devis_ia', 'page_lue'] LOOP
        v_besoin := CASE v_unite WHEN 'devis_ia' THEN coalesce(p_devis, 0) ELSE coalesce(p_pages, 0) END;
        CONTINUE WHEN v_besoin = 0;
        v_inclus := CASE v_unite WHEN 'devis_ia' THEN o.devis_ia ELSE o.pages_lues END;
        SELECT coalesce(sum(quantite) FILTER (WHERE reserve = 'forfait' AND periode_debut = v_periode), 0),
               coalesce(sum(quantite) FILTER (WHERE reserve = 'recharge'), 0)
          INTO v_forfait, v_recharge
          FROM blueseatra.registre_consommation
         WHERE tenant_id = p_tenant AND unite = v_unite;
        -- v_pris = part imputée aux recharges ; le reste va au forfait
        v_pris := 0;
        IF v_inclus IS NOT NULL AND v_besoin > greatest(v_forfait, 0) AND v_recharge > 0 THEN
            v_pris := least(v_besoin - greatest(v_forfait, 0), v_recharge);
            INSERT INTO blueseatra.registre_consommation
                (tenant_id, unite, quantite, nature, reserve, demande_id, acteur)
            VALUES (p_tenant, v_unite, -v_pris, 'consommation', 'recharge', p_demande, p_acteur);
        END IF;
        IF v_besoin - v_pris > 0 THEN
            INSERT INTO blueseatra.registre_consommation
                (tenant_id, unite, quantite, nature, reserve, periode_debut, demande_id, acteur)
            VALUES (p_tenant, v_unite, -(v_besoin - v_pris), 'consommation', 'forfait',
                    v_periode, p_demande, p_acteur);
        END IF;
    END LOOP;

    RETURN jsonb_build_object('autorise', true, 'depassement', v_depasse,
                              'motif', v_motif, 'offre', o.code);
END $$;

-- Annule (ligne inverse) toutes les consommations non encore annulées d'une
-- demande : utilisé quand l'extraction échoue. Idempotent.
CREATE OR REPLACE FUNCTION blueseatra.quota_annuler(p_tenant varchar, p_demande varchar, p_motif varchar)
RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
    PERFORM blueseatra.quota_garde_tenant(p_tenant);
    PERFORM pg_advisory_xact_lock(hashtext('blueseatra.quota:' || p_tenant));
    INSERT INTO blueseatra.registre_consommation
        (tenant_id, unite, quantite, nature, reserve, periode_debut, demande_id, annule_id, acteur, motif)
    SELECT c.tenant_id, c.unite, -c.quantite, 'annulation', c.reserve, c.periode_debut,
           c.demande_id, c.id, 'systeme', p_motif
      FROM blueseatra.registre_consommation c
     WHERE c.tenant_id = p_tenant AND c.demande_id = p_demande AND c.nature = 'consommation'
       AND NOT EXISTS (SELECT 1 FROM blueseatra.registre_consommation x
                       WHERE x.tenant_id = p_tenant AND x.annule_id = c.id);
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;

-- Recharge (achat d'un pack) : réservée à la plateforme, jamais à
-- l'application (aucun droit EXECUTE pour blueseatra_app).
CREATE OR REPLACE FUNCTION blueseatra.quota_crediter_recharge(
    p_tenant varchar, p_unite varchar, p_quantite integer, p_acteur varchar, p_motif varchar)
RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE v_id bigint;
BEGIN
    IF p_quantite IS NULL OR p_quantite <= 0 THEN
        RAISE EXCEPTION 'quantité de recharge invalide';
    END IF;
    INSERT INTO blueseatra.registre_consommation
        (tenant_id, unite, quantite, nature, reserve, acteur, motif)
    VALUES (p_tenant, p_unite, p_quantite, 'recharge', 'recharge', p_acteur, p_motif)
    RETURNING id INTO v_id;
    RETURN v_id;
END $$;

REVOKE ALL ON FUNCTION blueseatra.quota_crediter_recharge(varchar, varchar, integer, varchar, varchar) FROM PUBLIC;
DO $$
DECLARE r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'blueseatra_app'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON FUNCTION blueseatra.quota_crediter_recharge(varchar, varchar, integer, varchar, varchar) FROM %I', r);
        END IF;
    END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION blueseatra.quota_garde_tenant(varchar) TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.quota_abonnement(varchar) TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.quota_periode(blueseatra.abonnements, blueseatra.offres, timestamptz) TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.quota_reserver(varchar, varchar, integer, integer, varchar, boolean) TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.quota_annuler(varchar, varchar, varchar) TO blueseatra_app;

-- Retour arrière (aucune donnée métier touchée) :
--   DROP FUNCTION blueseatra.quota_reserver, blueseatra.quota_annuler, ... ;
--   DROP TABLE blueseatra.registre_consommation, blueseatra.abonnements, blueseatra.offres;
