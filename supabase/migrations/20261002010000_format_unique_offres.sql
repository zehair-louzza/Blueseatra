-- Format unique des offres fournisseurs (étape 1 : identité, unités, prix comparables).
--
-- Spécification : docs/specs/format-unique-catalogue-fournisseur.md (validée le 02/10/2026).
--
-- Principe
-- --------
-- * Les données sources ne sont JAMAIS modifiées : supplier_offers reste tel quel
--   (2,5 Go, 18 index). Le format unique vit dans une table 1-1,
--   blueseatra.offres_normalisees : la réécrire ne gonfle pas la grande table, et la
--   supprimer annule tout.
-- * Chaque offre reçoit une clé produit : GTIN:<14 chiffres> si l'EAN est valide
--   (clé GS1 vérifiée), sinon MR:<marque>:<référence fabricant>. Les offres d'un même
--   produit, décrit différemment chez chaque fournisseur, partagent cette clé.
-- * Le prix comparé est le prix par unité de base : chez YESSS, l'unité « 100 »
--   désigne un prix pour 100 (vérifié sur 203 EAN communs avec Rexel : rapport médian
--   de 125 à 133).
-- * Une nouvelle offre est normalisée automatiquement à l'import (déclencheur de
--   fin d'instruction). Une erreur de normalisation n'empêche jamais un import : elle
--   est signalée en WARNING et se rattrape avec normaliser_offres_lot().
--
-- Le calcul initial des 967 563 offres n'est pas dans cette migration (trop long pour
-- une seule transaction) : il se fait par lots avec normaliser_offres_lot(), puis
-- recalculer_marques() et rattacher_produits().

-- ---------------------------------------------------------------------------
-- 1. Fonctions de normalisation (immuables, search_path vide)
-- ---------------------------------------------------------------------------

-- GTIN : 8, 12, 13 ou 14 chiffres, clé GS1 juste, pas uniquement des zéros.
-- Renvoie le GTIN sur 14 chiffres, ou NULL.
CREATE OR REPLACE FUNCTION blueseatra.gtin14(p_code text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
    SELECT CASE WHEN d ~ '^([0-9]{8}|[0-9]{12,14})$' AND d !~ '^0+$'
                 AND (10 - (SELECT sum(substr(lpad(d, 14, '0'), i, 1)::int
                                       * CASE WHEN i % 2 = 1 THEN 3 ELSE 1 END)
                              FROM generate_series(1, 13) i) % 10) % 10
                     = right(d, 1)::int
           THEN lpad(d, 14, '0') END
      FROM (SELECT regexp_replace(coalesce(p_code, ''), '\s', '', 'g') AS d) s
$$;

-- Clé de marque : minuscules sans accents, ponctuation retirée, formes juridiques et
-- suffixes retirés (« LEGRAND S.N.C. » -> « legrand », « Hager SAS » -> « hager »).
CREATE OR REPLACE FUNCTION blueseatra.cle_marque(p_marque text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
    WITH t AS (
        SELECT ' ' || regexp_replace(lower(public.unaccent('public.unaccent'::regdictionary,
                                                            coalesce(p_marque, ''))),
                                     '[^a-z0-9]+', ' ', 'g') || ' ' AS v
    ), f AS (
        SELECT ' (s a s u|sasu|s a s|sas|s a r l|sarl|s n c|snc|s p a|spa|s r l|srl|s c a|sca|s a|sa|eurl|gmbh|ltd|limited|inc|ag|bv|nv|kg|france|group|groupe|industries|industrie|distribution|et fils) ' AS motif
    )
    SELECT nullif(replace(regexp_replace(regexp_replace(t.v, f.motif, ' ', 'g'), f.motif, ' ', 'g'),
                          ' ', ''), '')
      FROM t, f
$$;

-- Clé de référence fabricant : majuscules, sans séparateurs, sans zéros de tête.
-- Moins de 3 caractères : trop ambiguë, NULL.
CREATE OR REPLACE FUNCTION blueseatra.cle_reference(p_ref text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
    SELECT CASE WHEN length(k) >= 3 THEN k END
      FROM (SELECT ltrim(upper(regexp_replace(coalesce(p_ref, ''), '[^A-Za-z0-9]', '', 'g')), '0') AS k) s
$$;

-- Unité : unité de base (U, M, M2, M3, KG, L, PAIRE), conditionnement et quantité.
-- code = OK (lue), SUPPOSEE (absente : pièce supposée, signalée), INCONNUE.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'unite_offre'
                   AND typnamespace = 'blueseatra'::regnamespace) THEN
        CREATE TYPE blueseatra.unite_offre AS (
            unite_base text, conditionnement text, qte numeric, code text);
    END IF;
END $$;

-- Constructeur typé (un ROW(...) littéral n'a pas de type en PL/pgSQL).
CREATE OR REPLACE FUNCTION blueseatra.unite_offre_de(p_base text, p_cond text, p_qte numeric, p_code text)
RETURNS blueseatra.unite_offre LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
    SELECT ROW(p_base, p_cond, p_qte, p_code)::blueseatra.unite_offre
$$;

CREATE OR REPLACE FUNCTION blueseatra.unite_normalisee(p_unite text, p_libelle text)
RETURNS blueseatra.unite_offre LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
DECLARE
    u text := btrim(regexp_replace(lower(public.unaccent('public.unaccent'::regdictionary,
                                                         coalesce(p_unite, ''))), '\s+', ' ', 'g'));
    l text := lower(public.unaccent('public.unaccent'::regdictionary, coalesce(p_libelle, '')));
    m text[];
    r blueseatra.unite_offre;
BEGIN
    u := replace(replace(u, '²', '2'), '³', '3');
    l := replace(replace(l, '²', '2'), '³', '3');
    -- Nombre seul : « 1 » = la pièce, « 100 » = prix pour 100 (YESSS). Pour un câble,
    -- l'unité de base est le mètre : « YSLY-JZ 3G1 C100 » à 1 726,96 € les 1 000 = 1,73 €/m.
    IF u ~ '^[0-9]+([.,][0-9]+)?$' THEN
        r.qte := replace(u, ',', '.')::numeric;
        IF r.qte <= 0 THEN RETURN blueseatra.unite_offre_de(NULL, NULL, NULL, 'INCONNUE'); END IF;
        IF r.qte > 1 AND l ~ '(\mc[aâ]bles?\M|\mfils?\M|\m[0-9]{1,2} ?[gx] ?[0-9]+([.,][0-9]+)?\M|\m(h07|h05|r2v|u1000|ysly|liycy|xvb|frn05|ar2v|cat ?[5-7]a?)\M)' THEN
            RETURN blueseatra.unite_offre_de('M', CASE WHEN r.qte >= 500 THEN 'TOURET' ELSE 'ROULEAU' END, r.qte, 'OK');
        END IF;
        RETURN blueseatra.unite_offre_de('U', CASE WHEN r.qte = 1 THEN 'UNITE' ELSE 'LOT' END, r.qte, 'OK');
    END IF;
    -- « Boîte de 100 », « Sachet de 10 », « Lot de 4 », « Rouleau de 50 m »
    m := regexp_match(u, '^(boite|sachet|sac|lot|paquet|carton|blister|conditionnement|rouleau|couronne|touret|bidon) de ([0-9]+([.,][0-9]+)?) ?(m|ml|metres?|kg|l|litres?)?$');
    IF m IS NOT NULL THEN
        r.qte := replace(m[2], ',', '.')::numeric;
        RETURN blueseatra.unite_offre_de(CASE WHEN m[4] IN ('m', 'ml', 'metre', 'metres') THEN 'M'
                        WHEN m[4] = 'kg' THEN 'KG'
                        WHEN m[4] IN ('l', 'litre', 'litres') THEN 'L' ELSE 'U' END,
                   CASE m[1] WHEN 'boite' THEN 'BOITE' WHEN 'sachet' THEN 'SAC' WHEN 'sac' THEN 'SAC'
                             WHEN 'carton' THEN 'CARTON' WHEN 'rouleau' THEN 'ROULEAU'
                             WHEN 'couronne' THEN 'ROULEAU' WHEN 'touret' THEN 'TOURET'
                             WHEN 'bidon' THEN 'BIDON' ELSE 'LOT' END,
                   r.qte, 'OK');
    END IF;
    CASE
        WHEN u IN ('piece', 'pieces', 'pce', 'pc', 'u', 'un', 'unite', 'unites', 'pcs') THEN
            RETURN blueseatra.unite_offre_de('U', 'UNITE', 1, 'OK');
        WHEN u IN ('paire', 'pr') THEN RETURN blueseatra.unite_offre_de('PAIRE', 'UNITE', 1, 'OK');
        WHEN u = 'cent' THEN RETURN blueseatra.unite_offre_de('U', 'LOT', 100, 'OK');
        WHEN u = 'mille' THEN RETURN blueseatra.unite_offre_de('U', 'LOT', 1000, 'OK');
        WHEN u IN ('metre', 'metres', 'm', 'ml', 'metre lineaire') THEN RETURN blueseatra.unite_offre_de('M', 'UNITE', 1, 'OK');
        WHEN u IN ('kilometre', 'km') THEN RETURN blueseatra.unite_offre_de('M', 'TOURET', 1000, 'OK');
        WHEN u IN ('metre carre', 'metres carres', 'm2') THEN RETURN blueseatra.unite_offre_de('M2', 'UNITE', 1, 'OK');
        WHEN u IN ('metre cube', 'metres cubes', 'm3') THEN RETURN blueseatra.unite_offre_de('M3', 'UNITE', 1, 'OK');
        WHEN u IN ('kilogramme', 'kg') THEN RETURN blueseatra.unite_offre_de('KG', 'UNITE', 1, 'OK');
        WHEN u IN ('tonne', 't') THEN RETURN blueseatra.unite_offre_de('KG', 'UNITE', 1000, 'OK');
        WHEN u IN ('litre', 'l') THEN RETURN blueseatra.unite_offre_de('L', 'UNITE', 1, 'OK');
        WHEN u IN ('panneau', 'plaque', 'panneau plaque', 'panneau/plaque', 'barre', 'tube',
                   'seau', 'pot', 'cartouche', 'longueur') THEN RETURN blueseatra.unite_offre_de('U', 'UNITE', 1, 'OK');
        ELSE NULL;
    END CASE;
    -- Contenant sans quantité dans l'unité : quantité lue dans la désignation
    -- (« boite de 100 », « lot de 4 », « sachet de 50 »), sinon UNITE_INCONNUE.
    IF u IN ('boite', 'sac', 'sachet', 'sac-sachet', 'sac sachet', 'lot', 'paquet', 'carton',
             'blister', 'botte', 'rouleau', 'bidon', 'palette', '') THEN
        -- « sac de 25 kg » = 25 KG ; « sachet de 28 pièces » = 28 U ; « boîte de 100 vis » = 100 U.
        -- Un nombre suivi d'une autre unité (« sac de 25 mm ») n'est pas une quantité.
        m := regexp_match(l, '\m(boite|bte|sachet|sac|lot|paquet|pqt|carton|blister|colis|seau|bidon|rouleau|couronne|touret)\s*(de|x)\s*([0-9]{1,5}([.,][0-9]{1,3})?)(\s*(kg|litres?|l|ml|metres?|m2|m|pieces?|pces?|pcs|unites?|u)\M)?(?!\s*(mm2|mm|cm|gr|g|w|v|a|kw|ah|bar)\M)');
        IF m IS NOT NULL AND replace(m[3], ',', '.')::numeric > 0 THEN
            r.unite_base := CASE WHEN m[6] = 'kg' THEN 'KG' WHEN m[6] IN ('l', 'litre', 'litres') THEN 'L'
                                 WHEN m[6] IN ('m', 'ml', 'metre', 'metres') THEN 'M' WHEN m[6] = 'm2' THEN 'M2'
                                 ELSE 'U' END;
            r.qte := replace(m[3], ',', '.')::numeric;
            -- Une quantité de pièces est entière ; « sac de 2,5 » sans unité reste inconnu.
            IF r.unite_base <> 'U' OR r.qte = trunc(r.qte) THEN
                RETURN blueseatra.unite_offre_de(r.unite_base,
                           CASE m[1] WHEN 'boite' THEN 'BOITE' WHEN 'bte' THEN 'BOITE' WHEN 'sachet' THEN 'SAC'
                                     WHEN 'sac' THEN 'SAC' WHEN 'carton' THEN 'CARTON' WHEN 'bidon' THEN 'BIDON'
                                     WHEN 'rouleau' THEN 'ROULEAU' WHEN 'couronne' THEN 'ROULEAU'
                                     WHEN 'touret' THEN 'TOURET' ELSE 'LOT' END,
                           r.qte, 'OK');
            END IF;
        END IF;
        IF u = '' THEN
            RETURN blueseatra.unite_offre_de('U', 'UNITE', 1, 'SUPPOSEE');
        END IF;
        RETURN blueseatra.unite_offre_de('U', CASE u WHEN 'boite' THEN 'BOITE' WHEN 'sac' THEN 'SAC' WHEN 'sachet' THEN 'SAC'
                               WHEN 'sac-sachet' THEN 'SAC' WHEN 'sac sachet' THEN 'SAC'
                               WHEN 'carton' THEN 'CARTON' WHEN 'rouleau' THEN 'ROULEAU'
                               WHEN 'bidon' THEN 'BIDON' WHEN 'palette' THEN 'PALETTE' ELSE 'LOT' END,
                   1, 'INCONNUE');
    END IF;
    RETURN blueseatra.unite_offre_de(NULL, NULL, NULL, 'INCONNUE');
END $$;

-- Désignation propre : ponctuation de tête retirée (libellés amputés à la source,
-- « , D 350 H 1, blanc »), espaces réduits ; si amputée, préfixée par marque et réf.
CREATE OR REPLACE FUNCTION blueseatra.designation_propre(p_libelle text, p_marque text, p_ref text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
    SELECT CASE
        WHEN p_libelle IS NULL THEN NULL
        WHEN p_libelle ~ '^\s*[,;.:\-‐-―·•/|]' THEN
            nullif(btrim(concat_ws(' · ',
                nullif(btrim(concat_ws(' ', nullif(btrim(p_marque), ''), nullif(btrim(p_ref), ''))), ''),
                nullif(btrim(regexp_replace(regexp_replace(p_libelle, '^[\s,;.:\-‐-―·•/|]+', ''), '\s+', ' ', 'g')), ''))), '')
        ELSE btrim(regexp_replace(p_libelle, '\s+', ' ', 'g'))
    END
$$;

-- Prix numérique depuis le JSON source (« 14.4136 », « 14,41 »), NULL si illisible.
CREATE OR REPLACE FUNCTION blueseatra.prix_json(p_valeur text)
RETURNS numeric LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = '' AS $$
    SELECT CASE WHEN v ~ '^-?[0-9]+(\.[0-9]+)?$' THEN v::numeric END
      FROM (SELECT replace(btrim(coalesce(p_valeur, '')), ',', '.') AS v) s
$$;

-- ---------------------------------------------------------------------------
-- 2. Référentiel des marques (commun, sans données d'entreprise)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.marques (
    cle               text PRIMARY KEY,
    nom               text NOT NULL,
    est_distributeur  boolean NOT NULL DEFAULT false,
    nb_offres         integer NOT NULL DEFAULT 0,
    calcule_le        timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS blueseatra.marques_alias (
    alias       text PRIMARY KEY,
    cle         text NOT NULL,
    preuve_gtin integer NOT NULL,           -- nombre de GTIN partagés qui prouvent l'alias
    calcule_le  timestamptz NOT NULL DEFAULT now(),
    CHECK (alias <> cle)
);
COMMENT ON TABLE blueseatra.marques IS
  'Nom canonique par clé de marque (cle_marque). Recalculé par recalculer_marques().';
COMMENT ON TABLE blueseatra.marques_alias IS
  'Écritures d''une même marque prouvées par au moins 5 GTIN partagés. Une clé liée à plusieurs marques est un distributeur et n''est jamais fusionnée.';

-- ---------------------------------------------------------------------------
-- 3. Offres au format unique (1-1 avec supplier_offers)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.offres_normalisees (
    offre_id                 varchar PRIMARY KEY
                             REFERENCES blueseatra.supplier_offers(id) ON DELETE CASCADE,
    tenant_id                varchar NOT NULL,
    supplier_id              varchar,
    version_id               varchar,
    gtin                     varchar(14),
    gtin_rejete              text,
    marque_cle               text,
    marque                   text,
    ref_fabricant            text,
    ref_fabricant_cle        text,
    cle_mr                   text,           -- MR:<marque>:<réf>, même si un GTIN existe
    cle_produit              text,
    niveau_identification    varchar(12) NOT NULL,
    designation              text,
    unite_base               varchar(6),
    conditionnement          varchar(10),
    qte_par_conditionnement  numeric,
    unite_code               varchar(10) NOT NULL,
    prix_net_ht              numeric,
    prix_public_ht           numeric,
    prix_net_ht_unite_base   numeric,
    anomalies                text[] NOT NULL DEFAULT '{}',
    score_qualite            smallint NOT NULL DEFAULT 0,
    normalise_le             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_offres_norm_tenant_produit
    ON blueseatra.offres_normalisees (tenant_id, cle_produit) INCLUDE (prix_net_ht_unite_base, supplier_id);
CREATE INDEX IF NOT EXISTS idx_offres_norm_cle_mr
    ON blueseatra.offres_normalisees (tenant_id, cle_mr) WHERE cle_mr IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_offres_norm_version
    ON blueseatra.offres_normalisees (version_id);
COMMENT ON TABLE blueseatra.offres_normalisees IS
  'Format unique des offres fournisseurs (spécification 02/10/2026). Calculé depuis supplier_offers, jamais saisi à la main.';

-- Même cloisonnement que supplier_offers : chaque entreprise ne voit que ses offres,
-- plus la lecture du catalogue commun.
ALTER TABLE blueseatra.offres_normalisees ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS offres_normalisees_tenant ON blueseatra.offres_normalisees;
CREATE POLICY offres_normalisees_tenant ON blueseatra.offres_normalisees TO blueseatra_app
    USING (tenant_id = blueseatra.current_tenant())
    WITH CHECK (tenant_id = blueseatra.current_tenant());
DROP POLICY IF EXISTS offres_normalisees_commun ON blueseatra.offres_normalisees;
CREATE POLICY offres_normalisees_commun ON blueseatra.offres_normalisees FOR SELECT TO blueseatra_app
    USING (tenant_id = blueseatra.tenant_catalogue_commun());
GRANT SELECT, INSERT, UPDATE, DELETE ON blueseatra.offres_normalisees TO blueseatra_app;
GRANT SELECT ON blueseatra.marques, blueseatra.marques_alias TO blueseatra_app;

-- ---------------------------------------------------------------------------
-- 4. Calcul (une seule définition, réutilisée par l'import et par les lots)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW blueseatra.v_offres_format_unique
WITH (security_invoker = true) AS
SELECT o.id AS offre_id, o.tenant_id, o.supplier_id, o.version_id,
       g.gtin,
       CASE WHEN g.gtin IS NULL AND nullif(btrim(o.ean), '') IS NOT NULL THEN btrim(o.ean) END AS gtin_rejete,
       k.marque_cle,
       coalesce(mq.nom, nullif(btrim(o.brand), '')) AS marque,
       nullif(btrim(o.manufacturer_ref), '') AS ref_fabricant,
       k.ref_cle AS ref_fabricant_cle,
       CASE WHEN k.marque_cle IS NOT NULL AND k.ref_cle IS NOT NULL
            THEN 'MR:' || k.marque_cle || ':' || k.ref_cle END AS cle_mr,
       CASE WHEN g.gtin IS NOT NULL THEN 'GTIN:' || g.gtin
            WHEN k.marque_cle IS NOT NULL AND k.ref_cle IS NOT NULL
            THEN 'MR:' || k.marque_cle || ':' || k.ref_cle END AS cle_produit,
       CASE WHEN g.gtin IS NOT NULL THEN 'GTIN'
            WHEN k.marque_cle IS NOT NULL AND k.ref_cle IS NOT NULL THEN 'MARQUE_REF'
            ELSE 'AUCUN' END AS niveau_identification,
       blueseatra.designation_propre(o.raw_label, coalesce(mq.nom, o.brand),
                                     coalesce(nullif(btrim(o.manufacturer_ref), ''), o.raw_reference)) AS designation,
       (uu.u).unite_base, (uu.u).conditionnement, (uu.u).qte AS qte_par_conditionnement, (uu.u).code AS unite_code,
       p.prix_net, p.prix_public,
       CASE WHEN p.prix_net > 0 AND (uu.u).qte > 0 THEN round(p.prix_net / (uu.u).qte, 6) END AS prix_net_ht_unite_base,
       array_remove(ARRAY[
           CASE WHEN p.prix_net IS NULL OR p.prix_net <= 0 THEN 'SANS_PRIX' END,
           CASE WHEN p.prix_net > 0 AND (p.prix_net < 0.01 OR p.prix_net > 50000) THEN 'PRIX_EXTREME' END,
           CASE WHEN p.prix_net > 0 AND p.prix_public > 0 AND p.prix_net > p.prix_public * 1.001 THEN 'PRIX_NET_SUP_PUBLIC' END,
           CASE WHEN g.gtin IS NULL AND nullif(btrim(o.ean), '') IS NOT NULL THEN 'GTIN_CLE' END,
           CASE WHEN o.raw_label ~ '^\s*[,;.:\-‐-―·•/|]' THEN 'DESIGNATION_AMPUTEE' END,
           CASE WHEN (uu.u).code = 'INCONNUE' THEN 'UNITE_INCONNUE' END,
           CASE WHEN (uu.u).code = 'SUPPOSEE' THEN 'UNITE_SUPPOSEE' END
       ], NULL) AS anomalies,
       (CASE WHEN g.gtin IS NOT NULL THEN 30 ELSE 0 END
        + CASE WHEN k.marque_cle IS NOT NULL AND k.ref_cle IS NOT NULL THEN 25 ELSE 0 END
        + CASE (uu.u).code WHEN 'OK' THEN 15 WHEN 'SUPPOSEE' THEN 5 ELSE 0 END
        + CASE WHEN p.prix_net > 0 THEN 15 ELSE 0 END
        + CASE WHEN nullif(o.raw_row ->> 'famille', '') IS NOT NULL THEN 5 ELSE 0 END)::smallint AS score_qualite
  FROM blueseatra.supplier_offers o
  CROSS JOIN LATERAL (SELECT blueseatra.gtin14(o.ean) AS gtin) g
  CROSS JOIN LATERAL (SELECT blueseatra.cle_marque(o.brand) AS marque_brute,
                             blueseatra.cle_reference(o.manufacturer_ref) AS ref_cle) kb
  LEFT JOIN blueseatra.marques_alias al ON al.alias = kb.marque_brute
  CROSS JOIN LATERAL (SELECT coalesce(al.cle, kb.marque_brute) AS marque_cle, kb.ref_cle) k
  LEFT JOIN blueseatra.marques mq ON mq.cle = k.marque_cle
  CROSS JOIN LATERAL (SELECT blueseatra.unite_normalisee(o.raw_unit, o.raw_label) AS u) uu
  CROSS JOIN LATERAL (SELECT CASE WHEN o.price_ht > 0 THEN o.price_ht::numeric END AS prix_net,
                             blueseatra.prix_json(o.raw_row ->> 'prix_public_ht') AS prix_public) p;

GRANT SELECT ON blueseatra.v_offres_format_unique TO blueseatra_app;

-- Écrit (ou réécrit) les offres demandées. Renvoie le nombre de lignes écrites.
CREATE OR REPLACE FUNCTION blueseatra.normaliser_offres_ids(p_ids varchar[])
RETURNS integer LANGUAGE plpgsql SET search_path = '' AS $$
DECLARE n integer;
BEGIN
    INSERT INTO blueseatra.offres_normalisees AS t (
        offre_id, tenant_id, supplier_id, version_id, gtin, gtin_rejete, marque_cle, marque,
        ref_fabricant, ref_fabricant_cle, cle_mr, cle_produit, niveau_identification, designation,
        unite_base, conditionnement, qte_par_conditionnement, unite_code, prix_net_ht, prix_public_ht,
        prix_net_ht_unite_base, anomalies, score_qualite, normalise_le)
    SELECT v.offre_id, v.tenant_id, v.supplier_id, v.version_id, v.gtin, v.gtin_rejete, v.marque_cle, v.marque,
           v.ref_fabricant, v.ref_fabricant_cle, v.cle_mr, v.cle_produit, v.niveau_identification, v.designation,
           v.unite_base, v.conditionnement, v.qte_par_conditionnement, v.unite_code, v.prix_net, v.prix_public,
           v.prix_net_ht_unite_base, v.anomalies, v.score_qualite, now()
      FROM blueseatra.v_offres_format_unique v
     WHERE v.offre_id = ANY (p_ids)
    ON CONFLICT (offre_id) DO UPDATE SET
        tenant_id = EXCLUDED.tenant_id, supplier_id = EXCLUDED.supplier_id, version_id = EXCLUDED.version_id,
        gtin = EXCLUDED.gtin, gtin_rejete = EXCLUDED.gtin_rejete, marque_cle = EXCLUDED.marque_cle,
        marque = EXCLUDED.marque, ref_fabricant = EXCLUDED.ref_fabricant,
        ref_fabricant_cle = EXCLUDED.ref_fabricant_cle, cle_mr = EXCLUDED.cle_mr,
        cle_produit = EXCLUDED.cle_produit, niveau_identification = EXCLUDED.niveau_identification,
        designation = EXCLUDED.designation, unite_base = EXCLUDED.unite_base,
        conditionnement = EXCLUDED.conditionnement, qte_par_conditionnement = EXCLUDED.qte_par_conditionnement,
        unite_code = EXCLUDED.unite_code, prix_net_ht = EXCLUDED.prix_net_ht,
        prix_public_ht = EXCLUDED.prix_public_ht, prix_net_ht_unite_base = EXCLUDED.prix_net_ht_unite_base,
        anomalies = EXCLUDED.anomalies, score_qualite = EXCLUDED.score_qualite, normalise_le = now();
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;

-- Calcul initial ou rattrapage, par lots : une version, découpée en p_modulo parts.
CREATE OR REPLACE FUNCTION blueseatra.normaliser_offres_lot(p_version varchar, p_modulo integer DEFAULT 1,
                                                            p_reste integer DEFAULT 0)
RETURNS integer LANGUAGE sql SET search_path = '' AS $$
    SELECT blueseatra.normaliser_offres_ids(ARRAY(
        SELECT o.id FROM blueseatra.supplier_offers o
         WHERE o.version_id IS NOT DISTINCT FROM p_version
           AND (p_modulo <= 1 OR abs(hashtext(o.id)) % p_modulo = p_reste)))
$$;

-- Normalisation automatique à l'import. Une erreur ne bloque jamais l'import.
CREATE OR REPLACE FUNCTION blueseatra.tg_normaliser_offres()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    BEGIN
        PERFORM blueseatra.normaliser_offres_ids(ARRAY(SELECT n.id FROM nouvelles n));
    EXCEPTION WHEN OTHERS THEN
        RAISE WARNING 'normalisation des offres différée (%): %', SQLSTATE, SQLERRM;
    END;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS normaliser_offres_insert ON blueseatra.supplier_offers;
CREATE TRIGGER normaliser_offres_insert AFTER INSERT ON blueseatra.supplier_offers
    REFERENCING NEW TABLE AS nouvelles FOR EACH STATEMENT
    EXECUTE FUNCTION blueseatra.tg_normaliser_offres();
DROP TRIGGER IF EXISTS normaliser_offres_update ON blueseatra.supplier_offers;
CREATE TRIGGER normaliser_offres_update AFTER UPDATE ON blueseatra.supplier_offers
    REFERENCING NEW TABLE AS nouvelles FOR EACH STATEMENT
    EXECUTE FUNCTION blueseatra.tg_normaliser_offres();

-- ---------------------------------------------------------------------------
-- 5. Marques : noms canoniques et alias prouvés par les GTIN
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION blueseatra.recalculer_marques()
RETURNS jsonb LANGUAGE plpgsql SET search_path = '' AS $$
DECLARE n_marques integer; n_alias integer; n_distrib integer;
BEGIN
    -- Nom canonique : l'écriture la plus fréquente, en préférant une écriture qui
    -- n'est pas tout en majuscules (« Legrand » plutôt que « LEGRAND »).
    CREATE TEMP TABLE _ecritures ON COMMIT DROP AS
        SELECT blueseatra.cle_marque(o.brand) AS cle, btrim(o.brand) AS ecriture, count(*) AS n
          FROM blueseatra.supplier_offers o
         WHERE o.is_active AND nullif(btrim(o.brand), '') IS NOT NULL
         GROUP BY 1, 2;
    DELETE FROM _ecritures WHERE cle IS NULL;

    CREATE TEMP TABLE _paires ON COMMIT DROP AS
        WITH g AS (
            SELECT blueseatra.gtin14(o.ean) AS gtin, blueseatra.cle_marque(o.brand) AS cle
              FROM blueseatra.supplier_offers o
             WHERE o.is_active AND o.ean IS NOT NULL AND nullif(btrim(o.brand), '') IS NOT NULL
        ), d AS (
            SELECT DISTINCT gtin, cle FROM g WHERE gtin IS NOT NULL AND cle IS NOT NULL
        )
        SELECT a.cle AS a, b.cle AS b, count(*) AS n
          FROM d a JOIN d b ON a.gtin = b.gtin AND a.cle < b.cle
         GROUP BY 1, 2 HAVING count(*) >= 5;

    -- Distributeur : clé reliée à au moins 2 marques différentes.
    CREATE TEMP TABLE _distrib ON COMMIT DROP AS
        SELECT cle FROM (SELECT a AS cle FROM _paires UNION ALL SELECT b FROM _paires) x
         GROUP BY cle HAVING count(*) >= 2;

    TRUNCATE blueseatra.marques_alias;
    INSERT INTO blueseatra.marques_alias (alias, cle, preuve_gtin)
    SELECT CASE WHEN na.n >= nb.n THEN p.b ELSE p.a END,
           CASE WHEN na.n >= nb.n THEN p.a ELSE p.b END, p.n
      FROM _paires p
      JOIN (SELECT cle, sum(n) n FROM _ecritures GROUP BY cle) na ON na.cle = p.a
      JOIN (SELECT cle, sum(n) n FROM _ecritures GROUP BY cle) nb ON nb.cle = p.b
     WHERE p.a NOT IN (SELECT cle FROM _distrib) AND p.b NOT IN (SELECT cle FROM _distrib);
    GET DIAGNOSTICS n_alias = ROW_COUNT;

    TRUNCATE blueseatra.marques;
    INSERT INTO blueseatra.marques (cle, nom, est_distributeur, nb_offres)
    SELECT DISTINCT ON (coalesce(al.cle, e.cle))
           coalesce(al.cle, e.cle), e.ecriture,
           coalesce(al.cle, e.cle) IN (SELECT cle FROM _distrib),
           sum(e.n) OVER (PARTITION BY coalesce(al.cle, e.cle))
      FROM _ecritures e
      LEFT JOIN blueseatra.marques_alias al ON al.alias = e.cle
     ORDER BY coalesce(al.cle, e.cle), (e.ecriture ~ '[a-z]') DESC, e.n DESC, e.ecriture;
    GET DIAGNOSTICS n_marques = ROW_COUNT;
    SELECT count(*) INTO n_distrib FROM blueseatra.marques WHERE est_distributeur;
    RETURN jsonb_build_object('marques', n_marques, 'alias', n_alias, 'distributeurs', n_distrib);
END $$;

-- ---------------------------------------------------------------------------
-- 6. Produits : rattachement par marque + référence, écarts de prix
-- ---------------------------------------------------------------------------
-- Une offre sans GTIN rejoint le produit GTIN qui porte la même marque et la même
-- référence, si ce GTIN est unique pour cette clé (sinon elle garde sa clé MR).
-- Puis une offre à plus de 3 fois le prix médian de son produit est signalée.
CREATE OR REPLACE FUNCTION blueseatra.rattacher_produits(p_tenant varchar)
RETURNS jsonb LANGUAGE plpgsql SET search_path = '' AS $$
DECLARE n_rattache integer; n_ecart integer;
BEGIN
    UPDATE blueseatra.offres_normalisees t
       SET cle_produit = g.cle_produit, niveau_identification = 'MARQUE_REF', normalise_le = now()
      FROM (SELECT cle_mr, min(cle_produit) AS cle_produit
              FROM blueseatra.offres_normalisees
             WHERE tenant_id = p_tenant AND gtin IS NOT NULL AND cle_mr IS NOT NULL
             GROUP BY cle_mr HAVING count(DISTINCT gtin) = 1) g
     WHERE t.tenant_id = p_tenant AND t.gtin IS NULL AND t.cle_mr = g.cle_mr
       AND t.cle_produit IS DISTINCT FROM g.cle_produit;
    GET DIAGNOSTICS n_rattache = ROW_COUNT;

    UPDATE blueseatra.offres_normalisees t
       SET anomalies = CASE WHEN t.prix_net_ht_unite_base > 3 * m.mediane
                            THEN array_append(array_remove(t.anomalies, 'ECART_PRIX_PRODUIT'), 'ECART_PRIX_PRODUIT')
                            ELSE array_remove(t.anomalies, 'ECART_PRIX_PRODUIT') END
      FROM (SELECT cle_produit, unite_base,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_net_ht_unite_base) AS mediane
              FROM blueseatra.offres_normalisees
             WHERE tenant_id = p_tenant AND cle_produit IS NOT NULL AND prix_net_ht_unite_base > 0
             GROUP BY cle_produit, unite_base HAVING count(DISTINCT supplier_id) >= 2) m
     WHERE t.tenant_id = p_tenant AND t.cle_produit = m.cle_produit AND t.unite_base = m.unite_base
       AND (t.prix_net_ht_unite_base > 3 * m.mediane) <> ('ECART_PRIX_PRODUIT' = ANY (t.anomalies));
    GET DIAGNOSTICS n_ecart = ROW_COUNT;
    RETURN jsonb_build_object('rattachees', n_rattache, 'ecarts_mis_a_jour', n_ecart);
END $$;

REVOKE ALL ON FUNCTION blueseatra.recalculer_marques() FROM PUBLIC;
REVOKE ALL ON FUNCTION blueseatra.rattacher_produits(varchar) FROM PUBLIC;
REVOKE ALL ON FUNCTION blueseatra.normaliser_offres_lot(varchar, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION blueseatra.normaliser_offres_ids(varchar[]) TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.tg_normaliser_offres() TO blueseatra_app;
GRANT EXECUTE ON FUNCTION blueseatra.unite_offre_de(text, text, numeric, text), blueseatra.gtin14(text), blueseatra.cle_marque(text), blueseatra.cle_reference(text),
                          blueseatra.unite_normalisee(text, text), blueseatra.designation_propre(text, text, text),
                          blueseatra.prix_json(text) TO blueseatra_app;

-- ---------------------------------------------------------------------------
-- 7. Contrôles
-- ---------------------------------------------------------------------------
DO $$
DECLARE u blueseatra.unite_offre;
BEGIN
    IF blueseatra.gtin14('3245060343880') <> '03245060343880' OR blueseatra.gtin14('3245060343881') IS NOT NULL
       OR blueseatra.gtin14('00000000') IS NOT NULL THEN
        RAISE EXCEPTION 'gtin14 : clé GS1 mal calculée';
    END IF;
    IF blueseatra.cle_marque('LEGRAND S.N.C.') <> 'legrand' OR blueseatra.cle_marque('Hager SAS') <> 'hager'
       OR blueseatra.cle_marque('Schneider Electric France') <> 'schneiderelectric' THEN
        RAISE EXCEPTION 'cle_marque : formes juridiques mal retirées';
    END IF;
    IF blueseatra.cle_reference('034388') <> '34388' OR blueseatra.cle_reference('a-1') IS NOT NULL THEN
        RAISE EXCEPTION 'cle_reference incorrecte';
    END IF;
    u := blueseatra.unite_normalisee('100', 'Conduit ICA 3321');
    IF u.unite_base <> 'U' OR u.qte <> 100 THEN RAISE EXCEPTION 'unité « 100 » mal lue'; END IF;
    u := blueseatra.unite_normalisee('Boîte de 100', NULL);
    IF u.conditionnement <> 'BOITE' OR u.qte <> 100 THEN RAISE EXCEPTION 'unité « Boîte de 100 » mal lue'; END IF;
    u := blueseatra.unite_normalisee('Mètre carré', NULL);
    IF u.unite_base <> 'M2' THEN RAISE EXCEPTION 'unité « Mètre carré » mal lue'; END IF;
    u := blueseatra.unite_normalisee(NULL, 'Vis bois tête fraisée - boite de 200');
    IF u.qte <> 200 OR u.code <> 'OK' THEN RAISE EXCEPTION 'quantité de la désignation mal lue'; END IF;
    u := blueseatra.unite_normalisee('Sac-sachet', 'Enduit monocouche WEBERPRAL GF sac de 25 kg');
    IF u.unite_base <> 'KG' OR u.qte <> 25 THEN RAISE EXCEPTION 'sac de 25 kg mal lu'; END IF;
    u := blueseatra.unite_normalisee('sac', 'Laine de verre Comblissimo sac de 17,3kg');
    IF u.unite_base <> 'KG' OR u.qte <> 17.3 THEN RAISE EXCEPTION 'sac de 17,3kg mal lu'; END IF;
    u := blueseatra.unite_normalisee('sac', 'Griffe REPARPLAC sachet de 28 pièces');
    IF u.unite_base <> 'U' OR u.qte <> 28 THEN RAISE EXCEPTION 'sachet de 28 pièces mal lu'; END IF;
    u := blueseatra.unite_normalisee('boite', 'Boîte de 100 vis 4x40');
    IF u.unite_base <> 'U' OR u.qte <> 100 THEN RAISE EXCEPTION 'boîte de 100 vis mal lue'; END IF;
    u := blueseatra.unite_normalisee('boite', 'Carrelage grès cérame PARADE 60 x 60 - boîte de 1,08 m²');
    IF u.unite_base <> 'M2' OR u.qte <> 1.08 THEN RAISE EXCEPTION 'boîte de 1,08 m² mal lue'; END IF;
    u := blueseatra.unite_normalisee('1000', 'YSLY-JZ 3G1 C100');
    IF u.unite_base <> 'M' OR u.qte <> 1000 THEN RAISE EXCEPTION 'câble au 1000 m mal lu'; END IF;
    u := blueseatra.unite_normalisee(NULL, 'Disjoncteur 16A');
    IF u.code <> 'SUPPOSEE' THEN RAISE EXCEPTION 'unité absente : pièce supposée attendue'; END IF;
    IF blueseatra.designation_propre(', D 350 H 1, blanc', 'RZB', '982552.002') <> 'RZB 982552.002 · D 350 H 1, blanc' THEN
        RAISE EXCEPTION 'designation_propre incorrecte';
    END IF;
END $$;
