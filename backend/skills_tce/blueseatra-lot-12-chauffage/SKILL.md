---
name: blueseatra-lot-12-chauffage
description: "Chauffage, climatisation, PAC et régulation."
metadata:
  version: "4.0.0"
---

# Lot 12 : Chauffage, climatisation et régulation

## Déclenchement
- Activer pour générateur, radiateur, PAC, climatiseur, réseau de chauffage ou régulation demandé.
- Non-exemple adjacent : raccorder électriquement une PAC relève du lot 14 et n'autorise pas l'achat de la PAC.

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
1. Reprendre l'extraction avec preuve, système, appareil, fourniture client et données d'étude disponibles.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer appareil, réseau, régulation, alimentation et mise en service ; ne pas dimensionner puissance ou débit avec le modèle.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Étude et existant | Besoin documenté, système conservé, émetteurs, puissance validée, implantation, accès et contraintes acoustiques. |
| Générateur | Modèle explicitement demandé, accessoires requis par notice, interfaces ECS/chauffage et espace d'entretien. |
| Supports | Console, socle, plots antivibratiles, rails, vis, chevilles, tiges, écrous, rondelles et charges sur support. |
| Réseau hydraulique | Tubes, raccords, coudes, tés, nourrices, fourreaux, colliers, isolation, joints et traversées. |
| Organes de réseau | Vannes, filtres, purgeurs, vidanges, circulateurs, expansion et sécurité selon étude ; vérifier ce qui est intégré au générateur. |
| Radiateurs | Appareil demandé, consoles, robinets, tête/commande, té de réglage, bouchons, purgeur et raccords. |
| Plancher chauffant | Système validé, isolant, tubes, rails/agrafes, collecteur, raccords, régulation, essais avant recouvrement et chape attribuée. |
| Climatisation/PAC | Unités demandées, liaisons prévues par fabricant, isolation, goulotte, raccords, supports et traversées étanchées. |
| Condensats | Bac si requis, tube, siphon selon système, pompe si justifiée, raccords, colliers et point de rejet autorisé à vérifier. |
| Combustion et gaz | Réseau, amenée d'air, fumées, conduit, terminal, joints et contrôles à confier aux intervenants adaptés ; aucune solution présumée. |
| Régulation et alimentation | Thermostat, sondes, actionneurs, câbles, commande, raccord électrique, protection à faire vérifier et configuration explicite. |
| Mise en service | Rinçage, essais, réglages, équilibrage, interventions sur fluides, documents et entretien : périmètre et professionnel à confirmer. |

## Informations manquantes
- Demander étude, modèles, puissance documentée, plan des réseaux, support, énergie, rejets, contenu des kits et responsabilité de mise en service.
- Longueurs, charges en fluide, accessoires, fixations et réglages non documentés : `null` ; pas de dimensionnement depuis la surface seule.
- Gaz, combustion et fluides frigorigènes : demander habilitations/qualifications et validations pertinentes sans affirmer leur acquisition.

## Interfaces
- Lot 11 pour ECS/eau ; lot 14 pour alimentation ; lot 13 pour air ; lot 04 pour traversées et rejet.
- Lots 03/06 pour supports ; lots 07/09 pour sol chauffant ; lot 17 si équipement spécial : attribution unique.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais métier reliés sans duplication.

## Vérification et sortie
- Faire vérifier compatibilité, puissance issue d'étude, sécurité, rejets et mise en service ; aucune garantie de conformité ou de performance.
- Vérifier kit, équipement fourni client, quantités `null` et absence de générateur ajouté à un raccordement.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un libellé externe bref sur données validées.
- Rendre visibles alimentation, conduits, réglages et entretien exclus ; transmettre à `blueseatra-tce-audit`.
