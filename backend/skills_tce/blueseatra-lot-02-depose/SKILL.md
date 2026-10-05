---
name: blueseatra-lot-02-depose
description: "Dépose, curage, tri et évacuation de travaux TCE."
metadata:
  version: "4.0.0"
---

# Lot 02 : Dépose et curage

## Déclenchement
- Activer pour déposer, démonter, démolir, curer, trier ou évacuer un élément identifié.
- Non-exemple adjacent : déposer un lavabo n'autorise ni sa fourniture neuve au lot 11 ni la réfection complète de la pièce.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter les kits de consignation ou d'obturation ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler leurs composants.
- Pose, dépose ou raccordement ne valent pas fourniture d'un équipement majeur neuf.

## Procédure
1. Reprendre l'extraction avec preuve, élément déposé, limites, maintien en service et destination du bien.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer dépose, consignation, manutention, déchets et reprises ; ne pas transformer une dépose en remplacement.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Périmètre conservé | Ouvrage visé, fixations cachées, éléments voisins, réseaux partagés, finitions et biens à protéger. |
| Risques avant dépose | Diagnostics, matériaux suspects, réseau gaz, électricité, eau, structure ; alerte et validation avant intervention concernée. |
| Consignation | Responsable, repérage, coupure autorisée, isolation de réseau, condamnation, étiquettes ; ne pas donner de mode opératoire dangereux. |
| Mise hors eau | Vidange, récupération, bouchons, capuchons, raccords d'obturation, joints ; maintien des réseaux voisins à vérifier. |
| Déconnexion électrique | Intervenant compétent, terminaison protégée, boîte, couvercle, repérage ; réutilisation ou abandon à décider. |
| Démontage réemployable | Repères, sachets pour vis/rondelles/écrous, conservation des ferrures, emballage, calage et stockage identifié. |
| Revêtements et doublages | Couches réellement déposées, colle résiduelle, plinthes, ossatures, suspentes, vis et chevilles restantes. |
| Appareils et menuiseries | Vannes, raccords, joints, scellements, pattes, vitrage, quincaillerie ; transport séparé des composants fragiles. |
| Supports provisoires | Étaiement ou maintien à étudier, platines, calages, ancrages ; aucune méthode structurelle définitive proposée. |
| Poussières et nuisances | Protection locale, captage, sacs, aspiration, consommables ; protections générales à mutualiser au lot 01. |
| Tri et transport | Catégories documentées, sacs, bacs, benne, chargement, portage, parcours, filière et justificatifs demandés. |
| Après dépose | Trous, arêtes, supports découverts, obturations, nettoyage local, photos ; reprises de finition à attribuer, pas à présumer. |

## Informations manquantes
- Demander état, dimensions, couches déposées, diagnostics, réseaux, accès, destination réemploi ou déchet et limites de reprise.
- Masse, volume, foisonnement, nombre de rotations, quantités de sacs ou de fixations non documentés : `null`.
- Sans diagnostic ou reconnaissance suffisante, formuler le contrôle préalable et la réserve ; ne pas conclure à l'absence de risque.

## Interfaces
- Lot 00 pour diagnostics ; lot 03 pour structure ; lots techniques pour consignations et remise en service.
- Lot receveur pour support après dépose ; lot 18 pour terrassements ; attribuer transport et déchets sans duplication.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur.

## Vérification et sortie
- Faire vérifier risques, stabilité et coupures par les professionnels concernés ; aucune certification ni faisabilité garantie.
- Vérifier prestations explicites, limites conservées, preuve de destination, kits et absence d'équipement neuf ajouté.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un poste externe concis sur données validées.
- Rendre visibles diagnostics manquants, reprises exclues et déchets non caractérisés ; transmettre à `blueseatra-tce-audit`.
