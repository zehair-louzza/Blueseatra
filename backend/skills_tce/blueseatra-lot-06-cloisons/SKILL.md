---
name: blueseatra-lot-06-cloisons
description: "Cloisons, doublages, plafonds et habillages."
metadata:
  version: "4.0.0"
---

# Lot 06 : Cloisons, doublages et plafonds

## Déclenchement
- Activer pour cloison, doublage, faux plafond, gaine, trappe ou habillage intérieur demandé.
- Non-exemple adjacent : un mur porteur relève du lot 03 ; son caractère non porteur ne se déduit pas d'une photo.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une pose ou un raccordement seul n'autorise pas la fourniture d'un équipement majeur.

## Procédure
1. Reprendre l'extraction avec preuve, tracé, hauteur connue, support, locaux et fonctions demandées.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer ossature, parements, isolation, joints, portes et peinture ; ne pas ajouter une finition non demandée.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Implantation | Tracé, niveaux, hauteur, épaisseur, ouvertures, supports haut/bas et contraintes de déformation. |
| Ossature verticale | Rails, montants, lisses, éclisses, bandes résilientes et raccords du système retenu. |
| Ossature plafond | Fourrures, porteurs, entretoises, cornières, suspentes, tiges, cavaliers et accès au support. |
| Fixations | Vis adaptées aux plaques/ossature, chevilles de support, rondelles, boulons et ancrages ; données fabricant/support requises. |
| Parements | Type de plaque, bords, nombre de parements prescrit, découpes, retours, angles et raccords. |
| Doublage collé | Support, plots ou mortier-colle selon système validé, calage et traitement des rives ; pas de mode de pose présumé. |
| Isolation intégrée | Isolant, maintien, membrane éventuelle, bandes, joints et continuité ; attribution unique avec lot 07. |
| Renforts | Charges suspendues déclarées, traverses, panneaux, platines, réservations, fixations et accès ultérieur. |
| Baies et trappes | Huisserie, renforts, linteau d'ossature, cadre, ouvrant de trappe, ferrures, joints et dimensions. |
| Réseaux incorporés | Boîtes, fourreaux, passages, grilles, appareillages, traversées, calfeutrements et contrôles avant fermeture. |
| Joints et rives | Bandes papier/armées, enduits, cornières, joints périphériques, mastic et traitement des raccords. |
| Livraison du support | Ponçage prévu, dépoussiérage, état de finition attendu, planéité à contrôler et peinture attribuée séparément. |

## Informations manquantes
- Demander plan coté, hauteur, type de support, système, usage des locaux, charges, réseaux et état de finition attendu.
- Surfaces, longueurs, entraxes prescrits, nombre de plaques, vis ou suspentes inconnus : `null` ; aucun métré IA.
- Sans reconnaissance du support, demander la vérification du maintien et de la compatibilité des ancrages.

## Interfaces
- Lots 03 et 05 pour supports/baies ; lot 07 pour isolation ; lot 08 pour portes ; lot 10 pour peinture.
- Lots 11 à 16 : coordonner incorporations, renforts, trappes et essais avant fermeture, sans reproduire leurs fournitures.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier système, stabilité, charges et performances demandées ; ne garantir ni conformité acoustique, ni résistance au feu.
- Vérifier références, kit, quantités `null`, maintien des accès et absence de peinture ou porte ajoutée implicitement.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` regroupe seulement les éléments validés.
- Rendre visibles isolation, renforts et finitions exclus ou non définis ; transmettre à `blueseatra-tce-audit`.
