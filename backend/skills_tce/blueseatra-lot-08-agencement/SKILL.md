---
name: blueseatra-lot-08-agencement
description: "Portes intérieures, mobilier, cuisines et agencement."
metadata:
  version: "4.0.0"
---

# Lot 08 : Menuiseries intérieures et agencement

## Déclenchement
- Activer pour porte intérieure, placard, meuble, cuisine, plan de travail, habillage ou quincaillerie demandé.
- Non-exemple adjacent : raccorder un évier relève du lot 11 et n'autorise pas l'achat de l'évier ou d'une cuisine.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une pose ou un raccordement seul n'autorise pas la fourniture d'un équipement majeur ou d'un mobilier neuf.

## Procédure
1. Reprendre l'extraction avec preuve, meuble ou porte, implantation, fourniture client et interventions demandées.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer achat, montage, pose, découpes, raccordement et finitions ; photographies non cotées insuffisantes pour commander.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Implantation | Cotes, aplomb, niveaux finis, dégagements, ouverture, réseaux, charges et support d'accrochage. |
| Portes battantes | Huisserie, ouvrant, paumelles, fiches, serrure, gâche, poignée, rosaces, butée, joints et couvre-joints. |
| Portes coulissantes | Rail, chariots, guides, butées, amortisseurs, habillage, poignées et accès de réglage. |
| Caissons et placards | Panneaux, fonds, tablettes, chants, tourillons, excentriques, taquets, vis d'assemblage et caches. |
| Façades et tiroirs | Portes, charnières, embases, poignées, coulisses, tiroirs, amortisseurs et réglages. |
| Supports et fixation | Pieds, vérins, socles, rails, suspentes, équerres, vis, chevilles, rondelles et dispositifs de maintien selon notice. |
| Plans de travail | Matériau, découpes, jonctions, chants, profilés, connecteurs, colle, mastic et protection des coupes. |
| Finitions d'ensemble | Fileurs, joues, plinthes, corniches, crédences, clips, joints périphériques et retouches demandées. |
| Évier et électroménager | Réservations, ventilation, support, accès, dimensions des appareils ; fourniture et raccordements explicitement attribués. |
| Rangements équipés | Tringles, supports, paniers, mécanismes, séparateurs et accessoires choisis ; aucun équipement intérieur automatique. |
| Habillage technique | Trappes, démontabilité, maintien des accès aux vannes, siphons, prises, compteurs et réseaux. |
| Réglage et livraison | Alignement, jeu de fonctionnement, fermeture, stabilité, nettoyage local et notices du mobilier. |

## Informations manquantes
- Demander plans cotés, référence, inventaire des colis, provenance du mobilier, support, finitions et équipements intégrés.
- Quantités de panneaux, ferrures, pieds, vis et chevilles inconnues : `null` ; ne pas appliquer de kit générique par meuble.
- Demander qui réalise découpes, raccordements, reprise des murs et modification des réseaux.

## Interfaces
- Lots 06 et 07 pour renforts ; lot 09 pour niveaux ; lot 10 pour finitions ; lot 16 pour fonction de sécurité d'une porte.
- Lot 11 pour évier/robinetterie ; lots 12 à 15 pour réseaux et commandes ; aucune fourniture d'appareil sans demande.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier stabilité, fixation, compatibilité et accès d'entretien ; aucune garantie de conformité ou de performance.
- Vérifier inventaire réel, kits, fourniture client, quantités `null` et absence de meuble neuf ajouté à une simple pose.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` regroupe les accessoires validés dans le poste parent.
- Rendre visibles mobilier, électroménager et raccordements exclus ; transmettre les alertes à `blueseatra-tce-audit`.
