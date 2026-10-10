---
name: blueseatra-tce-audit
description: "Repérer omissions et écarts avant rendu du devis."
metadata:
  version: "4.0.0"
---
# Audit contradictoire

## Déclenchement
Charger avant validation humaine du descriptif, avec les données assainies.
Ne pas utiliser comme autorisation de publication ou comme validateur de prix.

## Sortie
JSON selon `references/schema.json`, à charger si non injecté.
Retourner les défauts dans `findings`, pas une version corrigée du devis.
Une liste vide n'est jamais une certification de conformité ou d'exhaustivité.

## Procédure
1. Comparer les sources et l'extraction : omissions, quantités interprétées comme
   capacités, mauvais lots, pose devenue fourniture, variantes fusionnées.
2. Comparer les postes approuvés au périmètre : doublons et accessoires manquants.
   Si la nomenclature ou les notices ne sont pas fournies, signaler cette limite.
3. Vérifier que protections, dépose, déchets, essais et documents demandés subsistent.
4. Vérifier l'absence d'élargissement du texte client et de donnée interne.
5. Signaler les réserves/exclusions qui risquent de disparaître.
6. Ne pas refaire les métrés ou calculs ; ne pas modifier les approbations serveur.
7. Retourner les anomalies avec identifiants connus ; pas d'identifiants inventés.

## Pièges
Un JSON valide peut être techniquement faux. Une citation existante peut être mal comprise.
Un descriptif fluide peut omettre des travaux. Une anomalie n'autorise pas sa correction
automatique sans repasser la validation de la version modifiée.

## Contrôle
Les anomalies IA complètent les contrôles déterministes, elles ne les remplacent pas.
Une incertitude ayant un impact client doit rester visible ou bloquer le devis final.
