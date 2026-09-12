# Runbook — activer `DATABASE_URL_AUTH` sur Render

Étapes 4 et 5 du durcissement RLS. Ce document est celui que tu exécutes toi-même, à la main, dans les interfaces Supabase et Render. Aucune commande ici ne doit être collée dans cette conversation ni dans un commit.

Prérequis : [PR #73](https://github.com/zehair-louzza/Blueseatra/pull/73) fusionnée (le code du moteur AUTH existe déjà et a un repli sûr), et la migration `20260912050000_rls_etape4_role_blueseatra_app.sql` appliquée sur Supabase.

> **Statut au 12/09/2026 — étapes 4 et 5 TERMINÉES.** Le rôle `blueseatra_app` est créé, son mot de passe défini, `DATABASE_URL_AUTH` configurée sur Render et le service redéployé. Vérifié : `blueseatra_app` et `postgres` apparaissent tous deux dans `pg_stat_activity`, les lectures métier et le catalogue fonctionnent. Prochaine étape : **7** (`FORCE ROW LEVEL SECURITY`, table par table).

## Ce qui se passe si tu t'arrêtes après l'étape 4

Rien. Le rôle `blueseatra_app` existe, a ses droits, mais aucune connexion ne l'utilise. `backend/database.py` ne bascule que si `DATABASE_URL_AUTH` diffère de `DATABASE_URL` dans l'environnement Render — tant que cette variable n'existe pas, le repli reste actif. Tu peux donc faire l'étape 4 aujourd'hui et l'étape 5 la semaine prochaine sans aucun risque intermédiaire.

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
   - Clé : `DATABASE_URL_AUTH`
   - Valeur : `postgresql+asyncpg://blueseatra_app.xmsxlochasjauhnxarvc:<MOT_DE_PASSE>@aws-0-eu-west-1.pooler.supabase.com:6543/postgres`

   Remplacer `<MOT_DE_PASSE>` par la valeur de l'étape 4bis. Garder le même hôte et le même port (6543, Transaction Pooler) que `DATABASE_URL`.

### Le piège du nom d'utilisateur — vérifié le 12/09/2026

L'utilisateur doit être **qualifié par l'identifiant du projet** : `blueseatra_app.xmsxlochasjauhnxarvc`, et **non** `blueseatra_app` seul.

Supavisor (le pooler de Supabase) mutualise un même point d'entrée entre tous les projets. Il a donc besoin du `ref` du projet pour savoir vers quelle base router la connexion. C'est la même logique que pour `DATABASE_URL`, dont l'utilisateur est `postgres.xmsxlochasjauhnxarvc` et non `postgres`.

Sans cette qualification, la connexion échoue avec :

```
InternalServerError: (ENOIDENTIFIER) no tenant identifier provided
(external_id or sni_hostname required)
```

Version originale de ce runbook indiquait `blueseatra_app` seul — erreur corrigée après diagnostic par connexion réelle. Le symptôme observé côté Render était trompeur : `socket.gaierror: [Errno -2] Name or service not known`, qui ressemble à un problème de DNS ou de nom d'hôte, alors que la cause était le nom d'utilisateur.

### Combinaisons testées par connexion réelle

| Hôte | Utilisateur | Port | Résultat |
|---|---|---|---|
| `aws-0-eu-west-1` | `blueseatra_app` | 6543 | `ENOIDENTIFIER` |
| `aws-0-eu-west-1` | `blueseatra_app.xmsxlochasjauhnxarvc` | 6543 | **OK** |
| `aws-0-eu-west-1` | `blueseatra_app.xmsxlochasjauhnxarvc` | 5432 | OK |
| `aws-1-eu-west-1` | `blueseatra_app.xmsxlochasjauhnxarvc` | 6543 | `ENOTFOUND` |

L'hôte est bien `aws-0`, pas `aws-1` — les deux résolvent en DNS, mais seul `aws-0` héberge ce projet.

### Caractères spéciaux dans le mot de passe

Préférer un mot de passe **strictement alphanumérique**, par exemple via `python3 -c "import secrets; print(secrets.token_hex(24))"`.

Dans une URI, `@` sépare les identifiants de l'hôte et `#` ouvre un fragment. Un mot de passe contenant l'un de ces caractères coupe l'analyse de l'URI au mauvais endroit, et le fragment restant est interprété comme nom d'hôte — d'où une erreur DNS trompeuse. Ils devraient sinon être encodés (`%40`, `%23`), ce qui ajoute une source d'erreur manuelle sans bénéfice.

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

**La vérification décisive** — une requête SQL qui montre quels rôles sont réellement connectés :

```sql
select usename, count(*) as connexions, max(backend_start) as derniere
from pg_stat_activity
where usename in ('blueseatra_app', 'postgres')
group by usename order by usename;
```

Tant que `blueseatra_app` n'apparaît **pas** dans le résultat, le repli est encore actif : le backend passe tout par `postgres` et la configuration n'a pas pris effet, même si `/api/health` répond et que l'application fonctionne. C'est exactement le piège rencontré le 12/09/2026 — tout semblait marcher, mais rien n'avait changé.

État attendu après une configuration réussie : **les deux rôles présents**, `blueseatra_app` pour le chemin métier et `postgres` pour le chemin d'authentification.

Compléter par un test fonctionnel :

1. Se connecter à l'application (un vrai login) — exerce le moteur AUTH sur `users`.
2. Consulter la liste des devis — exerce le moteur métier sur `quotes`.

Si les deux fonctionnent alors que les deux rôles sont connectés, le routage par table est confirmé en conditions réelles.

---

## Après cette étape

Le runbook complet (`supabase/migrations/20260912040000_rls_etape3_force_NON_APPLIQUEE.sql`) continue avec :

- **Étape 6** — sans objet, déjà vérifié le 12/09 : les `WITH CHECK` existent.
- **Étape 7** — `FORCE ROW LEVEL SECURITY`, table par table, en commençant par `audit_logs`. C'est la première étape qui rend RLS réellement contraignante. Ne pas l'appliquer avant d'avoir confirmé que l'étape 5 fonctionne depuis au moins quelques jours en production.
- **Étape 8** — sondage croisé A/B (`test_tenant_isolation_live.py`), avec deux comptes de test réels.
- **Étape 9** — vérifier que `blueseatra_app` n'a jamais reçu `rolbypassrls` par erreur.

## Retour arrière, à tout moment

Supprimer la variable `DATABASE_URL_AUTH` dans Render et sauvegarder. Le code retombe immédiatement sur le comportement de repli (moteur unique), sans redéploiement de code nécessaire — seul un redémarrage du service, déclenché automatiquement par le changement de variable d'environnement.
