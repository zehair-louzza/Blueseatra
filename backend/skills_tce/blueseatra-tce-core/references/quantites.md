# Quantités, unités et kits

L'IA extrait une quantité textuelle sans la calculer. Une quantité certaine exige
une preuve unique dans une source normalisée immuable et une validation du sens.

| Entrée | Extraction | Hors IA |
|---|---|---|
| Un chauffe-eau 150 L | 1 U ; capacité 150 L | Validation produit, fixations et circuits |
| Prises blanches | quantité null | Relevé pièce par pièce |
| Peindre un mur de 4 m sur 2,5 m | dimensions, surface null | Calcul surface puis déductions |
| Gaine de 10 m | 10 m si longueur réellement demandée | Conducteurs par fonction et parcours |
| Douche 120 × 80 cm | dimensions, équipement selon texte | Réservation, étanchéité, support |
| Vis et chevilles | quantité null | Notice, support, points de fixation |

Jamais de multiplicateur universel de conducteurs, de perte universelle ou de
nombre forfaitaire de sacs de colle. Quantité posée, quantité d'achat, conditionnement,
pertes approuvées et ressources internes sont des champs serveur séparés.

Le backend calcule le complément d'achat uniquement après identification du kit,
compatibilité des pièces et besoin réel. Conserver les composants inclus en interne
mais ne pas leur attribuer une deuxième ligne d'achat ou de facturation.

Une quantité inconnue ne doit pas être remplacée par « 1 forfait ». Une estimation
requiert une hypothèse versionnée approuvée et, si nécessaire, une réserve client.
La V4 volontairement ne permet pas à la nomenclature IA de quantifier ses candidats.
