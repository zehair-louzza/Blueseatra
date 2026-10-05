---
name: blueseatra-lot-16-securite
description: "Sécurité incendie, sûreté et serrurerie."
metadata:
  version: "4.0.0"
---

# Lot 16 : Sécurité incendie et sûreté

## Déclenchement
- Activer pour incendie, évacuation, désenfumage, éclairage de sécurité, serrurerie ou dispositif de sûreté demandé.
- Non-exemple adjacent : une serrure de porte standard déjà intégrée au lot 08 ne doit pas être fournie à nouveau ici.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter le contenu réel des kits ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Une pose, réparation ou un raccordement seul n'autorise pas la fourniture d'un équipement majeur.

## Procédure
1. Reprendre l'extraction avec preuve, usage du bâtiment, système existant, mission et documents de sécurité disponibles.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer fourniture, pose, intégration, paramétrage, essais et maintenance ; ne pas déduire des obligations d'un nom de local.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Référentiel du projet | Usage, classement documenté, étude, plans, consignes, contraintes d'accessibilité et intervenant responsable. |
| Détection/alarme incendie | Centrale, détecteurs, socles, déclencheurs, diffuseurs, modules et interfaces selon étude ; aucun nombre standard présumé. |
| Réseau et alimentation | Câbles, conduits, boîtes, borniers, presse-étoupes, batteries ou alimentation selon système ; compatibilité à valider. |
| Éclairage de sécurité | Blocs demandés, pictogrammes, supports, commande, câblage, autonomie et essais issus de documents validés. |
| Extinction | Extincteurs ou équipements demandés, supports, signalisation, coffret éventuel, accès et contrôle professionnel. |
| Désenfumage | Ouvrants, volets, moteurs, commandes, liaisons, amenées d'air, conduits et essais selon étude ; pas de solution générique. |
| Portes de sécurité | Ensemble documenté, joints, paumelles, sélecteur, ferme-porte, retenue, déclenchement et interfaces. |
| Serrurerie | Serrure, cylindre, clés, gâche, rosaces, poignées, barre de sortie si prévue, vis de fixation et réglages. |
| Contrôle d'accès | Lecteur, contrôleur, contact, bouton, gâche/ventouse, alimentation et comportement en sécurité à faire valider. |
| Fixations et finitions | Platines, supports, vis, chevilles, rondelles, écrous, capots ; support et compatibilité avec l'ensemble requis. |
| Traversées et signalisation | Calfeutrement documenté, étiquettes, panneaux, plans/consignes demandés et maintien des dégagements. |
| Essais et maintenance | Scénarios validés, tests, relevés, registre, notices, formation et contrat séparé ; aucune attestation automatique. |

## Informations manquantes
- Demander usage, étude, plans, références, état existant, responsabilité d'intégration, scénario de sécurité et essais attendus.
- Nombre d'appareils, implantations, performances, batteries, câbles et ancrages inconnus : `null`.
- Demander la validation professionnelle des obligations incendie/accessibilité ; ne pas annoncer une mise en conformité globale.

## Interfaces
- Lots 05/08 pour portes ; lot 06 pour cloisons ; lot 04 pour ouvrants ; lot 13 pour désenfumage/air à attribuer.
- Lots 14 et 15 pour alimentation, communication et accès ; ne pas doubler dispositifs, câblage ou paramétrage.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais métier reliés sans duplication.

## Vérification et sortie
- Faire vérifier cohérence du système, comportement en sécurité, accessibilité et essais ; aucune garantie de conformité ou de sûreté.
- Vérifier kit, ensembles certifiés documentés, quantités `null` et absence d'obligation normative inventée.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un libellé externe bref sur données validées.
- Rendre visibles intégration, attestations, maintenance et travaux hors périmètre ; transmettre à `blueseatra-tce-audit`.
