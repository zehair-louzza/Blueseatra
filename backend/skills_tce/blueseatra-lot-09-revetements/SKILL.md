---
name: blueseatra-lot-09-revetements
description: "Carrelage, parquet, sols souples et revêtements muraux."
metadata:
  version: "4.0.0"
---

# Lot 09 : Revêtements murs et sols

## Déclenchement
- Activer pour carrelage, faïence, parquet, sol souple, plinthe ou préparation de support associée.
- Non-exemple adjacent : peindre un mur relève du lot 10 ; un carrelage ne vaut pas automatiquement création d'une douche étanche.

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
1. Reprendre l'extraction avec preuve, zones, support, revêtement, mode de pose demandé et fourniture client.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer dépose, préparation, étanchéité, revêtement et finitions ; le mauvais état supposé ne justifie pas une chape certaine.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Support | Nature, humidité mesurée, cohésion, planéité, fissures, ancien revêtement et compatibilité du système. |
| Préparation | Nettoyage, ponçage, grattage, aspiration, réparations, primaire ; ragréage/chape seulement si besoin validé. |
| Chape ou forme | Matériau prescrit, bandes périphériques, joints, armature éventuelle, niveaux et pentes issus de données validées. |
| Étanchéité sous revêtement | Système retenu, primaire, membrane/enduit, bandes, angles, collerettes et raccord au siphon ; attribution unique. |
| Carrelage et faïence | Référence, format, calepinage, coupes, colle compatible, peigne/moyens distincts des fournitures, croisillons et cales. |
| Joints et profils | Produit de jointoiement, teinte, joints de mouvement, fond de joint, mastic, baguettes, nez de marche et angles. |
| Parquet | Lames, sous-couche, pare-vapeur si prescrit, colle ou clips, languettes, jeux selon notice et raccords de seuil. |
| Sols souples | Rouleaux/dalles/lames, colle ou fixation prescrite, joints soudés éventuels, cordon, relevés et angles. |
| Plinthes et rives | Plinthes, angles, embouts, colle, clips, vis, chevilles, joints et raccords avec huisseries. |
| Seuils et raccords | Barres, profilés, transition de niveaux, fixation, joints, découpe sous porte à attribuer. |
| Traversées et équipements | Coupes autour tubes, siphons, receveurs, WC et supports ; démontage/repose à confirmer avec le lot concerné. |
| Livraison | Nettoyage adapté, protection locale, retrait des cales prévu, produits d'entretien et contrôle d'aspect convenu. |

## Informations manquantes
- Demander surfaces relevées, support contrôlé, format, calepinage, niveaux, pentes validées et référence du système.
- Quantités d'achat, chutes, sacs, colle, joints, profilés et fixations inconnues : `null` ; calculs et pertes au backend.
- Distinguer surface explicitement posée et quantité à commander ; ne pas appliquer un pourcentage de pertes universel.

## Interfaces
- Lots 03, 06 et 07 pour supports ; lot 08 pour huisseries ; lot 11 pour douche/siphon ; lot 12 pour sol chauffant.
- Attribuer étanchéité, forme de pente, découpe de porte et démontage sanitaire une seule fois ; limites à confirmer.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier support, humidité, compatibilité et usage ; aucune garantie de conformité, d'étanchéité ou de planéité présumée.
- Vérifier kits, quantités `null`, références, limites de préparation et absence de métrés ou consommations inventés.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un poste externe bref sur données validées.
- Rendre visibles dépose, préparation lourde et étanchéité exclues ; transmettre à `blueseatra-tce-audit`.
