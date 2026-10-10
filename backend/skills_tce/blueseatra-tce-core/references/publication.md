# Barrière serveur de publication

Un JSON accepté est une proposition, pas une décision. Les validations technique,
périmètre, texte, commerciale et légale appartiennent au SaaS et aux personnes habilitées.

Le rendu final est interdit si l'un de ces contrôles échoue :
- Version/scénario modifiés depuis la dernière approbation.
- Prestation demandée non traitée, doublon de couverture ou composant facturé deux fois.
- Travail inclus non chiffré, quantité commerciale absente ou variante non résolue.
- Prix absent remplacé par zéro, gratuité non explicite ou inclusion sans parent chiffré.
- Réserve matérielle supprimée ; données légales non approuvées.
- Total partiel présenté comme total du périmètre ; statut technique bloquant.

Le noyau FastAPI livré distingue `chiffre`, `inclus`, `offert`, `a_chiffrer`.
`inclus` n'est pas un prix zéro : pas de montant propre, parent chiffré obligatoire.
`offert` est un zéro explicitement approuvé. Les options ne contribuent pas au total de base.

Ce pack n'envoie aucun document et ne crée pas de signature. Son endpoint de projection
ne produit qu'un JSON éligible au rendu ; l'envoi et la publication restent un workflow
SaaS distinct avec droits, journalisation, conditions d'acceptation et révision immuable.

L'estimation provisoire et l'avenant ne sont pas implémentés dans le noyau de code V4.
Ne pas contourner les blocages : ajouter des contrats dédiés, validation et tests
avant d'autoriser ces modes. Un provisoire doit être clairement non soumis à acceptation.
