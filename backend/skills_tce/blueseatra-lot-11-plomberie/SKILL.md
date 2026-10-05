---
name: blueseatra-lot-11-plomberie
description: "EF/ECS, évacuations, sanitaires et chauffe-eau."
metadata:
  version: "4.0.0"
---

# Lot 11 : Plomberie et sanitaires

## Déclenchement
- Activer pour eau froide/chaude, évacuation, vasque, WC, douche, évier, robinetterie ou chauffe-eau demandé.
- Non-exemple adjacent : « raccorder l'évier existant » ne signifie ni fournir un évier neuf ni créer toutes ses alimentations.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter les kits : bonde, siphon, flexibles, joints et fixations ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; aucun doublon.
- Une pose ou un raccordement seul n'autorise pas la fourniture d'un appareil majeur, même s'il figure dans la checklist.

## Procédure
1. Reprendre l'extraction avec preuve, appareil, fourniture client, réseaux existants et actions réellement demandées.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Séparer appareil, pose, raccordement existant, création/modification de réseau et remise en service ; aucune extension silencieuse.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Réseaux EF/ECS | Matériau, parcours, tubes, coudes, tés, réductions, raccords, nourrices, vannes, purge, fourreaux et calorifuge éventuel. |
| Évacuations | Tracé, raccord existant, tubes, coudes, culottes, manchons, réductions, tampons, joints, colle et accès de curage. |
| Fixation et étanchéité | Colliers, consoles, rosaces, tiges, vis, chevilles, rondelles, écrous, joints plats, mastic et produits adaptés aux raccords. |
| Vasque/lavabo | Appareil seulement si fourni dans la demande, support, bonde, trop-plein, siphon de vasque, raccord d'évacuation et accès. |
| Robinetterie de vasque | Mitigeur/mélangeur demandé, flexibles, robinets d'arrêt, joints, fixation, rosaces et raccord EF/ECS compatible. |
| WC au sol | Cuvette, abattant, réservoir/mécanisme selon modèle, robinet d'arrêt, alimentation, pipe/manchon, joints et fixation au sol. |
| WC suspendu | Bâti, ancrages, cuvette, tiges, abattant, plaque de commande, manchettes, joints ; habillage, trappe et finition à attribuer. |
| Chauffe-eau : support | Modèle demandé, support, console/trépied si prescrit, ancrages, raccords EF/ECS et accessoires de raccord selon notice. |
| Chauffe-eau : sécurité | Groupe de sécurité prévu par système, raccordement, siphon, évacuation du groupe jusqu'au réseau, accès et maintenance. |
| Chauffe-eau : électricité | Alimentation existante ou à créer, raccord, commande/protection à faire vérifier au lot 14 ; aucun calibre inventé. |
| Douche : receveur | Receveur demandé, bonde-siphon, évacuation, pieds/châssis/socle, calage, support, accessibilité et niveaux à vérifier. |
| Douche : étanchéité | Support, système, primaire, bandes, angles, collerettes, raccord bonde/receveur/mur et joints ; partage explicite avec lot 09. |
| Douche/baignoire : équipement | Robinet, raccords, barre, flexible, douchette, paroi/profilés, joints, vis/chevilles ; baignoire, pieds, vidage, trop-plein, tablier si concernés. |
| Évier et appareils | Évier existant ou neuf explicitement demandé, bonde, trop-plein, siphon, robinets, flexibles ; lave-linge/lave-vaisselle : arrivée et rejet à vérifier. |
| Essais et particularités | Mise en eau, étanchéité, écoulement, accès, nettoyage local ; gaz ou réseau collectif : intervention distincte à faire valider. |

## Informations manquantes
- Demander modèles, inventaire des kits, support, emplacement, tracés, arrivées/évacuations existantes et fourniture client.
- Longueurs, diamètres non fournis, pentes, raccords, joints et ancrages inconnus : `null` ; capacité d'un appareil ≠ quantité.
- Demander si évier/douche/WC sont fournis, seulement posés ou raccordés ; distinguer adaptation locale et création complète.

## Interfaces
- Lots 03/06 pour supports et réservations ; lot 08 pour meubles ; lot 09 pour étanchéité/niveaux ; lot 10 pour finition.
- Lots 12 et 14 pour production partagée, alimentation et commande ; lot 18 pour réseau extérieur ; attribuer chaque raccord une seule fois.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais métier reliés sans duplication.

## Vérification et sortie
- Faire vérifier supports, kits, raccordements, accessibilité et essais par un professionnel ; ne garantir ni conformité ni étanchéité.
- Vérifier siphon vasque, cuvette/abattant/habillage WC, évacuation du groupe et alimentation chauffe-eau, support/étanchéité douche.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` regroupe les petits composants validés dans le poste parent.
- Rendre visibles appareils non fournis, réseaux et habillages exclus ; transmettre les manques à `blueseatra-tce-audit`.
