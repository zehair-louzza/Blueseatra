# Format unique des catalogues fournisseurs Blueseatra

Version 1.0 du 2 octobre 2026. Ce format s'applique à tous les fournisseurs (Rexel, Prolians, Point.P, YESSS, La Plateforme du Bâtiment, SFIC, Au Forum du Bâtiment, Chausson, Icilux et les suivants). Une ligne correspond à **une offre** : un produit vendu par un fournisseur à un prix donné.

Objectif : quand on tape « disjoncteur 16A courbe C ph+n », **un même produit apparaît une seule fois**, avec le prix de chaque fournisseur, même s'il est décrit différemment chez chacun.

## Pourquoi un format unique

Constat mesuré le 2 octobre 2026 sur les 967 563 offres actives :

| Fournisseur | Offres | EAN valide | Réf. fabricant | Marque | Sans prix |
|---|---:|---:|---:|---:|---:|
| Rexel | 747 771 | 77,8 % | 100 % | 100 % | 0 % |
| Prolians | 79 894 | **0 %** | 72,9 % | 82,6 % | **28,0 %** |
| Point.P | 58 250 | 93,8 % | 90,8 % | 100 % | 0 % |
| YESSS | 29 053 | 89,0 % | 100 % | 100 % | 0 % |
| La Plateforme du Bâtiment | 24 600 | **0 %** | **0 %** | 100 % | 0 % |
| SFIC | 17 271 | 0,1 % | **0 %** | 100 % | 0,2 % |
| Au Forum du Bâtiment | 14 515 | 94,9 % | 79,2 % | 99,3 % | 0,9 % |
| Chausson Matériaux | 199 | 0 % | 0 % | 0 % | 0 % |
| Icilux | 123 | 0 % | 0 % | 0 % | 0 % |

Trois manques communs à **tous** les fournisseurs :

- **Unité normalisée** : vide sur 100 % des offres. Il existe plus de 40 écritures différentes (« Pièce », « pièce », « u », « Unité », « 1 », « 100 », « Cent », « Boîte de 100 »…).
- **Produit commun** : aucun lien entre fournisseurs (0 %). Pourtant, 13 194 produits ont le même EAN chez au moins 2 fournisseurs, et 13 394 la même marque et la même référence fabricant.
- **Caractéristiques techniques** (calibre, courbe, pôles, section…) : jamais extraites (0 %).

Le même produit chez trois fournisseurs :

| Fournisseur | Désignation | Marque | Unité | Famille | Prix net HT |
|---|---|---|---|---|---:|
| Rexel | Barrette à cosses Cosga avec platine métal 150x45mm et fixation par vis D=3,5mm | Legrand | Pièce | Distribution et gestion de l'énergie | 43,11 € |
| Point.P | Barrette de coupure Cosga - platine métal - 150x45 mm | LEGRAND | Pièce | Electricité, ventilation | 48,67 € |
| YESSS | Barrette à cosses Cosga avec platine métal 150x45mm et fixation par vis Ø3,5mm | LEGRAND S.N.C. | 1 | BARRETTES | 54,03 € |

Les trois offres ont le même EAN, 3245060343880, et la même référence, 034388. Ce format les réunit sous une seule clé, `GTIN:03245060343880`, et montre l'écart de 25 %.

## Standards suivis

- **GTIN / EAN** (GS1) : identifiant mondial du produit, clé de contrôle vérifiée.
- **ETIM** : classification technique internationale des produits électriques, sanitaires et CVC, utilisée par les distributeurs. Exemple : la classe [EC000042 « Miniature circuit breaker (MCB) »](https://viewer.etim-international.com/class/EC000042?lang=en-US). ETIM France la présente comme [le standard international pour la classification des données techniques](https://www.etim-france.fr/) de ces secteurs.
- **UN/CEFACT Recommandation 20** : [codes d'unités de mesure du commerce international](https://unece.org/trade/uncefact/cl-recommendations) (H87 pièce, MTR mètre, MTK m²…).
- Les colonnes reprennent les notions du format d'échange fabricants-distributeurs **FAB-DIS**, qui s'appuie lui aussi sur [ETIM](https://simpleone.fr/quest-ce-quun-logiciel-pim-que-peut-on-gerer-avec-un-logiciel-pim/). Un fichier fabricant pourra donc être converti sans perte.

## Les colonnes

Fichier `.xlsx`, ou `.csv` séparateur `;` encodé en `utf-8-sig`. Les décimales s'écrivent avec un point. Une colonne vide reste vide : jamais « N/A », « - » ou « 0 ».

### A. Identité du produit (sert à reconnaître les produits identiques)

| Colonne | Obligatoire | Règle | Exemple |
|---|---|---|---|
| `gtin` | si connu | 8, 12, 13 ou 14 chiffres, **clé GS1 vérifiée**, complété à 14 chiffres par des zéros à gauche. Un code à la clé fausse va dans `gtin_rejete`. | `03245060343880` |
| `gtin_rejete` | non | Code fourni mais invalide (code interne, mauvaise clé), conservé tel quel. | |
| `marque` | oui | Nom canonique issu de la **table des marques** (voir les règles). | `Legrand` |
| `marque_source` | oui | Marque telle que fournie. | `LEGRAND S.N.C.` |
| `ref_fabricant` | si connue | Référence du fabricant telle qu'imprimée, sans le préfixe du distributeur. | `034388` |
| `ref_fabricant_cle` | calculée | Majuscules, sans espaces, points, tirets ni barres, zéros de tête retirés. | `34388` |
| `cle_produit` | calculée | `GTIN:<gtin>` si le GTIN est valide, sinon `MR:<marque_cle>:<ref_fabricant_cle>` si la référence fait au moins 3 caractères, sinon vide. | `GTIN:03245060343880` |
| `niveau_identification` | calculée | `GTIN`, `MARQUE_REF` ou `AUCUN`. | `GTIN` |

### B. Offre du fournisseur

| Colonne | Obligatoire | Règle | Exemple |
|---|---|---|---|
| `fournisseur` | oui | Nom de la liste fermée des fournisseurs. | `YESSS` |
| `ref_fournisseur` | oui | Code article du distributeur, unique chez lui. | `BLI525509` (Rexel) |
| `url_fiche` | conseillé | Lien vers la **fiche produit**, pas vers une catégorie. | |
| `date_tarif` | oui | Date du prix, `AAAA-MM-JJ`. | `2026-09-23` |
| `disponibilite` | non | `STOCK`, `COMMANDE`, `ARRETE`, `INCONNU`. | `STOCK` |

### C. Description

| Colonne | Obligatoire | Règle | Exemple |
|---|---|---|---|
| `designation_source` | oui | Texte du fournisseur, **jamais modifié**. | `Barrette à cosses Cosga avec platine métal…` |
| `designation` | calculée | Désignation propre et homogène : `<Type> <marque> <gamme> <caractéristiques clés>`. Ponctuation de tête retirée, espaces doublés supprimés, unités écrites de la même façon. | `Barrette de coupure Legrand Cosga platine métal 150 x 45 mm` |
| `texte_recherche` | calculée | Minuscules, sans accents, décimales avec un point, unités collées au nombre, abréviations dépliées (`ph+n` → `1p+n`, `cbe` → `courbe`). Sert uniquement à la recherche. | `barrette coupure legrand cosga platine metal 150x45mm` |

### D. Classement commun

| Colonne | Obligatoire | Règle | Exemple |
|---|---|---|---|
| `classe_etim` | conseillé | Code ETIM de la classe. | `EC000042` |
| `type_produit` | oui | Nom court de la classe en français, dans la liste fermée Blueseatra. | `Disjoncteur modulaire` |
| `famille` | oui | Une des familles TCE communes (voir la liste). | `Électricité – protection` |
| `famille_source` / `sous_famille_source` | oui | Classement du fournisseur, conservé. | `BARRETTES` |

Familles communes : Électricité – protection · Électricité – appareillage · Électricité – distribution et tableaux · Câbles et conducteurs · Conduits et cheminement · Éclairage · Courants faibles et VDI · Sécurité incendie et alarme · Chauffage · Climatisation et ventilation · Plomberie – tubes et raccords · Sanitaire et robinetterie · Évacuation · Quincaillerie · Fixation et visserie · Outillage · EPI · Plâtrerie et isolation · Menuiserie et fermetures · Peinture et revêtements muraux · Revêtements de sols · Gros œuvre et maçonnerie · Couverture et étanchéité · Consommables et produits d'entretien.

### E. Caractéristiques techniques (colonnes typées, unité fixe)

Une colonne ne se remplit que si la valeur est **lue dans la source** : désignation, fiche ou attributs du fournisseur. Elle n'est jamais devinée.

| Colonne | Unité | Valeurs |
|---|---|---|
| `poles` | | `1P`, `1P+N`, `2P`, `3P`, `3P+N`, `4P` |
| `calibre_a` | A | nombre (`16`) |
| `courbe` | | `B`, `C`, `D`, `K`, `Z` |
| `pouvoir_coupure_ka` | kA | nombre (`4.5`) |
| `sensibilite_ma` | mA | nombre (`30`) |
| `type_differentiel` | | `AC`, `A`, `F`, `B`, `Asi` |
| `section_mm2` | mm² | nombre (`2.5`) |
| `nb_conducteurs` | | nombre (`3`) |
| `composition_cable` | | `3G2.5` |
| `tension_v` | V | nombre |
| `puissance_w` | W | nombre |
| `flux_lm` | lm | nombre |
| `temperature_couleur_k` | K | nombre (`4000`) |
| `indice_ip` / `indice_ik` | | `IP65`, `IK08` |
| `diametre_mm`, `longueur_mm`, `largeur_mm`, `hauteur_mm`, `epaisseur_mm` | mm | nombre |
| `couleur` | | liste fermée (`blanc`, `noir`, `gris`, `anthracite`, `alu`…) |
| `matiere` | | liste fermée (`cuivre`, `PER`, `multicouche`, `PVC`, `acier galva`, `inox`…) |
| `attributs_autres` | | JSON `{"code ETIM": valeur}` pour le reste |

### F. Unités et prix (pour comparer ce qui est comparable)

| Colonne | Obligatoire | Règle | Exemple |
|---|---|---|---|
| `unite_base` | oui | Unité dans laquelle on compare : `U` (pièce, H87), `M` (MTR), `M2` (MTK), `M3` (MTQ), `KG` (KGM), `L` (LTR), `PAIRE` (PR). | `U` |
| `conditionnement` | oui | `UNITE`, `BOITE`, `SAC`, `ROULEAU`, `TOURET`, `CARTON`, `LOT`, `BIDON`, `PALETTE`. | `BOITE` |
| `qte_par_conditionnement` | oui | Nombre d'unités de base dans ce que l'on achète. | `100` |
| `unite_source` | oui | Unité telle que fournie, conservée. | `Boîte de 100` |
| `prix_net_ht` | oui | Prix d'achat HT de ce que l'on achète (le conditionnement), en euros. | `12.40` |
| `prix_public_ht` | si connu | Prix public HT du même conditionnement. | |
| `prix_net_ht_unite_base` | calculée | `prix_net_ht / qte_par_conditionnement`. **C'est ce prix-là qu'on compare.** | `0.124` |
| `eco_contribution_ht` | si connue | Séparée du prix, jamais additionnée en silence. | `0.02` |
| `taux_tva` | oui | `20`, `10`, `5.5`, `0`. | `20` |
| `statut_prix` | oui | `NET_CLIENT`, `PUBLIC`, `PROMO`, `SANS_PRIX`. | `NET_CLIENT` |

### G. Qualité

| Colonne | Règle |
|---|---|
| `anomalies` | Codes séparés par une barre verticale : `SANS_PRIX`, `PRIX_NET_SUP_PUBLIC`, `PRIX_EXTREME`, `GTIN_CLE`, `REF_DOUBLON`, `DESIGNATION_AMPUTEE`, `UNITE_INCONNUE`, `UNITE_SUPPOSEE`, `ECART_PRIX_PRODUIT` (plus de 3 fois le prix médian du même produit), `CONFLIT_ATTRIBUT` (deux fournisseurs donnent une caractéristique différente pour le même produit). |
| `score_qualite` | 0 à 100 : GTIN 30, marque et réf. 25, unité et conditionnement 15, prix 15, type et famille 10, au moins 2 caractéristiques 5. |

## Règles de nettoyage

1. **Ne jamais écraser la source.** Chaque valeur nettoyée garde sa colonne `_source`.
2. **GTIN** : chiffres seulement, longueur 8, 12, 13 ou 14, clé GS1 juste, pas de code composé uniquement de zéros. Complété à 14 chiffres.
3. **Marque** : passage en minuscules et retrait des accents, ponctuation remplacée par des espaces, puis retrait des formes juridiques et suffixes (`sa`, `sas`, `sasu`, `snc`, `sarl`, `eurl`, `gmbh`, `spa`, `srl`, `ltd`, `inc`, `ag`, `bv`, `france`, `group`, `industries`, `distribution`…). On obtient la clé de marque (`legrandsnc` devient `legrand`), puis la **table des marques** donne le nom canonique.
   - **Alias prouvés par le GTIN** : deux écritures qui partagent au moins 5 GTIN sont la même marque (40 paires trouvées, par exemple `CAME / CAME SA` sur 576 GTIN, ou `Golmar / Evicom Golmar` sur 320).
   - **Exception distributeurs** : une « marque » rattachée par GTIN à plusieurs marques différentes est un distributeur, pas un fabricant (`L2S Systorm` avec Hikvision et TP-Link). Elle n'est jamais fusionnée.
4. **Référence fabricant** : retirer le préfixe distributeur quand il précède la référence (Rexel : `BLI525509` → `525509`, `RZB982552.002` → `982552.002`). La clé de comparaison est en majuscules, sans séparateurs ni zéros de tête.
5. **Unités** : table de correspondance fermée.
   - `Pièce`, `pièce`, `u`, `Unité`, `1` → `U` × 1.
   - `Cent`, `100`, `Boîte de 100` → `U` × 100 (`BOITE`) ; `Mille`, `1000` → `U` × 1000.
   - `Mètre`, `m` → `M` ; `Mètre carré`, `m²` → `M2` ; `Rouleau de 50 m` → `M` × 50 (`ROULEAU`).
   - **Nombre seul** (YESSS : `100`, `1000`) : le prix est donné pour ce nombre d'unités. On l'a vérifié sur 203 EAN communs avec Rexel (rapport médian de 125 à 133). Pour un câble, l'unité de base est le mètre : « YSLY-JZ 3G1 C100 » à 1 726,96 € les 1 000 revient à 1,73 €/m.
   - **Quantité dans la désignation**, quand l'unité est un contenant (« Sac », « Boîte », « Paquet ») : « sac de 25 kg » → `KG` × 25 ; « sachet de 28 pièces » → `U` × 28 ; « boîte de 1,08 m² » → `M2` × 1,08.
   - **Unité absente** (Prolians, 100 % des offres) : la pièce est supposée, et l'offre est signalée `UNITE_SUPPOSEE`.
   - Une unité inconnue est signalée `UNITE_INCONNUE`, jamais devinée.
6. **Désignation** : retirer la ponctuation de tête (les 47 libellés Rexel du type « , D 350 H 1, blanc »), réduire les espaces, écrire les unités de la même façon (`16 A`, `2,5 mm²`, `4,5 kA`, `IP65`). Ne rien inventer : un type absent de la source reste vide.
7. **Prix** : un prix absent n'est jamais `0`. Un prix net supérieur au prix public, ou plus de 3 fois la médiane du même produit, est signalé.

## Trois niveaux de comparaison

| Niveau | Condition | Affichage |
|---|---|---|
| **Identique certain** | même `gtin` valide | une seule ligne produit, un prix par fournisseur |
| **Identique probable** | même `marque` canonique et même `ref_fabricant_cle` (au moins 3 caractères) | une seule ligne produit, marquée « même référence » |
| **Équivalent technique** | même `type_produit` et mêmes caractéristiques clés de la classe, marques différentes | des lignes séparées, regroupées sous « équivalents », jamais fusionnées |

Caractéristiques clés par classe, par exemple :

- disjoncteur : `poles` + `calibre_a` + `courbe` + `pouvoir_coupure_ka` ;
- interrupteur différentiel : `poles` + `calibre_a` + `sensibilite_ma` + `type_differentiel` ;
- câble : `composition_cable` (ou `nb_conducteurs` + `section_mm2`) + type de câble (`R2V`, `H07V-U`…) ;
- luminaire : `puissance_w` + `flux_lm` + `temperature_couleur_k` + `indice_ip`.

**Jamais** de rapprochement sur la seule ressemblance des désignations : deux libellés proches peuvent désigner deux calibres différents.

## Ce que voit l'utilisateur quand il tape une recherche

Recherche : « disjoncteur 16a courbe c ph+n ».

1. La requête est traduite en caractéristiques : `type_produit = Disjoncteur modulaire`, `poles = 1P+N`, `calibre_a = 16`, `courbe = C`.
2. Les offres sont filtrées sur ces colonnes, puis complétées par le texte de recherche.
3. Les résultats sont **regroupés par `cle_produit`**, avec une ligne par produit :

Exemple réel tiré de vos catalogues :

| Produit (clé) | Rexel | YESSS | Écart |
|---|---:|---:|---:|
| Disjoncteur Legrand DNX³ 4500 1P+N 16 A courbe C, vis/vis (réf. 406774, `GTIN:03245064067744`) | 9,16 € | 28,64 € | +213 % |
| Disjoncteur Legrand DNX³ 4500 1P+N 16 A courbe C, auto/auto (réf. 406783, `GTIN:03245064067836`) | 8,68 € | 27,89 € | +221 % |
| Disjoncteur Legrand DNX³ 1P+N 16 A courbe C 6 kA, auto/vis (réf. 406883, `GTIN:03245064068833`) | 21,03 € | 28,64 € | +36 % |

Aujourd'hui, ces offres sortent comme 6 lignes sans lien, avec 6 désignations différentes.

Le même tableau révèle un **conflit de caractéristiques** : pour le même GTIN 3245064067744, Rexel écrit « 4,5 kA » et YESSS « 6 kA ». Ce cas est signalé `CONFLIT_ATTRIBUT` sur le produit. La valeur retenue est celle du fabricant (fiche ETIM), sinon celle de la majorité des fournisseurs, et l'écart reste visible.

4. En dessous, les **équivalents techniques** des autres marques, triés par `prix_net_ht_unite_base`.

## Ce que le nettoyage apportera (mesuré)

| Indicateur | Aujourd'hui | Avec ce format |
|---|---:|---:|
| Produits reconnus identiques chez au moins 2 fournisseurs, par le GTIN | 0 lien | 13 194 |
| Produits reconnus identiques par marque et réf. fabricant | 0 lien | 13 394, dont ~4 400 avec Prolians qui n'a aucun GTIN |
| Écritures de marques | 2 082 | 1 971 clés, avant la table des alias |
| Écritures d'unités | plus de 40 | 7 unités de base |
| Offres avec un prix comparable par unité de base | 0 % | 100 % des offres avec un prix |

Les deux premiers chiffres se recoupent en partie : le total exact des produits comparables sera calculé lors du nettoyage complet.
