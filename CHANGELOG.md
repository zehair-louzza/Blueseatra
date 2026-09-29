# Changelog

## 2026-09-29 — Toute l'IA passe par l'agent Hermès, OCR local GLM-OCR par défaut

- **GLM-OCR remplace PaddleOCR-VL-1.6** en tête de l'OCR, à la demande de l'utilisateur : PaddleOCR lisait mal par la passerelle Hermès (« Pome » au lieu du texte de l'image d'essai). PaddleOCR sort de la cascade ; une préférence « paddleocr » enregistrée vaut désormais GLM-OCR (migration `20260929020000_settings_ocr_glm.sql`).
- **Devis : schémas et règles de l'agent validé dans Mistral Studio** (les mêmes que les skills Hermès `extraire-demande-travaux` et `decrire-demande-travaux`) :
  - `backend/schemas_ia/` contient les deux schémas JSON ;
  - la sortie est contrainte par schéma : `format` pour Ollama, `response_format` `json_schema` strict pour Hermès et Mistral, avec un nouvel essai automatique sans schéma si la passerelle le refuse ; `BLUESEATRA_IA_SCHEMA_STRICT=0` n'utilise que la consigne ;
  - extraction : métré en 14 familles (`famille_poste`, `postes_verifies`), engins sur ligne propre (`moyens_acces_engins`), `notes` par ligne et `reserves` ;
  - descriptif : `preliminaires` et `controles_fin_travaux` en plus de `description` et `etapes`, désormais imprimés dans le texte du devis (Préliminaires, puis Déroulement, puis Contrôles de fin de travaux) ;
  - correction : un modèle « Mistral (via Hermès) » était routé vers Ollama lors de l'extraction.
- **Plus aucun appel direct du SaaS vers Ollama.** Tous les appels vont à `POST /v1/chat/completions` de l'agent Hermès, qui choisit le fournisseur à chaque requête : `custom:ollama` pour les modèles du VPS, `custom:mistral` pour l'API Mistral. Cela couvre l'OCR, la cascade de structuration, l'extraction, la décomposition, la rédaction, la vision approfondie et Mistral.
  - `BLUESEATRA_IA_VIA_HERMES=0` sert uniquement de retour arrière d'urgence.
  - Sans `HERMES_GATEWAY_URL`, l'erreur est explicite ; il n'y a pas de repli silencieux vers Ollama.
- **Hermès :** la passerelle est le service `hermes-passerelle` du dépôt `ovh-ai-stack` (PR #30, ADR-009), sans aucun outil, avec les fournisseurs `ollama` et `mistral`. Elle est joignable sur `https://hermes.blueseatra.com` avec l'en-tête `X-Api-Key`.
- **OCR toujours local (GLM-OCR par défaut) :**
  - une image n'est jamais envoyée à Mistral ou OpenAI ; seul le texte lu sur le VPS part vers le fournisseur choisi ;
  - le choix « Modèle OCR préféré » est enfin enregistré : la colonne manquait, et le choix revenait à « Automatique » après chaque enregistrement (migration `20260929010000_settings_ocr_preference.sql`).
- **Page Paramètres :** après « Enregistrer », le formulaire se recharge avec les valeurs réellement enregistrées.
- **Mistral :** relances en cas de limite de débit (429) avec délai exponentiel (2, 4, 8, 16 s), en respectant `Retry-After`.

## 2026-09-29 — Mistral interrogeable par l'agent Hermès (ticket #88)

- **Agent Hermès** (`ovh-ai-stack-corrige/hermes/config.yaml`) :
  - nouveau fournisseur nommé `mistral` (`https://api.mistral.ai/v1`, clé `MISTRAL_API_KEY` du `.env` du VPS) ;
  - `direct_model_requests: true`, pour que le modèle demandé par le SaaS soit respecté ;
  - `compose.yaml` transmet `MISTRAL_API_KEY` au conteneur `hermes`.
- **SaaS :**
  - Paramètres → Moteur IA → « Moteur intégré (Hermès) » propose désormais Mistral Medium, Large et Small (via Hermès), en plus des modèles locaux ;
  - chaque appel envoie `provider: custom:mistral` et le modèle choisi ;
  - images prises en charge ;
  - le test de connexion fait un petit appel réel par Hermès.
- **Repli :** sans passerelle Hermès configurée, appel direct à l'API Mistral avec la clé de la plateforme.

## 2026-09-29 — Mistral remplace Cerebras (ticket #88)

- **Nouveau fournisseur « Mistral AI (API) »** pour l'extraction des demandes (texte, PDF et images), la décomposition en fournitures et la rédaction du descriptif de travaux.
  - Modèles proposés : `mistral-medium-latest` (par défaut), `mistral-large-latest` et `mistral-small-latest`.
  - Réponse JSON imposée à chaque appel ; les garde-fous IA retirent toujours tout prix renvoyé.
- **Page Paramètres → Moteur IA :**
  - la clé est enregistrée chiffrée, puis seuls ses 4 derniers caractères restent affichés ;
  - un bouton « Tester la connexion » vérifie la clé sans consommer de jeton ;
  - la clé peut être supprimée ;
  - sans clé propre, la clé de la plateforme `MISTRAL_API_KEY` est utilisée.
- **Variables d'environnement :**
  - `BLUESEATRA_IA_FOURNISSEUR_DEFAUT=mistral` bascule toutes les entreprises sans réglage propre ;
  - `MISTRAL_MODEL` choisit le modèle par défaut ;
  - la coupure d'urgence accepte `BLUESEATRA_IA_REPLI_PROVIDER=mistral`.
- **Sécurité :** le journal `ia_appel` lit le modèle par son nom de paramètre, pour qu'une clé API ne puisse plus jamais y apparaître.
- 4 tests unitaires, sans appel réseau.

## 2026-09-25 — Paiement Stripe en mode test (ticket #90)

- **Catalogue Stripe :** `scripts/stripe/creer_catalogue.py` crée, sans jamais créer de doublon (`lookup_key` stables), les offres Initial, Pilotage et Performance (mensuel et annuel avec 2 mois offerts), le siège supplémentaire et les 3 recharges.
- **Paiement :**
  - `POST /api/abonnement/checkout` : Stripe Checkout, avec TVA intracommunautaire et adresse de facturation ;
  - `POST /api/abonnement/recharge` ;
  - `POST /api/abonnement/portail` : portail client (changement d'offre, moyens de paiement, factures, annulation) ;
  - `GET /api/abonnement/stripe`.
- **Webhook `POST /api/stripe/webhook` :**
  - signature vérifiée (HMAC SHA-256, tolérance de 5 minutes) ;
  - **idempotent**, chaque événement étant enregistré par son identifiant avant d'être appliqué (table `stripe_evenements`) ;
  - traite l'abonnement créé, modifié ou supprimé, la recharge payée (crédit dans le registre) et les factures.
- **Cycle de vie :**
  - `active`/`trialing` → actif ;
  - `past_due` → actif pendant les relances de Stripe ;
  - `unpaid`/`canceled` → lecture seule ;
  - `paused` → suspendu ;
  - **jamais de suppression de données**. Les offres `interne` et Signature ne sont jamais modifiées par Stripe.
- **Sécurité :** clés et événements live refusés tant que `BLUESEATRA_STRIPE_LIVE=1` n'est pas défini.
- **Page Offre et consommation :** choix de l'offre (mensuel ou annuel), recharges, accès au portail, badge « mode test ».
- Migration `20260927090000_facturation_stripe.sql` (additive). 5 tests unitaires.
- **Recette réelle en mode test Stripe :**
  - catalogue créé dans le compte de test (7 produits, 11 prix ; un second passage ne crée rien) ;
  - abonnement Pilotage + 1 siège payé par la carte de test 4242 ;
  - les 4 événements Stripe réels sont appliqués, puis ignorés au rejeu ;
  - le portail client s'ouvre.
- Corrections trouvées pendant la recette :
  - encodage du formulaire envoyé à Stripe ;
  - lot de 10 `lookup_keys` au plus ;
  - `customer_update[name]` requis avec la collecte de n° de TVA ;
  - métadonnées des factures au format Stripe récent.

## 2026-09-25 — Import de catalogue contrôlé avant activation (ticket #86)

- **Assistant en 5 étapes :** fichier, correspondance des colonnes, import, **contrôle**, activation. L'import crée désormais une version **brouillon** : elle n'est activée qu'après lecture du contrôle.
- **Comparaison avec la version active** (`backend/catalogue_comparaison.py`, 6 tests) : articles nouveaux, retirés, en hausse, en baisse et inchangés, avec les plus fortes variations. La comparaison se fait par référence ; les codes générés `ART-n` sont comparés par libellé. Nouvelle route `GET /api/catalogs/{id}/versions/{vid}/comparaison`.
- **Seuils de sécurité :**
  - BLOQUANT : version vide, prix négatif, au moins 25 % de rejets, chute d'au moins 20 % du nombre d'articles ;
  - À VÉRIFIER : au moins 10 % de prix manquants (0 € compris), au moins 10 % d'unités inconnues, au moins 5 % de rejets, hausse moyenne d'au moins 15 %, variations de plus de 30 %.
- **Activation d'une version BLOQUANTE :** refusée (409). Seul un propriétaire ou un administrateur peut la forcer (`?force=true`), et le verdict est inscrit au journal d'audit.

## 2026-09-25 — Garde-fous de l'IA en production (ticket #88, partie sans clé)

- **Schéma strict de sortie** (`backend/ia_garde_fous.py`) :
  - types convertis ;
  - urgence et confiance normalisées ;
  - lignes non structurées écartées ;
  - **tout prix, montant, taux de TVA ou marge produit par l'IA est retiré et signalé** dans `_anomalies_schema`.
- **Coupure d'urgence** `BLUESEATRA_IA_COUPURE` :
  - `arret` : refus explicite ; la demande échoue proprement et le devis assisté est remboursé ;
  - `repli` : bascule vers `BLUESEATRA_IA_REPLI_PROVIDER` / `_MODEL` / `_KEY`.
- **Journal par appel** `ia_appel` : fournisseur, modèle, rôle, succès, durée, taille des échanges et coût estimé, sans le contenu.
- **Corpus de test BTP** (`backend/corpus_ia/`) : 8 demandes fictives annotées, dont une tentative d'injection de prompt et une demande en anglais. Le script `scripts/ia/evaluer_corpus.py` mesure le taux de réussite, avec un seuil de bascule à 80 %. Référence mesurée : 54 % pour l'extraction de secours sans IA.

## 2026-09-25 — Quotas : projection, rapprochement, politique de dépassement (ticket #89)

- **Projection :** chaque jauge renvoie son rythme par jour, la projection en fin de période et la date d'épuisement prévue. La page Offre et consommation affiche l'alerte (4 tests).
- **Rapprochement :** `GET /api/abonnement/rapprochement` compare chaque demande IA au registre. Une demande lue doit avoir consommé 1 devis, une demande échouée doit avoir été remboursée ; tout écart est listé.
- **Politique de dépassement :** écrite dans [`docs/tarification-2026-09.md`](./docs/tarification-2026-09.md) (§8). Refus en 402 avec un message clair, sans surfacturation silencieuse, et le travail manuel reste toujours possible.

## 2026-09-25 — Observabilité, alertes et RGPD (ticket #93)

- **Journaux structurés JSON** (par défaut sur Render, sinon `LOG_FORMAT=json`) :
  - `request_id` renvoyé dans l'en-tête `X-Request-ID` ;
  - entreprise pseudonymisée ;
  - aucun e-mail en clair, y compris dans les traces d'exception ;
  - requêtes en 5xx ou de plus de 3 s journalisées automatiquement.
- **Mesures et SLO :** `GET /api/exploitation/mesures` (volume, 5xx, p50/p95 par route, respect des SLO), protégée par `BLUESEATRA_METRICS_TOKEN`. Elle répond 404 tant que la variable n'est pas définie.
- **Alerte :** nouveau workflow `surveillance.yml`, qui sonde l'API toutes les heures en jours ouvrés. Il ouvre un ticket « Alerte production » en cas de panne et le ferme au retour à la normale.
- **RGPD :**
  - `GET /api/rgpd/export` : zip de toutes les données de l'entreprise, sans secret ;
  - `POST /api/rgpd/personnes/anonymiser` : effacement d'une personne par son e-mail ;
  - `GET /api/rgpd/echeances` : contacts à anonymiser après 3 ans d'archivage ;
  - chaque opération est tracée dans `audit_logs` ;
  - nouvel onglet **Paramètres → Données personnelles**.
- **Isolation :** le contrôle statique couvre maintenant le SQL écrit dans `clients_module.py` et `observabilite.py`, ainsi que les 7 tables Clients. Sept requêtes à conditions dynamiques ont été réécrites pour que le filtre `tenant_id` soit visible, et la mutation du filtre est détectée.
- **Documents :** [`docs/conformite-rgpd.md`](./docs/conformite-rgpd.md) (registre des traitements, droits, sous-traitants) et [`docs/runbook-incident.md`](./docs/runbook-incident.md) (SLO, corrélation, déroulé, RACI, post-mortem, incident simulé).

## 2026-09-25 — Boîte de réception et versions de devis (ticket #85)

- **Demandes :**
  - recherche sans accents ;
  - 7 filtres avec compteurs ;
  - tri par priorité (à relire, urgentes, sans devis, échéance) ;
  - colonnes client, date de réponse et devis liés.
- **Versions de devis :** une remise en brouillon ouvre la version suivante. Nouvelles routes `GET /api/quotes/{id}/versions` et `GET /api/quotes/{id}/versions/compare?de=N`, et bouton « Historique » avec comparaison ligne à ligne (`backend/quote_versions_diff.py`, 5 tests).
- **Correction :** caractère « } » parasite à côté du bouton Dupliquer.
- **CI (ticket #84) :** nouveau job « Tests unitaires de l'API » : 56 tests (IA, rapprochement, file, versions, quotas). 4 tests anciens avaient des attentes obsolètes et ont été corrigés.

## 2026-09-25 — Module Clients (lots 1 à 4)

- **Fiches** : clients (6 types, SIRET unique par entreprise), contacts (contact principal, opposition aux relances, anonymisation RGPD), chantiers, archivage sans suppression. Écrans `/app/clients` et `/app/clients/:id`.
- **Suggestions IA** : après chaque extraction, donneur d'ordre et client final proposés avec la phrase source comme preuve ; rattachement automatique seulement sur SIRET ou e-mail identique (annulable) ; reprise des noms déjà saisis dans les devis.
- **Relances** : planifiées à l'envoi du devis (jours ouvrés et fériés, urgence, rappel d'expiration, appel au-delà du seuil), annulées à l'issue, à la remise en brouillon ou à l'archivage ; écran `/app/relances` avec texte proposé, résultat et report ; réglages par entreprise ; badge dans le menu.
- **Devis** : panneau « Client et suivi » (donneur d'ordre, client final, validité, issue Accepté / Refusé / Sans suite, relances).
- **Pilotage** : indicateurs de la fiche (devis signés, en attente, taux de transformation, délai de réponse), import et export CSV.
- Migration `20260926090000_module_clients.sql` (additive). Tests : 11 règles, 7 SQL, 7 de bout en bout sur l'API réelle.

## 2026-09-23/24 — Catalogue commun, performances, refonte visuelle, tarification

PR #98 à #106 sur `main`.

### Catalogue fournisseurs
- **#98, #99** : import de catalogues volumineux (`scripts/fournisseur/import_catalogue_lourd.py`), avec analyse, rapport d'anomalies, version inactive et activation atomique. Les offres historiques sans catalogue restent visibles, et la commande `nettoyer` est ajoutée.
- **#100** : catalogue commun à toutes les entreprises (tenant système `00000000-0000-4000-8000-000000000c0d`), en lecture seule, masquable par entreprise, jamais supprimé. Correctif RLS de l'import sous `blueseatra_app`.
- **#101** : synonymes de colonnes du catalogue TCE 2026 (prix d'achat, prix public, unité). La migration SET ROLE est rendue tolérante à l'absence du rôle `postgres`, et la permission `pull-requests: read` est ajoutée pour gitleaks.
- **#102** : page Catalogue fournisseurs, avec les routes `GET /api/fournisseurs/catalogue`, `/catalogue/{cle}/produits` et `/catalogue/{cle}/familles`, et deux index de parcours.

### Performances
- **#103** : la liste des fournisseurs passe de 24 s à 24 ms. La sous-requête lit une seule offre avant le nom du fournisseur ; elle provoquait auparavant des `TimeoutError` (erreurs 500).
- **#104** : nouvel index compact `idx_offers_recherche_prix_v2`, créé `CONCURRENTLY`, et lecture en deux temps. « disjoncteur » dans Rexel passe de plus de 60 s à 0,05 s une fois l'index en mémoire. Résultats identiques (comparaison automatique ancien/nouveau code).
- Maintenance : `VACUUM (ANALYZE)` de `supplier_offers` en production.

### Site
- **#105** : refonte visuelle (Geist, palette du logo, accueil, Tarifs avec bascule mensuel/annuel, connexion, menu groupé, icône de marque). `.htaccess` est inclus dans chaque build.

### Exploitation
- **#106** : réveil automatique de l'API Render via pg_cron (`reveil-api-render`, toutes les 13 min), migration idempotente et sans effet hors Supabase.

### Tarification (décision)
- Essai de 14 jours (1 siège, 10 devis assistés, 30 pages lues), puis Initial 59 €, Pilotage 149 € et Performance 399 € HT par mois, Signature sur devis. Devis, PDF et catalogues illimités ; seuls les devis assistés par l'IA et les pages lues sont comptés. Détail et règles multi-entreprises dans `docs/tarification-2026-09.md`.

## 2026-08-26 — Génération automatique du devis + confirmation directe de suggestion

PR #66 (suggestion) et génération automatique de devis.

### Génération automatique du brouillon de devis
- Demande explicite : la création du brouillon de devis ne doit plus attendre un clic manuel sur «Générer un devis», mais **le devis généré doit toujours attendre une confirmation humaine** avant validation/envoi/PDF.
- `process_request()` appelle désormais `_auto_generate_quote_if_needed()` dès qu'une demande atteint le statut `done` ou `needs_review`. Logique de création partagée avec l'endpoint manuel (`_build_quote_drafts`, refactorisé hors de `POST /quotes/draft`).
- Ne génère jamais un deuxième brouillon pour la même demande (retraitement manuel n'empile pas) ; le bouton «Générer un devis» reste disponible pour créer volontairement un devis supplémentaire.
- Toute erreur (catalogue absent, échec IA) est journalisée sans jamais faire échouer la demande elle-même.
- `GET /requests` et `GET /requests/{id}` exposent désormais les devis liés (`quotes: [{id, number, status}]`) ; la page Détail de la demande affiche un badge cliquable par devis généré, sans que l'utilisateur ait besoin de le chercher.
- **Aucune étape de confirmation humaine n'est retirée en aval** : le devis reste `status="draft"` jusqu'à validation explicite (`POST /quotes/{id}/validate`), comme avant.

### Confirmation directe d'une suggestion catalogue ambiguë (PR #66)
- Bouton «Confirmer» ajouté directement sur la ligne à correspondance ambiguë (suite à PR #61) : applique l'article suggéré en place, sans repasser par la recherche manuelle du panneau catalogue.

## 2026-08-25/26 — Gestion des membres, affichage suggestion catalogue, file d'extraction séquentielle

PR #60 à #64 sur `main`.

### Documentation (PR #60)
- README/CHANGELOG mis à jour avec les rôles IA par clé dédiée (voir entrée précédente) et le correctif Gemma frontend.

### Correctif affichage suggestion catalogue (PR #61)
- Bug réel signalé par l'utilisateur : une ligne à correspondance ambiguë (`status="to_confirm"`, score 45-89) ne recevait volontairement aucun prix automatique (comportement voulu de `matching.py` — jamais de prix sur une correspondance incertaine), mais le frontend n'affichait alors **rien du tout**, laissant croire que l'IA n'avait pas cherché dans le catalogue alors que l'article y était bien présent.
- `QuoteEditor.js` affiche désormais l'indice de suggestion (`suggested_item_code` / `suggested_label`, déjà calculé par le backend mais jamais rendu) sur chaque ligne `to_confirm`, avec un texte explicite invitant à confirmer via « Ajouter depuis le catalogue ».

### Gestion des membres (PR #62, #63)
- `DELETE /api/members/{user_id}` : retire un membre du tenant. Refuse de retirer le dernier `owner` ou de se retirer soi-même.
- `PATCH /api/members/{user_id}` étendu : accepte désormais `name` (renommer un membre) et `password` — ce dernier **réservé au rôle owner** (403 pour un admin), pour que le changement de mot de passe d'un membre ne soit possible que depuis le compte owner.
- Page Membres (`Members.js`) : édition inline du nom (crayon), bouton Supprimer avec confirmation, bouton «clé» (changement de mot de passe) visible uniquement pour le rôle owner.

### File d'extraction séquentielle (PR #64)
- Bug de production confirmé le 25/08 : 5 demandes créées à ~2 min d'intervalle sont restées bloquées sur `processing` pendant 80+ minutes ; le VPS était en réalité inactif (0 % CPU) au moment du contrôle — contention CPU entre extractions concurrentes, puis perte des tâches en mémoire lors d'un redéploiement Render.
- Nouvelle file FIFO in-process (`asyncio.Queue` + une tâche de fond persistante) : une seule extraction IA à la fois, dans l'ordre d'arrivée. Nouveau statut `queued` avec position réelle exposée par l'API et affichée clairement dans le SaaS (« En file d'attente (position N) »).
- Filet de sécurité au démarrage (`_requeue_stuck_on_startup`) : toute demande encore `queued`/`processing` au redémarrage du service est remise en file automatiquement — a réparé seul les 5 demandes bloquées en production.
- Détail complet et alternatives écartées : [`docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md`](./docs/decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md).

## 2026-08-25 — Rôles IA isolés (describe) + garde-fous hallucination + correctif Gemma frontend

PR #55 à #59 sur `main`.

### Rôles IA par clé dédiée (`ai_service.py`)
- Nouveau rôle `describe`, strictement confiné aux champs **Description des travaux** et **Étapes à suivre** — ne touche jamais au calcul, aux quantités, aux prix ni à la décomposition matériaux. Modèle : `HERMES_DESCRIPTION_MODEL` (défaut `glm-4.7-flash:Q3_K_M`), `force_think=False` (mesuré ~28-54 s contre >200 s en mode réflexion sur ce rôle).
- `HERMES_REASONING_MODEL` (rôle `reason`) reste `gpt-oss:20b` après un essai réel de `glm-4.7-flash` comme modèle principal Hermes, reverté (préfill trop lent avec le prompt système complet de Hermes, >200 s pour 34 % d'un prompt de 15k tokens).
- Journalisation du rôle + modèle réellement utilisés à chaque appel (`logger.info("ai_role_resolved ...")`, `ai_call_attempt`/`ai_call_success`/`ai_call_failed`) — aucune journalisation de ce type n'existait avant.

### Garde-fous anti-hallucination (rôle `describe`)
- Rejet automatique si le modèle ajoute une étape de dépose/retrait sur une installation explicitement neuve, ou invente une exclusion non fournie — 2 hallucinations réelles trouvées et corrigées (repli sur le gabarit déterministe existant).
- Règles des 12 skills devis (jusque-là jamais lues par le pipeline SaaS — FastAPI appelle Ollama directement, pas la passerelle Hermes) activées dans les prompts système réels (`EXTRACTION_SYSTEM`, `EXPAND_SYSTEM`, `DESCRIPTION_SYSTEM`), avec défense anti-injection de prompt sur le contenu de document non fiable.

### Frontend
- Le panneau « Extraction IA » affichait en dur « lu directement par **Gemma** » sur le chemin de secours vision, alors que `gemma4:26b` a été retiré du VPS le 23/08. Le backend exposait déjà `_ocr_engine` dynamiquement — seul le libellé frontend (`i18n.js`, `req.ocr_fallback_note`) n'avait pas suivi. Corrigé pour interpoler `{{engine}}`.

## 2026-08-15 — OVH + MCP + devis

Tout est sur `main` (PR #1 à #9). Smoke : ce commit.

### IA locale (OVH)
- Hermes / Ollama derrière Caddy (`HERMES_BASE_URL=https://ia.blueseatra.com`, `HERMES_API_KEY`)
- `extract_from_text` / `extract_from_image` / PDF / DOCX
- Modèles UI = ceux du VPS : `hermes-3`, `qwen3.6:27b`, `qwen2.5:14b`
- Mapping `client_name` / `location` → champs écran devis

### Devis
- Rapprochement catalogue (`description` + pluriels → Spot LED encastré)
- Marge % : `HT = qté × PU × (1 + marge/100)`
- Catalogue slim + cache 45 s + `GET /catalog/search`
- pandas chargé seulement à l’import CSV (boot Render plus court)

### MCP Perplexity Computer
- `POST /mcp` (Streamable HTTP)
- `MCP_TENANT_ID` = ANELEC Test `9171d808-f7ee-4d51-92f6-db60d93d8ecc`
- Outils : list_requests, get_request, list_quotes, search_catalog

### Infra
- Pooler Supabase : `prepared_statement_cache_size` et `statement_cache_size` à 0

### Hostinger (manuel)
Rebuild frontend pour voir marge / picker en direct :

```bash
cd frontend && yarn build
```

Uploader le contenu de `frontend/build/` vers `public_html/`.

## Jalons antérieurs

### Juillet 2026 — Migration Hermes AI / Ollama / OVH VPS

**Changements majeurs :**
- ✅ **Suppression totale du provider Emergent** (`emergentintegrations` désinstallé, `EMERGENT_LLM_KEY` supprimée)
- ✅ **Hermes-3 via Ollama** sur VPS OVH devient le moteur IA par défaut (`ai_service.py` réécrit)
- ✅ **litellm mis à jour vers 1.80.0** comme couche d'abstraction pour les fallbacks tenant (OpenAI / Anthropic / Gemini)
- ✅ Variables d'environnement `HERMES_BASE_URL` et `HERMES_DEFAULT_MODEL` ajoutées
- ✅ `requirements.txt` mis à jour (suppression `emergentintegrations`, ajout `litellm==1.80.0`)

### Étapes précédentes

| Étape | Description |
|-------|-------------|
| Migration MongoDB → Supabase | `pg_adapter.py` + `models_sql.py` + `migrate_mongo_to_supabase.py` |
| Activation RLS | `enable_rls.py` — policy deny-all sur toutes les tables |
| Éditeur de devis v2 | Lignes typées, TVA par ligne, marge masquée, sélecteur catalogue |
| Import CSV universel | Auto-détection colonnes + mapping manuel + attributs dynamiques |
| Génération PDF Pro Forma | ReportLab — gabarit métier complet avec profil entreprise |
| Multi-tenant RBAC | Rôles `owner` / `admin` / `operator` / `viewer` / `billing_admin` |
| Internationalisation | react-i18next — FR / EN |
| Webhook n8n | Configurable par tenant dans les paramètres d'intégration |
| Journal d'audit | Table `audit_logs` — toutes les actions sensibles tracées |
| Profil entreprise PDF | SIRET, IBAN, mentions légales, conditions injectés dans le PDF |

