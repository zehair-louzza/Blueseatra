# ADR : file d'extraction séquentielle in-process (une demande à la fois)

## Statut
Accepté — 2026-08-26 (PR #64)

## Contexte

Le VPS d'inférence IA (`162.19.44.2`, OVH) n'a **pas de GPU** — extraction
mesurée à ~8.8 tokens/s en CPU seul. Avant ce correctif, chaque demande créée
via `POST /api/requests` (ou retraitée via `POST /api/requests/{id}/process`)
lançait sa propre tâche asyncio en arrière-plan (`BackgroundTasks.add_task`),
sans aucune coordination entre elles.

**Bug réel observé en production le 25/08/2026** : 5 demandes créées à
~2 minutes d'intervalle (`N°26081206`, `N°26080320`, `N°26081277`,
`N°26081290`, `N°26081293`) sont restées bloquées sur le statut
`"processing"` pendant plus de 80 minutes. Vérification directe sur le VPS
(`docker stats`, `ollama ps`, `uptime`) au moment du contrôle : CPU à 0 %,
aucun modèle activement en train de traiter quoi que ce soit. Cause double,
confirmée en recoupant avec l'historique des déploiements Render :

1. **Contention CPU** : les 5 extractions tournaient en parallèle sur un
   processeur unique déjà lent en soi — chacune ralentit toutes les autres.
2. **Perte silencieuse** : ~46 minutes après la création de la 5ᵉ demande,
   un redéploiement Render (déclenché par la fusion d'une PR sans lien,
   comme c'est fréquent sur ce projet — chaque merge redéploie) a tué le
   processus `blueseatra-api` en cours, emportant avec lui toutes les tâches
   asyncio en mémoire. Aucun mécanisme n'existait pour détecter ou
   récupérer une demande ainsi abandonnée : elle restait bloquée
   **indéfiniment**, sans aucun signal pour l'utilisateur.

## Décision

Ajouter une file FIFO strictement séquentielle, **in-process** :

- `_extraction_queue` (`asyncio.Queue`) + une seule tâche de fond persistante
  (`_extraction_worker_loop`), démarrée une fois au `startup` de l'app.
- `create_request()` et `reprocess_request()` poussent désormais
  `(request_id, tenant_id, vision_pages)` sur cette file au lieu de lancer
  une tâche indépendante. Statut intermédiaire `"queued"`.
- Le worker traite un item à la fois : `await process_request(...)` doit
  être **totalement terminé** (succès ou échec) avant de dépiler le
  suivant. Une seule extraction IA tourne jamais en même temps.
- **Filet de sécurité au démarrage** (`_requeue_stuck_on_startup`) : toute
  demande encore `"queued"` ou `"processing"` quand le processus redémarre
  est automatiquement remise en file. Corrige directement le mode de panne
  observé le 25/08 — a réparé seul les 5 demandes bloquées dès ce
  déploiement, sans intervention manuelle.
- Position réelle exposée par l'API (`GET /api/requests`,
  `GET /api/requests/{id}` → champ `queue_position`, calculé par ordre de
  création parmi les demandes `queued` du tenant) et affichée clairement
  dans le SaaS : « En file d'attente (position N) » plutôt qu'un statut
  muet.

## Alternatives considérées

### Réactiver la file durable Redis/RQ existante (`extraction_worker.py`)

- **Pour** : le code existe déjà dans ce repo, prêt à l'emploi ; survit à un
  redémarrage de `blueseatra-api` puisque le worker RQ est un processus
  séparé.
- **Contre** : nécessite un service Render `type: worker` dédié (Starter,
  ~7 $/mois) **et** un Redis Key Value (Starter, ~10 $/mois) — retiré du
  `render.yaml` le 23/08/2026 précisément pour éviter ce coût récurrent,
  alors que la file n'avait encore rien à traiter (`REDIS_URL` jamais
  définie). Réintroduire ce coût uniquement pour résoudre un problème de
  *sérialisation* (une IA lente qui ne doit jamais tourner deux fois en
  parallèle) est disproportionné : aucun besoin actuel de scaler
  horizontalement le traitement.
- **Rejeté pour l'instant**, mais le chemin de code reste intact et
  prioritaire : si `REDIS_URL` est un jour définie, `create_request()`
  utilise `_enqueue_extraction()` (RQ) au lieu de la file in-process. Cette
  ADR ne s'applique qu'à la branche `else` (Redis absent), qui est le cas
  réel en production aujourd'hui.

### Limiteur de concurrence simple (sémaphore `asyncio.Semaphore(1)`)

- **Pour** : plus simple qu'une vraie file.
- **Contre** : ne donne aucune visibilité d'ordre ni de position à
  l'utilisateur (le besoin explicite de cette demande était de « les
  énumérer clairement sur le SaaS ») ; ne distingue pas un item en attente
  d'un item en cours dans l'API. Une `asyncio.Queue` coûte le même effort
  d'implémentation et couvre ce besoin nativement.

## Conséquences

- **Compatibilité** : sans changement de configuration, le comportement
  bascule automatiquement de « tâches concurrentes non coordonnées » à
  « file séquentielle » — aucune variable d'environnement à ajouter.
- **Limite connue** : la file vit en mémoire du processus `blueseatra-api`.
  Un redémarrage perd l'ordre exact de la file (mais pas les demandes
  elles-mêmes, grâce au filet de sécurité au démarrage, qui les requeue —
  simplement dans un ordre potentiellement différent de l'ordre de création
  originel si plusieurs étaient en attente au moment du redémarrage).
- **Limite connue** : la file est globale au processus, pas partitionnée
  par tenant — un tenant très actif peut retarder les demandes d'un autre
  tenant. Acceptable au stade actuel (un tenant réel : ANELEC Test) ; à
  reconsidérer si le nombre de tenants actifs augmente.
- Le worker RQ durable (`extraction_worker.py`) et son chemin d'activation
  (`_enqueue_extraction`, variable `REDIS_URL`) restent inchangés et
  disponibles pour une future migration si un vrai besoin de scaling
  horizontal apparaît.
