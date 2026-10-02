# Contrat d'API — recherche et comparaison fournisseurs

Base : `https://blueseatra-api.onrender.com/api`
Authentification : `Authorization: Bearer <jwt>` (identique au reste du SaaS).
Toutes les réponses sont cloisonnées par tenant.

---


![Comparer les prix](./assets/manuel/15b-comparateur-resultats.jpg)

![Chiffrage sur sources activables](./assets/schema-chiffrage.png)

## `GET /fournisseurs/recherche`

Recherche par inclusion sur le catalogue fournisseurs du tenant.

**Règle absolue :** tout produit contenant les termes demandés est renvoyé. La pertinence trie, elle ne filtre jamais.

### Paramètres

| Nom | Type | Défaut | Rôle |
|---|---|---|---|
| `q` | string | — | requête libre, obligatoire |
| `limite` | int | 50 | nombre de lignes de la liste principale (max 200) |
| `inclure_qualifiants` | bool | false | si `true`, les produits d'une autre nature réintègrent la liste principale |
| `famille` | string | — | restreint à une famille de produits (`raw_row.famille`, valeurs de `GET /fournisseurs/familles`) ; plafond de comparaison ramené à 1 000 offres |

La réponse rappelle `famille` (ou `null`) et `plafond` (5 000, ou 1 000 avec une famille) : `tronque` vaut `true` quand `total` atteint ce plafond — ce sont alors les offres **les moins chères** qui sont comparées.

### Réponse `200`

```json
{
  "requete": "disjoncteur 16a courbe c ph+n",
  "total": 126,
  "comparables": 59,
  "termes_reconnus": [
    {"saisi": "ph+n", "equivalences": ["1P+N", "Ph+N", "U+N", "phase neutre"]},
    {"saisi": "courbe", "equivalences": ["courbe", "Cbe", "Crb"]}
  ],
  "prix": {
    "min": 6.83, "max": 200.67, "median": 32.61, "ecart_pct": 2838,
    "unites_differentes": false
  },
  "resultats": [
    {
      "id": "uuid",
      "fournisseur": "Rexel",
      "designation": "SN201SL Disjoncteur modulaire - 1P+N - 16A - courbe C",
      "marque": "ABB",
      "reference_fournisseur": "SN201SL16C",
      "reference_fabricant": "SN201SL16C",
      "code_ean": "4016779584241",
      "prix_net_ht": 6.83,
      "prix_public_ht": 21.34,
      "unite_vente": "Pièce",
      "url_produit": null,
      "cle_produit": "GTIN:04016779584241",
      "niveau_identification": "GTIN",
      "unite_base": "U",
      "qte_par_conditionnement": 1.0,
      "prix_unite_base_ht": 6.83,
      "unite_code": "OK",
      "marque_canonique": "ABB",
      "anomalies": [],
      "nb_fournisseurs_produit": 2
    }
  ],
  "moins_cher_par_fournisseur": [
    {"fournisseur": "Rexel", "prix_net_ht": 6.83, "prix_unite_base_ht": 6.83, "unite_base": "U", "qte_par_conditionnement": 1.0, "designation": "...", "id": "uuid"},
    {"fournisseur": "YESSS", "prix_net_ht": 155.14, "prix_unite_base_ht": 1.5514, "unite_base": "M", "qte_par_conditionnement": 100.0, "designation": "...", "id": "uuid"}
  ],
  "produits_identiques": [
    {
      "cle_produit": "GTIN:00731304338444",
      "designation": "Easy UPS BVS - onduleur 1 ph line-interactive - 230V - 500VA - 4 prise Schuko/FR",
      "marque": "Schneider Electric",
      "reference_fabricant": "BVS500I-GR",
      "gtin": "00731304338444",
      "unite_base": "U",
      "unites_differentes": false,
      "nb_fournisseurs": 3,
      "prix_min": 89.75, "prix_max": 165.1, "ecart_pct": 84,
      "offres": [
        {"id": "uuid", "fournisseur": "Rexel", "designation": "...", "prix_net_ht": 89.75, "prix_unite_base_ht": 89.75,
         "unite_base": "U", "qte_par_conditionnement": 1.0, "ecart_pct": 0, "par_reference": true,
         "designation_differente": false, "autres_offres": 0, "anomalies": [], "url_produit": "https://..."},
        {"id": "uuid", "fournisseur": "Prolians", "designation": "Onduleur EASY UPS - Puissance de sortie : 500 VA - ...",
         "prix_net_ht": 106.11, "prix_unite_base_ht": 106.11, "unite_base": "U", "ecart_pct": 18,
         "par_reference": true, "designation_differente": true, "anomalies": ["UNITE_SUPPOSEE"]}
      ]
    }
  ],
  "qualifiants_isoles": [
    {"libelle": "différentiel", "nombre": 65, "prix_median": 158.90},
    {"libelle": "reconditionné", "nombre": 1, "prix_median": 8.79},
    {"libelle": "appareil combiné", "nombre": 1, "prix_median": 64.25}
  ],
  "criteres_a_affiner": [
    {"critere": "pôles", "valeurs": [
      {"valeur": "1P+N", "nombre": 111},
      {"valeur": "3P+N / 4P", "nombre": 46}
    ]}
  ]
}
```

### Notes d'affichage

`comparables` est le nombre de lignes réellement comparables sur la spécification demandée ; `total` inclut les qualifiants isolés. **Toujours afficher les deux** : masquer l'écart romprait la garantie d'inclusion.

`qualifiants_isoles` doit être visible et cliquable — un clic renvoie la même requête avec `inclure_qualifiants=true`. Ces produits ne sont jamais supprimés, seulement mis à part.

`criteres_a_affiner` n'apparaît que si les résultats sont hétérogènes. Chaque valeur est cliquable et ajoute le terme à la requête.

**Format unique (02/10/2026, PR #159 et #160).** Les champs suivants viennent de `blueseatra.offres_normalisees`, lue en lecture seule avec un filtre tenant explicite. Si la table est indisponible, ils sont absents ou vides et le comparateur retombe sur les prix bruts : aucune erreur.

- `prix_unite_base_ht` : prix par unité de base (`unite_base` : `U`, `M`, `M2`, `M3`, `KG`, `L`, `PAIRE`). C'est lui qui sert au tri, à `prix` et à `moins_cher_par_fournisseur`. `prix_net_ht` reste le prix publié pour `qte_par_conditionnement` unités (155,14 € pour 100 m).
- `cle_produit` : `GTIN:<14 chiffres>` ou `MR:<marque>:<réf. fabricant>` ; identique chez tous les fournisseurs du même article. `niveau_identification` : `GTIN`, `MARQUE_REF` ou `AUCUN`.
- `anomalies` : seules les anomalies utiles à l'achat sont renvoyées (`UNITE_SUPPOSEE`, `UNITE_INCONNUE`, `PRIX_NET_SUP_PUBLIC`, `PRIX_EXTREME`, `ECART_PRIX_PRODUIT`).
- `produits_identiques` : produits d'au moins 2 fournisseurs parmi les clés des lignes affichées, 20 au plus, dans l'ordre des résultats. Toutes les offres **visibles** de la clé sont lues, y compris celles dont la désignation ne contient pas les termes (`designation_differente: true`). Une offre par fournisseur (la moins chère ; les autres comptées dans `autres_offres`). `par_reference: true` : rattachée par marque + référence, sans GTIN chez ce fournisseur.
- `unites_differentes` (dans `prix` et dans chaque produit) : offres d'unités de base différentes ; `ecart_pct` vaut alors `null`.

`termes_reconnus` sert à montrer au chiffreur que « ph+n » a bien été compris comme « 1P+N », « U+N », etc. Sans ce retour, une requête sans résultat est indébuggable côté utilisateur.

---

## `GET /fournisseurs/detail/{id}`

Fiche d'une offre, avec les autres offres du même fournisseur sur la même famille.

```json
{
  "offre": { "...comme dans resultats..." },
  "historique_prix": [
    {"date": "2026-09-12", "prix_net_ht": 6.83}
  ],
  "meme_famille_chez_autres_fournisseurs": [
    {"fournisseur": "Prolians", "designation": "...", "prix_net_ht": 18.02, "id": "uuid"}
  ]
}
```

---

## `GET /fournisseurs/familles`

Familles de produits de tous les catalogues visibles par l'entreprise (les siens + le catalogue commun s'il n'est pas masqué), pour alimenter le filtre du comparateur. Les libellés sont propres à chaque fournisseur : ils sont regroupés tels quels, triés par ordre alphabétique (sans tenir compte des accents ni de la casse). Pas de comptage par famille : il exigerait de lire chaque fiche (voir migration `20261001210000`).

```json
{
  "familles": [
    {"famille": "Appareillage et contrôle du bâtiment", "fournisseurs": ["Rexel"]},
    {"famille": "Eclairage", "fournisseurs": ["Rexel", "YESSS"]}
  ]
}
```

---

## `GET /fournisseurs/liste`

Fournisseurs du tenant, avec volumétrie.

```json
{
  "fournisseurs": [
    {"nom": "Rexel", "references": 747771, "derniere_maj": "2026-09-11",
     "taux_ean": 77.8, "prix_renseignes_pct": 97.5}
  ],
  "total_references": 914628
}
```

---

## Erreurs

| Code | Cas |
|---|---|
| `400` | `q` absent ou vide |
| `401` | jeton absent ou expiré |
| `403` | rôle insuffisant |
| `422` | `limite` hors bornes |

Format : `{"detail": "message lisible"}`, conforme au reste de l'API.
