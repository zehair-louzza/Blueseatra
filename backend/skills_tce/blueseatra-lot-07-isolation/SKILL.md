---
name: blueseatra-lot-07-isolation
description: "Isolation thermique, acoustique et étanchéité à l'air."
metadata:
  version: "4.0.0"
---

# Lot 07 : Isolation et acoustique

## Déclenchement
- Activer pour isolation thermique, traitement acoustique ou étanchéité à l'air explicitement demandé.
- Non-exemple adjacent : une cloison n'autorise pas automatiquement un isolant neuf ; l'ITE intégrée au lot 04 ne se duplique pas ici.

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
1. Reprendre l'extraction avec preuve, zones, composition existante, objectif demandé et études disponibles.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Distinguer matériau, système complet, membrane, support et finition ; ne pas choisir seul épaisseur ou performance.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| État initial | Support, humidité, moisissures, ventilation, isolant conservé, réseaux et obstacles à documenter. |
| Matériau | Référence, format, épaisseur prescrite, caractéristiques documentées, destination et compatibilité du système. |
| Murs et rampants | Panneaux ou rouleaux, découpe, jonctions, ossature, maintien, rives et accès aux réseaux. |
| Combles | Accès, trappe, cheminement, repères, déflecteurs, protections des équipements ; soufflage seulement si demandé/validé. |
| Sols et planchers | Support, isolant, bandes périphériques, sous-couche, désolidarisation, relevés et niveaux finis. |
| Plafonds | Panneaux, suspentes adaptées, ossature, clips, rondelles et joints ; charges et support à vérifier. |
| Membranes | Pare-vapeur ou frein-vapeur seulement selon étude/système ; recouvrements prescrits, raccords et continuité. |
| Étanchéité à l'air | Rubans, mastics, primaires, manchons, œillets, collerettes et raccords aux baies/traversées. |
| Fixations | Rosaces, chevilles, vis, agrafes, feuillards, fils ou clips selon notice, support et méthode retenue. |
| Acoustique | Source de bruit, transmission, panneaux absorbants, suspentes, bandes résilientes et joints ; objectif à qualifier. |
| Points singuliers | Angles, pieds de mur, jonctions plancher, trappes, conduits, équipements chauds et ponts à examiner. |
| Protection et contrôle | Parement éventuel, maintien provisoire, inspection avant fermeture, photos, fiches produits et mesures demandées. |

## Informations manquantes
- Demander surfaces, composition, humidité, référence, objectif, épaisseur issue d'étude, accès et finition attendue.
- Quantités posées, achats, densité de mise en œuvre, fixations et consommables inconnus : `null`.
- Demander étude ou notice pour membranes et points sensibles ; aucune performance ni économie d'énergie déduite du seul matériau.

## Interfaces
- Lot 04 pour enveloppe/ITE ; lot 06 pour ossature et parements ; lot 09 pour sols : affecter l'isolant une seule fois.
- Lots 11 à 14 pour traversées, ventilation, réseaux et équipements ; ne pas obstruer un cheminement sans validation.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier humidité, continuité, compatibilités et performances du système ; aucune garantie thermique, acoustique ou réglementaire.
- Vérifier kit, quantités `null`, absence de choix arbitraire et contrôles avant fermeture.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` rédige un poste externe bref sur données validées.
- Rendre visibles parements exclus, zones inaccessibles et performances non établies ; transmettre à `blueseatra-tce-audit`.
