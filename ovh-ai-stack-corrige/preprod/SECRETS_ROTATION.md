# Rotation des secrets Blueseatra

Ce runbook couvre Render, Supabase, Hermès/Cerebras, Stripe et la préproduction
OVH. Il décrit la séquence à suivre, mais n'autorise pas une rotation
automatique en production. Les nouveaux secrets sont générés et conservés
dans un gestionnaire de secrets, jamais dans Git, une issue, les logs ou une
commande dont l'historique shell est partagé.

## Préparation commune

1. Recenser les consommateurs du secret (API Render, worker, Hermès, VPS,
   webhooks). Ouvrir une fenêtre de changement et noter une voie de retour.
2. Créer un nouveau secret avec des droits minimaux. Quand le fournisseur
   autorise deux clés simultanées, conserver l'ancienne active pendant le
   déploiement et le test.
3. Mettre à jour chaque consommateur, redémarrer au besoin, vérifier la
   connectivité, une opération métier et les journaux sans exposer la valeur.
4. Révoquer l'ancien secret seulement lorsque tous les consommateurs ont
   basculé. Tester la révocation et noter l'heure dans le journal interne.
5. Si une fuite est suspectée, traiter la rotation comme un incident :
   isoler d'abord la ressource, invalider les sessions ou jetons concernés,
   rechercher les accès anormaux et notifier selon la procédure d'incident.

## Inventaire et ordre particulier

| Secret | Stockage / consommateurs | Rotation sans interruption |
|---|---|---|
| `DATABASE_URL`, `DATABASE_URL_APP` | Render API/worker ; Supabase pour production, PostgreSQL OVH pour préprod | Nouveau rôle/mot de passe, mise à jour API et worker, test authentification + RLS, puis révocation de l'ancien rôle. Ne jamais inverser le rôle privilégié (`DATABASE_URL`) et le rôle métier (`DATABASE_URL_APP`). |
| Clés Supabase publishable / service role | Configuration serveur et frontend selon l'usage | La clé publishable peut être diffusée au client ; la clé service role est exclusivement serveur. Créer/remplacer selon les contrôles Supabase et vérifier Storage/RLS avant révocation. Ne jamais mettre une service role dans le frontend. |
| `HERMES_API_KEY` / gateway key | Render API/worker et passerelle Hermès | Créer une seconde clé, basculer API/worker, vérifier une requête de test et les erreurs 401/403, révoquer l'ancienne. Garder préprod et production séparées. |
| Clé Cerebras | Passerelle Hermès uniquement | Créer une nouvelle clé avec plafond de consommation, mettre à jour Hermès, tester l'inférence de contrôle, puis révoquer l'ancienne. Ne jamais exposer la clé au frontend. |
| Clés Stripe et secrets de signature webhook | Backend billing quand l'intégration sera effectivement déployée | Distinguer `sk_test_` / `sk_live_` ; faire chevaucher l'ancien et le nouveau secret webhook selon les capacités Stripe, vérifier un événement signé et son idempotence, puis révoquer. Ne pas considérer Stripe live comme activé par ce runbook. |
| `POSTGRES_PASSWORD`, `PREPROD_APP_DB_PASSWORD`, `REDIS_PASSWORD` | `.env.preprod` sur OVH | Modifier un service à la fois. Changer le mot de passe du rôle PostgreSQL dans la base avant de basculer l'API/worker ; changer Redis côté service puis côté clients ; redémarrer et vérifier. `POSTGRES_PASSWORD` dans Compose ne modifie pas à lui seul un volume PostgreSQL déjà initialisé. |
| `BACKUP_ENCRYPTION_PASSPHRASE` | Gestionnaire de secrets + `.env.preprod` | Avant rotation, restaurer/vérifier un ancien backup, le déchiffrer et le rechiffrer avec le nouveau secret si la rétention doit se poursuivre. Garder l'ancien secret jusqu'à expiration ou migration de tous ses backups. |

## `JWT_SECRET` : invalidation des sessions

`backend/server.py` signe et valide actuellement les JWT avec une seule
valeur. Changer `JWT_SECRET` invalide donc immédiatement tous les jetons
existants. Prévoir une fenêtre de maintenance, prévenir les utilisateurs
qu'ils devront se reconnecter, modifier simultanément API et worker si
nécessaire, puis tester inscription/login et accès authentifié. Ne pas
prétendre qu'une rotation sans déconnexion est possible sans ajouter
auparavant une validation multi-clé avec identifiant de clé (`kid`).

## `APP_ENCRYPTION_KEY` : ne jamais remplacer directement

`backend/server.py` utilise Fernet pour chiffrer `settings_integrations.ai_key`
avec le préfixe `enc::`. La fonction de déchiffrement n'accepte aujourd'hui
qu'une seule clé. Remplacer la variable directement rendrait les clés déjà
stockées illisibles.

Procédure obligatoire avant toute rotation :

1. Faire un backup chiffré et vérifier sa restauration dans un environnement
   isolé. Conserver l'ancienne clé hors ligne jusqu'à validation complète.
2. Implémenter et tester une transition à deux clés : déchiffrer avec
   l'ancienne ou la nouvelle, chiffrer exclusivement avec la nouvelle.
   Prévoir le déploiement coordonné API/worker et un retour arrière.
3. Rechiffrer les valeurs `enc::` existantes par lots avec checkpoint et
   journal d'audit, sans afficher ni exporter leur texte clair.
4. Comparer le nombre de valeurs migrées au nombre attendu, tester la lecture
   et les appels fournisseur, puis seulement retirer l'ancienne clé.

**État actuel :** la transition à deux clés n'est pas codée. Cette rotation
doit être une tâche dédiée, revue et testée avant exécution ; ce document
ne constitue pas une autorisation pour la lancer.

## Vérifications de sortie

- API/worker préprod : `./scripts/healthcheck.sh` puis
  `./scripts/smoke-test.sh` (après correction/validation du smoke test).
- Production : login sur un tenant de test, accès tenant A/B et appel IA
  contrôlé ; vérifier les logs d'échec de déchiffrement ou d'authentification.
- Sauvegardes : vérifier qu'un fichier créé avec la nouvelle passphrase se
  restaure sans dépendre de l'ancienne.
- Journal interne : date, opérateur, familles de secrets changées, tests
  exécutés, anciennes clés révoquées, voie de retour restante. Jamais la
  valeur d'un secret.
