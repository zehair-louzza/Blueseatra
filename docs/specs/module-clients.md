# Spécification : module Clients

| | |
|---|---|
| **Statut** | Implémenté (lots 1 à 4), 25/09/2026 |
| **Version** | 1.0, 24/09/2026 |
| **Langues** | Français et anglais (traductions `i18n.js`, clés `clients.*` et `relances.*`) |
| **Fichiers préparés** | `supabase/migrations/20260926090000_module_clients.sql`, `backend/relances_regles.py`, `backend/tests_clients/` (18 tests) |
| **Origine** | Étude du CRM open source trycompai/crm (licence MIT) : ses idées sont reprises, pas son code, qui ne gère qu'une seule entreprise |

---

## 1. Objectif

Donner à chaque entreprise un suivi simple de ses clients, construit directement dans Blueseatra. L'utilisateur doit savoir :

- **qui** lui demande des devis (donneur d'ordre, client final, contacts) ;
- **où** il intervient (chantiers, sites, magasins) ;
- **ce qui est en cours** : demandes, devis envoyés, acceptés ou refusés ;
- **qui relancer aujourd'hui, et pourquoi.**

Ce n'est pas un outil de prospection : pas de lecture des boîtes mail, pas d'enrichissement LinkedIn, pas de recherche de personnes sur le web.

## 2. Principes non négociables

1. **Isolation.** Chaque table porte `tenant_id`, protégée par RLS (`current_tenant()`) et par un filtre explicite dans le code (mode repli). Aucune entreprise ne voit les clients d'une autre.
2. **Rien n'est supprimé.** Un client, un contact ou un chantier est archivé. Seule exception légale : un contact peut être anonymisé (droit à l'effacement RGPD), sans casser l'historique des devis.
3. **L'IA propose, l'humain valide.** Aucune fiche n'est créée ni modifiée par l'IA seule. Chaque proposition cite la phrase du document qui la justifie. Seule une correspondance exacte (même SIRET, ou même e-mail) rattache automatiquement une demande à un client existant, avec cette preuve affichée.
4. **Aucun prix touché.** Le module ne calcule rien : les montants affichés viennent des devis.
5. **Relances envoyées seules uniquement sur décision de l'entreprise.** Une relance est une tâche avec un texte proposé et modifiable ; l'utilisateur envoie, appelle ou marque « faite ». L'envoi automatique des relances par e-mail à l'échéance est désactivé par défaut et s'active dans les réglages (section 4.7, demande du 10/10/2026).
6. **Journal en ajout seul.** Les échanges ne sont jamais modifiés : une erreur se corrige par une ligne de correction.
7. **Hors quotas.** Le module ne consomme ni devis assistés ni pages lues. Seule l'extraction de la demande, déjà comptée, alimente les suggestions.

## 3. Modèle de données

Toutes les tables sont dans le schéma `blueseatra`. La migration est additive : les tables `requests` et `quotes` reçoivent uniquement des colonnes facultatives.

### 3.1 Tables

| Table | Rôle | Points clés |
|---|---|---|
| `clients` | Donneurs d'ordre et clients finals | Type (entreprise, particulier, syndic, bailleur, collectivité, enseigne), SIRET valide et unique par entreprise, adresse, langue FR/EN, délai de paiement, étiquettes, source (manuel, suggestion IA, import, devis existant), `archive_le` |
| `contacts` | Personnes chez un client | Un seul contact principal par client ; `accepte_relances` (opposition RGPD) ; `anonymise_le` |
| `chantiers` | Sites d'intervention | Code site (n° de magasin, lot, résidence), adresse, consignes d'accès |
| `suggestions_clients` | Propositions de l'IA à valider | Type (nouveau client, contact, chantier, rattachement, mise à jour), rôle (donneur d'ordre ou client final), `preuve` obligatoire, force (exacte, probable, faible), statut |
| `echanges_clients` | Journal des échanges | Appel, e-mail, visite, note, relance, devis envoyé, accepté ou refusé ; ajout seul (déclencheur) |
| `regles_relance` | Réglages par entreprise | Délais en jours ouvrés, délais en cas d'urgence, nombre maximal, validité du devis, seuil d'appel, heure, fuseau |
| `relances` | Tâches de relance | Rang, échéance, canal, raison, brouillon, statut, résultat ; une seule relance active par rang et par devis |

### 3.2 Colonnes ajoutées

| Table | Colonnes | Usage |
|---|---|---|
| `requests` | `client_id`, `client_final_id`, `chantier_id`, `contact_id` | Rattachement d'une demande |
| `quotes` | les mêmes, plus `issue`, `issue_le`, `motif_issue`, `valable_jusqu_au` | Suivi commercial, distinct du statut technique (brouillon, validé, envoyé) |

L'issue commerciale d'un devis vaut `en_attente`, `accepte`, `refuse` ou `sans_suite`. Le statut technique existant reste inchangé.

### 3.3 Correspondance avec l'extraction actuelle

L'extraction produit déjà `donneur_d_ordre`, `donneur_email`, `donneur_address`, `client_name`, `client_final`, `client_email`, `client_phone`, `client_address`, `location` et `di_number`. Elle ne change pas.

| Champ extrait | Devient |
|---|---|
| `donneur_d_ordre`, `donneur_email`, `donneur_address` | Suggestion « client » de rôle donneur d'ordre |
| `client_final` / `client_name` | Suggestion « client » de rôle client final (type enseigne) |
| `client_email`, `client_phone` | Suggestion « contact » |
| `location` | Suggestion « chantier » |

### 3.4 Droits

| Action | owner | admin | operator | viewer | billing_admin |
|---|:-:|:-:|:-:|:-:|:-:|
| Voir clients, contacts, chantiers, relances | oui | oui | oui | oui | non |
| Créer ou modifier | oui | oui | oui | non | non |
| Valider une suggestion | oui | oui | oui | non | non |
| Archiver | oui | oui | non | non | non |
| Anonymiser un contact | oui | oui | non | non | non |
| Régler les relances | oui | oui | non | non | non |
| Exporter (CSV) | oui | oui | non | non | non |

## 4. Écrans

Tous les écrans sont en français et en anglais, avec le thème actuel (Geist, marine et turquoise). Le menu reçoit un groupe **Clients** placé entre « Ventes » et « Achats et prix » : Clients, À relancer.

### 4.1 Liste des clients (`/app/clients`)

![Liste des clients](../assets/manuel/07-clients.jpg)

```text
┌ Clients ─────────────────────────────────────────────── [+ Nouveau client] [Importer] ┐
│ [Rechercher nom, ville, SIRET…]  Type ▾  Étiquette ▾  [ ] Devis en attente  [ ] Archivés │
├──────────────────────┬────────────┬──────────┬───────────────┬──────────────┬───────────┤
│ Client               │ Type       │ Ville    │ Devis en cours│ Dernier éch. │ Relance   │
├──────────────────────┼────────────┼──────────┼───────────────┼──────────────┼───────────┤
│ Foncia Versailles    │ Syndic     │ Versailles│ 3 · 12 480 € │ il y a 2 j   │ Aujourd'hui│
│ Picard Surgelés      │ Enseigne   │ —        │ 1 ·  2 150 €  │ 18/09        │ 29/09     │
└──────────────────────┴────────────┴──────────┴───────────────┴──────────────┴───────────┘
                                                                   Page 1 · 50 par page
```

- Recherche sans accents sur nom, nom commercial, ville et SIRET (`recherche_norm`), paginée côté serveur.
- **État vide :** « Aucun client pour l'instant. Ils apparaîtront ici dès votre prochaine demande, ou créez-en un. »
- **Import CSV :** mêmes principes que les catalogues (aperçu, correspondance des colonnes, validation). Les doublons de SIRET sont signalés, jamais écrasés.

### 4.2 Fiche client (`/app/clients/:id`)

![Fiche client](../assets/manuel/08-fiche-client.jpg)

```text
┌ ← Clients   Foncia Versailles   [Syndic]                    [Modifier] [Archiver] ┐
│ SIRET 123 456 789 00011 · 12 rue … 78000 Versailles · 01 23 45 67 89 · FR          │
├ Vue d'ensemble │ Contacts (3) │ Chantiers (5) │ Demandes et devis (14) │ Échanges │ Relances ┤
│ ┌ Devis signés ┐ ┌ En attente ┐ ┌ Taux de transformation ┐ ┌ Délai de réponse ┐       │
│ │ 48 200 € HT  │ │ 3 · 12 480 €│ │ 62 % (8 sur 13)        │ │ 6 jours en moyenne│       │
│ └──────────────┘ └────────────┘ └────────────────────────┘ └──────────────────┘       │
│ Prochaine relance : D-2026-041, aujourd'hui 9 h, e-mail — « envoyé le 24/09, relance 1 sur 3 » │
│ Derniers échanges : 22/09 Appel · RDV fixé le 30/09 (J. Morel)                        │
└────────────────────────────────────────────────────────────────────────────────────┘
```

- **Vue d'ensemble :** les indicateurs se calculent à partir des devis (issue et total HT), sans nouveau calcul de prix.
- **Contacts :** principal en tête, « refuse les relances » visible ; action Anonymiser (owner/admin) avec confirmation.
- **Chantiers :** code site, adresse, consignes d'accès ; bouton « Nouvelle demande pour ce chantier ».
- **Demandes et devis :** liste unique, avec statut technique et issue commerciale.
- **Échanges :** journal chronologique et « Ajouter une note / un appel ». Une correction apparaît comme telle, jamais en écrasant.
- **Relances :** prévues, faites et annulées, chacune avec sa raison.

### 4.3 À relancer (`/app/relances`)

![À relancer](../assets/manuel/09-relances.jpg)

```text
┌ À relancer ───────────────────────────────── En retard (2) · Aujourd'hui (4) · Cette semaine (9) ┐
│ ● EN RETARD                                                                                       │
│ D-2026-032 · Nexity Le Chesnay · 8 900 € HT · appel                                               │
│   « Devis envoyé le 10/09/2026, sans réponse : relance 2 sur 3. »                                  │
│   [Appeler 01 23…] [Marquer faite ▾] [Reporter ▾] [Annuler]                                       │
│ ● AUJOURD'HUI                                                                                     │
│ D-2026-041 · Foncia Versailles · 2 400 € HT · e-mail à M. Martin                                   │
│   « Devis envoyé le 24/09/2026, sans réponse : relance 1 sur 3. »                                  │
│   ┌ Brouillon ─────────────────────────────────────────────────┐                                 │
│   │ Bonjour, je me permets de revenir vers vous au sujet…       │ [Envoyer] [Modifier] [Copier]  │
│   └─────────────────────────────────────────────────────────────┘                                 │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Marquer faite** demande un résultat : sans réponse, à rappeler, en réflexion, accepté, refusé.
  - « Accepté » ou « refusé » met à jour l'issue du devis et annule les relances restantes.
  - « À rappeler » crée une tâche le jour ouvré suivant.
- **Reporter :** demain, dans 3 jours ouvrés ou date choisie.
- **Envoyer maintenant** envoie l'e-mail depuis la boîte de l'entreprise, après confirmation, avec l'objet et le texte relus (section 4.7). Sans messagerie d'envoi configurée, **Ouvrir l'e-mail** ouvre le logiciel de messagerie de l'utilisateur (`mailto:`).
- Un badge dans le menu affiche le nombre de relances en retard ou du jour.

### 4.4 Suggestions à valider

Elles s'affichent dans le détail d'une demande, et par un badge sur la liste des clients.

```text
┌ Suggestions pour cette demande ───────────────────────────────────────────────┐
│ Nouveau client détecté · donneur d'ordre · probable                            │
│   Foncia Versailles — gestion@foncia-versailles.fr                            │
│   Preuve : « Devis à adresser exclusivement à FONCIA VERSAILLES »             │
│   [Créer le client] [Rattacher à un client existant ▾] [Ignorer]               │
│ Rattachement exact · client final                                              │
│   Picard Surgelés (même e-mail que la fiche existante) — rattaché ✓ [Annuler] │
└───────────────────────────────────────────────────────────────────────────────┘
```

| Force | Condition | Effet |
|---|---|---|
| **Exacte** | SIRET identique, ou e-mail identique à une fiche active | Rattachement automatique, affiché et annulable |
| **Probable** | Nom normalisé identique ou très proche (score ≥ 90), ou même domaine d'e-mail | Proposée, validation requise |
| **Faible** | Nom seul, ou proche (score entre 75 et 89) | Proposée en second, jamais présélectionnée |

Une suggestion ne remplace jamais une valeur déjà saisie par un humain : elle propose une « mise à jour », que l'utilisateur accepte ou rejette.

### 4.5 Éditeur de devis

- Le champ texte « Client » devient un sélecteur avec recherche. Il reste possible de taper un nom libre, qui génère une suggestion.
- Des champs sont ajoutés : client final, chantier, contact destinataire, date de validité (30 jours par défaut, réglable).
- Sur un devis envoyé, trois boutons d'issue : **Accepté**, **Refusé** (motif), **Sans suite**.

### 4.6 Réglages des relances (bouton « Réglages des relances » de l'écran À relancer, owner/admin)

Relances activées ; délais en jours ouvrés (3, 7, 14) ; délais en cas d'urgence (1, 2, 4) ; nombre maximal (3) ; validité des devis (30 jours) ; rappel avant expiration (3 jours ouvrés) ; seuil d'appel (10 000 € HT) ; heure (9 h) ; fuseau. Un aperçu montre le calendrier calculé pour un devis envoyé aujourd'hui.

### 4.7 Envoi des relances par e-mail

Ajouté le 10/10/2026. Code : `backend/envoi_relances.py` (SMTP, sans base) et `backend/relances_email.py` (API et tâche de fond). Migration : `20261010020000_relances_envoi_email.sql`.

**Messagerie d'envoi.** Chaque entreprise renseigne sa propre boîte dans **À relancer → Réglages des relances → Messagerie d'envoi (SMTP)**. Réservé au propriétaire et aux administrateurs.

- **Champs :** serveur, port, identifiant, mot de passe, adresse d'expédition, nom affiché, signature, copie cachée.
- **Ports :** 465 (SSL) ou 587 (STARTTLS) uniquement, certificat vérifié. Render bloque le port 25.
- **Serveur :** nom d'hôte public uniquement. Une adresse privée, locale ou réservée est refusée.
- **Mot de passe :** chiffré (Fernet, `APP_ENCRYPTION_KEY`), jamais renvoyé au site. Champ vide = inchangé.
- **E-mail de test :** envoyé à l'adresse d'expédition. Il est obligatoire avant l'envoi automatique. Changer le serveur, le port, l'identifiant, l'adresse ou le mot de passe annule la vérification.
- **Préréglages :** Zoho Mail (Europe), OVHcloud, Hostinger, Gmail et Microsoft 365. Gmail et Microsoft 365 demandent un mot de passe d'application.

**Envoi par clic.**

1. L'utilisateur relit l'objet et le texte de la relance et peut les modifier. **Enregistrer le texte** garde la version modifiée.
2. **Envoyer maintenant** demande une confirmation qui affiche l'adresse du destinataire.
3. Le serveur envoie l'e-mail et marque la relance « faite ». L'envoi est noté au journal des échanges du client et au journal d'audit.

**Envoi automatique** (case **Envoyer automatiquement les relances par e-mail à leur échéance**, désactivée par défaut).

- **Balayage :** toutes les 5 minutes. Il envoie les relances par e-mail arrivées à échéance.
- **Relances concernées :** seulement celles dont l'échéance tombe après l'activation. Un retard plus ancien reste à envoyer à la main.
- **Texte :** modifiable jusqu'à l'envoi. La carte indique « Envoi automatique le … ».
- **Limites :** 20 e-mails par entreprise et par balayage, et 3 tentatives par relance, espacées d'au moins une heure.
- **Panne de la boîte :** si le mot de passe est refusé ou si le serveur est injoignable, le balayage s'arrête pour cette entreprise et l'erreur s'affiche dans la messagerie d'envoi.
- **Effets de la messagerie :** désactiver la messagerie désactive aussi l'envoi automatique.

**Règles communes.**

| # | Règle |
|---|---|
| E1 | **Jamais deux fois :** la relance est réservée par une mise à jour conditionnelle avant l'envoi. Un second clic ou un second balayage reçoit « déjà envoyée ». |
| E2 | **Opposition RGPD :** un contact opposé aux relances ne reçoit jamais d'e-mail, même si l'opposition arrive après la planification. |
| E3 | **Contenu :** texte brut, sans pièce jointe ni lien de suivi. La signature est ajoutée sous le texte. Les réponses vont à l'adresse d'expédition (Reply-To). |
| E4 | **Échec visible :** le message d'erreur s'affiche sur la carte. Il ne contient aucun secret. La relance reste « prévue » et peut être renvoyée. |
| E5 | **Coupure d'urgence :** `BLUESEATRA_ENVOI_AUTO=0` sur Render arrête la tâche de fond. L'envoi par clic reste possible. |

## 5. Règles de relance

![Cycle de vie d'un devis et relances](../assets/schema-cycle-devis.png)

Elles sont implémentées et testées dans `backend/relances_regles.py` (11 tests).

| # | Règle |
|---|---|
| R1 | **Déclencheur :** passage d'un devis au statut « envoyé ». Aucune relance sur un brouillon ou un devis validé mais non envoyé. |
| R2 | **Échéances en jours ouvrés**, hors samedi, dimanche et les 11 jours fériés nationaux (Pâques calculée), à l'heure de l'entreprise : J+3 après l'envoi, puis +7, puis +14. |
| R3 | **Urgence :** si la demande est marquée urgente, J+1, puis +2, puis +4. |
| R4 | **Expiration :** si le devis a une date de validité, un rappel « valable jusqu'au … » est prévu 3 jours ouvrés avant. Les relances ordinaires tombant à partir de ce rappel ne sont pas prévues. |
| R5 | **Canal :** appel si le total HT dépasse le seuil (10 000 € par défaut) ou si le contact n'a pas d'e-mail ; sinon e-mail. |
| R6 | **Opposition RGPD :** si le contact refuse les relances, seule une tâche interne est créée, sans brouillon d'e-mail. |
| R7 | **Arrêt :** accepté, refusé, sans suite, remis en brouillon, client archivé ou relances désactivées. Les relances prévues passent à « annulée » avec leur motif ; elles ne sont jamais supprimées. |
| R8 | **Après une relance faite :** « à rappeler » crée une tâche le jour ouvré suivant ; « sans réponse » et « en réflexion » laissent courir le calendrier ; « accepté » ou « refusé » applique R7. |
| R9 | **Une seule relance active par rang et par devis** (index unique). Replanifier ne recrée jamais une relance passée. |
| R10 | **Raison lisible** sur chaque relance, affichée telle quelle, par exemple : « Devis D-2026-041 envoyé le 24/09/2026, sans réponse : relance 1 sur 3. » |
| R11 | **Brouillon en français ou en anglais**, selon la langue du contact ou du client. Il cite le numéro et la date du devis, jamais un montant recalculé. |
| R12 | **Regroupement :** plusieurs relances du même contact le même jour s'affichent en une seule carte, avec la liste des devis. |

**Exemple vérifié par les tests.** Un devis envoyé le jeudi 24/09/2026, à 2 400 € HT, avec un contact joignable par e-mail, donne :
- 1re relance le mardi 29/09 à 9 h ;
- 2e le jeudi 08/10 ;
- 3e le mercredi 28/10.

Avec une validité au 15/10 :
- 1re relance le 29/09 ;
- 2e le 08/10 ;
- rappel d'expiration le lundi 12/10 ;
- aucune 3e relance.

## 6. API

Toutes les routes sont sous `/api`, avec le tenant du jeton ; les listes sont paginées.

| Méthode | Route | Rôle |
|---|---|---|
| GET / POST | `/clients` | Liste (recherche, filtres, page) / création |
| GET / PATCH | `/clients/{id}` | Fiche / modification |
| POST | `/clients/{id}/archiver`, `/clients/{id}/restaurer` | Archivage réversible |
| GET | `/clients/{id}/resume` | Indicateurs de la vue d'ensemble |
| GET / POST | `/clients/{id}/contacts` | Contacts |
| PATCH | `/contacts/{id}` ; POST `/contacts/{id}/anonymiser` | Modification ; effacement RGPD |
| GET / POST | `/clients/{id}/chantiers` ; PATCH `/chantiers/{id}` | Chantiers |
| GET / POST | `/clients/{id}/echanges` | Journal, en ajout seul |
| GET | `/suggestions-clients?demande_id=` | Suggestions ouvertes |
| POST | `/suggestions-clients/{id}/accepter`, `/rejeter` | Validation (avec cible pour un rattachement) |
| GET | `/relances?periode=retard\|aujourdhui\|semaine` | Écran À relancer |
| POST | `/relances/{id}/faite`, `/reporter`, `/annuler` | Actions (résultat, nouvelle date, motif) |
| PATCH | `/relances/{id}/texte` | Objet et texte d'une relance par e-mail, tant qu'elle n'est pas partie |
| POST | `/relances/{id}/envoyer` | Envoi immédiat depuis la messagerie d'envoi (409 si déjà envoyée) |
| GET, PUT | `/messagerie` | Messagerie d'envoi (owner/admin) ; le mot de passe n'est jamais renvoyé |
| POST | `/messagerie/test` | E-mail de test à l'adresse d'expédition (owner/admin) |
| POST | `/quotes/{id}/issue` | Accepté / refusé / sans suite |
| GET / PUT | `/regles-relance` | Réglages (owner/admin) |
| POST | `/clients/import/preview`, `/clients/import` ; GET `/clients/export` | Import et export CSV |

**Branchements dans l'existant :**
- `process_request` : après l'extraction, créer les suggestions, sans bloquer ni modifier la demande en cas d'erreur.
- `send_quote` : planifier les relances.
- `reopen_quote` et l'issue d'un devis : annuler les relances.
- Archivage d'un client : annuler ses relances.

## 7. Données existantes

Aucune fiche n'est créée automatiquement lors de la mise en place. Une commande de reprise, lancée à la demande par entreprise, lit les noms `quotes.client` / `quotes.client_final` et les extractions des demandes. Elle crée des suggestions « nouveau client » (source « devis existant ») regroupées par nom normalisé. L'entreprise les valide en lot depuis la liste des clients.

## 8. Sécurité et RGPD

- RLS et filtre `tenant_id` explicite. Les tests d’isolation statiques seront étendus aux 7 nouvelles tables (lot 1).
- Aucune suppression depuis le site. L'anonymisation remplace prénom, nom, e-mail et téléphones par des valeurs neutres et note la date. L'historique des devis est conservé, conformément à l'obligation comptable.
- L'opposition aux relances est respectée (R6) et visible sur la fiche.
- Aucune donnée n'est recherchée hors de Blueseatra : pas de LinkedIn, pas de web, pas de lecture de boîte mail.
- Chaque création, archivage, anonymisation, validation de suggestion et changement de règles est inscrit au journal d'audit.

## 9. Découpage en lots

| Lot | Contenu | Prérequis |
|---|---|---|
| **1. Fiches** | Migration ; API clients, contacts et chantiers ; écrans liste et fiche ; sélecteur dans l'éditeur de devis ; archivage ; FR/EN | Accord pour appliquer la migration |
| **2. Suggestions IA** | Suggestions depuis l'extraction ; rattachement exact ; panneau de validation ; reprise des devis existants | Lot 1 |
| **3. Relances** | Planification à l'envoi ; écran À relancer ; résultats ; réglages ; badge du menu | Lot 1 |
| **4. Pilotage** | Indicateurs de la fiche ; import et export CSV ; tableau de bord « taux de transformation » | Lots 1 à 3 |

Chaque lot fait l'objet d'une PR distincte, avec ses tests et des captures, puis d'une fusion après accord : toute fusion côté serveur redéploie l'API.

## 10. Critères d'acceptation

- [ ] Aucune entreprise ne voit ni ne modifie les clients, contacts, chantiers, échanges ou relances d'une autre (tests SQL et API).
- [ ] Aucune route ne supprime un client, un contact, un chantier ou un échange ; l'archivage est réversible.
- [ ] Une suggestion affiche toujours sa preuve ; rien n'est créé sans validation, sauf un rattachement exact annulable.
- [ ] Les échéances respectent les jours ouvrés et fériés français (tests).
- [ ] Un devis accepté, refusé ou remis en brouillon n'a plus aucune relance prévue.
- [ ] Un contact opposé aux relances ne reçoit jamais de brouillon d'e-mail.
- [ ] Toutes les chaînes existent en français et en anglais.
- [ ] Les listes de plus de 10 000 clients répondent en moins de 300 ms (index par tenant, pagination).

## 11. Hors périmètre de la v1

Synchronisation de la boîte mail ou de l'agenda (lecture des réponses), enrichissement externe, facturation et relances d'impayés (module Facturation), application mobile.
