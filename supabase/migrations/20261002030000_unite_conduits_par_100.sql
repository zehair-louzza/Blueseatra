-- Unités : conduits et gaines YESSS vendus « par 100 » = 100 m (02/10/2026).
--
-- Vérification en production du comparateur (#159) : « conduit icta 20 » comparait
-- 0,44 €/m chez Rexel à 1,55 €/pièce chez YESSS (écart affiché 253 %). YESSS publie
-- ses conduits avec l'unité « 100 » (= 100 m) ; la règle du format unique ne
-- reconnaissait que les câbles comme produits linéaires. 84 offres YESSS concernées.
-- Les lots d'accessoires (manchons, courbes, fixations… « lot de 10 ») sont de vrais
-- lots de pièces et ne changent pas.

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
        -- Conduits et gaines vendus « par 100 » : 100 m, pas 100 pièces. Le libellé
        -- COMMENCE par le produit linéaire (« Conduit ICA 3321 Ø20 ») ; un accessoire
        -- (« Courbe conduit 20 », « Manchon tube IRL », « Fixation pour gaine »)
        -- reste à la pièce.
        IF r.qte > 1 AND l ~ '^\s*(conduits?|gaines?|tubes? (irl|ica|icta|ico|mrb|tpc)|tpc)\M'
           AND l !~ '\m(manchons?|coudes?|courbes?|raccords?|fixations?|chevilles?|crochets?|embouts?|bouchons?|colliers?|rosaces?|boites?|supports?|clips?|attaches?|derivations?|reductions?|adaptateurs?|presse|joints?|brides?|obturateurs?|sorties?|terminal|tire-fils?|aiguilles?|etriers?|pattes?)\M' THEN
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

DO $$
DECLARE r blueseatra.unite_offre;
BEGIN
    r := blueseatra.unite_normalisee('100', 'Conduit ICA 3321 TurboGliss® Ø20mm pour cloisons verticales');
    IF r.unite_base <> 'M' OR r.qte <> 100 THEN RAISE EXCEPTION 'conduit ICA par 100 : % %', r.unite_base, r.qte; END IF;
    r := blueseatra.unite_normalisee('100', 'Conduits DuoGliss® 4433 Ø50mm pour courant fort');
    IF r.unite_base <> 'M' THEN RAISE EXCEPTION 'conduits DuoGliss : %', r.unite_base; END IF;
    r := blueseatra.unite_normalisee('100', 'Gaine ICTA 3422 Ø16 grise');
    IF r.unite_base <> 'M' THEN RAISE EXCEPTION 'gaine ICTA : %', r.unite_base; END IF;
    r := blueseatra.unite_normalisee('100', 'Courbe conduit 20');
    IF r.unite_base <> 'U' OR r.qte <> 100 THEN RAISE EXCEPTION 'courbe conduit : % %', r.unite_base, r.qte; END IF;
    r := blueseatra.unite_normalisee('100', 'Conduit - manchon pour tube IRL Ø20');
    IF r.unite_base <> 'U' THEN RAISE EXCEPTION 'manchon : %', r.unite_base; END IF;
    r := blueseatra.unite_normalisee('100', 'Cheville pour fixation immédiate pour moulure');
    IF r.unite_base <> 'U' THEN RAISE EXCEPTION 'cheville : %', r.unite_base; END IF;
    r := blueseatra.unite_normalisee('1', 'Conduit ICA 3321 Ø20');
    IF r.unite_base <> 'U' OR r.qte <> 1 THEN RAISE EXCEPTION 'conduit a l unite : % %', r.unite_base, r.qte; END IF;
    r := blueseatra.unite_normalisee('1000', 'Câble U1000 R2V 3G2,5');
    IF r.unite_base <> 'M' OR r.qte <> 1000 THEN RAISE EXCEPTION 'cable : % %', r.unite_base, r.qte; END IF;
END $$;
