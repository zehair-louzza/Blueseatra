# Changelog

## 2026-10-02 (4) — Comparateur : regroupement par produit et prix par unité de base

Format unique, étape 2. Le comparateur lit `offres_normalisees`, en lecture seule et sous point de reprise : si la table manque, il retombe sur les prix bruts.

- **Prix comparable** : prix par unité de base (m, m², kg… ou pièce) quand il est connu. Un conduit YESSS à 146,61 € les 100 m vaut 1,47 €/m et n'est plus classé « le plus cher ». Ce prix sert au tri, au bloc de prix, au « moins cher chez chaque fournisseur » et à la colonne « Prix net HT » du tableau (par exemple « 1,47 €/m »). Le prix publié du lot reste affiché en dessous (« 146,61 € pour 100 m »).
- **Produits identiques** (`produits_identiques`) : toutes les offres visibles qui partagent la clé produit (GTIN, ou marque + réf. fabricant) d'un résultat, **même si leur désignation ne contient pas les termes cherchés**.
  - Une ligne par fournisseur, la moins chère ; écart en % par rapport au moins cher.
  - Pastilles « autre libellé » et « par réf. », pour les offres sans EAN rattachées par marque + référence.
  - Pas d'écart calculé quand les unités diffèrent.
- **Anomalies visibles** : unité supposée, unité illisible, net > public, prix inhabituel, écart anormal.
- **Coût mesuré en production** (lecture des offres d'un même produit, 50 produits, 116 offres) : 120 ms au premier appel, 2 ms ensuite.
- **Tests** : `backend/tests/test_comparateur_produits.py` (10 tests).

## 2026-10-02 (3) — Alias de marques : preuve plus stricte

- **Premier calcul en production : 25 alias.** 10 étaient des libellés de groupe, pas des écritures d'une même marque :
  - « DeWalt Stanley Black & Decker » → Stanley (14 % de GTIN partagés) ;
  - « Milwaukee Ryobi AEG » → Milwaukee (15 %) ;
  - Sicame → Catu, et Sewosy → Faac (5 %).
- **Les vrais alias partagent 53 à 100 %** des GTIN de la plus petite marque, par exemple Modul Modelec → Modelec (100 %) ou Evicom Golmar → Golmar (98 %).
- **Règle** : au moins 5 GTIN partagés **et** au moins 50 % des GTIN de la plus petite marque. Migration `20261002020000_marques_alias_recouvrement.sql`.

## 2026-10-02 (2) — Format unique des offres fournisseurs (étape 1)

- **Spécification validée** : `docs/specs/format-unique-catalogue-fournisseur.md`, avec son modèle Excel `docs/specs/modele-format-unique-catalogue.xlsx` (55 colonnes, listes fermées, exemples réels). Elle suit GTIN (GS1), ETIM et UN/CEFACT Rec. 20.
- **Migration `20261002010000_format_unique_offres.sql`** :
  - nouvelle table 1-1 `offres_normalisees` ; `supplier_offers` (2,5 Go) n'est pas modifiée ;
  - clé produit : `GTIN:` (clé GS1 vérifiée) ou `MR:marque:référence` ;
  - marque canonique (`marques`, `marques_alias` : alias prouvés par au moins 5 GTIN partagés, distributeurs jamais fusionnés) ;
  - unité de base, conditionnement et **prix par unité de base** ;
  - anomalies et score de qualité.
- **Unités corrigées** :
  - chez YESSS, « 100 » et « 1000 » sont des prix pour 100 ou 1 000 (le comparateur comparait 146,61 € les 100 m à 1,08 € le mètre) ; pour un câble, c'est un prix au mètre ;
  - « sac de 25 kg » → 25 KG ;
  - « boîte de 1,08 m² » → 1,08 M2.
- **Normalisation automatique à l'import** : déclencheur de fin d'instruction, qui ne bloque jamais un import.
- **Calcul des offres existantes** par lots : `normaliser_offres_lot`, `recalculer_marques`, `rattacher_produits`.
- **Testé sur 2 513 offres réelles** (les 9 fournisseurs), sur PostgreSQL local, en tant que `blueseatra_app` avec cloisonnement entre entreprises : migration idempotente, 16 contrôles intégrés.

## 2026-10-02 (1) — search_path fixé sur 10 fonctions (Security Advisor)

- **10 avertissements « Function Search Path Mutable » corrigés** par la migration `20261002000000_search_path_fixe.sql` :
  - `search_path = ''` sur les 9 fonctions de quotas, de registre et d'échanges, et sur `tenant_catalogue_commun` ;
  - `search_path = public, pg_temp` sur `normalise_recherche`, car `unaccent` est installée dans `public`.
- **Vérifié avant d'écrire la migration** :
  - aucune de ces fonctions n'est SECURITY DEFINER ;
  - toutes les tables sont qualifiées `blueseatra.` ;
  - les seuls appels sont des fonctions de `pg_catalog`.
- **Aucun effet sur la recherche** : sur 200 000 lignes, `recherche_norm` est identique (0 différence), avec +3 % de temps d'import.
- **Contrôle intégré à la migration** : elle échoue si une fonction du schéma `blueseatra` reste sans `search_path` fixe, ou si `normalise_recherche` ne trouve plus `unaccent`. Elle est idempotente.
- **Non traité : « Extension in Public »** (`unaccent`, `pg_trgm`). Les extensions appartiennent à `supabase_admin`, et les recréer supprimerait les index trigrammes des 967 563 offres. Le risque est faible : seuls `postgres` et `dashboard_user` peuvent créer des objets dans `public`.

## 2026-10-01 (20) — Infrastructure et parcours complet d'un devis

- **Nouveau document bilingue** `docs/infrastructure.md` / `docs/infrastructure.en.md` : les dix phases d'un devis, de la réception au PDF final, avec pour chacune l'intégration qui agit et celle qui réagit ; carte de l'infrastructure (Mermaid) ; vues Supabase et Render ; points d'attention.
- **Nouveaux visuels FR/EN** : `schema-parcours-complet(-en).png`, `vue-supabase(-en).png`, `vue-render(-en).png`, construits à partir des API Supabase et Render (lecture seule, 1er octobre 2026). Aucune donnée personnelle : noms, e-mails, identifiants de projet et de service masqués.
- README français et anglais : schéma du parcours complet dans la section Architecture et lien dans la Documentation ; index de la documentation à jour.

## 2026-10-01 (19) — Montants de la page d'accueil et du module Clients traduits

- **Page d'accueil** : grille de prix dans la langue de la page, « 59 € » et « soit 1 490 € HT facturés par an » en français, « €59 » et « €1,490 excl. VAT billed yearly » en anglais.
- **Module Clients** (liste, fiche client, relances, panneau client du devis) : montants « 1 250 € HT » / « €1,250 excl. VAT », dates et heures selon la langue. Les formateurs partagés de `ClientForm.js` passent par `localeCourante()`.

## 2026-10-01 (18) — Désignations fournisseurs amputées lisibles

- **47 libellés Rexel amputés à la source** (45 accessoires RZB « , D 350 H 1, blanc », un Daikin « .ERAMIC FIBRE… », un Blm « - Boite de dérivation… ») : affichés « RZB 982552.002 · D 350 H 1, blanc », soit marque, référence fabricant et texte sans la ponctuation de tête.
- **Affichage seulement** : `raw_label` reste intact en base, aucune migration. Nouveau module `backend/designation_fournisseur.py`, appliqué au catalogue fournisseurs, au comparateur (résultats et moins cher par fournisseur) et à la recherche d'articles du devis. Un libellé normal est rendu au caractère près.
- **Tri inchangé** : ces lignes restent en tête du tri alphabétique. Changer le tri demanderait un nouvel index sur 967 563 offres pour 47 lignes.
- 16 tests (`backend/tests/test_designation_fournisseur.py`), ajoutés aux tests métier de la CI.

## 2026-10-01 (17) — Cartes d'offre traduites

- **Prix des offres dans la langue de l'interface** : « 59 € HT / mois » en français, « €59 excl. VAT / month » en anglais, sur les cartes d'offre, les recharges et la ligne de l'offre actuelle (page Offre et consommation). Nouvelle clé `cl.p_ht`.

## 2026-10-01 (16) — Bandeaux du README retravaillés

- **Palette professionnelle à plusieurs couleurs** pour les 18 bandeaux shields.io (README français et anglais) : libellé gris foncé commun (`2D333B`), couleur de marque pour chaque technologie (Python, FastAPI, React, Tailwind, PostgreSQL, Supabase, Render, Vercel, Ollama · OVH), une couleur par indicateur (routes, migrations, tests, isolation, RGPD, langues) et par statut (production, version, licence).
- **Lisibilité** : contraste du texte blanc d'au moins 4,6:1 sur chaque couleur (niveau AA), logos ajoutés aux indicateurs.
- Les 3 bandeaux GitHub Actions restent tels quels : leur couleur dépend du résultat des tests.

## 2026-10-01 (15) — README anglais : comparateur et catalogue fournisseurs

- **Deux captures ajoutées** au README anglais, après la traduction (#147) : comparateur de prix (« disjoncteur 16a courbe c ») et catalogue fournisseurs. Données personnelles masquées.
- **Captures « Catalogues » et « Plan and usage » refaites** : badge « Shared » et date « 9 October 2026 » désormais en anglais.

## 2026-10-01 (14) — Écrans fournisseurs traduits en anglais

- **Comparateur de prix et catalogue fournisseurs traduits** : nouveau dictionnaire `fo` (`frontend/src/i18n_fournisseurs.js`, 129 clés FR/EN, mêmes paramètres des deux côtés). Couvre la recherche, la synthèse, les termes reconnus, le moins cher par fournisseur, le tableau des résultats, les produits isolés, les critères à affiner, le filtre famille, le panneau du catalogue commun (badge « Commun » → « Shared »), la page Catalogue fournisseurs et la boîte de dialogue de contenu d'un catalogue. Les textes français sont repris mot pour mot.
- **Données non traduites** : désignations, familles, unités de vente, termes reconnus et exemples de requête restent en français, car ils doivent trouver des produits dans des catalogues français.
- **Prix, nombres et dates dans la langue de l'interface** (`frontend/src/lib/locale.js`) : 3,20 € / €3.20 sur les écrans fournisseurs ; « 9 octobre 2026 » / « 9 October 2026 » sur la page Offre et consommation.
- Page Catalogues : « produits » et en-têtes du tableau des articles traduits.

## 2026-10-01 (13) — Captures du README anglais en anglais

- **6 captures de l'interface anglaise** pour le README anglais (`docs/assets/manuel-en/`) : demande lue par l'IA, éditeur de devis, fiche client, tableau de bord, catalogues, offre et consommation. Données personnelles masquées (flou renforcé à 10 px), langue de l'utilisateur rétablie en français après capture.
- **Deux écrans remplacés** par rapport au README français : « À relancer » (aucune relance en base aujourd'hui, l'écran serait vide) et « Catalogue fournisseurs », dont l'interface n'est pas encore traduite — tout comme le comparateur de prix.

## 2026-10-01 (12) — Schémas du README anglais en anglais

- **3 schémas en anglais** pour le README anglais : architecture, chiffrage sur sources activables, recherche fournisseurs sous RLS (`docs/assets/schema-*-en.png`, générés par `scripts/docs/generer_schemas_en.py`, même code de dessin et même style que les versions françaises).
- **Schéma d'architecture français corrigé** : il indiquait encore 113 routes et 18 migrations (114 et 22).

## 2026-10-01 (11) — Documentation à jour, README anglais complet

- **README anglais complet**, aligné section par section sur le README français (pourquoi, aperçu, fonctionnalités, démarrage rapide, architecture, documentation, qualité et sécurité, écosystème, feuille de route) ; il ne comptait que 3 sections.
- **README français** : badges à jour (114 routes, 22 migrations, 300+ tests), fonctionnalités du jour (recherche rapide sous RLS, recherche dans chaque catalogue, filtre par famille, équivalences « courbe c »), quotas et feuille de route alignés sur l'état réel (#89 clos, blocage activable).
- **Nouveau schéma** `schema-recherche-rls.png` (recherche fournisseurs sous RLS, les 4 fonctions, mesures avant/après relevées depuis le navigateur) ; `schema-chiffrage` mis à jour (il annonçait encore « index trigramme à rétablir ») ; `schema-isolation` mentionne les 3 fonctions `SECURITY DEFINER`.
- **Documentation** : section « Recherche fournisseurs sous RLS » dans l'architecture ; fonctions de recherche dans le schéma de base ; addendum à l'audit d'isolation (surface hors RLS et ses garde-fous) ; tests SQL des fonctions dans le guide développeur ; symptôme « recherche lente ou vide » dans le runbook ; galerie des schémas.

## 2026-10-01 (10) — Lisibilité du menu Famille

- **Comparateur, menu Famille** : sur la ligne survolée (fond accent), le nom du fournisseur restait en gris standard et devenait presque illisible. Il passe en blanc sur cette ligne (contraste ≈ 4,7:1, niveau AA pour le texte).

## 2026-10-01 (9) — Liste des familles du comparateur : 75 s → 1,5 s

- **Constat juste après #141** : `GET /fournisseurs/familles` prenait 75 s au premier appel (puis 3,3 s). Pour chaque catalogue, le `GROUP BY raw_row->>'famille'` finissait en parcours complet de `supplier_offers` (2,5 Go) : l'index des familles porte sur une expression que PostgreSQL ne sait pas lire sans la fiche, et sous RLS `->>` ne peut pas servir de condition d'index.
- **Migration `20261001210000`** : `blueseatra.familles_catalogue(tenant, version, hist)`, parcours « en saut » de `idx_offers_tenant_version_famille` (une lecture par famille), `SECURITY DEFINER`, mêmes règles de cloisonnement et de portée que les autres fonctions. Mesuré sous RLS en production : 9 catalogues en ≈ 1,5 s à froid (Rexel : 17 ms), puis cache par version (une version publiée ne change jamais). Aucune table modifiée.
- **Sans comptage** : compter exigerait de lire chaque fiche. Liste triée par ordre alphabétique, sans accents ni casse.
- **Écran** : 2 419 familles (un fournisseur en emploie 2 204) — le menu devient une liste **filtrable à la saisie** (sans accents ni casse, 100 correspondances affichées au plus), avec les fournisseurs sous chaque famille.
- **Tests** : 2 tests SQL de plus (25 au total) ; test d'agrégation réécrit (tenant de chaque source, tri, cache par version).

## 2026-10-01 (8) — Filtre par famille dans le comparateur de prix

- **Comparateur** : nouveau paramètre `famille` sur `GET /fournisseurs/recherche` et nouveau `GET /fournisseurs/familles` (familles de tous les catalogues visibles et fournisseurs qui les emploient ; voir l'entrée (9) pour sa vitesse). Écran : menu **Famille** sous le champ de recherche, bandeau du filtre actif, filtre conservé dans l'URL.
- **Migration `20261001200000`** : `offres_candidates` reçoit `p_famille` (8ᵉ paramètre, `NULL` par défaut). Signature remplacée par `DROP` + `CREATE` dans la même transaction, pour qu'il n'existe jamais deux surcharges ; les appels à 7 arguments du code déjà déployé restent valides pendant la bascule. Aucune table modifiée.
- **Plafond de comparaison ramené à 1 000 offres avec une famille** : la famille n'est pas dans l'index par prix, chaque offre parcourue coûte une lecture de fiche. Mesuré sous RLS (production) : « led » + Éclairage 17 s à 5 000 offres, 3,4 s à 1 000 ; « disjoncteur 16a courbe c » + Distribution 44 ms ; « prise » + Éclairage 6 s. La réponse rappelle `famille` et `plafond`.
- **Tests** : 3 tests SQL de plus (23 au total : filtre identique à la référence, famille inconnue, autre entreprise, injection, appel à 7 arguments, signature unique) ; 2 tests unitaires (plafond réduit, agrégation des familles). Référence API régénérée (114 routes).

## 2026-10-01 (7) — Recherche rapide à l'intérieur de chaque catalogue

- **Constat en production** (écran « Afficher le catalogue », Rexel 747 771 offres, rôle `blueseatra_app`) : même blocage RLS que pour le comparateur. « disjoncteur 16a courbe c » 26,6 s, terme rare 43,9 s, mot + famille : délai dépassé (erreur).
- **Nouvelle fonction `blueseatra.catalogue_page`** (migration `20261001190000`, aucune table modifiée) : une page triée par prix d'une version (ou d'un fournisseur sans catalogue), filtre de famille facultatif, total plafonné à 1 001. `SECURITY DEFINER`, `search_path` vide, réservée à `blueseatra_app` ; refuse tout tenant autre que l'entreprise ou le catalogue commun et exige une portée précise. Les fiches sont relues par id sous RLS.
- **Règles de recherche partagées** : `blueseatra.recherche_conditions(jsonb)` (fonction interne, non appelable par l'application) traduit les termes pour les deux fonctions ; `offres_candidates` réécrite dessus, comportement inchangé.
- **Chemin choisi selon les correspondances** : moins de 1 001 → index trigramme puis tri ; terme courant → index par prix, arrêt à la page ; terme courant avec famille → index trigramme si le mot est assez sélectif (estimation du planificateur).
- **Mesures sous RLS** (production, Rexel) : « disjoncteur 16a courbe c » 26,6 s → 1,3 s ; terme rare 43,9 s → 0,24 s ; « prise » 61 ms (page 20 : 0,3 s) une fois en cache ; mot + famille : erreur → 3,5 à 5 s au premier appel, 0,1 s ensuite. Pages identiques à la requête de référence (vérifié en production sur 2 cas, et sur base jetable pour tous les chemins).
- **Tests** : 8 tests SQL de plus (20 au total : isolation, portée obligatoire, exactitude des deux chemins avec et sans famille, pagination, bornes) ; 3 tests unitaires de `catalogue_navigation.produits`. Deux sabotages (vérification de tenant retirée, tri cassé) font bien échouer les tests.

## 2026-10-01 (6) — Recherche fournisseurs rapide sous RLS, limites de mot corrigées

- **Cause mesurée en production** : sous le rôle `blueseatra_app`, la RLS de `supplier_offers` empêchait PostgreSQL d'utiliser l'index trigramme (`LIKE` n'est pas « leakproof »). Chaque recherche lisait les offres ligne à ligne : ≈ 27 s au comparateur, plus de 30 s (délai dépassé, liste vide) au sélecteur d'articles du devis et pendant la génération.
- **Nouvelle fonction `blueseatra.offres_candidates`** (migration `20261001180000`, aucune table modifiée) : `SECURITY DEFINER`, `search_path` vide, exécution réservée à `blueseatra_app`. Elle ne renvoie que des identifiants et colonnes de tri, **refuse tout tenant autre que l'entreprise courante ou le catalogue commun**, et injecte les motifs en littéraux échappés (`format %L`). Les fiches sont relues ensuite par id, **toujours sous RLS** et avec le filtre tenant explicite.
- **Comparateur** : chemin choisi selon le nombre estimé de correspondances (≤ 3 000 : index trigramme puis tri ; au-delà : index par prix, arrêt à 5 000). Mêmes lignes et même ordre que la requête de référence (vérifié sur la production : 0 écart sur 3 requêtes).
- **Sélecteur d'articles et génération de devis** : une branche par source activée, 200 candidats par source via l'index trigramme.
- **Bug ancien corrigé** : le vocabulaire écrit les limites de mot en `\b` (syntaxe Python) ; en PostgreSQL `\b` signifie *retour arrière*. Les équivalences « courbe c », « 2p », « ph+n », « alu », « diff »… ne trouvaient rien. Traduction en `\y` à un seul endroit (`motif_postgres`). « disjoncteur 16a courbe c » : 0 → 320 offres.
- **Mesures sous RLS** (rôle `blueseatra_app`, production) : « dalle led 600x600 » 20–190 ms, « disjoncteur 16a courbe c » 30 ms, terme rare 50–90 ms ; termes très courants (« prise », 18 000 offres) 0,5 à 3 s selon le cache, contre 27 s avant. Sélecteur : 0,2 à 1,7 s, contre plus de 30 s.
- **Tests** : 12 tests SQL sur base jetable avec vraies politiques RLS (isolation, injection, droits, exactitude des deux chemins, `\y`) ajoutés au job « Tests métier » ; 4 tests unitaires du contrat du comparateur ; test du sélecteur mis à jour. Les tests d'isolation échouent bien si l'on retire la vérification de tenant (essai de sabotage).

## 2026-10-01 (5) — Documentation illustrée, bannière refaite, sélecteur d'articles corrigé

- **Bannière du README refaite** (`scripts/docs/generer_banniere.py`) : fond papier de la charte et logo officiel en couleurs (l'ancienne passait le logo en silhouette blanche, la vague du B disparaissait), capture actuelle masquée du tableau de bord.
- **7 nouveaux schémas** : chaîne de livraison, isolation des entreprises, cycle de vie du devis et relances, quotas, import de catalogue, droits RGPD, déroulé d'incident. Intégrés au manuel, à l'architecture, au guide développeur, à l'exploitation, au runbook, au RGPD, à la tarification, à la spec du module Clients, à DEPLOIEMENT.md et CONTRIBUTING.md ; galerie dans `docs/README.md`.
- **Nouvelles captures masquées** : lignes extraites d'une demande, PDF Pro Forma (2 pages), comparateur de prix, Société & PDF devis, journal d'audit, sources fournisseurs activées.
- **Sélecteur « Ajouter depuis le catalogue »** (PR #137) : champ de recherche toujours visible ; il était masqué sans catalogue interne.
- **Correction d'une mesure** : les « 189 ms » annoncés pour la PR #133 avaient été mesurés hors RLS. Sous le rôle `blueseatra_app`, la RLS empêche l'usage de l'index trigramme pour `LIKE` (opérateur non « leakproof ») : chaque branche filtre ligne à ligne sur l'index par prix (1,6 s sur Rexel pour « prise », délai de 30 s dépassé sur la requête complète). Correctif à venir.

## 2026-10-01 (4) — Schémas et captures d'écran à jour

- **Schémas redessinés** (`docs/assets/schema-*.png`, rendu x2) : architecture (Vercel, Render, Supabase, passerelle Hermès, `custom:ollama` / `custom:mistral`), parcours d'une demande, routage IA, et nouveau schéma **Chiffrage sur sources activables** (recherche en deux temps, règles de génération). Affichés dans le README et `docs/architecture.md`. Générateur : `scripts/docs/generer_schemas.py` (hors `backend/`, donc sans redéploiement Render).
- **Captures du manuel refaites** sur l'interface actuelle (1440×900), dont deux nouvelles : sources fournisseurs du chiffrage et fenêtre « Afficher le catalogue ».
- **Données personnelles masquées** sur toutes les captures et la bannière : noms de personnes, clients, entreprise, e-mails, téléphones, adresses, SIREN/SIRET et suffixe de clé API.

## 2026-10-01 (3) — Génération robuste et rapide : recherche en deux temps, frontend sur Vercel

- **Recherche fournisseurs en deux temps** (PR #133) : chaque libellé est d'abord filtré par l'index trigramme `idx_offers_recherche_trgm` dans une sous-requête **sans tri** (plafond 200 id), puis trié par prix sur le petit résultat. Avec un `ORDER BY price` dans la branche filtrante, le planificateur parcourait tout l'index par prix (960k lignes) pour des termes rares et dépassait le `command_timeout` asyncpg de 30 s — `TimeoutError` en production sur « trou evacuation rongeurs » ; la même requête passe désormais en **189 ms** (EXPLAIN ANALYZE vérifié sur la base de production).
- **Tenant exact par branche UNION ALL** (PR #132) : chaque branche de recherche porte le `tenant_id` issu du parcours de visibilité (entreprise ou catalogue commun) — plus de clause `OR` qui bloquait les index.
- **Parallélisme réduit 4 → 3** par label (PR #131) et délai d'attente du front porté à 300 s pour la génération (`makeQuote`).
- **La génération ne refuse que si l'entreprise n'a NI catalogue interne NI source fournisseur activée** (PR #134) : des sources actives sans aucune correspondance (libellés introuvables dans les 971 676 offres) produisent désormais un devis avec des lignes à confirmer — plus aucun faux « Aucun catalogue actif ».
- **Frontend migré d'Hostinger vers Vercel** : projet `blueseatra` (Root Directory `frontend/`, production sur `main`), domaines `www.blueseatra.com` (principal) et apex en 308 ; DNS Hostinger `A @ 216.198.79.1` + `CNAME www → d3e2977595b6a031.vercel-dns-017.com` ; CORS Render étendu aux domaines Vercel ; build CRA réparé (`legacy-peer-deps`, `ajv@8`, `DISABLE_ESLINT_PLUGIN`).
- **Documentation alignée** : référence API régénérée (113 routes), nouveau document [`docs/schema-base-donnees.md`](docs/schema-base-donnees.md), architecture et manuel à jour (sources de chiffrage activables, Vercel).

## 2026-10-01 (2) — Tout catalogue activé est utilisable pour le chiffrage

- **Génération de devis sans catalogue interne** : les catalogues fournisseurs activés par l'entreprise pour le chiffrage complètent le catalogue tarifaire interne pour le rapprochement automatique — et le remplacent s'il n'y en a pas. C'est l'entreprise qui choisit ses sources via les boutons d'activation ; le catalogue interne reste prioritaire (marges et prix de vente maîtrisés).
- Chaque libellé de la demande est recherché dans les sources actives (index trigramme) ; les meilleures offres deviennent candidates au rapprochement (borne mémoire : 15 libellés, 8 offres par libellé, 120 candidats).
- Repli silencieux : un incident côté fournisseurs ne bloque jamais la génération ; sans aucune source ni catalogue, le message d'erreur explicite invité à importer un catalogue ou activer un catalogue fournisseur.
- `pricing_snapshot` du devis trace la provenance (`Catalogues fournisseurs`, drapeau `sources_fournisseurs`).
- 6 nouveaux tests unitaires (`candidats_rapprochement`, extraction des libellés).

## 2026-10-01 — Catalogues fournisseurs dans le chiffrage des devis

- **Sources fournisseurs du chiffrage** : chaque catalogue fournisseur visible (les siens + le catalogue commun non masqué) peut être **activé ou désactivé pour le chiffrage** via un bouton poussoir, depuis « Catalogue fournisseurs » ou depuis la nouvelle section « Catalogues fournisseurs » de la page Catalogues. L'état est persisté (table `chiffrage_sources`, migration `20261001120000_sources_chiffrage_fournisseurs.sql`, RLS par entreprise) ; désactiver ne supprime rien — contenu conservé et réactivable en un clic.
- **Aucune copie de données** : les articles ne sont pas dupliqués dans `pricing_items`. La recherche d'articles du devis (`GET /catalog/search`) lit en SQL les offres des sources activées (index trigramme `recherche_norm`), avec un quota réservé pour que les résultats fournisseurs ne soient jamais affamés par le catalogue interne, et un repli silencieux en cas d'incident côté fournisseurs.
- **Sélecteur d'articles du devis** : les articles fournisseurs apparaissent dans la recherche, marqués d'un badge fournisseur (prix net HT, unité de vente, marque, référence).
- **Page Catalogues** : interrupteur « Utiliser pour le chiffrage » sur chaque catalogue interne (active sa version la plus récente / désactive sans rien perdre) ; section « Catalogues fournisseurs » avec interrupteur par source et bouton « Afficher le catalogue » (contenu paginé et filtrable).
- **Correctif parcours fournisseurs** : `catalogue_navigation` ne liste plus comme fournisseurs les catalogues de chiffrage importés en CSV (aucune offre rattachée) — filtre `EXISTS` sur `supplier_offers`.

## 2026-09-29 — Toute l'IA passe par l'agent Hermès, OCR local GLM-OCR par défaut

- **GLM-OCR remplace PaddleOCR-VL-1.6** en tête de l'OCR, à la demande de l'utilisateur : PaddleOCR lisait mal par la passerelle Hermès (« Pome » au lieu du texte de l'image d'essai). PaddleOCR sort de la cascade ; une préférence « paddleocr » enregistrée vaut désormais GLM-OCR (migration `20260929020000_settings_ocr_glm.sql`).
- **Devis : schémas et règles de l'agent validé dans Mistral Studio** (les mêmes que les skills Hermès `extraire-demande-travaux` et `decrire-demande-travaux`) :
  - `backend/schemas_ia/` contient les deux schémas JSON ;
  - la sortie est contrainte par schéma : `format` pour Ollama, `response_format` `json_schema` strict pour Hermès et Mistral, avec un nouvel essai automatique sans schéma si la passerelle le refuse ; `BLUESEATRA_IA_SCHEMA_STRICT=0` n'utilise que la consigne ;
  - extraction : métré en 14 familles (`famille_poste`, `postes_verifies`), engins sur ligne propre (`moyens_acces_engins`), `notes` par ligne et `reserves` ;
  - descriptif : `preliminaires` et `controles_fin_travaux` en plus de `description` et `etapes`, désormais imprimés dans le texte du devis (Préliminaires, puis Déroulement, puis Contrôles de fin de travaux) ;
  - correction : un modèle « Mistral (via Hermès) » était routé vers Ollama lors de l'extraction.
- **Plus aucun appel direct du SaaS vers Ollama.** Tous les appels vont à `POST /v1/chat/completions` de l'agent Hermès, qui choisit le fournisseur à chaque requête : `custom:ollama` pour les modèles du VPS, `custom:mistral` pour l'API Mistral. Cela couvre l'OCR, la cascade de structuration, l'extraction, la décomposition, la rédaction, la vision approfondie et Mistral.
  - `BLUESEATRA_IA_VIA_HERMES=0` sert uniquement de retour arrière d'urgence.
  - Sans `HERMES_GATEWAY_URL`, l'erreur est explicite ; il n'y a pas de repli silencieux vers Ollama.
- **Hermès :** la passerelle est le service `hermes-passerelle` du dépôt `ovh-ai-stack` (PR #30, ADR-009), sans aucun outil, avec les fournisseurs `ollama` et `mistral`. Elle est joignable sur `https://hermes.blueseatra.com` avec l'en-tête `X-Api-Key`.
- **OCR toujours local (GLM-OCR par défaut) :**
  - une image n'est jamais envoyée à Mistral ou OpenAI ; seul le texte lu sur le VPS part vers le fournisseur choisi ;
  - le choix « Modèle OCR préféré » est enfin enregistré : la colonne manquait, et le choix revenait à « Automatique » après chaque enregistrement (migration `20260929010000_settings_ocr_preference.sql`).
- **Page Paramètres :** après « Enregistrer », le formulaire se recharge avec les valeurs réellement enregistrées.
- **Mistral :** relances en cas de limite de débit (429) avec délai exponentiel (2, 4, 8, 16 s), en respectant `Retry-After`.

## 2026-09-29 — Mistral interrogeable par l'agent Hermès (ticket #88)

- **Agent Hermès** (`ovh-ai-stack-corrige/hermes/config.yaml`) :
  - nouveau fournisseur nommé `mistral` (`https://api.mistral.ai/v1`, clé `MISTRAL_API_KEY` du `.env` du VPS) ;
  - `direct_model_requests: true`, pour que le modèle demandé par le SaaS soit respecté ;
  - `compose.yaml` transmet `MISTRAL_API_KEY` au conteneur `hermes`.
- **SaaS :**
  - Paramètres → Moteur IA → « Moteur intégré (Hermès) » propose désormais Mistral Medium, Large et Small (via Hermès), en plus des modèles locaux ;
  - chaque appel envoie `provider: custom:mistral` et le modèle choisi ;
  - images prises en charge ;
  - le test de connexion fait un petit appel réel par Hermès.
- **Repli :** sans passerelle Hermès configurée, appel direct à l'API Mistral avec la clé de la plateforme.

## 2026-09-29 — Mistral remplace Cerebras (ticket #88)

- **Nouveau fournisseur « Mistral AI (API) »** pour l'extraction des demandes (texte, PDF et images), la décomposition en fournitures et la rédaction du descriptif de travaux.
  - Modèles proposés : `mistral-medium-latest` (par défaut), `mistral-large-latest` et `mistral-small-latest`.
  - Réponse JSON imposée à chaque appel ; les garde-fous IA retirent toujours tout prix renvoyé.
- **Page Paramètres → Moteur IA :**
  - la clé est enregistrée chiffrée, puis seuls ses 4 derniers caractères restent affichés ;
  - un bouton « Tester la connexion » vérifie la clé sans consommer de jeton ;
  - la clé peut être supprimée ;
  - sans clé propre, la clé de la plateforme `MISTRAL_API_KEY` est utilisée.
- **Variables d'environnement :**
  - `BLUESEATRA_IA_FOURNISSEUR_DEFAUT=mistral` bascule toutes les entreprises sans réglage propre ;
  - `MISTRAL_MODEL` choisit le modèle par défaut ;
  - la coupure d'urgence accepte `BLUESEATRA_IA_REPLI_PROVIDER=mistral`.
- **Sécurité :** le journal `ia_appel` lit le modèle par son nom de paramètre, pour qu'une clé API ne puisse plus jamais y apparaître.
- 4 tests unitaires, sans appel réseau.

## 2026-09-25 — Paiement Stripe en mode test (ticket #90)

- **Catalogue Stripe :** `scripts/stripe/creer_catalogue.py` crée, sans jamais créer de doublon (`lookup_key` stables), les offres Initial, Pilotage et Performance (mensuel et annuel avec 2 mois offerts), le siège supplémentaire et les 3 recharges.
- **Paiement :**
  - `POST /api/abonnement/checkout` : Stripe Checkout, avec TVA intracommunautaire et adresse de facturation ;
  - `POST /api/abonnement/recharge` ;
  - `POST /api/abonnement/portail` : portail client (changement d'offre, moyens de paiement, factures, annulation) ;
  - `GET /api/abonnement/stripe`.
- **Webhook `POST /api/stripe/webhook` :**
  - signature vérifiée (HMAC SHA-256, tolérance de 5 minutes) ;
  - **idempotent**, chaque événement étant enregistré par son identifiant avant d'être appliqué (table `stripe_evenements`) ;
  - traite l'abonnement créé, modifié ou supprimé, la recharge payée (crédit dans le registre) et les factures.
- **Cycle de vie :**
  - `active`/`trialing` → actif ;
  - `past_due` → actif pendant les relances de Stripe ;
  - `unpaid`/`canceled` → lecture seule ;
  - `paused` → suspendu ;
  - **jamais de suppression de données**. Les offres `interne` et Signature ne sont jamais modifiées par Stripe.
- **Sécurité :** clés et événements live refusés tant que `BLUESEATRA_STRIPE_LIVE=1` n'est pas défini.
- **Page Offre et consommation :** choix de l'offre (mensuel ou annuel), recharges, accès au portail, badge « mode test ».
- Migration `20260927090000_facturation_stripe.sql` (additive). 5 tests unitaires.
- **Recette réelle en mode test Stripe :**
  - catalogue créé dans le compte de test (7 produits, 11 prix ; un second passage ne crée rien) ;
  - abonnement Pilotage + 1 siège payé par la carte de test 4242 ;
  - les 4 événements Stripe réels sont appliqués, puis ignorés au rejeu ;
  - le portail client s'ouvre.
- Corrections trouvées pendant la recette :
  - encodage du formulaire envoyé à Stripe ;
  - lot de 10 `lookup_keys` au plus ;
  - `customer_update[name]` requis avec la collecte de n° de TVA ;
  - métadonnées des factures au format Stripe récent.

## 2026-09-25 — Import de catalogue contrôlé avant activation (ticket #86)

- **Assistant en 5 étapes :** fichier, correspondance des colonnes, import, **contrôle**, activation. L'import crée désormais une version **brouillon** : elle n'est activée qu'après lecture du contrôle.
- **Comparaison avec la version active** (`backend/catalogue_comparaison.py`, 6 tests) : articles nouveaux, retirés, en hausse, en baisse et inchangés, avec les plus fortes variations. La comparaison se fait par référence ; les codes générés `ART-n` sont comparés par libellé. Nouvelle route `GET /api/catalogs/{id}/versions/{vid}/comparaison`.
- **Seuils de sécurité :**
  - BLOQUANT : version vide, prix négatif, au moins 25 % de rejets, chute d'au moins 20 % du nombre d'articles ;
  - À VÉRIFIER : au moins 10 % de prix manquants (0 € compris), au moins 10 % d'unités inconnues, au moins 5 % de rejets, hausse moyenne d'au moins 15 %, variations de plus de 30 %.
- **Activation d'une version BLOQUANTE :** refusée (409). Seul un propriétaire ou un administrateur peut la forcer (`?force=true`), et le verdict est inscrit au journal d'audit.

## 2026-09-25 — Garde-fous de l'IA en production (ticket #88, partie sans clé)

- **Schéma strict de sortie** (`backend/ia_garde_fous.py`) :
  - types convertis ;
  - urgence et confiance normalisées ;
  - lignes non structurées écartées ;
  - **tout prix, montant, taux de TVA ou marge produit par l'IA est retiré et signalé** dans `_anomalies_schema`.
- **Coupure d'urgence** `BLUESEATRA_IA_COUPURE` :
  - `arret` : refus explicite ; la demande échoue proprement et le devis assisté est remboursé ;
  - `repli` : bascule vers `BLUESEATRA_IA_REPLI_PROVIDER` / `_MODEL` / `_KEY`.
- **Journal par appel** `ia_appel` : fournisseur, modèle, rôle, succès, durée, taille des échanges et coût estimé, sans le contenu.
- **Corpus de test BTP** (`backend/corpus_ia/`) : 8 demandes fictives annotées, dont une tentative d'injection de prompt et une demande en anglais. Le script `scripts/ia/evaluer_corpus.py` mesure le taux de réussite, avec un seuil de bascule à 80 %. Référence mesurée : 54 % pour l'extraction de secours sans IA.

## 2026-09-25 — Quotas : projection, rapprochement, politique de dépassement (ticket #89)

- **Projection :** chaque jauge renvoie son rythme par jour, la projection en fin de période et la date d'épuisement prévue. La page Offre et consommation affiche l'alerte (4 tests).
- **Rapprochement :** `GET /api/abonnement/rapprochement` compare chaque demande IA au registre. Une demande lue doit avoir consommé 1 devis, une demande échouée doit avoir été remboursée ; tout écart est listé.
- **Politique de dépassement :** écrite dans [`docs/tarification-2026-09.md`](./docs/tarification-2026-09.md) (§8). Refus en 402 avec un message clair, sans surfacturation silencieuse, et le travail manuel reste toujours possible.

## 2026-09-25 — Observabilité, alertes et RGPD (ticket #93)

- **Journaux structurés JSON** (par défaut sur Render, sinon `LOG_FORMAT=json`) :
  - `request_id` renvoyé dans l'en-tête `X-Request-ID` ;
  - entreprise pseudonymisée ;
  - aucun e-mail en clair, y compris dans les traces d'exception ;
  - requêtes en 5xx ou de plus de 3 s journalisées automatiquement.
- **Mesures et SLO :** `GET /api/exploitation/mesures` (volume, 5xx, p50/p95 par route, respect des SLO), protégée par `BLUESEATRA_METRICS_TOKEN`. Elle répond 404 tant que la variable n'est pas définie.
- **Alerte :** nouveau workflow `surveillance.yml`, qui sonde l'API toutes les heures en jours ouvrés. Il ouvre un ticket « Alerte production » en cas de panne et le ferme au retour à la normale.
- **RGPD :**
  - `GET /api/rgpd/export` : zip de toutes les données de l'entreprise, sans secret ;
  - `POST /api/rgpd/personnes/anonymiser` : effacement d'une personne par son e-mail ;
  - `GET /api/rgpd/echeances` : contacts à anonymiser après 3 ans d'archivage ;
  - chaque opération est tracée dans `audit_logs` ;
  - nouvel onglet **Paramètres → Données personnelles**.
- **Isolation :** le contrôle statique couvre maintenant le SQL écrit dans `clients_module.py` et `observabilite.py`, ainsi que les 7 tables Clients. Sept requêtes à conditions dynamiques ont été réécrites pour que le filtre `tenant_id` soit visible, et la mutation du filtre est détectée.
- **Documents :** [`docs/conformite-rgpd.md`](./docs/conformite-rgpd.md) (registre des traitements, droits, sous-traitants) et [`docs/runbook-incident.md`](./docs/runbook-incident.md) (SLO, corrélation, déroulé, RACI, post-mortem, incident simulé).

## 2026-09-25 — Boîte de réception et versions de devis (ticket #85)

- **Demandes :**
  - recherche sans accents ;
  - 7 filtres avec compteurs ;
  - tri par priorité (à relire, urgentes, sans devis, échéance) ;
  - colonnes client, date de réponse et devis liés.
- **Versions de devis :** une remise en brouillon ouvre la version suivante. Nouvelles routes `GET /api/quotes/{id}/versions` et `GET /api/quotes/{id}/versions/compare?de=N`, et bouton « Historique » avec comparaison ligne à ligne (`backend/quote_versions_diff.py`, 5 tests).
- **Correction :** caractère « } » parasite à côté du bouton Dupliquer.
- **CI (ticket #84) :** nouveau job « Tests unitaires de l'API » : 56 tests (IA, rapprochement, file, versions, quotas). 4 tests anciens avaient des attentes obsolètes et ont été corrigés.

## 2026-09-25 — Module Clients (lots 1 à 4)

- **Fiches** : clients (6 types, SIRET unique par entreprise), contacts (contact principal, opposition aux relances, anonymisation RGPD), chantiers, archivage sans suppression. Écrans `/app/clients` et `/app/clients/:id`.
- **Suggestions IA** : après chaque extraction, donneur d'ordre et client final proposés avec la phrase source comme preuve ; rattachement automatique seulement sur SIRET ou e-mail identique (annulable) ; reprise des noms déjà saisis dans les devis.
- **Relances** : planifiées à l'envoi du devis (jours ouvrés et fériés, urgence, rappel d'expiration, appel au-delà du seuil), annulées à l'issue, à la remise en brouillon ou à l'archivage ; écran `/app/relances` avec texte proposé, résultat et report ; réglages par entreprise ; badge dans le menu.
- **Devis** : panneau « Client et suivi » (donneur d'ordre, client final, validité, issue Accepté / Refusé / Sans suite, relances).
- **Pilotage** : indicateurs de la fiche (devis signés, en attente, taux de transformation, délai de réponse), import et export CSV.
- Migration `20260926090000_module_clients.sql` (additive). Tests : 11 règles, 7 SQL, 7 de bout en bout sur l'API réelle.

## 2026-09-23/24 — Catalogue commun, performances, refonte visuelle, tarification

PR #98 à #106 sur `main`.

### Catalogue fournisseurs
- **#98, #99** : import de catalogues volumineux (`scripts/fournisseur/import_catalogue_lourd.py`), avec analyse, rapport d'anomalies, version inactive et activation atomique. Les offres historiques sans catalogue restent visibles, et la commande `nettoyer` est ajoutée.
- **#100** : catalogue commun à toutes les entreprises (tenant système `00000000-0000-4000-8000-000000000c0d`), en lecture seule, masquable par entreprise, jamais supprimé. Correctif RLS de l'import sous `blueseatra_app`.
- **#101** : synonymes de colonnes du catalogue TCE 2026 (prix d'achat, prix public, unité). La migration SET ROLE est rendue tolérante à l'absence du rôle `postgres`, et la permission `pull-requests: read` est ajoutée pour gitleaks.
- **#102** : page Catalogue fournisseurs, avec les routes `GET /api/fournisseurs/catalogue`, `/catalogue/{cle}/produits` et `/catalogue/{cle}/familles`, et deux index de parcours.

### Performances
- **#103** : la liste des fournisseurs passe de 24 s à 24 ms. La sous-requête lit une seule offre avant le nom du fournisseur ; elle provoquait auparavant des `TimeoutError` (erreurs 500).
- **#104** : nouvel index compact `idx_offers_recherche_prix_v2`, créé `CONCURRENTLY`, et lecture en deux temps. « disjoncteur » dans Rexel passe de plus de 60 s à 0,05 s une fois l'index en mémoire. Résultats identiques (comparaison automatique ancien/nouveau code).
- Maintenance : `VACUUM (ANALYZE)` de `supplier_offers` en production.

### Site
- **#105** : refonte visuelle (Geist, palette du logo, accueil, Tarifs avec bascule mensuel/annuel, connexion, menu groupé, icône de marque). `.htaccess` est inclus dans chaque build.

### Exploitation
- **#106** : réveil automatique de l'API Render via pg_cron (`reveil-api-render`, toutes les 13 min), migration idempotente et sans effet hors Supabase.

### Tarification (décision)
- Essai de 14 jours (1 siège, 10 devis assistés, 30 pages lues), puis Initial 59 €, Pilotage 149 € et Performance 399 € HT par mois, Signature sur devis. Devis, PDF et catalogues illimités ; seuls les devis assistés par l'IA et les pages lues sont comptés. Détail et règles multi-entreprises dans `docs/tarification-2026-09.md`.

## 2026-08-26 — Génération automatique du devis + confirmation directe de suggestion

PR #66 (suggestion) et génération automatique de devis.

### Génération automatique du brouillon de devis
- Demande explicite : la création du brouillon de devis ne doit plus attendre un clic manuel sur «Générer un devis», mais **le devis généré doit toujours attendre une confirmation humaine** avant validation/envoi/PDF.
- `process_request()` appelle désormais `_auto_generate_quote_if_needed()` dès qu'une demande atteint le statut `done` ou `needs_review`. Logique de création partagée avec l'endpoint manuel (`_build_quote_drafts`, refactorisé hors de `POST /quotes/draft`).
- Ne génère jamais un deuxième brouillon pour la même demande (retraitement manuel n'empile pas) ; le bouton «Générer un devis» reste disponible pour créer volontairement un devis supplémentaire.
- Toute erreur (catalogue absent, échec IA) est journalisée sans jamais faire échouer la demande elle-même.
- `GET /requests` et `GET /requests/{id}` exposent désormais les devis liés (`quotes: [{id, number, status}]`) ; la page Détail de la demande affiche un badge cliquable par devis généré, sans que l'utilisateur ait besoin de le chercher.
- **Aucune étape de confirmation humaine n'est retirée en aval** : le devis reste `status="draft"` jusqu'à validation explicite (`POST /quotes/{id}/validate`), comme avant.

### Confirmation directe d'une suggestion catalogue ambiguë (PR #66)
- Bouton «Confirmer» ajouté directement sur la ligne à correspondance ambiguë (suite à PR #61) : applique l'article suggéré en place, sans repasser par la recherche manuelle du panneau catalogue.

## 2026-08-25/26 — Gestion des membres, affichage suggestion catalogue, file d'extraction séquentielle

PR #60 à #64 sur `main`.

### Documentation (PR #60)
- README/CHANGELOG mis à jour avec les rôles IA par clé dédiée (voir entrée précédente) et le correctif Gemma frontend.

### Correctif affichage suggestion catalogue (PR #61)
- Bug réel signalé par l'utilisateur : une ligne à correspondance ambiguë (`status="to_confirm"`, score 45-89) ne recevait volontairement aucun prix automatique (comportement voulu de `matching.py` — jamais de prix sur une correspondance incertaine), mais le frontend n'affichait alors **rien du tout**, laissant croire que l'IA n'avait pas cherché dans le catalogue alors que l'article y était bien présent.
- `QuoteEditor.js` affiche désormais l'indice de suggestion (`suggested_item_code` / `suggested_label`, déjà calculé par le backend mais jamais rendu) sur chaque ligne `to_confirm`, avec un texte explicite invitant à confirmer via « Ajouter depuis le catalogue ».

### Gestion des membres (PR #62, #63)
- `DELETE /api/members/{user_id}` : retire un membre du tenant. Refuse de retirer le dernier `owner` ou de se retirer soi-même.
- `PATCH /api/members/{user_id}` étendu : accepte désormais `name` (renommer un membre) et `password` — ce dernier **réservé au rôle owner** (403 pour un admin), pour que le changement de mot de passe d'un membre ne soit possible que depuis le compte owner.
- Page Membres (`Members.js`) : édition inline du nom (crayon), bouton Supprimer avec confirmation, bouton «clé» (changement de mot de passe) visible uniquement pour le rôle owner.

### File d'extraction séquentielle (PR #64)
- Bug de production confirmé le 25/08 : 5 demandes créées à ~2 min d'intervalle sont restées bloquées sur `processing` pendant 80+ minutes ; le VPS était en réalité inactif (0 % CPU) au moment du contrôle — contention CPU entre extractions concurrentes, puis perte des tâches en mémoire lors d'un redéploiement Render.
- Nouvelle file FIFO in-process (`asyncio.Queue` + une tâche de fond persistante) : une seule extraction IA à la fois, dans l'ordre d'arrivée. Nouveau statut `queued` avec position réelle exposée par l'API et affichée clairement dans le SaaS (« En file d'attente (position N) »).
- Filet de sécurité au démarrage (`_requeue_stuck_on_startup`) : toute demande encore `queued`/`processing` au redémarrage du service est remise en file automatiquement — a réparé seul les 5 demandes bloquées en production.
- Détail complet et alternatives écartées : [`docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md`](./docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md).

## 2026-08-25 — Rôles IA isolés (describe) + garde-fous hallucination + correctif Gemma frontend

PR #55 à #59 sur `main`.

### Rôles IA par clé dédiée (`ai_service.py`)
- Nouveau rôle `describe`, strictement confiné aux champs **Description des travaux** et **Étapes à suivre** — ne touche jamais au calcul, aux quantités, aux prix ni à la décomposition matériaux. Modèle : `HERMES_DESCRIPTION_MODEL` (défaut `glm-4.7-flash:Q3_K_M`), `force_think=False` (mesuré ~28-54 s contre >200 s en mode réflexion sur ce rôle).
- `HERMES_REASONING_MODEL` (rôle `reason`) reste `gpt-oss:20b` après un essai réel de `glm-4.7-flash` comme modèle principal Hermes, reverté (préfill trop lent avec le prompt système complet de Hermes, >200 s pour 34 % d'un prompt de 15k tokens).
- Journalisation du rôle + modèle réellement utilisés à chaque appel (`logger.info("ai_role_resolved ...")`, `ai_call_attempt`/`ai_call_success`/`ai_call_failed`) — aucune journalisation de ce type n'existait avant.

### Garde-fous anti-hallucination (rôle `describe`)
- Rejet automatique si le modèle ajoute une étape de dépose/retrait sur une installation explicitement neuve, ou invente une exclusion non fournie — 2 hallucinations réelles trouvées et corrigées (repli sur le gabarit déterministe existant).
- Règles des 12 skills devis (jusque-là jamais lues par le pipeline SaaS — FastAPI appelle Ollama directement, pas la passerelle Hermes) activées dans les prompts système réels (`EXTRACTION_SYSTEM`, `EXPAND_SYSTEM`, `DESCRIPTION_SYSTEM`), avec défense anti-injection de prompt sur le contenu de document non fiable.

### Frontend
- Le panneau « Extraction IA » affichait en dur « lu directement par **Gemma** » sur le chemin de secours vision, alors que `gemma4:26b` a été retiré du VPS le 23/08. Le backend exposait déjà `_ocr_engine` dynamiquement — seul le libellé frontend (`i18n.js`, `req.ocr_fallback_note`) n'avait pas suivi. Corrigé pour interpoler `{{engine}}`.

## 2026-08-15 — OVH + MCP + devis

Tout est sur `main` (PR #1 à #9). Smoke : ce commit.

### IA locale (OVH)
- Hermes / Ollama derrière Caddy (`HERMES_BASE_URL=https://ia.blueseatra.com`, `HERMES_API_KEY`)
- `extract_from_text` / `extract_from_image` / PDF / DOCX
- Modèles UI = ceux du VPS : `hermes-3`, `qwen3.6:27b`, `qwen2.5:14b`
- Mapping `client_name` / `location` → champs écran devis

### Devis
- Rapprochement catalogue (`description` + pluriels → Spot LED encastré)
- Marge % : `HT = qté × PU × (1 + marge/100)`
- Catalogue slim + cache 45 s + `GET /catalog/search`
- pandas chargé seulement à l’import CSV (boot Render plus court)

### MCP Perplexity Computer
- `POST /mcp` (Streamable HTTP)
- `MCP_TENANT_ID` = ANELEC Test `9171d808-f7ee-4d51-92f6-db60d93d8ecc`
- Outils : list_requests, get_request, list_quotes, search_catalog

### Infra
- Pooler Supabase : `prepared_statement_cache_size` et `statement_cache_size` à 0

### Hostinger (manuel)
Rebuild frontend pour voir marge / picker en direct :

```bash
cd frontend && yarn build
```

Uploader le contenu de `frontend/build/` vers `public_html/`.

## Jalons antérieurs

### Juillet 2026 — Migration Hermes AI / Ollama / OVH VPS

**Changements majeurs :**
- ✅ **Suppression totale du provider Emergent** (`emergentintegrations` désinstallé, `EMERGENT_LLM_KEY` supprimée)
- ✅ **Hermes-3 via Ollama** sur VPS OVH devient le moteur IA par défaut (`ai_service.py` réécrit)
- ✅ **litellm mis à jour vers 1.80.0** comme couche d'abstraction pour les fallbacks tenant (OpenAI / Anthropic / Gemini)
- ✅ Variables d'environnement `HERMES_BASE_URL` et `HERMES_DEFAULT_MODEL` ajoutées
- ✅ `requirements.txt` mis à jour (suppression `emergentintegrations`, ajout `litellm==1.80.0`)

### Étapes précédentes

| Étape | Description |
|-------|-------------|
| Migration MongoDB → Supabase | `pg_adapter.py` + `models_sql.py` + `migrate_mongo_to_supabase.py` |
| Activation RLS | `enable_rls.py` — policy deny-all sur toutes les tables |
| Éditeur de devis v2 | Lignes typées, TVA par ligne, marge masquée, sélecteur catalogue |
| Import CSV universel | Auto-détection colonnes + mapping manuel + attributs dynamiques |
| Génération PDF Pro Forma | ReportLab — gabarit métier complet avec profil entreprise |
| Multi-tenant RBAC | Rôles `owner` / `admin` / `operator` / `viewer` / `billing_admin` |
| Internationalisation | react-i18next — FR / EN |
| Webhook n8n | Configurable par tenant dans les paramètres d'intégration |
| Journal d'audit | Table `audit_logs` — toutes les actions sensibles tracées |
| Profil entreprise PDF | SIRET, IBAN, mentions légales, conditions injectés dans le PDF |

