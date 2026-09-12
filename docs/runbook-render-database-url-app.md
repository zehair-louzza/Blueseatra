# Runbook — activer `DATABASE_URL_APP` sur Render

Étapes 4 et 5 du durcissement RLS. Ce document est celui que tu exécutes toi-même, à la main, dans les interfaces Supabase et Render. Aucune commande ici ne doit être collée dans cette conversation ni dans un commit.

Prérequis : [PR #73](https://github.com/zehair-louzza/Blueseatra/pull/73) fusionnée (le code du moteur AUTH existe déjà et a un repli sûr), et la migration `20260912050000_rls_etape4_role_blueseatra_app.sql` appliquée sur Supabase.

## Ce qui se passe si tu t'arrêtes après l'étape 4

Rien. Le rôle `blueseatra_app` existe, a ses droits, mais aucune connexion ne l'utilise. `backend/database.py` ne bascule que si `DATABASE_URL_APP` diffère de `DATABASE_URL` dans l'environnement Render — tant que cette variable n'existe pas, le repli reste actif. Tu peux donc faire l'étape 4 aujourd'hui et l'étape 5 la semaine prochaine sans aucun risque intermédiaire.

---

## Étape 4 — appliquer la migration du rôle

1. Ouvrir [supabase.com/dashboard/project/xmsxlochasjauhnxarvc/sql/new](https://supabase.com/dashboard/project/xmsxlochasjauhnxarvc/sql/new)
2. Coller le contenu de `supabase/migrations/20260912050000_rls_etape4_role_blueseatra_app.sql`
3. Exécuter
4. Lire les trois requêtes de vérification à la fin :
   - `rolbypassrls` doit valoir `false`
   - `tables_accessibles` doit valoir `11`
   - la dernière requête doit renvoyer **zéro ligne**

Si l'une des trois diverge, ne pas continuer vers l'étape 5 — le rôle n'est pas dans l'état attendu.

## Étape 4bis — générer le mot de passe

Choisir une des deux options, décrites en détail à la fin du fichier de migration :

- **Dashboard Supabase** (recommandé) : [Database → Roles](https://supabase.com/dashboard/project/xmsxlochasjauhnxarvc/database/roles) → trouver `blueseatra_app` → *Reset password* → copier immédiatement la valeur affichée.
- **SQL Editor**, si le dashboard n'est pas accessible : générer une valeur forte localement (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`), puis `ALTER ROLE blueseatra_app WITH PASSWORD '...'` dans un onglet SQL Editor que tu fermes immédiatement après.

Ne colle cette valeur nulle part d'autre que dans le champ Render de l'étape 5.1.

---

## Étape 5 — configurer Render

### 5.1 — Ajouter la variable, sans redéployer encore

1. [dashboard.render.com/web/srv-d8tlsuf7f7vs73f9cjeg](https://dashboard.render.com/web/srv-d8tlsuf7f7vs73f9cjeg) → **Environment**
2. **Add Environment Variable**
   - Clé : `DATABASE_URL_APP`
   - Valeur : `postgresql+asyncpg://blueseatra_app:<MOT_DE_PASSE>@aws-0-eu-west-1.pooler.supabase.com:6543/postgres`

   Remplacer `<MOT_DE_PASSE>` par la valeur de l'étape 4bis. Garder le même hôte et le même port (6543, Transaction Pooler) que `DATABASE_URL` — seuls l'utilisateur et le mot de passe changent.

3. **Save Changes**

Render propose de redéployer immédiatement. **Refuser** si l'interface le permet, ou accepter — les deux sont sûrs : le code lit les deux variables au démarrage et se comporte correctement dans les deux cas, y compris avant que le mot de passe soit validé. Si le déploiement échoue à cause d'un mot de passe incorrect, l'ancien déploiement continue de servir le trafic (Render ne bascule qu'après un `/api/health` réussi sur la nouvelle instance).

### 5.2 — Vérifier avant de valider

Après le redéploiement :

```
curl https://blueseatra-api.onrender.com/api/health
```

Doit répondre `{"status":"healthy","commit":"<dernier commit>"}`. Si l'appel échoue ou boucle en `build_in_progress` puis `failed`, le mot de passe ou l'URI est probablement incorrect — corriger la variable et resauvegarder, sans toucher au code.

Puis, dans les logs Render (**Logs** dans le tableau de bord), chercher une éventuelle ligne mentionnant une authentification refusée sur Postgres (`password authentication failed`) — c'est le signal le plus direct d'une URI mal formée.

### 5.3 — Confirmer que le moteur AUTH est réellement utilisé

Pas de commande SQL nécessaire ici : le test `test_repli_sans_database_url_auth` de `backend/tests_security/test_rls_engine_routing.py` vérifie l'inverse (le repli). Pour confirmer le cas actif, le plus fiable est un test fonctionnel :

1. Se connecter à l'application (un vrai login).
2. Consulter la liste des devis (une vraie lecture métier).

Si les deux fonctionnent, les deux moteurs sont opérationnels : l'authentification a réussi via le moteur AUTH (rôle privilégié, table `users`), et la lecture des devis a réussi via le moteur métier (rôle `blueseatra_app`, table `quotes`). C'est la preuve la plus simple que le routage par table fonctionne en conditions réelles.

---

## Après cette étape

Le runbook complet (`supabase/migrations/20260912040000_rls_etape3_force_NON_APPLIQUEE.sql`) continue avec :

- **Étape 6** — sans objet, déjà vérifié le 12/09 : les `WITH CHECK` existent.
- **Étape 7** — `FORCE ROW LEVEL SECURITY`, table par table, en commençant par `audit_logs`. C'est la première étape qui rend RLS réellement contraignante. Ne pas l'appliquer avant d'avoir confirmé que l'étape 5 fonctionne depuis au moins quelques jours en production.
- **Étape 8** — sondage croisé A/B (`test_tenant_isolation_live.py`), avec deux comptes de test réels.
- **Étape 9** — vérifier que `blueseatra_app` n'a jamais reçu `rolbypassrls` par erreur.

## Retour arrière, à tout moment

Supprimer la variable `DATABASE_URL_APP` dans Render et sauvegarder. Le code retombe immédiatement sur le comportement de repli (moteur unique), sans redéploiement de code nécessaire — seul un redémarrage du service, déclenché automatiquement par le changement de variable d'environnement.

---

## Incident du 12/09/2026 — inversion des moteurs

### Ce qui s'est passé

La variable s'appelait initialement `DATABASE_URL_AUTH` et alimentait le moteur d'**authentification**. En suivant le runbook, les identifiants du rôle **restreint** (`blueseatra_app`) y ont été placés — ce qui est le réflexe naturel, puisque c'est le nouveau rôle qu'on vient de créer.

Or le chemin d'authentification lit `users`, `tenants` et `tenant_users` **avant** qu'un tenant soit connu. Et `blueseatra_app` n'a délibérément aucun droit sur ces trois tables. Résultat immédiat en production : plus aucun login possible, avec le message « Connexion au serveur impossible ».

### Pourquoi le nom était le piège

`DATABASE_URL_AUTH` se lit comme « l'URL du nouveau rôle » alors qu'elle signifiait « l'URL du chemin AUTH », donc le rôle **privilégié**. Le sens correct est l'inverse de l'intuition : c'est le chemin **métier** qui reçoit le rôle restreint, et l'authentification qui conserve `DATABASE_URL`.

### Correction

La variable s'appelle désormais `DATABASE_URL_APP` — le mot `APP` fait écho au nom du rôle lui-même (`blueseatra_app`), ce qui rend l'association évidente.

Et le moteur d'authentification n'est **plus configurable** : il utilise toujours `DATABASE_URL`. Trois tests verrouillent cet invariant par lecture du source, dont un qui échoue explicitement si quelqu'un reproduit l'inversion.

Si `DATABASE_URL_AUTH` est encore définie dans l'environnement, elle est ignorée et le code émet un avertissement au démarrage — plutôt que de laisser une configuration héritée sans effet, silencieusement.

### Ce qui a masqué le problème

`/api/health` répondait `healthy` et l'application servait tout le trafic, parce que le moteur métier restait sur `DATABASE_URL`. Seul le login échouait. C'est la deuxième fois dans ce chantier qu'un repli silencieux masque un échec de configuration — d'où la requête `pg_stat_activity` de l'étape 5.3, qui est la seule vérification fiable.
