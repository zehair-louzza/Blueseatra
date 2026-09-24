# Politique de sécurité

## Signaler une faille

N'ouvrez pas de ticket public. Écrivez directement au propriétaire du dépôt ([@zehair-louzza](https://github.com/zehair-louzza)). Nous accusons réception sous 72 heures.

## Principes appliqués

- **Isolation des entreprises** : RLS PostgreSQL sur le schéma `blueseatra`, `tenant_id` toujours résolu côté serveur, rôle applicatif `blueseatra_app` sans droit de contournement.
- **Secrets** : jamais dans le dépôt. Analyse gitleaks à chaque PR ; clés tierces chiffrées (Fernet, `APP_ENCRYPTION_KEY`).
- **Données** : le catalogue commun est masquable, jamais supprimé ; aucune purge automatique de données client.
- **Journal d'audit** : toutes les actions sensibles sont tracées par entreprise.
- **IA** : l'IA ne calcule aucun prix ; les montants viennent de règles fixes et du catalogue.

## Versions prises en charge

Seule la branche `main`, déployée en production, reçoit les correctifs.
