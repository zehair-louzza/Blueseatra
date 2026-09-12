-- Aligne les colonnes de date du module Fournisseur sur la convention
-- du projet : des chaines ISO, pas des types temporels natifs.
-- =====================================================================
--
-- LE PROBLEME
-- -----------
-- Les tables creees par 20260912020000 declarent :
--
--   suppliers.created_at        timestamptz
--   suppliers.updated_at        timestamptz
--   supplier_offers.created_at  timestamptz
--   supplier_offers.source_date date
--
-- alors que TOUTES les tables preexistantes stockent des chaines :
--
--   catalogs.created_at         character varying
--   catalog_versions.created_at character varying
--   quotes.created_at           character varying
--
-- Ce n'est pas un detail de style. C'est la convention documentee du
-- projet, inscrite en tete de backend/models_sql.py :
--
--   "Timestamps are stored as ISO strings (String) to match the current
--    now_iso() usage and preserve lexical-sort behaviour during
--    migration."
--
-- Tout le code appelle now_iso(), qui renvoie une chaine. Or asyncpg
-- est strict sur les types : il REFUSE une chaine Python pour un
-- parametre timestamptz, il exige un datetime. L'import de tarifs
-- aurait donc echoue a l'insertion, sur chaque ligne.
--
-- Detecte en preparant l'import reel du catalogue La Plateforme
-- (24 600 lignes). Les deux bugs precedents du meme genre --
-- match_status='pending' refuse par une contrainte CHECK, et l'exposant
-- perdu dans la normalisation -- avaient aussi echappe a tous les tests
-- du bac a sable, faute de serveur Postgres pour les executer.
--
-- POURQUOI ALIGNER LES NOUVELLES TABLES, ET PAS L'INVERSE
-- --------------------------------------------------------
-- timestamptz est objectivement le meilleur type. Mais basculer tout le
-- projet vers des datetime touche quotes, requests, catalogs,
-- pricing_items, audit_logs et 44 devis existants -- un chantier sans
-- rapport avec le module Fournisseur, et un risque bien plus grand que
-- le gain.
--
-- On aligne donc les quatre colonnes nouvelles sur l'existant. Le jour
-- ou le projet passera aux types temporels natifs, il le fera partout
-- d'un coup.
--
-- LE CAS source_date EST DIFFERENT, ET PLUS IMPORTANT
-- ---------------------------------------------------
-- Cette colonne recoit la date de prix TELLE QU'ECRITE dans le fichier
-- fournisseur. Les formats observes sur les catalogues reels incluent
-- "09/2026", "2026-09", "sept. 2026" et des cellules vides. Un type
-- `date` ferait echouer l'import sur la premiere valeur non
-- convertible -- et ferait perdre l'information plutot que de la
-- conserver imparfaite.
--
-- Une date de tarif approximative reste exploitable : elle dit si le
-- prix a six mois. Une ligne rejetee ne dit rien.

SET search_path TO blueseatra, public;

-- ---------------------------------------------------------------------
-- La vue doit etre retiree avant de changer le type d'une colonne
-- ---------------------------------------------------------------------
-- Postgres refuse : "cannot alter type of a column used by a view or
-- rule -- rule _RETURN on view v_best_offer_per_product depends on
-- column source_date".
--
-- Elle est recreee a l'identique plus bas, avec UNE correction : la
-- jointure sur suppliers ne filtrait pas tenant_id. Les identifiants
-- etant uniques, ce n'etait pas une fuite en pratique, mais c'est le
-- meme defaut que celui corrige partout ailleurs dans le projet -- une
-- jointure inter-tenants qui ne dit pas non.
DROP VIEW IF EXISTS blueseatra.v_best_offer_per_product;

ALTER TABLE blueseatra.suppliers
    ALTER COLUMN created_at TYPE varchar(40)
        USING to_char(created_at AT TIME ZONE 'UTC',
                      'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    ALTER COLUMN created_at SET DEFAULT to_char(
        now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    ALTER COLUMN updated_at TYPE varchar(40)
        USING to_char(updated_at AT TIME ZONE 'UTC',
                      'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    ALTER COLUMN updated_at SET DEFAULT to_char(
        now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');

ALTER TABLE blueseatra.supplier_offers
    ALTER COLUMN created_at TYPE varchar(40)
        USING to_char(created_at AT TIME ZONE 'UTC',
                      'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    ALTER COLUMN created_at SET DEFAULT to_char(
        now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    -- source_date : conserve la valeur brute du fichier fournisseur.
    ALTER COLUMN source_date TYPE varchar(20)
        USING CASE WHEN source_date IS NULL THEN NULL
                   ELSE to_char(source_date, 'YYYY-MM-DD') END;

-- Les autres tables du module, par coherence.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'blueseatra'
                 AND table_name = 'canonical_products'
                 AND column_name = 'created_at'
                 AND data_type = 'timestamp with time zone') THEN
        EXECUTE $sql$
            ALTER TABLE blueseatra.canonical_products
                ALTER COLUMN created_at TYPE varchar(40)
                    USING to_char(created_at AT TIME ZONE 'UTC',
                                  'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                ALTER COLUMN updated_at TYPE varchar(40)
                    USING to_char(updated_at AT TIME ZONE 'UTC',
                                  'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        $sql$;
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- Controle de coherence : plus aucune colonne de date du module ne doit
-- etre d'un type temporel natif.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    restantes text;
BEGIN
    SELECT string_agg(table_name || '.' || column_name || ' (' ||
                      data_type || ')', ', ')
      INTO restantes
      FROM information_schema.columns
     WHERE table_schema = 'blueseatra'
       AND table_name IN ('suppliers', 'supplier_offers',
                          'canonical_products')
       AND column_name IN ('created_at', 'updated_at', 'source_date')
       AND data_type IN ('timestamp with time zone', 'timestamp without time zone',
                         'date');
    IF restantes IS NOT NULL THEN
        RAISE EXCEPTION
            'Colonnes de date encore en type temporel natif : %. '
            'asyncpg refusera les chaines ISO produites par now_iso() '
            'et l''import echouera a chaque ligne.', restantes;
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- Vue recreee, avec le filtre tenant_id sur la jointure
-- ---------------------------------------------------------------------
CREATE VIEW blueseatra.v_best_offer_per_product AS
 SELECT DISTINCT ON (o.tenant_id, o.canonical_product_id) o.tenant_id,
    o.canonical_product_id,
    o.id AS offer_id,
    o.supplier_id,
    s.name AS supplier_name,
    o.price_ht_per_unit,
    o.unit_canonical,
    o.packaging_qty,
    o.min_qty,
    o.delay,
    o.source_date,
    o.product_url,
    o.match_status,
    o.match_confidence,
    count(*) OVER (PARTITION BY o.tenant_id, o.canonical_product_id)
        AS offers_compared
   FROM blueseatra.supplier_offers o
     JOIN blueseatra.suppliers s
       ON s.id = o.supplier_id
      -- AJOUT : sans ce filtre, la jointure traverse les tenants.
      AND s.tenant_id = o.tenant_id
  WHERE o.is_active
    AND o.canonical_product_id IS NOT NULL
    AND o.price_ht_per_unit IS NOT NULL
    AND o.match_status = 'matched'
  ORDER BY o.tenant_id, o.canonical_product_id, o.price_ht_per_unit,
           o.source_date DESC NULLS LAST;

COMMENT ON VIEW blueseatra.v_best_offer_per_product IS
    'Meilleure offre par produit canonique. La jointure filtre '
    'tenant_id des deux cotes : sans cela elle traverserait les '
    'tenants, le moteur metier pouvant tourner en repli sous un role '
    'BYPASSRLS.';

COMMENT ON COLUMN blueseatra.supplier_offers.source_date IS
    'Date du prix TELLE QU''ECRITE dans le fichier fournisseur. Chaine '
    'et non date : les formats reels vont de "09/2026" a "sept. 2026". '
    'Une date approximative dit si le tarif a six mois ; une ligne '
    'rejetee ne dit rien.';
