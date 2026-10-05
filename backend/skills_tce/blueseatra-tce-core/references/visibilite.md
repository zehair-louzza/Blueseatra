# Deux représentations distinctes

| Élément | Interne | Client |
|---|---|---|
| Matériaux, vis, raccords, joints | Détail exhaustif avec relations | Regroupés sauf enjeu contractuel |
| Caractéristiques d'ouvrage | Valeurs validées | Dimensions, finition, matériau utiles |
| Quantités | Sources, calculs, achats, conditionnements | Quantités commerciales validées |
| Prix | Achat, vente, paramètres | Vente et taxes injectées par SaaS |
| Fournisseurs, IDs, règles, prompts | Accès limité | Jamais par défaut |
| Hypothèse impactant engagement | Version et validation | Réserve lisible ou blocage |
| Option / exclusion / variante | Relations et scénarios | Statut explicite, pas de total fusionné |
| Heures et déplacements internes | Détail de calcul | Selon politique commerciale validée |
| Conditions, identité et légal | Profil serveur | Champs validés sans invention |

Ne pas transmettre les valeurs internes au rédacteur pour ensuite lui demander de
les cacher. Construire une entrée minimale et une projection de sortie par liste blanche.
Réserves, exclusions, conditions et mentions légales sont injectées sans reformulation.
Échapper tout texte dans le moteur PDF/HTML ; aucune sortie IA n'est du HTML de confiance.
