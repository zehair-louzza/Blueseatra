# Lot 0 — mesures sur données réelles

Mesures effectuées sur le catalogue consolidé **914 628 produits, 5 fournisseurs** (Rexel, Prolians, Point.P, La Plateforme du Bâtiment, SFIC), prix nets négociés réels.

Objet : décider si le module Fournisseur est constructible, et sous quelle forme. Toutes les valeurs ci-dessous sont reproductibles avec les scripts de `scripts/fournisseur/`.

---

## Verdict

**Le rapprochement automatique de produits entre fournisseurs n'est pas réalisable.** La référence fabricant, seul identifiant commun disponible, produit **98,6 % de faux rapprochements**.

**En revanche, la recherche dans le catalogue consolidé fonctionne parfaitement** et délivre l'essentiel de la valeur : trouver le prix réel de ce qu'on chiffre, parmi 914 628 produits.

La forme retenue combine les deux : une recherche à recall garanti, et un regroupement des équivalents **à l'intérieur des résultats**, où une erreur reste visible et corrigeable.

---

## 1. Ce que contiennent réellement les données

| Fournisseur | Références | EAN renseigné |
|---|---|---|
| Rexel | 747 771 | 77,8 % |
| Prolians | 79 894 | **0 %** |
| Point.P | 58 250 | 93,8 % |
| La Plateforme | 24 600 | **0 %** |
| SFIC | 4 113 | **0 %** |

Signaux disponibles sur l'ensemble : référence fournisseur 100 %, marque 98,5 %, référence fabricant 93,9 %, prix net 97,5 %, **EAN 69,5 %** — mais concentré sur deux fournisseurs seulement.

### Le recouvrement entre fournisseurs est quasi nul

| Critère de rapprochement | Présent chez ≥ 2 fournisseurs |
|---|---|
| Code EAN | 149 EAN, soit **0,02 %** |
| Référence fabricant | 5 533 réfs, soit **0,66 %** |
| Marque + référence fabricant | 2 364 couples, soit **0,28 %** |

Après filtrage rigoureux (référence ≥ 8 caractères, même marque, unicité chez chaque fournisseur, prix > 1 €) : **739 références réellement comparables, soit 0,08 % du catalogue.**

Ces cinq fournisseurs ne se concurrencent pas, ils se **complètent** : Rexel fait l'éclairage et le génie climatique, Point.P le carrelage et la toiture, SFIC les portes et plafonds, La Plateforme le généraliste par métier. Un comparateur de prix n'a presque rien à comparer.

---

## 2. Pourquoi la référence fabricant est inutilisable

Méthode : sur les 630 945 lignes portant **à la fois** un EAN à 13 chiffres et une référence fabricant, l'EAN sert d'**arbitre** — il dit la vérité sur l'identité produit. On juge donc n'importe quel autre critère en comparant son verdict au sien.

- **Positifs** : paires de même EAN → vraiment le même produit
- **Négatifs** : paires de même référence fabricant mais d'EAN différent → confusion à éviter

Résultat : **7 062 paires jugées identiques par la référence, dont 101 correctes. 98,6 % de faux.**

### Deux causes, toutes deux dans la donnée

**La référence désigne une gamme, pas un produit.** Chez Point.P, `COF12LINT` couvre 58 coffres de linteau de tailles différentes. `645640` couvre toutes les pointures d'une chaussure PUMA. `40062` toute une série de carrelage Cinca en formats variés. La variante n'existe que dans le descriptif.

**Les références courtes se percutent par hasard.** `2201` relie un câble LED Rexel (EUROPOLE) et une faïence Point.P (CINCA) — deux univers sans aucun rapport. Et 8 826 références sont dupliquées chez un même fournisseur, ce qui suffit à prouver qu'une référence fabricant n'identifie pas un produit de façon unique.

---

## 3. Effet de chaque mesure additionnelle

Sur le jeu arbitré par EAN — 149 vrais doublons contre 6 961 confusions :

| Mesure, prise seule | Vrais conservés | Confusions restantes |
|---|---|---|
| aucune (référence seule) | 149 | 6 961 |
| marque identique | 145 | 1 120 |
| prix dans un rapport ≤ 1,6 | 119 | 1 766 |
| unité de vente identique | 120 | 5 510 |
| attributs du descriptif compatibles | 136 | 5 603 |
| référence ≥ 8 caractères | 69 | 744 |
| libellés proches (≥ 45 %) | 64 | 1 095 |

### La similarité de libellé est un piège

Elle paraît séduisante et détruit tout : cumulée aux autres, elle fait chuter le rappel de **97 % à 9 %**.

La raison est structurelle : **deux fournisseurs décrivent le même produit avec des mots entièrement différents.** Le même disjoncteur devient « Disjoncteur FIXMATIC AUTO 10 A courbe C Phase + Neutre GEWISS » chez l'un et « HAGER Disjoncteur Phase + Neutre 10A 3kA Courbe C bornes à vis 1 Module » chez l'autre.

Le descriptif doit donc détecter une **contradiction**, jamais mesurer une **ressemblance**.

### Combinaison retenue

`marque identique` + `prix dans un rapport ≤ 1,6` + `attributs du descriptif compatibles`

**97,2 % des confusions éliminées, 62 % des vrais doublons conservés.** Il reste 193 confusions pour 92 vrais doublons — donc 67,7 % de faux au lieu de 98,6 %.

C'est une amélioration de facteur 30, et cela reste insuffisant pour décider seul. Ce test est volontairement adverse : il ne contient que des paires partageant une référence fabricant, soit le pire cas d'entrée possible.

---

## 4. Ce qui est extrait du descriptif

Puisque trois fournisseurs sur cinq n'ont aucun EAN, le descriptif est leur seule source d'identité.

**Attributs de variante** — dimensions (`45x45`, `60x120`, triées pour que `45x60` égale `60x45`), pointure (`T. 40`), finition (mat, brillant, rectifié, satiné), couleur, conditionnement (`lot de 3`, `couronne de 100`).

**Grandeurs techniques** — ampérage, milliampérage, watt, volt, section en mm², litre, modules, kelvin, lumen, indices IP et IK, courbe de déclenchement.

**Nombre de pôles** — `1P`, `2P`, `3P`, `1P+N`, `3P+N`, unipolaire à tétrapolaire. Discriminant numéro un de l'appareillage électrique : son absence dans une première version regroupait du 2P, du 1P+N, du 3P et du 4P dans un seul ensemble affiché à **+145 % d'écart** comme s'il s'agissait du même article.

**Gamme** — jetons mêlant lettres et chiffres (`ic60n`, `idt40t`, `dnx3`, `ba13`). Comparés par recouvrement de moitié, et non par simple intersection : `Acti9 iC60N` et `Acti9 iDT40T` partagent `acti9` et seraient sinon confondus.

**Famille** — différentiel contre simple, étanche contre encastré, télérupteur contre contacteur contre minuterie. Éliminatoire.

### Deux bugs trouvés par la mesure

La normalisation remplaçait tout caractère non alphanumérique par une espace, donc `2,5 mm²` devenait `2 5 mm2` et la section était perdue. Conséquence mesurée : confusion systématique entre fil 1,5 mm² et 2,5 mm², deux articles de prix différents. Les séparateurs décimaux sont désormais protégés avant normalisation.

La bande de prix ne s'appliquait qu'entre le germe et chaque candidat, pas à l'ensemble du groupe. Une chaîne d'ajouts successifs pouvait donc couvrir un rapport très supérieur à 1,6. Elle porte maintenant sur le minimum et le maximum du groupe.

---

## 5. La forme retenue

### Recherche par inclusion — garantie absolue

Tout produit contenant les mots tapés remonte, même si son libellé contient bien davantage. La pertinence sert à **trier**, jamais à **filtrer** : aucun produit ne peut être écarté par un score trop faible.

Vérifié à chaque requête par comptage en force brute, indépendamment du moteur :

| Requête | Moteur | Force brute | Conforme |
|---|---|---|---|
| peinture | 2 467 | 2 467 | oui |
| disjoncteur 16a | 848 | 848 | oui |
| carrelage 60x60 | 1 503 | 1 503 | oui |
| vis inox | 3 586 | 3 586 | oui |
| cable 2,5 | 2 597 | 2 597 | oui |
| placo ba13 | 125 | 125 | oui |
| laine de verre | 578 | 578 | oui |

Les pluriels sont absorbés sans dictionnaire par réduction à la racine, et les décimales sont préservées pour que `2,5` reste cherchable.

### Regroupement à l'intérieur des résultats

Le même rapprochement, inapplicable à l'échelle du catalogue, devient acceptable appliqué à un résultat de recherche :

- les candidats sont déjà restreints au sujet demandé, ce qui élimine les collisions de hasard — une recherche ne rapproche jamais un câble LED d'une faïence ;
- l'utilisateur **voit** le groupe en contexte. Une erreur se repère d'un coup d'œil, alors qu'un rapprochement automatique invisible se découvre sur la facture.

Chaque produit trouvé appartient à exactement un groupe, seul si nécessaire. Un contrôle de couverture vérifie à chaque requête que la somme des groupes égale le nombre de produits trouvés.

Exemple réel sur `disjoncteur 16a` — 848 produits, 438 groupes, 15 comparables entre fournisseurs :

```
Acti9 iDT40T Disjoncteur Modulaire 3P+N 16A    3 fournisseurs, écart +58 %
     80,25 EUR  [La Plateforme]
     91,80 EUR  [La Plateforme]  version auto/vis
     97,53 EUR  [Rexel]          version auto/vis
    126,62 EUR  [Prolians]
```

---

## 6. Conséquences pour le plan d'intégration

Le découpage de `docs/integration-module-fournisseur.md` reste valide, avec deux inflexions.

**Le lot 2 change de nature.** L'identité produit en cascade EAN → référence fabricant → marque et attributs est à abandonner : l'EAN couvre deux fournisseurs sur cinq et se recoupe à 0,02 %, la référence fabricant produit 98,6 % de faux. Le lot 2 devient l'extraction d'attributs depuis le descriptif, seule voie mesurée comme viable.

**Le lot 3 devient le cœur du produit, et non un affichage.** La promesse « le moins cher à spécification égale » n'est pas tenable automatiquement. La promesse tenable est : « cherche, vois les prix réels de tes cinq fournisseurs, et compare quand un équivalent existe ».

**Ce qu'il ne faut pas promettre.** Un rapprochement automatique fiable, une couverture large du comparatif — 0,08 % du catalogue est réellement comparable —, et une économie chiffrée à l'avance.

---

## Reproduire ces mesures

```
scripts/fournisseur/mesure_rapprochement.py   # taux de rapprochement, seuils, top-N
scripts/fournisseur/mesure_confusion.py       # arbitrage par EAN, effet de chaque mesure
scripts/fournisseur/recherche_groupee.py      # recherche par inclusion + regroupement
```

Le catalogue consolidé doit être converti en CSV au préalable ; le chemin attendu est indiqué en tête de `recherche_groupee.py`.
