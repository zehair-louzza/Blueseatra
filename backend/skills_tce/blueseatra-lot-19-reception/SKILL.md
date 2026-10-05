---
name: blueseatra-lot-19-reception
description: "Essais, réception, nettoyage final et livraison TCE."
metadata:
  version: "4.0.0"
---

# Lot 19 : Essais, réception et livraison

## Déclenchement
- Activer pour essais, réglages, mise en service, nettoyage final, documents, réception ou levée de réserves demandé.
- Non-exemple adjacent : un essai électrique déjà porté au lot 14 doit être référencé, pas facturé ou exécuté une seconde fois ici.

## Cadre impératif
- Cette checklist est un brouillon candidat en attente d'approbation professionnelle, pas un catalogue de règles approuvées.
- Elle n'autorise pas à créer des lignes commerciales confirmées ; produire seulement des candidats et questions.
- Utiliser `blueseatra-tce-nomenclature` et son schéma chargé par `blueseatra-tce-core` ; ne pas inventer de champs.
- Aucun prix, calcul, métré final, dimensionnement ou durée ; les calculs appartiennent au backend.
- Pour tout candidat, `quantity=null`, même si une quantité est explicite ; conserver celle-ci dans la preuve source, sans calcul.
- Vis et chevilles : quantités uniquement selon notice fabricant, support et méthode validés ; aucun ratio générique.
- Inspecter les kits et accessoires remis ; `kit=a_verifier` par défaut, `kit=non_concerne` si hors kit établi ; ne pas doubler les composants déjà fournis.
- Une pose, un raccordement ou une mise en service seul n'autorise pas la fourniture d'un équipement majeur.

## Procédure
1. Reprendre l'extraction avec preuve, prestations à contrôler, intervenants, périmètre de livraison et documents attendus.
2. Parcourir les contrôles applicables ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Attribuer chaque essai une seule fois : conserver son porteur métier et coordonner ici sa preuve et sa remise.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Préparation | Liste des ouvrages, périmètre accepté pour contrôle, accès, rendez-vous, intervenants et moyens réellement disponibles. |
| Contrôles visuels | Ouvrages achevés, finitions, fixations visibles, joints, accès maintenance, étiquettes et protections provisoires. |
| Eau et sanitaires | Mise en eau, fuite, écoulement, siphons, vannes, groupe de sécurité et réglages ; résultats fournis par professionnel. |
| Chauffage/climatisation | Mise en service, réglages, équilibrage, condensats et documents du professionnel ; aucun résultat simulé. |
| Ventilation | Entrées d'air, transfert, extraction, rejet, mesures, équilibrage et accès entretien ; rapport et limites. |
| Électricité | Repérage, essais et mesures du professionnel, schémas et attestations si processus confirmé ; aucune valeur fabriquée. |
| Réseaux et sécurité | Tests fonctionnels, communication, scénarios de sécurité validés, paramétrage, droits d'accès et documentation. |
| Enveloppe et menuiseries | Fonctionnement ouvrants, joints, interfaces et essais convenus ; contrôle partiel distinct d'une garantie globale. |
| Moyens et consommables | Appareils de mesure, accessoires d'essai, bouchons, flexibles, joints, étiquettes et chiffons ; moyens non livrés sauf demande. |
| Retouches et anomalies | Vis, chevilles, caches, joints ou pièces manquants identifiés ; réparation candidate au lot d'origine, pas ajout automatique. |
| Nettoyage final | Aspiration, lavage adapté, produits, chiffons, sacs, retrait des films et déchets ; distinguer nettoyage courant du lot 01. |
| Documents et remise | DOE demandé, plans de récolement, notices, rapports, clés, badges, accessoires, garanties réellement documentées et formation prévue. |
| Réception et réserves | Constat daté, participants, réserves, responsable, preuve de correction, levée à confirmer ; aucune acceptation ou signature inventée. |

## Informations manquantes
- Demander liste des essais, protocoles validés, résultats, professionnels, pièces attendues et responsabilité du nettoyage final.
- Nombre de contrôles, visites, consommables et pièces de reprise absent : `null` ; prévoir un essai n'est pas prouver sa réussite.
- Document ou résultat absent : demander la preuve et maintenir l'incertitude ; ne pas générer certificat, attestation ou date fictifs.

## Interfaces
- Tous lots : référencer les essais existants et leurs preuves ; défaut identifié renvoyé au lot porteur sans reprise implicite.
- Lot 00 pour préparation documentaire ; lot 01 pour repli ; lot 02 pour déchets ; un seul porteur par zone et phase.
- Protections communes au lot 01 et réception commune ici : une seule occurrence, sans effacer les essais métier distincts.

## Vérification et sortie
- Faire examiner résultats, réserves et documents par les professionnels/parties compétents ; aucune garantie de conformité ou d'acceptation.
- Vérifier preuves, périmètre réel des contrôles, quantités `null`, kits remis et absence de doublon de nettoyage ou réception.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare une synthèse externe brève des données validées.
- Rendre visibles essais non faits, réserves ouvertes et documents manquants ; transmettre les blocages à `blueseatra-tce-audit`.
