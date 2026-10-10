---
name: blueseatra-lot-10-peinture
description: "Peinture, préparation, papier peint et finitions."
metadata:
  version: "4.0.0"
---

# Lot 10 : Peinture et finitions

## Déclenchement
- Activer pour peinture, préparation associée, papier peint, vernis, lasure ou joint de finition demandé.
- Non-exemple adjacent : un enduit structurel ou de façade relève des lots 03/04 ; peindre ne résout pas une infiltration.

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
1. Reprendre l'extraction avec preuve, pièces, faces, état décrit, teinte, finition et limites de préparation.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Distinguer réparation localisée et ratissage général ; ne pas convertir une simple remise en peinture en rénovation totale.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Support | Matériau, ancien revêtement, adhérence, humidité, fissures, taches, défauts et diagnostics à demander. |
| Protection locale | Film, bâche, ruban compatible, masquage vitrages/appareillages ; distinguer protections communes. |
| Dépose accessoire | Poignées, plaques, luminaires ou grilles concernés ; repérage, sachets de vis et attribution aux lots compétents. |
| Nettoyage | Lessivage, dégraissant, rinçage adapté, chiffons, éponges et gestion des résidus selon support. |
| Décapage et grattage | Anciennes couches, matériel, abrasifs, captage, sacs ; risque du revêtement à vérifier avant intervention. |
| Réparation | Rebouchage, enduit, bandes localisées, calicot, mastic compatible ; cause des fissures non supposée résolue. |
| Ratissage et ponçage | Périmètre réellement demandé, enduit, abrasifs, dépoussiérage et niveau de préparation convenu. |
| Impression | Primaire adapté, traitement des fonds, fixateur ou isolant de tache seulement si système validé. |
| Peinture | Référence, teinte, aspect, destination, couches prévues par demande/notice ; aucune quantité de peinture déduite. |
| Papier peint | Référence, lés, raccords, préparation, colle, joints, découpes et dépose de l'ancien revêtement attribuée. |
| Bois et métal | Préparation, primaire, vernis/lasures/laque, traitement local prescrit et protection des ferrures. |
| Joints et livraison | Fond de joint, mastic de finition, retrait masquage, repose attribuée, retouches et nettoyage local. |

## Informations manquantes
- Demander surfaces par support, état, teinte, aspect, système, préparation attendue et éléments à déposer/reposer.
- Litres, couches non indiquées, abrasifs, consommables, longueurs de joints et fixations absents : `null`.
- Une tache ou une photo ne suffit pas à diagnostiquer sa cause ; demander contrôle avant promesse de résultat.

## Interfaces
- Lots 02 et 06 pour ancien revêtement et joints de plaques ; lot 09 pour plinthes ; lot 08 pour menuiseries.
- Lots 11 à 16 pour dépose/repose d'appareils et grilles ; ne pas doubler bandes, enduits ou joints déjà portés ailleurs.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier supports, compatibilité, conditions d'application et préparation ; aucune garantie de conformité ou de finition parfaite.
- Vérifier kits, quantités `null`, preuve des couches et absence de ratissage généralisé implicite.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un poste externe bref sur données validées.
- Rendre visibles traitement de cause, reprises lourdes et supports exclus ; transmettre à `blueseatra-tce-audit`.
