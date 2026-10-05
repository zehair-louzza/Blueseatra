---
name: blueseatra-lot-03-structure
description: "Gros œuvre, maçonnerie, ouvertures et structure."
metadata:
  version: "4.0.0"
---

# Lot 03 : Gros œuvre et structure

## Déclenchement
- Activer pour fondation, maçonnerie, dalle, béton, reprise structurelle ou ouverture d'un ouvrage potentiellement porteur.
- Non-exemple adjacent : déplacer une cloison légère identifiée relève du lot 06 ; si sa fonction est inconnue, demander vérification.

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
1. Reprendre l'extraction avec preuve, ouvrage, dimensions fournies, support, charges connues et documents d'étude.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à la prestation concernée et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Signaler toute atteinte structurelle pour étude professionnelle ; ne choisir ni section, ni ferraillage, ni séquence de démolition.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Reconnaissance | Fonction porteuse, composition, état, fissures, appuis, charges, plans et limites de reconnaissance. |
| Sol et fondations | Données de sol, réseaux, fouilles, assise, eau, ouvrage existant ; solution et profondeur issues d'étude. |
| Maintien provisoire | Étaiement, répartition, calages, contreventement, accès et levage à définir par professionnel. |
| Maçonnerie | Éléments, mortier, liaisons, angles, arases, joints, réservations et raccords avec existant. |
| Coffrage | Panneaux, poutrelles, entretoises, tiges, écrous, rondelles, cônes, huile de démoulage et obturation des traversées. |
| Béton | Spécification validée, accès livraison, pompage éventuel, mise en œuvre, cure, joints et protection à documenter. |
| Armatures | Plans, barres, treillis, attentes, recouvrements prescrits, cales, chaises et fil de ligature ; aucun dimensionnement IA. |
| Ouverture | Étude, linteau ou poutre prescrit, appuis, sommiers, scellement, rebouchage et finition des tableaux. |
| Assemblages | Platines, connecteurs, boulons, vis, rondelles, écrous, chevilles ou scellements ; support et notice requis. |
| Reprises locales | Purge autorisée, préparation, passivation éventuelle, mortier de réparation, résine, injection ; cause à diagnostiquer. |
| Humidité structurelle | Coupure capillaire, joints, traversées, relevés ou protection enterrée à examiner selon système retenu. |
| Réservations et finition | Fourreaux, percements autorisés, calfeutrements, rives, seuils, arasement et support livré aux lots suivants. |

## Informations manquantes
- Demander plans, étude, support, charges, dimensions, état, accès et responsabilités de validation.
- Sections, armatures, volumes, quantités de mortier et ancrages non documentés : `null` ; aucune règle au mètre carré.
- Une photo ou le mot « mur » ne prouve ni portance, ni stabilité, ni possibilité d'ouverture.

## Interfaces
- Lot 00 pour études ; lot 02 pour dépose ; lot 18 pour terrassement ; lot 04 pour raccords d'enveloppe.
- Lots 05, 06, 09 et techniques pour niveaux, appuis, réservations et scellements : affecter chaque ouvrage une seule fois.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Demander validation structurelle, phasage et contrôles adaptés ; ne garantir ni conformité, ni stabilité, ni faisabilité.
- Vérifier preuves, conditions, ancrages documentés, quantités `null` et absence de solution structurelle inventée.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` rédige brièvement sur données validées.
- Rendre visibles études, reprises et renforcements exclus ou non définis ; transmettre à `blueseatra-tce-audit`.
