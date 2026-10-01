# Runbook incident

Détecter, diagnostiquer, corriger, puis tirer les leçons sans chercher de coupable.

## Objectifs de service (SLO)

| Indicateur | Objectif | Mesure |
|---|---|---|
| Disponibilité de l'API | 99,5 % sur 30 jours | `GET /api/health` (réveil pg_cron toutes les 13 minutes, historique dans `cron.job_run_details`) |
| Latence p95 de l'API | ≤ 1 500 ms | `GET /api/exploitation/mesures`, `global.p95_ms` |
| Taux d'erreurs 5xx | ≤ 1 % | `global.taux_5xx_pct` |
| Échec d'extraction IA | ≤ 5 % des demandes | Demandes au statut `failed` dans la base |

`/api/exploitation/mesures` renvoie 404 tant que la variable `BLUESEATRA_METRICS_TOKEN` n'est pas définie sur Render. Une fois la variable définie, on lit les mesures avec l'en-tête `X-Metrics-Token`. Les mesures couvrent les 2 000 derniers appels de chaque route, depuis le dernier démarrage.

## Corrélation

Chaque réponse porte un en-tête `X-Request-ID`. Pour retrouver une requête :

1. Récupérer l'identifiant auprès de l'utilisateur, par exemple depuis l'onglet Réseau de son navigateur.
2. Chercher `"request_id": "<id>"` dans les journaux Render. Ils sont en JSON sur Render : `LOG_FORMAT=json` par défaut.
3. L'entreprise y apparaît sous forme pseudonymisée (`tenant`, 10 caractères). Aucun e-mail n'apparaît en clair.

Les requêtes en erreur 5xx ou de plus de 3 secondes sont journalisées automatiquement (`blueseatra.acces`), avec la route, le statut et la durée.

## Déroulé

![Déroulé d'un incident](./assets/schema-incident.png)

| Étape | Action | Délai visé |
|---|---|---|
| 1. Détecter | Alerte, message d'un client ou échec du réveil pg_cron | — |
| 2. Qualifier | `curl /api/health` (état et commit), `/api/exploitation/mesures`, journaux Render filtrés sur `"niveau": "ERROR"` | 10 min |
| 3. Contenir | Voir le tableau ci-dessous | 15 min |
| 4. Corriger | PR avec un test qui reproduit le problème, CI verte, fusion | selon la gravité |
| 5. Vérifier | `/api/health` sur le nouveau commit, puis parcours critique : connexion, demande, devis, PDF | 10 min |
| 6. Post-mortem | Fiche ci-dessous, dans un ticket GitHub, sous 5 jours ouvrés | — |

## Contenir selon le symptôme

| Symptôme | Première action |
|---|---|
| API en 5xx après un déploiement | Render → Rollback vers le déploiement précédent |
| Quotas qui bloquent à tort (402) | `BLUESEATRA_QUOTAS_APPLIQUES=0` sur Render |
| Extraction IA en échec | Vérifier le VPS (`/api/tags` sur `HERMES_BASE_URL`). Pour tout le monde : `BLUESEATRA_IA_COUPURE=repli` (avec `BLUESEATRA_IA_REPLI_*`) ou `=arret` sur Render. Pour une seule entreprise : fournisseur de repli dans ses paramètres |
| Recherche fournisseurs lente ou vide | Mesurer sous le vrai rôle : `BEGIN; SET LOCAL ROLE blueseatra_app; SELECT set_config('app.tenant_id', '<tenant>', true); EXPLAIN ANALYZE …; ROLLBACK;` (une mesure sous `postgres` ignore la RLS). Premier appel d'un terme plus lent : cache de la base (224 Mo) à froid. Vérifier que les fonctions `offres_candidates`, `catalogue_page`, `familles_catalogue` existent et que `blueseatra_app` peut les exécuter |
| Base inaccessible | Tableau de bord Supabase ; vérifier `DATABASE_URL_APP` et le pooler (port 6543) |
| Soupçon de fuite entre entreprises | Couper l'accès (suspension Render), conserver les journaux, prévenir les entreprises concernées sous 72 h si des données personnelles sont touchées (art. 33 RGPD) |

## Rôles (RACI)

| Activité | Responsable (R) | Approbateur (A) | Consulté (C) | Informé (I) |
|---|---|---|---|---|
| Surveillance quotidienne | Exploitation | Propriétaire | — | — |
| Incident de production | Exploitation | Propriétaire | Développement | Clients touchés |
| Retour arrière | Exploitation | Propriétaire | Développement | — |
| Violation de données | Propriétaire | Propriétaire | Juriste | CNIL, clients touchés |
| Post-mortem | Développement | Propriétaire | Exploitation | Équipe |

Aujourd'hui, le propriétaire assure tous les rôles. Le tableau fixe l'ordre des décisions pour le jour où l'équipe grandira.

## Fiche post-mortem

```markdown
### Incident AAAA-MM-JJ : titre
- Détection : quand, comment
- Impact : entreprises, durée, données
- Chronologie : horodatage des étapes
- Cause racine : pourquoi, cinq fois
- Ce qui a bien fonctionné / moins bien
- Actions : ticket, responsable, échéance
```

## Incident simulé (critère du ticket #93)

Test du 25/09/2026 sur un serveur local :

1. Une route répondant en 5xx a été appelée ; le journal a enregistré une ligne `blueseatra.acces` avec son `request_id`.
2. `/api/exploitation/mesures` a compté l'erreur, le taux de 5xx et la p95.
3. Le `request_id` a permis de retrouver la ligne de journal correspondante.

Le test en production reste à faire après la définition de `BLUESEATRA_METRICS_TOKEN`.
