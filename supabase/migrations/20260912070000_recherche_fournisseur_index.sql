-- =====================================================================
-- Colonne de recherche normalisee et index trigramme sur supplier_offers
-- =====================================================================
--
-- POURQUOI UN INDEX EST INDISPENSABLE ICI
-- ----------------------------------------
-- L'endpoint existant /catalog/search charge TOUT le catalogue actif en
-- memoire puis filtre en Python. C'est acceptable pour les 712 lignes de
-- pricing_items. Le catalogue fournisseurs consolide en compte 914 628 :
-- la meme approche saturerait la memoire du service et depasserait tout
-- delai raisonnable.
--
-- La recherche fournisseurs se fait donc EN SQL, et a besoin d'un index
-- capable d'accelerer un motif de type '%terme%'.
--
-- POURQUOI TRIGRAMME (pg_trgm) ET PAS RECHERCHE PLEIN TEXTE
-- ----------------------------------------------------------
-- tsvector decoupe en mots et applique un stemming par langue. Il est
-- excellent pour du texte redige, et inadapte ici :
--
--   - les designations fournisseurs sont truffees de references
--     alphanumeriques (SN201SL, iDT40T, DNX3) qu'un stemmer mutile ;
--   - le chiffreur cherche des fragments : "ba13", "2.5", "ip65", et
--     doit pouvoir taper "peintur" sans le "e" final ;
--   - la garantie exigee est une INCLUSION de sous-chaine, pas une
--     proximite lexicale.
--
-- GIN + gin_trgm_ops repond exactement a ce besoin : il accelere
-- LIKE '%...%' et ILIKE, sur des fragments arbitraires.
--
-- NORMALISATION FIGEE DANS LA COLONNE
-- ------------------------------------
-- La colonne est generee, donc toujours coherente avec la designation :
-- impossible qu'elle derive apres une mise a jour, et rien a maintenir
-- cote application.
--
-- Elle applique la MEME normalisation que le code Python (unaccent,
-- minuscules, ponctuation reduite a des espaces) a une exception pres,
-- volontaire : les separateurs decimaux colles a des chiffres sont
-- PRESERVES. "2,5 mm2" ne doit pas devenir "2 5 mm2", sinon une
-- recherche sur "2,5" ne trouve plus rien -- et surtout la section est
-- perdue, ce qui faisait confondre le fil 1,5 mm2 et le 2,5 mm2, deux
-- articles de prix differents. Bug mesure, puis corrige.
-- =====================================================================

BEGIN;

-- unaccent et pg_trgm sont disponibles sur Supabase mais pas actives par
-- defaut. CREATE EXTENSION est idempotent.
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- ---------------------------------------------------------------------
-- 1. Fonction de normalisation
-- ---------------------------------------------------------------------
-- IMMUTABLE est OBLIGATOIRE pour qu'une colonne generee puisse
-- l'appeler. unaccent() etant declaree STABLE et non IMMUTABLE, on
-- passe par unaccent('unaccent', ...) qui fixe le dictionnaire et rend
-- l'appel deterministe.
CREATE OR REPLACE FUNCTION blueseatra.normalise_recherche(txt text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
  SELECT trim(regexp_replace(
    -- 3. tout ce qui n'est ni lettre, ni chiffre, ni point, ni plus
    --    devient une espace ; les espaces multiples sont reduits
    regexp_replace(
      -- 2. minuscules, sans accents
      lower(unaccent('unaccent', coalesce(txt, ''))),
      -- 1. protege les decimales : "2,5" -> "2.5" AVANT le nettoyage,
      --    sinon la virgule serait remplacee par une espace
      '(\d)[.,](\d)', '\1.\2', 'g'
    ),
    '[^a-z0-9.+]+', ' ', 'g'
  ));
$$;

COMMENT ON FUNCTION blueseatra.normalise_recherche(text) IS
  'Normalisation partagee avec le code Python (vocabulaire_btp). '
  'Preserve les decimales collees : "2,5 mm2" reste cherchable, sinon '
  'la section est perdue et le fil 1,5 est confondu avec le 2,5.';


-- ---------------------------------------------------------------------
-- 2. Colonne generee
-- ---------------------------------------------------------------------
-- Concatene les champs reellement utiles a la recherche. raw_label --
-- le libelle brut du fournisseur -- vient en premier : c'est lui qui
-- porte l'information discriminante,
-- comme l'a montre l'analyse des variantes de gamme (une meme reference
-- fabricant couvre 58 tailles de coffre chez Point.P, seule la
-- designation les distingue).
ALTER TABLE blueseatra.supplier_offers
  ADD COLUMN IF NOT EXISTS recherche_norm text
  GENERATED ALWAYS AS (
    blueseatra.normalise_recherche(
      coalesce(raw_label, '') || ' ' ||
      coalesce(brand, '') || ' ' ||
      coalesce(raw_reference, '') || ' ' ||
      coalesce(manufacturer_ref, '') || ' ' ||
      coalesce(ean, '')
    )
  ) STORED;

COMMENT ON COLUMN blueseatra.supplier_offers.recherche_norm IS
  'Champ de recherche normalise, genere. Ne jamais ecrire directement.';


-- ---------------------------------------------------------------------
-- 3. Index trigramme
-- ---------------------------------------------------------------------
-- CONCURRENTLY est impossible dans une transaction ; sur une table
-- encore vide le verrou est de toute facon instantane. Si la table est
-- deja peuplee au moment de l'application, sortir cet ordre du bloc et
-- le passer en CONCURRENTLY.
CREATE INDEX IF NOT EXISTS idx_offers_recherche_trgm
  ON blueseatra.supplier_offers
  USING gin (recherche_norm gin_trgm_ops);

-- Tri par prix croissant : c'est l'ordre par defaut de la comparaison,
-- donc l'index evite un tri sur des dizaines de milliers de lignes.
-- NULLS LAST correspond au comportement voulu (un produit sans prix ne
-- doit jamais apparaitre comme "le moins cher").
CREATE INDEX IF NOT EXISTS idx_offers_tenant_prix
  ON blueseatra.supplier_offers (tenant_id, price_ht ASC NULLS LAST);


-- ---------------------------------------------------------------------
-- 4. Verification bloquante
-- ---------------------------------------------------------------------
DO $$
DECLARE
  essai text;
BEGIN
  essai := blueseatra.normalise_recherche('Câble H07V-U 2,5 mm² Bleu');
  IF essai IS DISTINCT FROM 'cable h07v u 2.5 mm2 bleu' THEN
    RAISE EXCEPTION
      'La normalisation ne produit pas le resultat attendu : "%". '
      'Attendu "cable h07v u 2.5 mm2 bleu". Verifier notamment que la '
      'decimale de 2,5 est preservee -- sa perte fait confondre le fil '
      '1,5 mm2 et le 2,5 mm2.', essai;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'blueseatra'
      AND indexname = 'idx_offers_recherche_trgm'
  ) THEN
    RAISE EXCEPTION 'Index trigramme absent : la recherche ferait un '
                    'balayage complet sur 900 000 lignes.';
  END IF;

  RAISE NOTICE 'OK : normalisation conforme et index en place.';
END $$;

COMMIT;

-- =====================================================================
-- RETOUR ARRIERE
-- =====================================================================
--   DROP INDEX IF EXISTS blueseatra.idx_offers_recherche_trgm;
--   DROP INDEX IF EXISTS blueseatra.idx_offers_tenant_prix;
--   ALTER TABLE blueseatra.supplier_offers DROP COLUMN IF EXISTS recherche_norm;
--   DROP FUNCTION IF EXISTS blueseatra.normalise_recherche(text);
--
-- Sans effet sur les donnees : la colonne est generee, aucune saisie
-- n'est perdue.
-- =====================================================================
