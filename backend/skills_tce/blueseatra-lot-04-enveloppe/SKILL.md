---
name: blueseatra-lot-04-enveloppe
description: "Toiture, façade, zinguerie et étanchéité extérieure."
metadata:
  version: "4.0.0"
---

# Lot 04 : Enveloppe extérieure

## Déclenchement
- Activer pour couverture, toiture, façade, ravalement, zinguerie, ITE ou étanchéité extérieure demandé.
- Non-exemple adjacent : le calfeutrement d'une fenêtre posée relève du lot 05 ; sa jonction de façade est une interface à attribuer.

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
1. Reprendre l'extraction avec preuve, zone, pathologie décrite, système existant, travaux demandés et limites de réparation.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Distinguer réparation locale, remplacement et traitement global ; une fuite signalée n'autorise pas une réfection complète.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Support et accès | Charpente, support maçonné, état, pente relevée, accès, levage, protections et exposition météo à vérifier. |
| Couverture | Éléments courants, rives, faîtages, arêtiers, noues, closoirs, sorties, ventilation de couverture selon système. |
| Support de couverture | Liteaux, contre-liteaux, volige, écran, bandes adhésives, agrafes, pointes, vis et clips selon notice. |
| Étanchéité courante | Support, primaire, membrane ou système liquide retenu, renforts, joints, relevés et protection ; pas de solution présumée. |
| Points singuliers | Angles, acrotères, couvertines, costières, solins, bandes de raccord, traversées, mastics et fonds de joint. |
| Eaux pluviales | Naissances, crapaudines, chéneaux, gouttières, crochets, descentes, coudes, manchons, colliers et évacuation finale. |
| Façade | Nettoyage autorisé, réparation, enduit, trame, baguettes, profilés, joints, tableaux et soubassement. |
| ITE | Système documenté, isolant, collage, chevilles, rosaces, rails, renforts d'angle, sous-enduit, finition et raccords. |
| Fixations | Pattes, équerres, vis, chevilles, rondelles, écrous, joints d'étanchéité ; ancrage et compatibilité des matériaux à valider. |
| Isolation et vapeur | Complexe existant, continuité, raccords de membrane, traversées et comportement hygrothermique à faire étudier. |
| Équipements traversants | Fenêtre de toit, rejet, conduit, antenne ou panneaux : embase, raccord et responsable ; équipement non ajouté. |
| Contrôles et livraison | Essais convenus, accès entretien, nettoyage local, photos avant fermeture et documents du système. |

## Informations manquantes
- Demander plans, surfaces, pentes relevées, état du support, système, accès, diagnostics et limites de la zone traitée.
- Longueurs de rives, relevés, descentes, fixations et consommables inconnues : `null` ; aucune extrapolation depuis une photo.
- Demander les conditions d'intervention et autorisations ; ne pas promettre une étanchéité globale après réparation partielle.

## Interfaces
- Lot 03 pour support ; lot 05 pour baies ; lot 07 pour isolation : attribuer l'ITE intégrée une seule fois.
- Lots 11, 13, 17 et 18 pour évacuations, rejets, panneaux et raccords ; chaque traversée a un porteur identifié.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier système, support, fixations, hygrothermie et accès par un professionnel ; aucune garantie de conformité ou d'étanchéité.
- Vérifier compatibilités, contenu des kits, preuves, interfaces et quantités `null`.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` ne publie que des regroupements validés.
- Rendre visibles surfaces exclues, support non reconnu et entretien hors mission ; transmettre à `blueseatra-tce-audit`.
