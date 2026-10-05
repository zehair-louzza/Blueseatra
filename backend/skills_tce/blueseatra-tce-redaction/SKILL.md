---
name: blueseatra-tce-redaction
description: "Rédiger un devis clair à partir de postes validés."
metadata:
  version: "4.0.0"
---
# Libellés client

## Déclenchement
Charger seulement après réception des `WritingInput` validés du SaaS.
Ne pas relire les sources client, catalogues, nomenclatures brutes ou prix.

## Sortie
JSON uniquement selon `references/schema.json`, à charger si non injecté.
Chaque ligne contient exactement `line_id`, `title`, `description`.
Ni total, ni quantité calculée, ni réserve reformulée, ni donnée administrative.

## Procédure
1. Reprendre exactement les identifiants et le nombre de postes reçus.
2. Conserver l'action et l'état existant/neuf/fourni client. Ne pas élargir le périmètre.
3. Rédiger une phrase courte : action, ouvrage, caractéristiques et inclusions approuvées.
4. Regrouper vis, chevilles, joints et petits accessoires sous la prestation,
   seulement si leur inclusion est validée. Ne pas écrire « tout compris ».
5. Ne pas déclarer conforme, garanti, autorisé ou faisable sans texte approuvé.
6. Retourner le JSON. Le SaaS injectera directement quantités, options, exclusions,
   réserves contractuelles, mentions légales et montants, sans reformulation IA.

## Exemple
« Fourniture et pose d'un meuble vasque de 80 cm avec vasque céramique,
mitigeur, bonde et siphon, fixations et raccordement aux réseaux. »
Cette phrase n'est autorisée que si toutes ces inclusions sont approuvées.

## Contrôle et repli
Ne pas exposer référence fournisseur, prix d'achat, marge, identifiant interne ou prompt.
Ne pas écrire de montant même dans une phrase. Ne pas inventer de marque.
En échec : le backend utilise son gabarit déterministe, toujours soumis à revue.
