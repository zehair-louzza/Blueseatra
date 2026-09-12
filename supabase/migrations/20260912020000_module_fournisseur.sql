-- ============================================================================
-- ATTENTION -- MIGRATION NON ENCORE APPLIQUEE EN PRODUCTION
-- ============================================================================
--
-- Corrigee le 12/09/2026 : les politiques ciblaient uniquement
-- `authenticated`. Or blueseatra_app a ete RETIRE de ce role le meme jour
-- (migration 20260912060000) pour fermer une faille : il heritait par ce
-- biais d'un CRUD complet sur tenant_users.
--
-- Appliquer cette migration dans sa version d'origine aurait rendu les 5
-- tables du module fournisseur INVISIBLES au chemin metier : zero ligne,
-- sans erreur, exactement le mode de defaillance qui a coute trois pannes
-- cette nuit-la. Les politiques ciblent donc desormais `authenticated,
-- blueseatra_app`.
--
-- Rappel du role de chaque cible :
--   authenticated   -> chemin PostgREST (utilisateur JWT cote Supabase)
--   blueseatra_app  -> chemin metier de l'API (moteur DATABASE_URL_APP)
--   service_role    -> ecritures sur les tables mutualisees, admin seul
--
-- ============================================================================

-- ============================================================================
-- Module Fournisseur — BlueSeaTra
-- fournisseur.blueseatra.com
--
-- Cree les 5 tables du module de normalisation des catalogues fournisseurs.
--
-- CONVENTIONS RESPECTEES (verifiees sur le schema existant le 12/09/2026) :
--   - schema           : blueseatra (PAS public)
--   - identifiants     : varchar(36), sans DEFAULT (generes par new_id() cote app)
--   - tenant_id        : varchar(36) NOT NULL sur les tables de donnees
--   - champs dynamiques: jsonb
--   - RLS              : (tenant_id)::text = blueseatra.current_tenant()
--
-- MODELE DE CONFIDENTIALITE (decision produit du 12/09/2026) :
--   - Les PRIX sont strictement cloisonnes par tenant. Un tarif negocie ne
--     doit jamais etre visible par un autre client.
--   - Les REGLES de normalisation (equivalences de libelles, conversions
--     d'unites) sont des faits metier, pas des donnees client. Elles sont
--     donc GLOBALES et mutualisees : chaque arbitrage humain enrichit le
--     referentiel pour tous. C'est l'actif cumulatif du module.
--
--   => suppliers / canonical_products / supplier_offers : PAR TENANT
--   => product_match_rules / unit_conversions           : GLOBALES
--
-- `pricing_items` n'est PAS modifiee : elle reste la couche des "prix
-- retenus" consommee par le moteur de devis et par blueseatra_search_catalog.
-- Le module l'alimente par projection. Aucune rupture pour l'existant.
-- ============================================================================

SET search_path TO blueseatra, public;


-- ----------------------------------------------------------------------------
-- 1. suppliers — les enseignes du tenant (Rexel, Point.P, AFDB, ...)
-- ----------------------------------------------------------------------------
-- Porte les conditions commerciales necessaires au calcul du COUT RENDU
-- CHANTIER, qui est le seul indicateur de decision pertinent : le prix
-- unitaire le moins cher est presque toujours trompeur une fois le franco
-- de port, le conditionnement impose et le delai pris en compte.
CREATE TABLE IF NOT EXISTS blueseatra.suppliers (
    id                  varchar(36)  PRIMARY KEY,
    tenant_id           varchar(36)  NOT NULL,
    name                varchar(200) NOT NULL,
    slug                varchar(120),
    website             text,
    -- Seuil de franco de port HT. Souvent 300-500 EUR chez les distributeurs
    -- pro : ignorer ce seuil fausse toute comparaison multi-fournisseurs.
    franco_ht           double precision,
    shipping_cost_ht    double precision,
    -- Remises negociees par famille : {"cables": 0.32, "appareillage": 0.25}
    discount_rules      jsonb        NOT NULL DEFAULT '{}'::jsonb,
    default_delay       varchar(60),
    agencies            jsonb        NOT NULL DEFAULT '[]'::jsonb,
    notes               text,
    is_active           boolean      NOT NULL DEFAULT true,
    created_at          timestamptz  NOT NULL DEFAULT now(),
    updated_at          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT suppliers_tenant_name_uniq UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_suppliers_tenant        ON blueseatra.suppliers (tenant_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_tenant_active ON blueseatra.suppliers (tenant_id, is_active);


-- ----------------------------------------------------------------------------
-- 2. canonical_products — le produit unique, cible du rapprochement
-- ----------------------------------------------------------------------------
-- Par tenant : le referentiel produit d'un client lui appartient, il reflete
-- son metier et ses habitudes d'achat.
CREATE TABLE IF NOT EXISTS blueseatra.canonical_products (
    id                  varchar(36)  PRIMARY KEY,
    tenant_id           varchar(36)  NOT NULL,
    label               text         NOT NULL,
    -- Libelle normalise (minuscules, sans accents, tokens tries).
    -- Meme convention que pricing_items.label_norm, produit par
    -- matching.normalize() pour rester coherent avec le moteur existant.
    label_norm          text         NOT NULL,
    lot                 varchar(120),
    family              varchar(120),
    brand               varchar(120),
    manufacturer_ref    varchar(120),
    ean                 varchar(20),
    -- Unite canonique de reference (u, ml, m2, ens, kg...). Tous les prix du
    -- produit sont ramenes a CETTE unite avant comparaison.
    unit_canonical      varchar(40)  NOT NULL,
    -- Attributs discriminants : {"section":"3G2.5","ip":"IP44","couleur":"blanc"}
    -- Deux produits ne sont identiques que si ces attributs coincident.
    attributes          jsonb        NOT NULL DEFAULT '{}'::jsonb,
    -- Sous-ensemble des cles d'`attributes` qui font foi pour l'identite.
    key_attributes      jsonb        NOT NULL DEFAULT '[]'::jsonb,
    created_at          timestamptz  NOT NULL DEFAULT now(),
    updated_at          timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_canonical_tenant        ON blueseatra.canonical_products (tenant_id);
CREATE INDEX IF NOT EXISTS idx_canonical_tenant_norm   ON blueseatra.canonical_products (tenant_id, label_norm);
CREATE INDEX IF NOT EXISTS idx_canonical_tenant_family ON blueseatra.canonical_products (tenant_id, family);
CREATE INDEX IF NOT EXISTS idx_canonical_ean           ON blueseatra.canonical_products (tenant_id, ean)
    WHERE ean IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_canonical_attributes    ON blueseatra.canonical_products USING gin (attributes);


-- ----------------------------------------------------------------------------
-- 3. supplier_offers — une ligne = une offre brute lue dans un fichier
-- ----------------------------------------------------------------------------
-- Le coeur du module. Conserve TOUJOURS la donnee brute a cote de la donnee
-- normalisee : sans le libelle d'origine, un rapprochement est indefendable
-- face a un client qui conteste un prix.
--
-- Rattachee a catalog_versions : chaque import horodate cree une version, on
-- n'ECRASE JAMAIS un import. C'est ce qui construit gratuitement l'historique
-- de prix (detection des hausses, indexation, levier de negociation) sans
-- ecrire une seule table supplementaire aujourd'hui.
CREATE TABLE IF NOT EXISTS blueseatra.supplier_offers (
    id                  varchar(36)  PRIMARY KEY,
    tenant_id           varchar(36)  NOT NULL,
    supplier_id         varchar(36)  NOT NULL,
    catalog_id          varchar(36),
    version_id          varchar(36),

    -- ---- donnee BRUTE, jamais modifiee ----
    raw_label           text         NOT NULL,
    raw_reference       varchar(160),
    raw_unit            varchar(60),
    raw_row             jsonb,          -- ligne source complete, pour audit

    -- ---- donnee NORMALISEE ----
    label_norm          text,
    brand               varchar(120),
    manufacturer_ref    varchar(120),
    ean                 varchar(20),
    unit_canonical      varchar(40),
    -- Quantite contenue dans un conditionnement : une couronne de cable
    -- U1000R2V = 100 ml. Un besoin de 120 ml impose donc 2 couronnes.
    -- Ignorer cette colonne rend toute comparaison de prix fausse.
    packaging_qty       double precision NOT NULL DEFAULT 1,
    min_qty             double precision,

    -- ---- prix ----
    price_ht            double precision,   -- prix du conditionnement vendu
    -- Prix ramene a l'unite canonique = seule valeur comparable entre enseignes.
    price_ht_per_unit   double precision,
    currency            varchar(8)   NOT NULL DEFAULT 'EUR',
    vat_rate            double precision,
    discount_applied    double precision,

    -- ---- disponibilite ----
    delay               varchar(60),
    availability        varchar(60),

    -- ---- tracabilite de la source (obligatoire) ----
    product_url         text,
    -- Date de validite du tarif. Un devis engage contractuellement : inserer
    -- un prix vieux de 5 mois dans un devis signe, c'est de la marge perdue
    -- en argent reel. L'UI doit afficher cette date et bloquer au-dela d'un
    -- seuil parametrable par tenant.
    source_date         date,
    source_filename     text,

    -- ---- rapprochement ----
    canonical_product_id varchar(36),
    -- matched   : rapproche automatiquement, confiance haute
    -- proposed  : propose, EN ATTENTE d'arbitrage humain (jamais applique)
    -- to_confirm: sous le seuil, a trancher
    -- orphan    : aucun rapprochement. Un orphelin VISIBLE vaut mieux qu'un
    --             faux rapprochement silencieux.
    -- rejected  : un humain a explicitement dit "ce n'est pas le meme produit"
    match_status        varchar(20)  NOT NULL DEFAULT 'orphan',
    match_confidence    integer,
    match_rule_id       varchar(36),
    -- Motifs lisibles, meme format que backend/matching.py :
    -- ["exact_ref(+70)", "unit_compatible(+20)"]. Un score sans explication
    -- n'est pas auditable.
    match_reasons       jsonb        NOT NULL DEFAULT '[]'::jsonb,
    matched_at          timestamptz,
    matched_by          varchar(120),

    is_active           boolean      NOT NULL DEFAULT true,
    created_at          timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT supplier_offers_match_status_chk CHECK (
        match_status IN ('matched','proposed','to_confirm','orphan','rejected')
    ),
    CONSTRAINT supplier_offers_confidence_chk CHECK (
        match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 100)
    ),
    CONSTRAINT supplier_offers_packaging_chk CHECK (packaging_qty > 0),
    CONSTRAINT supplier_offers_supplier_fk FOREIGN KEY (supplier_id)
        REFERENCES blueseatra.suppliers (id) ON DELETE CASCADE,
    -- ON DELETE SET NULL : supprimer un produit canonique ne doit JAMAIS
    -- detruire une offre. L'offre redevient orpheline et repasse en file
    -- de resolution.
    CONSTRAINT supplier_offers_canonical_fk FOREIGN KEY (canonical_product_id)
        REFERENCES blueseatra.canonical_products (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_offers_tenant           ON blueseatra.supplier_offers (tenant_id);
CREATE INDEX IF NOT EXISTS idx_offers_tenant_canonical ON blueseatra.supplier_offers (tenant_id, canonical_product_id);
CREATE INDEX IF NOT EXISTS idx_offers_tenant_supplier  ON blueseatra.supplier_offers (tenant_id, supplier_id);
CREATE INDEX IF NOT EXISTS idx_offers_tenant_version   ON blueseatra.supplier_offers (tenant_id, version_id);
-- Index partiel : la file de resolution humaine est l'ecran le plus consulte
-- du module, elle ne doit jamais faire de scan complet.
CREATE INDEX IF NOT EXISTS idx_offers_resolution_queue ON blueseatra.supplier_offers (tenant_id, match_status)
    WHERE match_status IN ('proposed','to_confirm','orphan');
CREATE INDEX IF NOT EXISTS idx_offers_ref              ON blueseatra.supplier_offers (tenant_id, manufacturer_ref)
    WHERE manufacturer_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_offers_ean              ON blueseatra.supplier_offers (tenant_id, ean)
    WHERE ean IS NOT NULL;
-- Recherche du meilleur prix : tri sur le prix ramene a l'unite canonique.
CREATE INDEX IF NOT EXISTS idx_offers_best_price       ON blueseatra.supplier_offers (tenant_id, canonical_product_id, price_ht_per_unit)
    WHERE is_active AND price_ht_per_unit IS NOT NULL;


-- ----------------------------------------------------------------------------
-- 4. product_match_rules — GLOBALE, mutualisee
-- ----------------------------------------------------------------------------
-- PAS de tenant_id : c'est volontaire et c'est le coeur de la strategie.
-- Ces regles sont des faits metier ("U1000R2V 3G2.5" == "U1000 R2V 3x2,5mm2"),
-- pas des donnees client. Chaque arbitrage humain, chez n'importe quel tenant,
-- enrichit le referentiel de tous. Aucun prix, aucun nom de client, aucune
-- remise n'y transite : mutualiser est donc sans risque contractuel.
--
-- C'est le seul design ou le systeme s'ameliore avec l'usage, et l'actif que
-- personne ne peut copier.
CREATE TABLE IF NOT EXISTS blueseatra.product_match_rules (
    id                  varchar(36)  PRIMARY KEY,
    -- exact_ref | ean | attributes | label_pattern | alias
    rule_type           varchar(30)  NOT NULL,
    -- Motif reconnu (libelle normalise, reference, regex simple).
    pattern             text         NOT NULL,
    -- Forme canonique cible. On stocke la CLE METIER (libelle normalise +
    -- attributs), jamais un canonical_product_id : celui-ci est propre a un
    -- tenant et n'aurait aucun sens ailleurs.
    target_label_norm   text         NOT NULL,
    target_attributes   jsonb        NOT NULL DEFAULT '{}'::jsonb,
    brand               varchar(120),
    family              varchar(120),
    unit_canonical      varchar(40),
    confidence          integer      NOT NULL DEFAULT 100,
    -- manual : tranche par un humain (fait foi)
    -- auto   : deduit par le moteur
    -- seed   : charge au demarrage
    origin              varchar(20)  NOT NULL DEFAULT 'manual',
    -- Compteurs d'usage : permettent de retirer une regle qui produit des
    -- rapprochements systematiquement rejetes ensuite.
    hit_count           integer      NOT NULL DEFAULT 0,
    reject_count        integer      NOT NULL DEFAULT 0,
    is_active           boolean      NOT NULL DEFAULT true,
    created_at          timestamptz  NOT NULL DEFAULT now(),
    updated_at          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT match_rules_type_chk CHECK (
        rule_type IN ('exact_ref','ean','attributes','label_pattern','alias')
    ),
    CONSTRAINT match_rules_origin_chk CHECK (origin IN ('manual','auto','seed')),
    CONSTRAINT match_rules_confidence_chk CHECK (confidence >= 0 AND confidence <= 100),
    CONSTRAINT match_rules_uniq UNIQUE (rule_type, pattern, target_label_norm)
);

CREATE INDEX IF NOT EXISTS idx_rules_lookup ON blueseatra.product_match_rules (rule_type, pattern)
    WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_rules_target ON blueseatra.product_match_rules (target_label_norm);


-- ----------------------------------------------------------------------------
-- 5. unit_conversions — GLOBALE, mutualisee
-- ----------------------------------------------------------------------------
-- Egalement sans tenant_id : "une couronne de cable fait 100 ml" est un fait
-- universel. Sans cette table, TOUTE comparaison de prix est fausse, et c'est
-- l'erreur la plus couteuse et la plus discrete du domaine.
CREATE TABLE IF NOT EXISTS blueseatra.unit_conversions (
    id                  varchar(36)  PRIMARY KEY,
    raw_unit            varchar(60)  NOT NULL,   -- "couronne", "cout.", "ml", "boite"
    unit_canonical      varchar(40)  NOT NULL,   -- "ml", "u", "m2"
    factor              double precision NOT NULL,  -- 1 raw_unit = factor x unit_canonical
    family              varchar(120),            -- contexte (ex. cables) si ambigu
    notes               text,
    created_at          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT unit_conv_factor_chk CHECK (factor > 0),
    CONSTRAINT unit_conv_uniq UNIQUE (raw_unit, unit_canonical, family)
);

CREATE INDEX IF NOT EXISTS idx_unit_conv_raw ON blueseatra.unit_conversions (raw_unit);


-- ============================================================================
-- RLS
-- ============================================================================
-- AVERTISSEMENT IMPORTANT (audit du 12/09/2026) :
-- blueseatra.current_tenant() lit `request.jwt.claims`, qui est renseigne par
-- l'API REST/PostgREST de Supabase -- PAS par la connexion asyncpg directe du
-- backend. Sur cette connexion, current_tenant() renvoie NULL et le role
-- privilegie CONTOURNE de toute facon RLS (relforcerowsecurity = false).
--
-- Ces politiques protegent donc les acces via l'API Supabase, mais NE sont PAS
-- la ligne de defense du backend. Pour le backend, l'isolation repose sur les
-- filtres `WHERE tenant_id = ...` du code applicatif.
--
-- L'audit de server.py (114 appels analyses) n'a releve AUCUNE fuite : le motif
-- "verifier l'appartenance puis muter par id" est respecte partout. Mais un
-- seul oubli dans une future PR rouvrirait le trou en silence.
-- Voir la section DURCISSEMENT en fin de fichier.
-- ============================================================================

-- ---- Tables PAR TENANT : cloisonnement strict ----
ALTER TABLE blueseatra.suppliers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE blueseatra.canonical_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE blueseatra.supplier_offers    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS suppliers_all ON blueseatra.suppliers;
CREATE POLICY suppliers_all ON blueseatra.suppliers
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());

DROP POLICY IF EXISTS canonical_products_all ON blueseatra.canonical_products;
CREATE POLICY canonical_products_all ON blueseatra.canonical_products
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());

DROP POLICY IF EXISTS supplier_offers_all ON blueseatra.supplier_offers;
CREATE POLICY supplier_offers_all ON blueseatra.supplier_offers
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());


-- ---- Tables GLOBALES : lecture pour tous, ecriture reservee ----
-- Un tenant peut LIRE les regles mutualisees (c'est l'interet), mais ne peut
-- pas les ecrire directement : sinon un client pourrait empoisonner le
-- referentiel de tous les autres. L'ecriture passe par le backend, qui valide
-- l'arbitrage avant de le promouvoir en regle.
ALTER TABLE blueseatra.product_match_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE blueseatra.unit_conversions    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS match_rules_read ON blueseatra.product_match_rules;
CREATE POLICY match_rules_read ON blueseatra.product_match_rules
    FOR SELECT TO authenticated, blueseatra_app USING (true);

DROP POLICY IF EXISTS match_rules_write_service ON blueseatra.product_match_rules;
CREATE POLICY match_rules_write_service ON blueseatra.product_match_rules
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS unit_conv_read ON blueseatra.unit_conversions;
CREATE POLICY unit_conv_read ON blueseatra.unit_conversions
    FOR SELECT TO authenticated, blueseatra_app USING (true);

DROP POLICY IF EXISTS unit_conv_write_service ON blueseatra.unit_conversions;
CREATE POLICY unit_conv_write_service ON blueseatra.unit_conversions
    FOR ALL TO service_role USING (true) WITH CHECK (true);


-- ============================================================================
-- Vue : meilleur prix par produit canonique
-- ============================================================================
-- Sert la fiche produit et le comparateur. Ne decide PAS du prix retenu :
-- la promotion vers pricing_items reste une action humaine explicite
-- ("retenir ce prix"), jamais un effet de bord.
CREATE OR REPLACE VIEW blueseatra.v_best_offer_per_product AS
SELECT DISTINCT ON (o.tenant_id, o.canonical_product_id)
    o.tenant_id,
    o.canonical_product_id,
    o.id                AS offer_id,
    o.supplier_id,
    s.name              AS supplier_name,
    o.price_ht_per_unit,
    o.unit_canonical,
    o.packaging_qty,
    o.min_qty,
    o.delay,
    o.source_date,
    o.product_url,
    o.match_status,
    o.match_confidence,
    -- Nombre d'offres comparees : une "meilleure offre" issue d'une seule
    -- source n'est pas une comparaison, l'UI doit le signaler.
    count(*) OVER (PARTITION BY o.tenant_id, o.canonical_product_id) AS offers_compared
FROM blueseatra.supplier_offers o
JOIN blueseatra.suppliers s ON s.id = o.supplier_id
WHERE o.is_active
  AND o.canonical_product_id IS NOT NULL
  AND o.price_ht_per_unit IS NOT NULL
  -- Seules les offres FIABLES entrent dans un meilleur prix. Un rapprochement
  -- non tranche ne doit jamais produire une recommandation d'achat.
  AND o.match_status = 'matched'
ORDER BY o.tenant_id, o.canonical_product_id, o.price_ht_per_unit ASC, o.source_date DESC NULLS LAST;


-- ============================================================================
-- Amorce des conversions d'unites (faits universels, non confidentiels)
-- ============================================================================
INSERT INTO blueseatra.unit_conversions (id, raw_unit, unit_canonical, factor, family, notes)
VALUES
    (gen_random_uuid()::text, 'ml',        'ml', 1,   NULL,     'metre lineaire'),
    (gen_random_uuid()::text, 'm',         'ml', 1,   NULL,     'metre = metre lineaire'),
    (gen_random_uuid()::text, 'metre',     'ml', 1,   NULL,     NULL),
    (gen_random_uuid()::text, 'u',         'u',  1,   NULL,     'unite'),
    (gen_random_uuid()::text, 'piece',     'u',  1,   NULL,     NULL),
    (gen_random_uuid()::text, 'pce',       'u',  1,   NULL,     NULL),
    (gen_random_uuid()::text, 'm2',        'm2', 1,   NULL,     NULL),
    (gen_random_uuid()::text, 'ens',       'ens',1,   NULL,     'ensemble / forfait'),
    (gen_random_uuid()::text, 'couronne',  'ml', 100, 'cables', 'couronne standard 100 m — A VERIFIER par fournisseur'),
    (gen_random_uuid()::text, 'touret',    'ml', 500, 'cables', 'touret 500 m — A VERIFIER par fournisseur')
ON CONFLICT (raw_unit, unit_canonical, family) DO NOTHING;


-- ============================================================================
-- DURCISSEMENT — A TRAITER SEPAREMENT, NE PAS APPLIQUER A L'AVEUGLE
-- ============================================================================
-- Pour que la BASE garantisse l'isolation au lieu de dependre du code
-- applicatif (prerequis avant de vendre le module a des entreprises
-- concurrentes), il faut trois changements coordonnes :
--
-- 1. Etendre current_tenant() pour accepter un reglage de session, afin que
--    la connexion asyncpg directe du backend puisse s'identifier :
--
--      CREATE OR REPLACE FUNCTION blueseatra.current_tenant()
--      RETURNS text LANGUAGE sql STABLE SET search_path TO '' AS $$
--        SELECT coalesce(
--          NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', ''),
--          NULLIF(current_setting('app.tenant_id', true), '')
--        )
--      $$;
--
-- 2. Faire emettre par le backend, au debut de CHAQUE transaction :
--      SET LOCAL app.tenant_id = '<tenant du jeton>';
--    (SET LOCAL, pas SET : obligatoire avec un pool de connexions, sinon le
--    tenant fuit d'une requete a la suivante -- ce serait pire que le
--    probleme initial.)
--
-- 3. Se connecter avec un role NON PROPRIETAIRE des tables, puis :
--      ALTER TABLE blueseatra.<table> FORCE ROW LEVEL SECURITY;
--    Sans le changement de role, FORCE reste sans effet pour le proprietaire.
--
-- L'ordre compte : appliquer (3) avant (1) et (2) coupe la production.
-- ============================================================================
