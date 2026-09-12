# Audit d'isolation inter-tenants — BlueSeaTra

**Date :** 12 septembre 2026
**Périmètre :** `backend/server.py`, `backend/pg_adapter.py`, politiques RLS du schéma `blueseatra`
**Contexte :** prérequis avant commercialisation du module fournisseur à des entreprises potentiellement concurrentes

---

## Verdict

**Aucune fuite inter-tenants détectée.** Sur 114 appels de lecture/écriture analysés dans `server.py`, tous sont correctement cloisonnés. Le code respecte partout le motif « vérifier l'appartenance, puis muter par identifiant ».

Mais l'isolation repose **entièrement sur la discipline du code applicatif**, jamais sur la base. Cette section explique pourquoi c'est le point à durcir avant la première vente, même en l'absence de faille actuelle.

---

## Méthode

Analyse statique de l'arbre syntaxique de `server.py` : extraction de tous les appels `db.<collection>.<opération>()`, puis pour chacun, recherche d'un filtre `tenant_id` dans l'appel lui-même ou d'une garde d'appartenance dans la fonction englobante.

| Catégorie | Nombre |
|---|---|
| Appels lecture/écriture analysés | 114 |
| Portant directement un filtre `tenant_id` | 78 |
| Sans `tenant_id` dans l'appel | 36 |
| → tables d'authentification sans `tenant_id` par conception | 9 |
| → protégés par une garde d'appartenance en amont | 23 |
| → sans garde détectée automatiquement | 4 |
| **Fuites confirmées après examen manuel** | **0** |

### Les 9 cas bénins

Les modèles `users` et `tenants` n'ont pas de colonne `tenant_id`, et c'est correct : `tenants` **est** la table des tenants, et `users` est globale, rattachée aux tenants par la table de jonction `tenant_users`. Les requêtes concernées sont des recherches d'authentification par email ou par identifiant utilisateur.

### Les 23 cas protégés

Motif systématique, correctement appliqué :

```python
q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id}, {"_id": 0})
if not q:
    raise HTTPException(404, "Quote not found")
await db.quotes.update_one({"id": quote_id}, {"$set": {...}})
```

La garde porte le `tenant_id` et renvoie 404 si l'objet n'appartient pas au tenant appelant. La mutation suivante peut donc filtrer sur le seul identifiant sans risque. C'est une protection valide contre l'IDOR, et le choix du 404 plutôt que du 403 est le bon — il ne révèle pas l'existence de l'objet.

### Les 4 cas examinés manuellement

| Ligne | Appel | Conclusion |
|---|---|---|
| 741 | `requests.update_one({"id": req_id}, ...)` dans `create_request()` | **Sûr.** `req_id` vient d'être généré dans la même fonction, l'objet appartient par construction au tenant appelant. |
| 902, 905, 910 | `requests.update_one({"id": request_id}, ...)` dans `_run_deep_vision()` | **Sûr.** Tâche de fond, pas un endpoint. Son unique appelant (ligne 942) exécute d'abord `find_one({"id": request_id, "tenant_id": cu.tenant_id})` et renvoie 404 sinon. Garde en amont. |

---

## Risque n° 1 — `_build_where` ignore silencieusement une colonne inconnue

`backend/pg_adapter.py` :

```python
col = getattr(model, key, None)
if col is None:
    logger.warning("_build_where: column '%s' not found on %s — skipped", key, model.__tablename__)
    continue
```

et en fin de fonction :

```python
return and_(*conds) if conds else true()
```

**Conséquence :** une faute de frappe sur un nom de colonne, ou le renommage d'une colonne sans mise à jour des appelants, ne provoque **aucune erreur**. Le filtre est simplement retiré. Si le filtre retiré est `tenant_id`, la requête retourne les lignes de **tous les tenants**. Si tous les filtres sont retirés, `true()` retourne la table entière.

Un `WARNING` dans les logs n'est pas un mécanisme de sécurité : personne ne lit les warnings d'une application en production.

**Correctif recommandé** — transformer l'avertissement en erreur :

```python
col = getattr(model, key, None)
if col is None:
    raise ValueError(
        f"_build_where: colonne '{key}' inconnue sur {model.__tablename__}. "
        f"Filtre refuse — un filtre partiel peut exposer les donnees d'autres tenants."
    )
```

Deux lignes, aucun changement de comportement pour le code correct, et transformation d'une faille silencieuse en échec bruyant. À faire avant tout nouveau développement sur cette couche.

Durcissement complémentaire : refuser toute opération sur une table possédant une colonne `tenant_id` lorsque le filtre n'en contient pas, sauf autorisation explicite par un paramètre nommé.

---

## Risque n° 2 — RLS est présente mais inerte pour le backend

Les 14 tables de `blueseatra` ont RLS activée, avec des politiques correctement écrites :

```sql
(tenant_id)::text = blueseatra.current_tenant()
```

La table `users` est verrouillée en `service_role` seul sur les quatre commandes. C'est du bon travail.

Mais la fonction est définie ainsi :

```sql
CREATE OR REPLACE FUNCTION blueseatra.current_tenant() RETURNS text
LANGUAGE sql STABLE SET search_path TO '' AS $$
  SELECT NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', '')
$$;
```

`request.jwt.claims` est renseigné par PostgREST, c'est-à-dire par l'API REST auto-générée de Supabase. **Sur la connexion `asyncpg` directe du backend, ce réglage n'existe pas et la fonction renvoie `NULL`.** Aucune politique ne peut donc jamais correspondre.

Et de toute façon `relforcerowsecurity` vaut `false` sur les 14 tables, tandis que le backend se connecte avec un rôle privilégié qui **contourne RLS** par construction.

**Conclusion :** RLS protège les accès passant par l'API Supabase, mais n'intervient à aucun moment dans le chemin applicatif. Ce n'est pas une seconde ligne de défense, c'est une ligne de défense inactive sur le seul chemin réellement utilisé.

### Plan de durcissement

Trois changements coordonnés, **dans cet ordre impératif** :

1. **Étendre `current_tenant()`** pour accepter un réglage de session, afin que la connexion directe puisse s'identifier :

```sql
CREATE OR REPLACE FUNCTION blueseatra.current_tenant() RETURNS text
LANGUAGE sql STABLE SET search_path TO '' AS $$
  SELECT coalesce(
    NULLIF(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', ''),
    NULLIF(current_setting('app.tenant_id', true), '')
  )
$$;
```

2. **Émettre `SET LOCAL app.tenant_id = '<tenant du jeton>'`** au début de chaque transaction du backend.

   `SET LOCAL`, jamais `SET`. Avec un pool de connexions (`pool_size=8`), un `SET` global persisterait sur la connexion et ferait fuiter le tenant d'une requête vers la suivante — un bug strictement pire que le problème initial.

3. **Se connecter avec un rôle non propriétaire** des tables, puis activer :

```sql
ALTER TABLE blueseatra.<table> FORCE ROW LEVEL SECURITY;
```

   Sans le changement de rôle, `FORCE` reste sans effet pour le propriétaire des tables.

Appliquer l'étape 3 avant les étapes 1 et 2 coupe la production instantanément.

---

## Risque n° 3 — l'isolation n'est couverte par aucun test

Les 23 gardes d'appartenance sont écrites à la main, endpoint par endpoint. Rien n'empêche une future contribution d'ajouter un endpoint sans garde. La faille serait alors silencieuse : pas d'erreur, pas de log, juste des données d'un autre tenant dans une réponse HTTP 200.

**Test à ajouter**, paramétré sur l'ensemble des endpoints :

1. Créer deux tenants de test, A et B, avec un devis, une demande et un catalogue chacun.
2. Pour chaque endpoint acceptant un identifiant, appeler avec le jeton de A et l'identifiant de B.
3. Exiger un 404 ou un 403. Tout 200 est un échec du test.
4. Vérifier symétriquement que les endpoints de liste ne renvoient jamais d'objet de l'autre tenant.

Ce test doit tourner en intégration continue et bloquer la fusion. C'est la seule protection qui résiste au temps et aux refactorisations, indépendamment de la vigilance des relecteurs.

---

## Synthèse des actions

| Priorité | Action | Effort | Statut |
|---|---|---|---|
| 1 | `_build_where` lève une erreur au lieu d'avertir | 2 lignes | à faire |
| 2 | Test automatisé de fuite inter-tenants en CI | 1 à 2 jours | à faire |
| 3 | Durcissement RLS en 3 étapes (`app.tenant_id` + `FORCE`) | 2 à 3 jours | à faire |
| — | Audit des 114 appels de `server.py` | fait | aucune fuite |

Aucune de ces actions n'est urgente au sens d'une faille ouverte. Toutes sont bloquantes avant d'héberger les tarifs négociés de deux entreprises concurrentes dans la même base.
