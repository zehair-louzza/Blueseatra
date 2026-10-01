-- Alias de marques : preuve plus stricte (02/10/2026, après le premier calcul en production).
--
-- Premier calcul : 25 alias. Dix d'entre eux étaient des libellés de groupe, pas des
-- écritures d'une même marque : « DeWalt Stanley Black & Decker » -> Stanley,
-- « Milwaukee Ryobi AEG » -> Milwaukee, Sicame -> Catu, Sewosy -> Faac… Ils ne
-- partageaient que 5 à 32 % des GTIN de la plus petite des deux marques, contre 53 à
-- 100 % pour les vrais alias (Evicom Golmar -> Golmar 98 %, Modul Modelec -> Modelec
-- 100 %, SCGA Thermor -> Thermor 73 %).
--
-- Règle : au moins 5 GTIN partagés ET au moins 50 % des GTIN de la plus petite
-- marque. La détection des distributeurs reste sur toutes les paires d'au moins
-- 5 GTIN (plus prudente).

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
        , nb AS (SELECT cle, count(*) AS n FROM d GROUP BY cle)
        SELECT a.cle AS a, b.cle AS b, count(*) AS n,
               count(*)::numeric / least(min(na.n), min(nb2.n)) AS recouvrement
          FROM d a JOIN d b ON a.gtin = b.gtin AND a.cle < b.cle
          JOIN nb na ON na.cle = a.cle
          JOIN nb nb2 ON nb2.cle = b.cle
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
     WHERE p.recouvrement >= 0.5
       AND p.a NOT IN (SELECT cle FROM _distrib) AND p.b NOT IN (SELECT cle FROM _distrib);
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
