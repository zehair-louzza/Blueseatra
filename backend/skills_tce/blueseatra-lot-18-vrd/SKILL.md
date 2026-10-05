---
name: blueseatra-lot-18-vrd
description: "VRD, terrassements, réseaux enterrés et extérieurs."
metadata:
  version: "4.0.0"
---

# Lot 18 : VRD et extérieurs

## Déclenchement
- Activer pour terrassement, réseau enterré, assainissement, drainage, clôture, terrasse ou aménagement extérieur demandé.
- Non-exemple adjacent : un raccord sanitaire intérieur relève du lot 11 ; une adresse ne prouve aucun réseau enterré.

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
1. Reprendre l'extraction avec preuve, zone, usage, accès, réseaux connus et limites de raccordement.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Demander plans et reconnaissance avant choix de tracé, profondeur ou pente ; ne pas déduire le sous-sol d'une photo.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Implantation | Limites, niveaux relevés, accès, portance, sol, arbres, ouvrages conservés, piquets et repères autorisés. |
| Réseaux existants | Plans, repérage, investigations, démarches DT/DICT si applicables et validation par intervenants compétents. |
| Terrassement | Décapage, fouille, soutènement/blindage éventuel, eau, stockage des terres, chargement et accès engins à étudier. |
| Déblais et remblais | Nature caractérisée, réemploi, filière, géotextile, lit de pose, matériaux de remblai et contrôle de compactage. |
| Eau et conduites | Tubes, raccords, vannes, coudes, tés, manchons, joints, fourreaux et interface concessionnaire à confirmer. |
| Assainissement | Tuyaux, culottes, tampons, regards, cunettes, couvercles, joints, raccords et solution issue d'étude si nécessaire. |
| Eaux pluviales/drainage | Caniveaux, grilles, drains, géotextile, regards, raccords, exutoire autorisé et entretien ; infiltration non présumée possible. |
| Réseaux secs | Fourreaux, aiguilles, chambres, réservations, dispositifs avertisseurs prescrits, câbles attribués et repérage. |
| Bordures et surfaces | Fondation validée, bordures, pavés/dalles/enrobé selon demande, joints, rives, seuils, niveaux et raccords. |
| Terrasse | Support, plots/lambourdes selon système, lames/dalles, clips, vis, calages, joints, rives et fixation documentée. |
| Clôture/portail | Poteaux, panneaux, jambes de force, scellements, platines, boulons, vis, chevilles, capuchons et quincaillerie. |
| Équipements extérieurs | Éclairage, motorisation, arrosage ou mobilier seulement si demandés ; support, réseaux et commandes attribués. |
| Contrôle et récolement | Photos avant remblai, essais convenus, niveaux relevés, plans, nettoyage local et remise en état du parcours. |

## Informations manquantes
- Demander plans, relevés, sol, reconnaissance réseaux, tracés, profils, exutoire, limites de propriété et accès engins.
- Longueurs, profondeurs, pentes, volumes, foisonnement, rotations, remblais et ancrages inconnus : `null`.
- Demander autorisations et filières ; aucun réseau, exutoire disponible ou aptitude du terrain ne doit être présumé.

## Interfaces
- Lot 00 pour études/démarches ; lot 03 pour fondations ; lot 04 pour EP ; lot 11 pour limites eau/assainissement.
- Lots 14/15/17 pour câbles, éclairage, portail et équipements ; attribuer tranchée, fourreau et remise en état une seule fois.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; déchets coordonnés avec lot 02.

## Vérification et sortie
- Faire vérifier sol, réseaux, stabilité des fouilles, raccordements et essais ; aucune garantie de conformité ou de faisabilité.
- Vérifier kits, quantités `null`, repérages et absence de pente, profondeur ou réseau inventé.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un libellé externe bref sur données validées.
- Rendre visibles raccordements, autorisations, terres non caractérisées et reprises exclues ; transmettre à `blueseatra-tce-audit`.
