---
name: blueseatra-lot-00-etudes
description: "Études, relevés, diagnostics et démarches TCE."
metadata:
  version: "4.0.0"
---

# Lot 00 : Études, diagnostics et administratif

## Déclenchement
- Activer pour relevé, plan, diagnostic, étude, coordination ou démarche explicitement demandé.
- Non-exemple adjacent : ouvrir un mur relève du lot 03 ; une étude possible devient une question, pas une étude commandée.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une demande de pose ou raccordement n'autorise pas la fourniture d'un équipement majeur.

## Procédure
1. Reprendre l'extraction avec preuve, objet, site, zones, livrables, intervenants et limites explicites.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à la prestation concernée et exprimer sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer étude, relevé, diagnostic, démarche et coordination ; une dépendance ne devient pas une commande implicite.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque sans improviser un contrat.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Mission | Objet, zones couvertes, limites, livrables, destinataire, rôle du professionnel, exclusions. |
| Relevé existant | Accès, plans disponibles, cotations, niveaux, photos repérées, zones non accessibles. |
| Repérage matériel | Cibles, étiquettes, jalons, ruban de marquage ; supports, clips, vis et chevilles seulement si une méthode les prévoit. |
| Diagnostics avant travaux | Documents disponibles, date, périmètre, matériaux suspects ; absence de document distincte d'absence de risque. |
| Structure | Plans, reconnaissance des supports, charges connues, mission d'étude à confirmer avant intervention concernée. |
| Thermique et acoustique | Objectif demandé, composition existante, contraintes, étude et mesures disponibles ; performances non présumées. |
| Réseaux techniques | Repérage électricité, gaz, eau, évacuations, ventilation et réseaux enterrés ; investigations autorisées à préciser. |
| Enveloppe et humidité | État toiture/façade, infiltrations, support, ventilation, relevés ou investigations à faire valider. |
| Démarches | Copropriété, urbanisme, gestionnaire réseau, occupation du domaine : besoin, responsable et état réel à vérifier. |
| Coordination | Interfaces des lots, accès occupés, séquençage à valider, réunion demandée, compte rendu et décisions tracées. |
| Déchets et risques | Diagnostics, filières documentées, modalités de caractérisation ; ne pas qualifier seul un déchet dangereux. |
| Dossier documentaire | Plans datés, versions, notices attendues, pièces manquantes ; préparation du dossier distincte de sa remise finale. |

## Informations manquantes
- Demander adresse validée, périmètre des investigations, plans, occupation, accès, diagnostics, objectif et livrables.
- Nombre de visites, prélèvements, sondages ou documents non indiqué : `null` ; ne pas déduire une mission exhaustive d'un intitulé.
- Relever les sondages destructifs éventuels comme questions séparées avec remise en état à attribuer.

## Interfaces
- Lots 02 et 03 : études et diagnostics avant dépose ou atteinte structurelle ; aucune méthode de travaux déduite.
- Lots 04 à 18 : transmettre les données utiles sans remplacer leurs études spécifiques ; lot 19 pour remise documentaire finale.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur, pas de duplication par étude.

## Vérification et sortie
- Vérifier le périmètre de compétence et les justificatifs avec un professionnel ; ne garantir ni conformité, ni faisabilité, ni autorisation.
- Vérifier preuves, quantités `null`, absence de règle inventée, doublons de mission et démarches encore non obtenues.
- Garder une nomenclature interne exhaustive ; préparer avec `blueseatra-tce-redaction` un libellé externe bref sur données validées.
- Rendre visibles études exclues, accès impossibles et investigations non réalisées ; transmettre les alertes à `blueseatra-tce-audit`.
