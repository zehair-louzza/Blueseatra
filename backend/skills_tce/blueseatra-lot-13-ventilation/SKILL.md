---
name: blueseatra-lot-13-ventilation
description: "Ventilation, VMC, entrées d'air et rejets."
metadata:
  version: "4.0.0"
---

# Lot 13 : Ventilation et qualité d'air

## Déclenchement
- Activer pour VMC, VMI, extraction, insufflation, gaines, bouches, entrées d'air ou entretien de ventilation demandé.
- Non-exemple adjacent : une bouche raccordée à un réseau collectif n'autorise ni VMC individuelle neuve ni rejet en façade.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une pose ou un raccordement seul n'autorise pas la fourniture d'un groupe majeur.

## Procédure
1. Reprendre l'extraction avec preuve, système individuel/collectif connu, locaux et intervention demandée.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Examiner le parcours de l'air entrant à l'air rejeté ; ne pas ajouter de bouches, moteur ou percements sans configuration.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Système existant | Nature, fonctionnement connu, colonnes, moteur, commandes, plans, propriété des réseaux et maintenance. |
| Contraintes collectives | Gestionnaire/syndic, autorisation, compatibilité bouche/réseau, perturbation des autres logements et vérification professionnelle. |
| Air entrant | Entrées d'air, prises extérieures, grilles, déflecteurs, moustiquaire/filtre si système prévu et passage réel de l'air. |
| Transfert intérieur | Cheminement entre pièces, passages ou grilles de transfert ; modification de porte à confirmer, pas à déduire. |
| Extraction/insufflation | Bouches, cadres, manchettes, joints, réglage, accessibilité, destination des pièces et nombre documenté. |
| Groupe | Appareil explicitement demandé, support, suspentes, plots antivibratiles, vis, chevilles et accès d'entretien. |
| Gaines | Type, parcours, isolation si prescrite, coudes, tés, répartiteurs, réductions, manchons et raccords. |
| Fixation et étanchéité | Colliers, feuillards, supports, tiges, écrous, rondelles, joints, rubans, mastic et maintien selon notice. |
| Rejet extérieur | Point de sortie autorisé, terminal, grille, chapeau, traversée, raccord d'étanchéité et protection contre entrées indésirables. |
| Double flux/traitement | Échangeur, filtres, bypass, réseaux distincts et condensats selon système ; aucun élément majeur automatique. |
| Sécurité et acoustique | Traversées, calfeutrements, dispositifs éventuels, atténuateurs et interactions combustion à faire vérifier selon projet. |
| Électricité et commande | Alimentation, protections à valider, boîtes, câbles, interrupteur, capteur ou régulation explicitement attribués. |
| Entretien et essais | Trappes, nettoyage, filtres, mesures, équilibrage, réglages, relevés et notices ; valeurs cibles issues de documents validés. |

## Informations manquantes
- Demander système, configuration des pièces, plans, propriété du réseau, entrées d'air, rejet, accès et autorisations.
- Débits, diamètres, longueurs, nombre de bouches et fixations inconnus : `null` ; aucune valeur réglementaire inventée.
- Rejet ou entrée d'air absent du dossier : question bloquante pour définir la solution, pas une sortie présumée disponible.

## Interfaces
- Lot 05 pour entrées d'air ; lot 04 pour rejets ; lots 06/08 pour gaines, trappes et transfert ; lot 14 pour alimentation.
- Lots 07 et 12 pour enveloppe, condensation et combustion ; intervention collective à coordonner avec gestionnaire.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais métier reliés sans duplication.

## Vérification et sortie
- Faire vérifier entrée, transfert, extraction, rejet et compatibilité collective ; aucune garantie de conformité ou de qualité d'air.
- Vérifier kit, autorisations, accès entretien, quantités `null` et absence de groupe ou bouche ajouté sans périmètre.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un libellé externe bref sur données validées.
- Rendre visibles rejet, entrées d'air, percements ou équilibrage exclus ; transmettre à `blueseatra-tce-audit`.
