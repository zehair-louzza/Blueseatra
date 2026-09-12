# Écran de recherche et comparaison fournisseurs (frontend)

Route `/app/fournisseurs` — `frontend/src/pages/SupplierSearch.js`.
Consomme `GET /api/fournisseurs/recherche` tel que décrit dans
`docs/contrat-api-fournisseurs.md`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/pages/SupplierSearch.js` | page : barre de recherche, états (vide / chargement / erreur), orchestration des relances |
| `src/components/SupplierSearchSummary.js` | bandeau de garantie d'inclusion (`total` + `comparables` côte à côte, prix min/médian/max, écart) et bandeau des termes reconnus |
| `src/components/SupplierCheapestPanel.js` | encart de négociation « le moins cher chez chaque fournisseur » + écart % moins cher → plus cher |
| `src/components/SupplierResultsTable.js` | tableau trié par prix net HT croissant (tablette/ordinateur) et liste de cartes (portable de chantier) |
| `src/components/SupplierRefinePanels.js` | « isolés car d'une autre nature » (relance avec `inclure_qualifiants=true`) et « affinez votre recherche » |
| `src/components/TruncatedText.js` | troncature sur une ligne + info-bulle avec le libellé complet |
| `src/lib/fournisseursApi.js` | appel API + jeu de données d'exemple et commutateur `UTILISER_JEU_EXEMPLE` |
| `src/lib/fournisseursFormat.js` | formatage français des prix (deux décimales, séparateur fr-FR), entiers, pourcentages |

## Choix

**La garantie d'inclusion est affichée, pas racontée.** `total` et
`comparables` sont rendus côte à côte en permanence, avec la mention du nombre
de produits mis à part. Masquer l'écart romprait la promesse du produit : rien
n'est caché, les produits d'une autre nature sont isolés, jamais supprimés.

**Les termes reconnus sont un outil de débogage utilisateur.** Le bandeau
montre que « ph+n » a été compris comme « 1P+N », « U+N », « phase neutre ».
Quand le bandeau est vide, il le dit explicitement : sans ce retour, une
requête sans résultat est indébuggable côté chiffreur.

**L'état de la recherche vit dans l'URL** (`q`, `inclure_qualifiants`,
`limite`). Cliquer un qualifiant isolé ou une valeur de `criteres_a_affiner` ne
fait que réécrire l'URL : la recherche est rejouable, partageable, et le bouton
« retour » du navigateur défait l'affinage.

**Un jeu de données d'exemple, pas des données inventées dans le rendu.**
`fournisseursApi.js` reproduit la charge utile du contrat (tri par prix,
qualifiants isolés avec nombre et prix médian, critères hétérogènes, erreurs
400/422 au format axios). Le commutateur `REACT_APP_FOURNISSEURS_MOCK=false`
bascule sur le vrai endpoint sans toucher aux composants.

**Texte en français en dur, hors i18n.** L'écran manipule du vocabulaire de
négoce électrique français (« 1P+N », « courbe C », « prix net HT », « unité de
vente ») et le catalogue source est français : une traduction anglaise
donnerait un écran illisible. Seule l'entrée de menu passe par `nav2.suppliers`
(FR/EN), comme les autres entrées.

**Lisibilité sur un portable de chantier.** Les désignations font 80 à 140
caractères : elles sont tronquées sur une ligne avec info-bulle (déclencheur
`<button>`, donc accessible au clavier, plus repli `title`). Sous `md`, le
tableau est remplacé par une carte par offre pour qu'aucun texte ne soit coupé.
Les prix sont alignés à droite, en `tabular-nums`, deux décimales, séparateur
français.

**Aucune dépendance npm ajoutée** : uniquement les composants shadcn/ui déjà
présents, `lucide-react`, `sonner` et `react-router-dom`.

## Limite de vérification

La chaîne JS n'est pas installable dans le bac à sable (aucun `node_modules`) :
la compilation et le rendu réels n'ont pas pu être exécutés. Ont été vérifiés :
analyse syntaxique de tous les fichiers touchés, résolution des imports et
concordance des noms exportés, et exécution du jeu de données d'exemple en
Node (tri par prix croissant, comptages `total`/`comparables`, réintégration
des qualifiants, requête sans résultat, erreurs 400 et 422).
