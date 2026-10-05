---
name: blueseatra-lot-15-courants-faibles
description: "Réseaux, interphonie, données et courants faibles."
metadata:
  version: "4.0.0"
---

# Lot 15 : Électricité courants faibles

## Déclenchement
- Activer pour réseau de communication, baie, interphonie, audiovisuel, contrôle d'accès ou système connecté demandé.
- Non-exemple adjacent : l'alimentation secteur d'une baie relève du lot 14 ; un système incendie relève du lot 16.

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
1. Reprendre l'extraction avec preuve, usages, points, équipements existants, fourniture client et limites réseau.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer câblage, appareils, abonnement, configuration et essais ; ne pas rendre la mise en service logicielle implicite.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Architecture | Usages, réseau existant, plans, équipements conservés, interfaces opérateur et caractéristiques validées. |
| Baie/coffret | Enveloppe, rails, panneaux, guides-câbles, tablettes, ventilation si prévue et accès maintenance. |
| Câbles | Cuivre, fibre, coaxial, audio ou bus selon projet, parcours, repères, connecteurs, pigtails et raccords adaptés. |
| Cheminements | Gaines, goulottes, supports, coudes, jonctions, couvercles, traversées, séparation des réseaux à faire vérifier. |
| Fixations | Vis, chevilles, équerres, rondelles, écrous-cages, colliers et attaches adaptées au câble et au support. |
| Prises et brassage | Boîtes, plastrons, modules, adaptateurs, panneaux, cordons, obturateurs et étiquetage ; kits à détailler. |
| Matériel actif | Commutateur, routeur, point d'accès ou convertisseur seulement si fourniture demandée ; alimentation et compatibilité à préciser. |
| Interphonie | Platine, poste, moniteur, supports, boîtiers, câbles, alimentation et interface de commande de porte. |
| Contrôle d'accès | Lecteur, contrôleur, contact, bouton, gâche/ventouse et alimentation ; attribution unique avec lot 16. |
| Intrusion/vidéo | Capteurs, centrale, caméras, support, enregistreur et stockage explicitement demandés ; implantation et droits à faire valider. |
| Audiovisuel | Prises, câbles, connectique, supports, appareils demandés, alimentation et commandes ; pas d'écran ou enceinte automatique. |
| Configuration et essais | Adressage, comptes remis par canal autorisé, licences, paramétrage, tests, mesures, repérage et documentation attendue. |

## Informations manquantes
- Demander architecture, plans, points, catégories/protocoles validés, références, parcours, alimentation et responsabilités de configuration.
- Longueurs, ports, cordons, supports, licences et fixations inconnus : `null` ; ne pas déduire un matériel actif de prises seules.
- Demander accès autorisés sans demander de secrets dans le devis ; licences, abonnements et stockage restent des périmètres séparés.

## Interfaces
- Lot 14 pour alimentation ; lot 06 pour réservations ; lot 16 pour sécurité/serrurerie ; lot 17 pour intégration domotique.
- Affecter contrôle d'accès et intrusion selon la prestation dominante ; ne pas répéter contrôleur, câblage ou configuration.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais métier reliés sans duplication.

## Vérification et sortie
- Faire vérifier compatibilités, performances, accès et obligations de protection des données ; aucune garantie de conformité ou de cybersécurité.
- Vérifier kit, équipements fournis client, quantités `null` et caractère explicite des licences et mises en service.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` rédige brièvement sans identifiants ni secrets.
- Rendre visibles matériel actif, abonnements, configuration et stockage exclus ; transmettre à `blueseatra-tce-audit`.
