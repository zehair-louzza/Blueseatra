---
name: blueseatra-lot-17-equipements-speciaux
description: "Photovoltaïque, IRVE, domotique et équipements spéciaux."
metadata:
  version: "4.0.0"
---

# Lot 17 : Énergies et équipements spéciaux

## Déclenchement
- Activer pour photovoltaïque, recharge de véhicule, domotique, ascenseur ou équipement spécifique identifié.
- Non-exemple adjacent : une PAC standard relève du lot 12 ; alimenter une borne au lot 14 ne commande pas une borne neuve.

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
1. Reprendre l'extraction avec preuve, fonction, équipement identifié, fourniture client et mission demandée.
2. Parcourir seulement la branche applicable ; rattacher chaque candidat à sa prestation et préciser sa condition.
3. Utiliser un `rule_id` approuvé seulement si fourni par le backend et applicable ; sinon `rule_id=null`, candidat conditionnel et question, sans supprimer les petits composants ni inventer d'identifiant.
4. Si l'équipement manque de notice ou de fiche spécialisée, demander ces données ; ne pas lui appliquer un kit universel.
5. Retourner uniquement le format demandé par le core ; si le schéma manque, signaler le manque.

## Checklist candidate : vérifier, ne pas prescrire
| Objet conditionnel | Détail à examiner ou à demander |
|---|---|
| Étude et implantation | Besoin, modèle, étude, support, charges, accès, maintenance, raccordement et autorisations à vérifier. |
| Photovoltaïque : modules | Modules explicitement demandés, implantation issue d'étude, rails, crochets, brides, jonctions et raccords d'enveloppe. |
| Photovoltaïque : réseau | Onduleur/micro-onduleur, câbles, connecteurs, coffrets, protections, liaison de terre, repérage et interface réseau selon projet. |
| Stockage éventuel | Batterie, supports, système de gestion, câbles, protections et conditions d'implantation ; jamais ajouté aux panneaux seuls. |
| IRVE : équipement | Borne demandée, socle/pied, platine, support, câble ou prise prévu au kit, fixation et accessibilité. |
| IRVE : interfaces | Alimentation, protections, communication, gestion de charge et mise en service par intervenant adapté ; pas de calibre IA. |
| Domotique | Contrôleur, passerelle, capteurs, actionneurs, bus, alimentation, interfaces et compatibilités documentées. |
| Ascenseur/élévateur | Équipement identifié, étude fabricant, structure, portes, machinerie, réservations, alimentation et maintenance ; aucune conception IA. |
| Autre équipement spécifique | Notice, nomenclature fabricant, périmètre de montage, organes de sécurité, réseaux et essais ; lacune = question. |
| Assemblages | Consoles, rails, platines, vis, chevilles, boulons, rondelles, écrous, joints et kits d'ancrage selon support. |
| Cheminements et raccords | Gaines, supports, boîtes, traversées, étanchéité, câbles/tubes et accès ; affectation unique aux lots concernés. |
| Logiciel et exploitation | Licences, comptes autorisés, configuration, mesures, essais, formation, notices, entretien et démarches séparés. |

## Informations manquantes
- Demander référence, étude, notice, contenu livré, support, tracés, puissance documentée, gestionnaire réseau et rôle des intervenants.
- Quantités d'équipements non explicites, rendement, production, capacité, câbles et fixations inconnus : `null`.
- Demander preuves d'autorisations et conditions de raccordement ; ne promettre ni aides, ni production, ni économies.

## Interfaces
- Lots 03/04 pour structure et enveloppe ; lot 14 pour puissance ; lot 15 pour données ; lot 16 pour sécurité.
- Lot 18 pour cheminements extérieurs ; attribuer matériel, alimentation, configuration et mise en service sans doublon.
- Protections communes au lot 01 et réception commune au lot 19 : un seul porteur ; essais spécialisés reliés sans duplication.

## Vérification et sortie
- Faire vérifier études, notices, qualifications pertinentes et essais ; aucune garantie de conformité, de raccordement ou de performance.
- Vérifier kit réel, branche applicable, quantités `null` et absence d'équipement, batterie ou licence ajouté implicitement.
- Garder la nomenclature interne exhaustive ; `blueseatra-tce-redaction` prépare un libellé externe bref sur données validées.
- Rendre visibles étude, réseau, autorisations, logiciels et maintenance exclus ; transmettre à `blueseatra-tce-audit`.
