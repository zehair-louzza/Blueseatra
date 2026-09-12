-- Designation canonique et attributs discriminants sur supplier_offers
-- =====================================================================
--
-- POURQUOI STOCKER PLUTOT QUE CALCULER A LA VOLEE
-- ------------------------------------------------
-- L'analyse d'un libelle coute environ 75 nanosecondes... par libelle.
-- Mesure reelle : 914 628 lignes analysees en 77 secondes. Refaire ce
-- travail a chaque recherche serait donc impossible -- une recherche
-- doit repondre en dessous de la seconde.
--
-- Les attributs sont donc extraits UNE FOIS a l'import et stockes en
-- colonnes. La recherche devient du SQL indexable, et la regle de
-- contradiction s'exprime directement :
--
--     AND (o.calibre IS NULL OR o.calibre = '16A')
--
-- Un libelle muet passe (IS NULL), un libelle contraire est ecarte.
-- C'est exactement la regle validee sur les 26 860 libelles de
-- disjoncteur : rappel 100 % sur la requete nue, zero fuite sur "16A".
--
-- POURQUOI DES COLONNES ET PAS DU JSONB
-- --------------------------------------
-- raw_row existe deja en JSONB, mais un index sur une cle JSONB est
-- moins direct et la lisibilite des requetes s'effondre. Ces neuf
-- attributs sont un socle stable, mesure sur le catalogue reel : ils
-- meritent des colonnes.

SET search_path TO blueseatra, public;

ALTER TABLE blueseatra.supplier_offers
    -- Libelle recompose : TYPE en tete, puis attributs discriminants.
    -- 23 % des libelles de disjoncteur ne commencent PAS par le type
    -- ("Acti9 C60H-DC - Disjoncteur modulaire - 2P - 2A"), et la
    -- colonne etant tronquee a l'ecran, c'est l'information
    -- distinctive qui disparaissait.
    ADD COLUMN IF NOT EXISTS designation_courte  text,

    -- Type produit normalise. Volontairement distinct pour les
    -- differentiels : sur les disjoncteurs 16A du catalogue, 22 % des
    -- lignes sont des differentiels, a 215,25 EUR de prix median contre
    -- 110,68 EUR. Les confondre fausse tout devis.
    ADD COLUMN IF NOT EXISTS type_produit        varchar(60),

    -- Attributs discriminants, sous forme UNIFIEE. "ph+n", "1P+N",
    -- "U+N" et "phase + neutre" designent la meme chose et deviennent
    -- tous "1P+N", sinon une recherche de 1P+N ignorerait les cinq
    -- autres ecritures.
    ADD COLUMN IF NOT EXISTS calibre             varchar(20),
    ADD COLUMN IF NOT EXISTS courbe              varchar(20),
    ADD COLUMN IF NOT EXISTS poles               varchar(12),

    -- Pouvoir de coupure. "4500A/6kA" figure 124 fois et "6000A/10kA"
    -- 643 fois SUR LA MEME LIGNE : la valeur en amperes suit la norme
    -- domestique NF EN 60898, celle en kA la norme industrielle
    -- IEC 60947-2. Un meme appareil porte les deux. On stocke celle en
    -- amperes quand les deux figurent, sans jamais convertir -- les
    -- paires ne sont pas toutes coherentes (6000<->50kA sur 52 lignes).
    ADD COLUMN IF NOT EXISTS pouvoir_coupure     varchar(20),

    ADD COLUMN IF NOT EXISTS sensibilite         varchar(20),
    ADD COLUMN IF NOT EXISTS section             varchar(20),
    ADD COLUMN IF NOT EXISTS puissance           varchar(20),
    ADD COLUMN IF NOT EXISTS temperature         varchar(20),

    -- Qualifiants : ils empechent une comparaison de prix directe et
    -- doivent rester VISIBLES, jamais absorbes. Un lot de 50 et une
    -- piece seule n'ont pas un prix comparable.
    ADD COLUMN IF NOT EXISTS conditionnement_lot integer,
    ADD COLUMN IF NOT EXISTS est_accessoire      boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS est_courant_continu boolean NOT NULL DEFAULT false;

-- Index de recherche
-- ------------------
-- La recherche filtre toujours tenant + is_active, puis restreint sur
-- le type et les attributs, puis trie par prix. Ces index couvrent le
-- chemin complet.

CREATE INDEX IF NOT EXISTS idx_offers_type_calibre
    ON blueseatra.supplier_offers (tenant_id, is_active, type_produit,
                                   calibre, price_ht);

-- Index partiels sur les attributs : seules les lignes RENSEIGNEES sont
-- indexees. Le calibre n'est present que sur 50,9 % des libelles de
-- disjoncteur et bien moins sur l'ensemble du catalogue ; indexer les
-- NULL gonflerait l'index sans jamais servir, la condition
-- "IS NULL OR = valeur" n'ayant pas besoin d'index pour la branche NULL.
CREATE INDEX IF NOT EXISTS idx_offers_courbe
    ON blueseatra.supplier_offers (tenant_id, courbe)
    WHERE courbe IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_offers_poles
    ON blueseatra.supplier_offers (tenant_id, poles)
    WHERE poles IS NOT NULL;

-- Recherche plein texte sur la designation recomposee, en complement de
-- recherche_norm qui porte sur le libelle d'origine. Les deux sont
-- necessaires : l'utilisateur peut taper le vocabulaire du fournisseur
-- comme le vocabulaire normalise.
CREATE INDEX IF NOT EXISTS idx_offers_designation_courte_trgm
    ON blueseatra.supplier_offers
    USING gin (lower(designation_courte) gin_trgm_ops)
    WHERE designation_courte IS NOT NULL;

COMMENT ON COLUMN blueseatra.supplier_offers.designation_courte IS
    'Libelle recompose : type en tete puis attributs discriminants. '
    'Le libelle fournisseur d''origine reste dans raw_label -- donnee '
    'contractuelle, c''est lui qui figure sur le devis.';

COMMENT ON COLUMN blueseatra.supplier_offers.pouvoir_coupure IS
    'Valeur en amperes (NF EN 60898) quand le libelle porte les deux '
    'normes, sinon la valeur telle qu''ecrite. Jamais convertie : les '
    'paires A/kA observees ne sont pas toutes coherentes.';
