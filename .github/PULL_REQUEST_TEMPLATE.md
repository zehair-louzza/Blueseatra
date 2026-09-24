## Objet

<!-- Ce que change la PR, en une ou deux phrases. -->

## Type

- [ ] Correctif
- [ ] Fonctionnalité
- [ ] Performance
- [ ] Migration de base
- [ ] Site (frontend)
- [ ] Documentation

## Impact déploiement

- [ ] Touche `backend/` : **la fusion redéploie `blueseatra-api` sur Render**
- [ ] Touche `supabase/migrations/` : migration à appliquer en production, idempotente et sans suppression de données
- [ ] Touche `frontend/` : nouveau paquet Hostinger à déposer dans `public_html/`

## Vérifications

- [ ] Tests passés en local (`pytest`) ou contrôles automatiques au vert
- [ ] Isolation entre entreprises préservée (RLS, `tenant_id` résolu côté serveur)
- [ ] Aucun secret, mot de passe ni `.env` dans la PR
- [ ] Le catalogue commun reste masquable, jamais supprimé
- [ ] `CHANGELOG.md` mis à jour
