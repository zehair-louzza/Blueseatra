# Masquage RGPD, fournisseurs IA externes et chaîne G3

Dernière mise à jour : 10 octobre 2026.

## Principe

Depuis le 9 octobre 2026, à la demande de l'exploitant, **tous les appels IA sont masqués**. Cela vaut pour les modèles du VPS (`custom:ollama`) comme pour les fournisseurs externes : Mistral (`custom:mistral`), OpenCode Free (`opencode-free`) et OpenAI (chemin hérité).

- **Avant l'envoi** : les informations personnelles sont remplacées par des marqueurs (`[adresse_1]`, `[personne_2]`…).
- **Après la réponse** : les vraies valeurs sont remises dans la réponse du modèle, sur le serveur Blueseatra. La table de correspondance ne quitte jamais le serveur.
- **Images** :
  - aucune image n'est envoyée à un fournisseur externe ;
  - les images restent lues par les modèles OCR du VPS, car une image ne peut pas être masquée ;
  - le texte qui en est tiré est masqué avant l'étape suivante.
- **Contrôle avant envoi** : si un détecteur trouve encore une information après le masquage, l'appel est refusé (`FuitePossible`).

Code : `backend/masquage_rgpd.py`. Branchement dans `ai_service` :
- `_hermes_chat`, point d'entrée de tous les appels en production ;
- le décorateur `avec_masquage`, qui couvre les chemins directs de retour arrière (Ollama direct, cascade, passerelle, Mistral direct, OpenAI) ;
- une variable de contexte qui empêche de masquer deux fois le même appel.

## Ce qui est masqué

| Information | Méthode | Exemple |
|---|---|---|
| Adresses | Numéro et type de voie ; voie suivie d'un nom propre ; code postal et ville ; ZA, ZI, centre commercial, « Shopping Centre » ; BP | « 24 avenue de la République, 75011 Paris » → `[adresse_1], [adresse_2]` |
| Noms de sites et de clients connus | Comparaison sans casse ni accents avec les clients, contacts, chantiers, société et utilisateurs du tenant, et avec les valeurs lues dans les champs « Client : », « Site : »… | « INTIMISSIMI Forum des Halles » → `[site_1]` |
| Donneurs d'ordre et raisons sociales | Noms en majuscules de l'en-tête des bons de commande et des blocs de coordonnées, puis masqués partout ailleurs dans le texte | « PRESTA MAINTENANCE » → `[nom_1]` |
| Personnes | Signature après « Cordialement », champs « Interlocuteur : » et « Contact : », civilités, « représenté par », prénoms INSEE suivis du nom | « Cordialement, Emaléa » → `[personne_1]` |
| Identifiants | E-mail, site web, téléphone, SIRET et SIREN, IBAN, BIC, TVA, numéros de dossier ou de commande | `[email_1]`, `[tel_1]`, `[siret_1]` |

Prénoms : [fichier des prénoms INSEE 2025](https://www.insee.fr/fr/statistiques/8595130), Licence Ouverte 2.0. Sont retenus les prénoms donnés au moins 1 000 fois depuis 1900, sans les homonymes de mots courants (pierre, rose, blanche…).

## Mesure sur les données réelles (lecture seule, 9 octobre 2026)

- **Corpus** : 26 demandes distinctes (37 en base), 4 tenants, avec les noms connus réels de chaque tenant.
- **Contrôle avant envoi** : 0 demande bloquée après masquage.
- **Relecture humaine** : les 725 lignes uniques du texte masqué ont été relues.
- **Fuites corrigées** : chaque fuite repérée à la relecture est reproduite dans un test fictif (`tests/test_masquage_rgpd.py`). Elles concernaient :
  - les téléphones à points en fin de phrase et les numéros tronqués ;
  - les voies abrégées ou sans numéro et les centres commerciaux ;
  - le prénom après « Cordialement, » au milieu d'une ligne, et le prénom seul avant « Devis GRATUIT à adresser » ;
  - le nom du représentant et la raison sociale d'un en-tête ;
  - le sigle « LED » pris à tort pour un nom.
- **Laissé en clair volontairement** : les noms de ville seuls (ville du tribunal compétent, « PARIS : » devant une liste de vitrines) et les sigles techniques (LED, PVC, EPI, PMR…).

## Limites, à lire avant d'activer un fournisseur externe

- **Ce qui reste indétectable** : un nom de famille inconnu de Blueseatra, absent de la liste des prénoms et écrit seul au milieu d'une phrase. Seul un modèle hébergé sur le VPS garantit l'absence totale de transfert.
- **OpenCode Free** : tous les modèles sont hébergés aux États-Unis. Plusieurs modèles gratuits peuvent réutiliser les données (Big Pickle, MiMo, Ling, Muse Spark). Les modèles Nemotron interdisent les données personnelles ou confidentielles ([conditions OpenCode Zen](https://opencode.ai/docs/zen/)).
  - À réserver aux essais. Pour un usage en production, préférer Mistral (UE), avec un DPA et l'option de conservation nulle.
- **Coupure d'urgence** : `BLUESEATRA_MASQUAGE_RGPD=0` sur Render désactive le masquage. Ne l'utiliser que si tous les fournisseurs choisis sont locaux.

## OpenCode Free dans les réglages

Le fournisseur se choisit dans Réglages, Intégrations, Fournisseur IA : « OpenCode Free (via Hermès, États-Unis, texte masqué) ».

- **Modèles proposés** : les 13 modèles gratuits de `https://opencode.ai/zen/v1/models`, relevés le 9 octobre 2026.
- **Clé** : aucune clé n'est demandée dans le SaaS.
- **Routage interne** : `opencode:<modèle>`, envoyé à la passerelle avec `provider: opencode-free` (variable `HERMES_OPENCODE_PROVIDER`).

Prérequis sur le VPS : le SaaS appelle la passerelle (`hermes-passerelle`), pas l'agent du tableau de bord. L'[extension oc-free-provider](https://hermes-agent.nousresearch.com/docs/plugins/oc-free-provider) doit donc être installée et activée dans la passerelle elle-même.

1. Installation, une seule fois. Les fichiers vont dans le volume `hermes_passerelle_data`, qui survit aux redémarrages et aux recréations :

   ```bash
   cd ~/ovh-ai-stack
   docker compose exec hermes-passerelle hermes plugins install oc-free-provider
   ```

2. Activation : elle se déclare dans le dépôt `ovh-ai-stack`, avec `plugins.enabled: [oc-free-provider]` dans `hermes/passerelle/config.yaml` (PR ovh-ai-stack #44). L'option `--enable` de la commande échoue en effet sur `Read-only file system`, car la configuration de la passerelle est montée en lecture seule pour protéger la production. La fusion de la PR déclenche le déploiement automatique, qui recrée la passerelle.

3. Contrôle : dans Réglages, choisir OpenCode Free, enregistrer, puis cliquer sur « Tester la connexion ».

## Chaîne G3

Code : `backend/recherche_g3.py`. Point d'accès : `POST /api/requests/{id}/suggestions-g3`. Il est désactivé tant que `BLUESEATRA_G3=1` n'est pas défini sur Render.

Étapes de la chaîne :

1. **Minimisation** : seule la description des travaux est gardée ; l'en-tête, les coordonnées et la signature sont retirés.
2. **Extraction** : le fournisseur IA de l'entreprise liste les fournitures. Le texte est masqué si le fournisseur est externe.
3. **Candidats** : 20 candidats par fourniture, issus de la recherche par mots (IDF, début de mot, synonymes BTP) et de BM25 sur le catalogue actif.
4. **Choix** : le modèle choisit au plus 3 codes parmi ces candidats ; tout code inventé est ignoré. Si l'appel échoue ou si le modèle ne choisit rien, une suggestion de repli est proposée.
5. **Validation** : le résultat est toujours « à valider » ; rien n'entre dans un devis sans validation du chiffreur.

| Mesure, 17 demandes réelles, 40 besoins | Besoins retrouvés | Précision |
|---|---:|---:|
| Recherche par mots seule (F) | 25 | 0,232 |
| Extraction par LLM, puis F | 30 | 0,40 |
| G3, modèle externe (rejeu des réponses enregistrées) | 33 | 0,535 |
| G3 sans le repli | 29 | 0,549 |
| Plafond : bon article parmi les 20 candidats | 37 | — |
| G3 avec gpt-oss:20b sur le VPS | 21 | 0,26 |

## État au 10 octobre 2026

| Élément | État |
|---|---|
| Masquage de tous les appels IA | En production depuis le 9 octobre 2026 à 22 h 03 : PR #194, commit `85eecd6`, déploiement Render en ligne, `/api/health` répond 200 |
| OpenCode Free dans les réglages | En production ; l'extension est installée dans la passerelle, son activation attend la fusion de la PR ovh-ai-stack #44 |
| Chaîne G3 | Code en production, désactivé (`BLUESEATRA_G3` absent) ; aucun bouton dans l'interface pour l'instant |
| Recherche par mots du module Fournisseur | En production : Fournisseur-Blueseatra PR #4, commit `78e7e8b` |

## Clé Mistral : où elle se trouve et comment la vérifier

Blueseatra n'envoie aucune clé Mistral : c'est la passerelle Hermès qui la lit, dans le fichier `.env` du VPS (`MISTRAL_API_KEY`). La procédure complète se trouve dans le guide d'exploitation Hermès du dépôt `ovh-ai-stack` (`docs/EXPLOITATION-HERMES.md`).

| Réponse de l'API Mistral à `GET /v1/models` | Signification |
|---|---|
| `200` | La clé est valide |
| `401 Invalid API Key` | La clé est incorrecte, révoquée ou d'un autre service ; en créer une nouvelle sur console.mistral.ai |
| `402` | La clé est bonne, mais le compte n'a pas de moyen de paiement |
