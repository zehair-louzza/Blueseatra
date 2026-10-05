---
name: blueseatra-tce-nomenclature
description: "Lister matériaux, petites pièces et dépendances TCE."
metadata:
  version: "4.0.0"
---
# Nomenclature interne

## Déclenchement
Charger après extraction approuvée, avec le skill du lot cible.
Ne pas utiliser pour choisir les prix, dimensionner ou acheter.

## Entrée et sortie
Entrée : parents approuvés, lot cible, règles approuvées du SaaS, fiche du lot.
Sortie : JSON uniquement selon `references/schema.json` ; charger si non injecté.

## Procédure
1. Parcourir chaque ouvrage, puis équipement, réseau, raccordement, support,
   fixation, joint, étanchéité, finition, consommable, essai et document.
2. Rattacher chaque candidat au `parent_id` réel. Ne pas créer un deuxième
   équipement principal déjà extrait ; compléter seulement ses composants.
3. Utiliser un `rule_id` uniquement s'il apparaît dans `approved_rules`.
   Une checklist du pack n'est PAS une règle approuvée. À défaut : `rule_id=null`.
4. Tous les candidats de cette étape gardent `quantity=null`, une condition et
   une question. Les quantités finales seront attribuées hors IA, par le SaaS.
5. Signaler le contenu de kit inconnu avec `kit=a_verifier`. Ne pas inventer
   de quantité de vis ni présumer que siphon, abattant ou fixations sont inclus.
6. Proposer les interfaces comme candidats conditionnels du lot cible, liés
   à l'ouvrage d'origine. Ne pas recréer une prestation identique dans deux lots.
7. Consolidation protections, déchets, nettoyage et consommables : une seule
   allocation serveur par zone/scénario, sans perdre les preuves de demande.
8. Retourner les candidats non tarifés et les questions. Aucun achat automatique.

## Exemple
Parent : pose d'un meuble vasque fourni par le client.
Candidats : fixations adaptées au mur, siphon si absent, raccords/joints selon kit.
Pas de meuble neuf. Pas de nombre forfaitaire de chevilles. Pas de fourniture validée.

## Contrôle
Tous les candidats ont un parent ; tous les `rule_id` non nuls sont approuvés.
Le lot du candidat correspond au lot traité, même si le parent relève d'un autre lot.
Les variantes restent rattachées à leur parent et ne deviennent pas une base commune.
