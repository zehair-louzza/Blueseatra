# Contrat d'API — recherche et comparaison fournisseurs

Base : `https://blueseatra-api.onrender.com/api`
Authentification : `Authorization: Bearer <jwt>` (identique au reste du SaaS).
Toutes les réponses sont cloisonnées par tenant.

---

## `GET /fournisseurs/recherche`

Recherche par inclusion sur le catalogue fournisseurs du tenant.

**Règle absolue :** tout produit contenant les termes demandés est renvoyé. La pertinence trie, elle ne filtre jamais.

### Paramètres

| Nom | Type | Défaut | Rôle |
|---|---|---|---|
| `q` | string | — | requête libre, obligatoire |
| `limite` | int | 50 | nombre de lignes de la liste principale (max 200) |
| `inclure_qualifiants` | bool | false | si `true`, les produits d'une autre nature réintègrent la liste principale |

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
    "min": 6.83, "max": 200.67, "median": 32.61, "ecart_pct": 2838
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
      "url_produit": null
    }
  ],
  "moins_cher_par_fournisseur": [
    {"fournisseur": "Rexel", "prix_net_ht": 6.83, "designation": "...", "id": "uuid"},
    {"fournisseur": "La Plateforme", "prix_net_ht": 13.98, "designation": "...", "id": "uuid"},
    {"fournisseur": "Prolians", "prix_net_ht": 18.02, "designation": "...", "id": "uuid"}
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
