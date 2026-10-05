---
name: blueseatra-lot-05-menuiseries-exterieures
description: "Fenêtres, portes extérieures, volets et vitrages."
metadata:
  version: "4.0.0"
---

# Lot 05 : Menuiseries extérieures

## Déclenchement
- Activer pour fenêtre, porte extérieure, volet, store, vitrage ou réglage de menuiserie extérieure demandé.
- Non-exemple adjacent : une porte intérieure relève du lot 08 ; une motorisation seule ne commande pas un volet neuf.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une pose, réparation ou un raccordement seul n'autorise pas la fourniture d'un équipement majeur.

## Procédure
1. Reprendre l'extraction avec preuve, baie, existant conservé, fourniture client éventuelle et type d'intervention.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer menuiserie, vitrage, accessoires, dépose, pose et raccordements ; ne pas déduire les cotes d'une photo ambiguë.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Baie et pose | Cotes relevées, aplomb, diagonales, tableau, feuillure, dormant conservé ou déposé, appui et seuil. |
| Ensemble menuisé | Dormant, ouvrants, matériau, finition, sens d'ouverture, traverses, meneaux et caractéristiques contractuelles. |
| Vitrage | Composition documentée, dimensions, parcloses, joints, cales, maintien ; performance et sécurité à faire vérifier. |
| Ferrures | Paumelles, charnières, compas, crémones, gâches, poignées, cylindre, butées et caches selon ensemble retenu. |
| Fixation | Pattes, équerres, vis, chevilles, boulons, rondelles, cales d'assise et d'écartement ; support et notice requis. |
| Calfeutrement | Bandes, membranes, joints précomprimés, fond de joint, mastic, primaire et raccords selon système validé. |
| Appuis et seuils | Bavette, rejingot existant, rejets d'eau, embouts, raccord latéral, continuité et évacuation à examiner. |
| Habillages | Tapées, couvre-joints, profilés, retours, découpes et reprises de tableaux ; finitions à attribuer. |
| Volets et stores | Tablier, coffre, axe, coulisses, attaches, butées, manivelle ou moteur, supports et commande selon demande. |
| Motorisation | Alimentation, passage de câble, boîte, commande, paramétrage et accès maintenance ; aucun circuit ou moteur présumé fourni. |
| Ventilation | Entrées d'air présentes ou demandées, accessoires, compatibilité avec menuiserie et système du bâtiment. |
| Réglage et contrôle | Ouverture, fermeture, verrouillage, drainage, joints, nettoyage local, protections retirées et notices. |

## Informations manquantes
- Demander relevé de baie, type de pose, dimensions, sens, support, référence, finition, performances demandées et contenu du kit.
- Quantités de fixations, longueurs de joints, habillages et fournitures absentes : `null` ; dimensions distinctes des quantités.
- Demander le traitement des dormants, volets, tableaux, seuils et raccordements non explicités.

## Interfaces
- Lots 02 et 03 pour dépose et baie ; lot 04 pour enveloppe ; lots 06, 09 et 10 pour raccords intérieurs.
- Lot 13 pour entrées d'air ; lot 14 pour alimentation ; lot 16 pour fonction de sécurité éventuelle, sans doublon de serrure.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier pose, performances, sécurité et interfaces par un professionnel ; aucune garantie de conformité ou d'étanchéité.
- Vérifier cotes sourcées, kit, quincaillerie, quantités `null` et absence de remplacement complet implicite.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un libellé externe bref sur données validées.
- Rendre visibles dépose, reprises et alimentation exclues ; transmettre les alertes à `blueseatra-tce-audit`.
