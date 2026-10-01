# Contribuer à Blueseatra

![Chaîne de livraison : PR, contrôles, fusion, déploiement](docs/assets/schema-livraison.png)

Dépôt privé et propriétaire : les contributions se font sur invitation.

## Flux de travail

1. Créez une branche depuis `main` : `feat/…`, `fix/…`, `perf/…`, `docs/…`, `chore/…`.
2. Commits courts et explicites, en français.
3. Ouvrez une PR : le modèle rappelle l'impact de déploiement.
4. Les contrôles « CI infra » et « Sécurité » doivent être au vert.
5. Fusion en squash, après accord du propriétaire.

**Important** : toute fusion qui touche `backend/` redéploie automatiquement l'API sur Render.

## Règles non négociables

- Aucune donnée d'une entreprise visible par une autre.
- Les prix, remises, marges et TVA sont calculés par des règles fixes, jamais par un modèle d'IA.
- Migrations idempotentes, sans suppression de données ; index créés avec `CONCURRENTLY`.
- Le catalogue commun peut être masqué, jamais supprimé.
- Pas de secret, de mot de passe ni de `.env` dans le dépôt.

## En local

Voir les sections 7 et 8 du [README](./README.md). Build du site : `CI=false GENERATE_SOURCEMAP=false npm run build` dans `frontend/`.
