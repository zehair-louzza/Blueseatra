# Quantités des tableaux, lots et actions TCE

Cette correction suit le test réel Parmentier : le modèle avait lu 21 prestations
mais cité des nombres isolés, utilisé les codes 00/01 pour les lots techniques et
transformé une pose de douche en fourniture et pose. Les quantités avaient été
rejetées à juste titre par le garde-fou, malgré leur présence dans les cellules.

## Décisions

- **Quantité source** : le backend lit les colonnes désignation, unité et quantité
  des tableaux à en-têtes reconnus. Une liaison exige une désignation identique
  après normalisation et unique ; les colonnes de prix ne participent jamais
  au calcul ni au choix de la quantité.
- **Ambiguïtés** : doublons, identifiants contradictoires, preuves d'un autre
  objet, quantités non finies et unités inconnues ne sont pas approuvés. La
  quantité reste inconnue et la revue demeure nécessaire.
- **Traçabilité** : la ligne source exacte, son identifiant et la liste des
  corrections sont conservés jusqu'au devis. Une correction automatique n'est
  jamais une approbation humaine.
- **Actions** : la désignation source prime. Une pose reste une pose, un
  raccordement reste un raccordement ; une fourniture doit être explicite.
- **Lots** : la taxonomie réelle est fournie au modèle ; la classification
  d'une ligne liée est confrontée au sens de sa désignation source.
- **Contexte** : la copie des tableaux ajoutée à un PDF est retirée de l'entrée
  modèle seulement si toutes ses cellules figurent déjà dans le texte natif.
  L'original n'est jamais modifié et reste l'autorité pour les preuves.
- **Troncature** : elle est signalée d'après le document réellement utilisé par
  l'étage de traitement, et non d'après le seul dépassement du budget compact.

## Vérification

Les tests `test_table_evidence.py` et `test_extraction_table_input.py` couvrent les
cellules, les erreurs adversariales, les actions, les lots, les preuves courtes
et la conservation du contenu source. Le rejeu local de la sortie réelle sert
à vérifier les garde-fous ; il ne remplace pas une nouvelle inférence sur le VPS.

La publication, la revue humaine, les calculs commerciaux, les catalogues et les
modèles OCR restent inchangés. Aucun devis existant n'est migré automatiquement.

Un correctif séparé ajoute le filtre SQL paramétré `$lt` requis pour afficher la
position d'une demande en attente ; les contrôles de tenant restent présents.
