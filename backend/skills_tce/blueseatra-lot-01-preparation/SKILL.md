---
name: blueseatra-lot-01-preparation
description: "Installation, accès et protections de chantier TCE."
metadata:
  version: "4.0.0"
---

# Lot 01 : Installation et préparation

## Déclenchement
- Activer pour installation de chantier, protection, balisage, accès, stockage ou repli demandé.
- Non-exemple adjacent : préparer un support à peindre relève du lot 10, pas de l'installation commune.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une pose ou un raccordement seul n'autorise pas l'achat d'un équipement majeur ; distinguer location et fourniture.

## Procédure
1. Reprendre l'extraction avec preuve, zones, accès, occupation, biens conservés et responsabilités.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à une prestation et indiquer sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Désigner un porteur pour chaque protection commune ; distinguer protection générale et besoin local propre à un ouvrage.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| État initial | Photos contradictoires demandées, biens conservés, zones fragiles, accès interdits, constat éventuel. |
| Sols et circulations | Film, feutre, plaques, ruban compatible, raccords, rives, maintien et risque de glissade à examiner. |
| Murs et équipements | Bâches, housses, cartons d'angle, mousse, ruban de masquage ; finitions sensibles et dépose sans dommage. |
| Parties communes | Escalier, ascenseur, seuils, portes, cheminement, horaires et autorisation du gestionnaire. |
| Poussières | Cloisons provisoires, film, fermeture zippée, joints, ruban ; captage, filtration et renouvellement d'air à faire valider. |
| Balisage | Barrières, plots, panneaux, rubalise, éclairage provisoire ; fixations, colliers, vis et chevilles selon support. |
| Accès en hauteur | Échafaudage, plateforme, accès, stabilisation, protections collectives, montage et contrôles par intervenants compétents. |
| Eau et électricité provisoires | Points disponibles, coffrets, câbles, tuyaux, raccords, supports, protection des cheminements à valider. |
| Stockage et manutention | Emplacements, protections contre intempéries, calage, sangles, racks, moyens de levage ; ne pas livrer l'outillage au client. |
| Base et hygiène | Installations demandées, sanitaires, lavage, consommables, accès et entretien ; besoins à confirmer selon chantier. |
| Déchets provisoires | Bacs, sacs, contenants identifiés, zone de tri ; attribution avec lot 02, sans doubler collecte ou transport. |
| Nettoyage et repli | Nettoyage courant, aspiration, collecte des protections, retrait adhésifs, démontage, remise en état ; livraison distincte. |

## Informations manquantes
- Demander surfaces et parcours à protéger, état des finitions, occupation, accès, stockage et équipements provisoires existants.
- Durée de maintien, surface protégée, nombre de dispositifs et consommations absents : `null` ; aucun ratio par pièce.
- Demander qui fournit, installe, entretient et retire chaque protection ; ne pas généraliser une protection locale au chantier entier.

## Interfaces
- Tous lots : mutualiser uniquement les mêmes zones, fonctions et phases ; conserver un besoin spécifique distinct lorsqu'il est prouvé.
- Lot 02 pour tri/évacuation ; lots 11 et 14 pour alimentations ; lot 19 pour nettoyage de livraison et réception.
- Protections communes portées ici une seule fois ; réception commune portée au lot 19 une seule fois.

## Vérification et sortie
- Faire vérifier accès, stabilité, réseaux provisoires et protections par un professionnel ; aucune garantie de conformité.
- Vérifier compatibilité adhésifs/supports, maintien des accès, kits réels, preuves et absence de doublons de moyens.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` ne regroupe que les éléments validés.
- Rendre visibles zones exclues et contraintes d'occupation ; transmettre les alertes à `blueseatra-tce-audit`.
