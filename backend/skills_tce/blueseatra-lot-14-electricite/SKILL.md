---
name: blueseatra-lot-14-electricite
description: "Tableaux, circuits, prises et éclairage courants forts."
metadata:
  version: "4.0.0"
---

# Lot 14 : Électricité courants forts

## Déclenchement
- Activer pour tableau, circuit, prise, éclairage, alimentation, raccordement ou contrôle électrique demandé.
- Non-exemple adjacent : alimenter un chauffe-eau ne commande pas le chauffe-eau ; un réseau de données relève du lot 15.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter les kits d'appareillage/tableau ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler supports, plaques ou accessoires.
- Une pose ou un raccordement seul n'autorise pas la fourniture d'un équipement majeur ou d'un appareil utilisateur.

## Procédure
1. Reprendre l'extraction avec preuve, points, circuits connus, appareils fournis client et limites de l'intervention.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Distinguer modification locale, création de circuit et réfection générale ; calibres, sections et schémas exigent validation technique.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| État et périmètre | Tableau, circuits, alimentation, terre, diagnostics, zones concernées et éléments conservés. |
| Mise en sécurité | Repérage, consignation, coupure autorisée et intervention compétente ; aucun mode opératoire sous tension. |
| Coffret/tableau | Enveloppe, rails, borniers, obturateurs, porte, repérage, fixations et espace disponible vérifié. |
| Protections/commande | Dispositifs prescrits, raccordements, peignes, embouts, contacteurs ou relais ; caractéristiques issues du projet validé. |
| Conducteurs | Câbles/fils, fonctions, parcours, connexions, embouts, cosses et repères ; pas de multiplication universelle par trois. |
| Cheminements | Gaines, tubes, goulottes, chemins, coudes, jonctions, embouts, couvercles, colliers et traversées. |
| Fixations | Clips, pattes, consoles, vis, chevilles, rondelles, écrous et supports ; notice et nature du support indispensables. |
| Boîtes et connexions | Boîtes d'encastrement/dérivation, couvercles, presse-étoupes, entrées, bornes et accès conservé. |
| Prises/interrupteurs | Mécanisme, support, plaque, enjoliveur, boîte, connexion et repérage ; composition réelle de chaque ensemble. |
| Éclairage | Point, douille/connecteur, sortie, luminaire explicitement fourni, source lumineuse si prévue, driver et fixation selon notice. |
| Appareils dédiés | Sortie de câble, alimentation, raccord, commande et protection à valider ; équipement alimenté non ajouté. |
| Terre et liaisons | Existant, conducteurs, barrette, bornes, colliers et continuité ; solution à faire vérifier sans valeur inventée. |
| Essais et documents | Contrôles appropriés, relevés, étiquettes, schémas et attestation seulement si mission/processus confirmés. |

## Informations manquantes
- Demander plans, points, parcours, état tableau/terre, caractéristiques des appareils, diagnostic et support.
- Longueurs par rôle, sections, calibres, tensions non fournies, modules et fixations inconnus : `null`.
- Une puissance, une section ou un calibre est une caractéristique, pas une quantité ; ne rien dimensionner par défaut.

## Interfaces
- Lots 03/06/09/10 pour percements, boîtes et reprises ; lots 11 à 13 pour appareils ; lot 18 pour parcours extérieur.
- Lots 15 à 17 pour données, sécurité et équipement spécial : attribuer alimentation, commande et essais une seule fois.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais métier reliés sans duplication.

## Vérification et sortie
- Faire vérifier circuits, protections, locaux particuliers, terre et essais par un professionnel ; aucune déclaration de conformité.
- Vérifier kit, preuve des caractéristiques, quantités `null` et absence de rénovation générale ou appareil neuf ajouté.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un poste externe bref sur données validées.
- Rendre visibles luminaires, appareils, reprises et attestations exclus ; transmettre à `blueseatra-tce-audit`.
