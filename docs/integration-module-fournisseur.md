# Intégration du module Fournisseur dans Blueseatra

Audit du prototype `Fournisseur-Blueseatra` et plan d'intégration dans le SaaS.

Établi le 12/09/2026, après lecture complète des deux bases de code.

---

## Conclusion en une phrase

Le prototype apporte ses **écrans**, pas son backend. Le SaaS sait déjà importer un catalogue client avec mapping dynamique de colonnes ; le prototype ne sait lire qu'un seul format Excel figé. Ce qu'il faut construire est une **dimension fournisseur** greffée sur le pipeline existant, pas un second pipeline.

---

## Ce que le SaaS sait déjà faire

C'est le point le plus important de cet audit, parce qu'il change complètement le périmètre.

`backend/server.py` expose déjà un pipeline de catalogue complet :

| Endpoint | Rôle |
|---|---|
| `POST /catalogs/import/preview` | lit le fichier, propose un mapping de colonnes, renvoie 5 lignes d'aperçu |
| `POST /catalogs/import` | importe en créant une nouvelle version |
| `POST /catalogs/{id}/activate/{version_id}` | bascule la version active |
| `GET /catalog-template.csv` | modèle à remplir |
| `GET /catalog/search` | recherche dans le catalogue actif |

Et `suggest_mapping()` fait de la **détection automatique de colonnes** en deux passes — synonymes exacts, puis correspondance partielle — sur 16 champs standards déjà définis :

```
item_label (requis), item_code, family, unit, unit_price_ht,
purchase_price_ht, vat_rate, margin, brand, supplier_main,
supplier_alt_1, supplier_alt_2, delay, min_qty, currency, notes
```

Autrement dit : **la capacité BYOC existe déjà**. Un client peut déposer son propre CSV ou Excel, quelles que soient ses en-têtes, et le système propose le mapping.

Il y a même déjà une amorce de dimension fournisseur — `supplier_main`, `supplier_alt_1`, `supplier_alt_2`.

### Le manque exact

Trois **noms** de fournisseurs, mais **un seul prix**. Impossible de dire « le même article coûte 194,63 € chez Rexel et 211,40 € chez Prolians ». C'est précisément le trou que le module doit combler, et c'est un trou étroit — pas un produit à reconstruire.

---

## Audit du prototype

### Ce qui est réutilisable

**Les écrans, et c'est la vraie valeur.** Les deux interfaces utilisent exactement la même pile :

| Dépendance | SaaS | Prototype |
|---|---|---|
| react | 19.0.0 | 19.0.0 |
| tailwindcss | 3.4.17 | 3.4.17 |
| @radix-ui/react-dialog | 1.1.11 | 1.1.11 |
| react-router-dom | 7.15.0 | 7.15.0 |
| recharts | 3.6.0 | 3.6.0 |

Même version majeure partout, même bibliothèque de composants (`components.json`, shadcn/ui), même build (craco). Les 73 fichiers front du prototype sont donc **transposables quasi tels quels** — il ne reste qu'à brancher les appels API sur les endpoints du SaaS.

Les écrans qui valent le portage :

- le **comparateur**, avec un prix par fournisseur et un lien cliquable vers la fiche produit de l'enseigne (afdb.fr, rexel.fr, pointp.fr) ouvert dans un nouvel onglet ;
- le **tableau de bord de décision** (`/stats/decision`, `/stats/by-supplier`, `/alerts`), qui répond à « où est-ce que je perds de l'argent ».

### Ce qu'il faut jeter

**`backend/catalogue_parser.py` (159 lignes).** Verrouillé sur une seule mise en page : positions de colonnes en dur de `r[0]` à `r[21]`, onglets dont le nom doit commencer par un chiffre, codes articles au format `^[A-Z]{2,4}-\d`, et un onglet « Base articles » obligatoire pour les offres concurrentes.

C'est l'exact opposé du BYOC. Un client dont le fichier a les colonnes dans un autre ordre obtient zéro ligne. Le `suggest_mapping()` du SaaS est strictement supérieur.

Une seule chose à en extraire : l'**extraction des hyperliens Excel** (`row[17].hyperlink.target`), qui récupère l'URL de fiche produit quand elle est posée comme lien et non comme texte. Une dizaine de lignes à reprendre.

**MongoDB.** Le prototype tourne sur `motor` + un fichier `catalogue_data.json` statique. Le SaaS est sur PostgreSQL/Supabase avec RLS. Rien à porter.

**`POST /best-prices` (15 lignes).** Parcourt les offres et garde le prix minimum. La logique est bonne mais triviale, et la migration prévoit déjà la vue `v_best_offer_per_product` avec un index dédié `idx_offers_best_price`. À réécrire en SQL, pas à porter.

**Aucune notion de tenant.** Le prototype est mono-client par construction : pas de `tenant_id`, pas d'authentification, pas de rôles. Tout endpoint porté doit être rebranché sur `get_current` et le contexte tenant.

---

## Le schéma de données est déjà écrit

`supabase/migrations/20260912020000_module_fournisseur.sql` — **non encore appliquée**.

5 tables, 1 vue, 26 index, 7 politiques :

| Table | Cloisonnement | Rôle |
|---|---|---|
| `suppliers` | par tenant | les fournisseurs du client |
| `canonical_products` | par tenant | l'article « pivot », indépendant du fournisseur |
| `supplier_offers` | par tenant | N offres par article pivot — **le cœur du module** |
| `product_match_rules` | **global** | règles de rapprochement, mutualisées |
| `unit_conversions` | **global** | conversions d'unités, mutualisées |

La distinction globale / par tenant est délibérée et reste valide : les **règles** profitent à tous tes clients, les **prix** ne sortent jamais du tenant.

### Un piège corrigé avant qu'il ne coûte une panne

Les politiques de cette migration ciblaient uniquement `authenticated`. Or `blueseatra_app` a été **retiré** de ce rôle le 12/09/2026 (migration `20260912060000`), parce qu'il en héritait un CRUD complet sur `tenant_users` — une élévation de privilèges.

Appliquée telle quelle, la migration aurait rendu les 5 tables **invisibles** au chemin métier : zéro ligne, sans erreur. Exactement le mode de défaillance qui a coûté trois pannes cette nuit-là.

Les politiques ciblent désormais `authenticated, blueseatra_app`, et le test `test_les_politiques_metier_ciblent_blueseatra_app` balaie les migrations pour empêcher que ça revienne.

---

## Le moteur de rapprochement existe aussi

`backend/matching.py`, 708 lignes, contient déjà `normalize()`, `match_line()` et `build_quote_lines()` — le rapprochement demande client → article de catalogue, avec score.

Le module fournisseur a besoin d'un rapprochement **différent mais voisin** : article fournisseur A → article pivot, pour savoir que la réf. Rexel X et la réf. Prolians Y désignent le même produit.

La fonction `normalize()` est directement réutilisable. La logique de score de `match_line()` sert de base, mais les critères changent : pour un produit, ce sont l'EAN, la référence fabricant, la marque et les attributs techniques qui décident — pas la proximité de libellé, qui n'est qu'un dernier recours.

---

## Découpage proposé

### Lot 0 — la mesure qui décide de tout

**Avant d'écrire une ligne de code.**

Mesurer le taux de rapprochement automatique réel sur 5 vraies listes de prix fournisseurs, environ 100 articles, en comptant :

- rapprochements corrects sans intervention ;
- rapprochements proposés mais à corriger ;
- articles non rapprochés du tout ;
- **faux positifs** — deux produits différents fusionnés. Le plus grave : ça fait chiffrer un article au prix d'un autre.

Seuils de décision :

| Taux automatique | Décision |
|---|---|
| au-dessus de 80 % | construire le module tel que prévu |
| entre 50 et 80 % | construire, mais l'écran de résolution manuelle devient le cœur du produit, pas un accessoire |
| en dessous de 50 % | ne pas construire. Le client passerait son temps à corriger |

Une demi-journée. Elle peut économiser des semaines.

### Lot 1 — la dimension fournisseur dans l'existant

Appliquer la migration corrigée, puis étendre `STANDARD_FIELDS` pour qu'un fichier fournisseur soit importable par le pipeline **déjà en place** : `supplier_name`, `supplier_ref`, `ean`, `manufacturer_ref`, `price_date`, `discount_pct`, `product_url`.

Reprendre l'extraction des hyperliens Excel du prototype.

À ce stade, aucun écran nouveau : on vérifie qu'un tarif fournisseur entre correctement en base, avec versionnage.

### Lot 2 — identité produit et résolution

Le rapprochement article fournisseur → `canonical_products`, en cascade : EAN, puis référence fabricant, puis marque plus attributs, puis libellé normalisé en dernier recours.

Et l'écran de résolution des cas douteux, alimenté par l'index `idx_offers_resolution_queue` déjà prévu. Sa priorité dépend directement du résultat du lot 0.

### Lot 3 — comparaison et décision

Portage du comparateur et du tableau de bord du prototype, rebranchés sur la vue `v_best_offer_per_product`.

C'est le lot le plus rapide, puisque les composants React sont compatibles.

### Lot 4 — branchement sur le devis

Le vrai gain métier : au chiffrage, proposer le meilleur prix à spécification égale, et tracer quel fournisseur a été retenu et à quelle date de prix.

C'est aussi le lot le plus sensible — il touche `matching.py` et `quote_scenarios.py`, donc le chemin de production des devis. À ne pas commencer avant que les lots 1 à 3 soient stables.

---

## Sur le sous-domaine `fournisseur.blueseatra.com`

Deux options, et la question mérite d'être tranchée avant le lot 3.

**Un seul service, une route `/fournisseurs`.** Le module est un onglet du SaaS. Une seule authentification, un seul déploiement, le contexte tenant déjà en place. C'est cohérent avec ta décision d'en faire un module vendable du SaaS plutôt qu'un produit séparé.

**Un service distinct sur le sous-domaine.** Justifié seulement si tu veux le vendre à des clients qui n'ont pas Blueseatra. Coût réel : une seconde authentification, un second déploiement, un partage de session entre domaines, et le risque de dupliquer la logique de chiffrage.

Recommandation : **une route dans le SaaS**, et le sous-domaine en simple redirection tant qu'il n'y a pas de client qui l'achète seul. Ça reste réversible ; l'inverse ne l'est pas.

---

## Ce qu'on ne fait pas, et pourquoi

- **Pas de catalogue fournisseur fourni par Blueseatra.** Décision confirmée : c'est le client qui apporte ses tarifs. Héberger des prix de distributeurs poserait un problème juridique et un travail de maintenance sans fin.
- **Pas de collecte automatique sur les sites fournisseurs.** Fragile, juridiquement risqué, et sans valeur tant que le rapprochement manuel n'est pas résolu.
- **Pas de reprise du backend du prototype.** MongoDB, parseur figé, aucun cloisonnement. Le porter coûterait plus cher que de l'écrire dans l'architecture existante.
- **Pas de nouveau pipeline d'import.** Celui du SaaS fait déjà mieux.
