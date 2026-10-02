<div align="center">

<img src="docs/assets/banniere.jpg" alt="Blueseatra : des demandes brutes aux devis validés, sur vos prix" width="100%">

<br>

**Le logiciel de devis assisté par IA pour les entreprises TCE, de maintenance et de second œuvre.**

<br>

[![CI infra](https://github.com/zehair-louzza/Blueseatra/actions/workflows/ci-infra.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/ci-infra.yml)
[![Sécurité](https://github.com/zehair-louzza/Blueseatra/actions/workflows/securite.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/securite.yml)
[![Tests métier](https://github.com/zehair-louzza/Blueseatra/actions/workflows/tests-metier.yml/badge.svg)](https://github.com/zehair-louzza/Blueseatra/actions/workflows/tests-metier.yml)
[![Production](https://img.shields.io/badge/production-en%20ligne-1A7F37?labelColor=2D333B)](https://blueseatra.com)
[![Version](https://img.shields.io/badge/version-2026.10.01-0969DA?labelColor=2D333B&logo=semver&logoColor=white)](./CHANGELOG.md)
[![Licence](https://img.shields.io/badge/licence-propri%C3%A9taire-8250DF?labelColor=2D333B)](./LICENSE)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?labelColor=2D333B&logo=python&logoColor=FFD43B)
![FastAPI](https://img.shields.io/badge/FastAPI-API-00796B?labelColor=2D333B&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-087EA4?labelColor=2D333B&logo=react&logoColor=61DAFB)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-0369A1?labelColor=2D333B&logo=tailwindcss&logoColor=38BDF8)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?labelColor=2D333B&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-RLS-18794E?labelColor=2D333B&logo=supabase&logoColor=3ECF8E)
![Render](https://img.shields.io/badge/API-Render-6D28D9?labelColor=2D333B&logo=render&logoColor=white)
![Vercel](https://img.shields.io/badge/Site-Vercel-000000?labelColor=2D333B&logo=vercel&logoColor=white)
![Ollama](https://img.shields.io/badge/IA-Ollama%20%C2%B7%20OVH-000E9C?labelColor=2D333B&logo=ollama&logoColor=white)

![Routes API](https://img.shields.io/badge/routes%20API-114-0969DA?labelColor=2D333B&logo=openapiinitiative&logoColor=white)
![Migrations](https://img.shields.io/badge/migrations-22-8250DF?labelColor=2D333B&logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests%20automatis%C3%A9s-300%2B-1A7F37?labelColor=2D333B&logo=pytest&logoColor=white)
![Isolation](https://img.shields.io/badge/isolation-RLS%20par%20entreprise-BC4C00?labelColor=2D333B&logo=supabase&logoColor=white)
![RGPD](https://img.shields.io/badge/RGPD-anonymisation%20%C2%B7%20opposition-BF3989?labelColor=2D333B)
![Langues](https://img.shields.io/badge/langues-FR%20%C2%B7%20EN-0E7490?labelColor=2D333B&logo=googletranslate&logoColor=white)

[**Site**](https://blueseatra.com) ·
[**Manuel d'utilisation**](./docs/manuel-utilisateur.md) ·
[**Documentation**](./docs/README.md) ·
[**Architecture**](./docs/architecture.md) ·
[**API**](./docs/reference-api.md) ·
[**Changements**](./CHANGELOG.md) ·
[**English**](./README.en.md)

</div>

---

## Pourquoi Blueseatra

Un chiffreur passe des heures à recopier des ordres de mission, retrouver des prix et relancer des clients. Blueseatra automatise la lecture et la mise en forme, sans jamais laisser l'IA décider d'un prix.

<table>
<tr>
<td width="33%" valign="top">

### Lire
Un e-mail, un PDF, une photo de chantier : l'IA repère le donneur d'ordre, le client final, le site, l'urgence et les travaux, puis les range en **lots TCE**.

</td>
<td width="33%" valign="top">

### Chiffrer
Les lignes sont rapprochées de **votre catalogue** et d'environ **967 000 références** de 9 distributeurs. Marges, remises et TVA bâtiment sont calculées par des règles fixes.

</td>
<td width="33%" valign="top">

### Suivre
Le devis validé part en PDF Pro Forma, puis les **relances en jours ouvrés** et l'issue commerciale sont suivies client par client.

</td>
</tr>
</table>

## Aperçu

<table>
<tr>
<td width="50%"><img src="docs/assets/manuel/03-demande-detail.jpg" alt="Lecture d'une demande par l'IA"><br><sub><b>Demande lue par l'IA</b> : données extraites, texte source et clients détectés avec leur preuve</sub></td>
<td width="50%"><img src="docs/assets/manuel/05-editeur-devis.jpg" alt="Éditeur de devis"><br><sub><b>Éditeur de devis</b> : lots numérotés, main-d'œuvre, déplacement, source tarifaire figée</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/manuel/08-fiche-client.jpg" alt="Fiche client"><br><sub><b>Fiche client</b> : contacts, chantiers, historique, taux de transformation</sub></td>
<td width="50%"><img src="docs/assets/manuel/09-relances.jpg" alt="À relancer"><br><sub><b>À relancer</b> : relances du jour, texte proposé, résultat en un clic</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/screens/catalogue-fournisseurs.jpg" alt="Catalogue fournisseurs"><br><sub><b>Catalogue fournisseurs</b> : 9 distributeurs, familles, prix nets</sub></td>
<td width="50%"><img src="docs/assets/manuel/10-offre-consommation.jpg" alt="Offre et consommation"><br><sub><b>Offre et consommation</b> : seul l'automatique est compté</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/manuel/15c-comparateur-produits-identiques.jpg" alt="Produits identiques chez plusieurs fournisseurs"><br><sub><b>Comparateur</b> : le même produit chez plusieurs fournisseurs, quel que soit son libellé, comparé par unité de base</sub></td>
<td width="50%"><img src="docs/assets/manuel/15b-comparateur-resultats.jpg" alt="Comparer les prix"><br><sub><b>Le moins cher par fournisseur</b> : termes reconnus, critères isolés, filtre par famille</sub></td>
</tr>
</table>

## Fonctionnalités

| Domaine | Ce qui est livré | État |
|---|---|:---:|
| **Lecture IA** | PDF, DOCX, XLSX, CSV, TXT, images ; cascade OCR ; file d'extraction séquentielle ; score de confiance ; brouillon généré automatiquement | ✅ |
| **Devis** | Lots et sous-lots, matériaux, main-d'œuvre, déplacement, notes ; TVA 20 / 10 / 5,5 / 0 % ; marge masquée ; variantes ; PDF Pro Forma | ✅ |
| **Catalogues sur mesure** | Import CSV ou Excel (.xlsx, .xls) de n'importe quel format, feuille et ligne d'en-tête détectées, classeurs à macros refusés, correspondance des colonnes, versions, activation atomique, fichiers volumineux | ✅ |
| **Catalogue fournisseurs** | Rexel, Prolians, Point.P, YESSS, La Plateforme du Bâtiment, Au Forum du Bâtiment, SFIC, Chausson, Icilux ; partagé, masquable, jamais supprimé ; recherche par mot et par famille dans chaque catalogue | ✅ |
| **Chiffrage sur sources activables** | Chaque catalogue fournisseur s'active ou se désactive pour le chiffrage (bouton poussoir, contenu conservé) ; sans catalogue interne, les sources activées génèrent le devis ; recherche rapide sous RLS (index trigramme via fonctions sécurisées) | ✅ |
| **Comparateur de prix** | Le moins cher par fournisseur, critères isolés, termes équivalents reconnus (« courbe c », « 2p », « ph+n »…), filtre par famille | ✅ |
| **Produits identiques entre fournisseurs** | Même article reconnu chez plusieurs fournisseurs (EAN, ou marque + réf. fabricant) même si les désignations diffèrent ; prix ramené à l'unité de base (un lot de 100 m comparé au mètre) ; anomalies signalées | ✅ |
| **Format unique des catalogues** | 971 676 offres de 9 fournisseurs nettoyées dans un format commun : GTIN vérifié, marque canonique, unité de base, prix par unité ; données source jamais modifiées | ✅ |
| **Clients** | Fiches, contacts, chantiers, journal des échanges, import et export CSV, indicateurs | ✅ |
| **Suggestions IA** | Donneur d'ordre et client final proposés avec la phrase source ; rattachement automatique seulement sur SIRET ou e-mail identique | ✅ |
| **Relances** | Jours ouvrés et fériés, urgence, rappel d'expiration, appel au-delà d'un seuil, opposition RGPD, textes FR / EN | ✅ |
| **Multi-entreprises** | Rôles owner, admin, operator, viewer, billing_admin ; sélecteur d'entreprise ; RLS PostgreSQL | ✅ |
| **Offres et quotas** | Découverte, Initial, Pilotage, Performance, Signature ; registre de consommation en ajout seul ; blocage activable (`BLUESEATRA_QUOTAS_APPLIQUES`) | ✅ |
| **Intégrations** | Webhook n8n par entreprise, pont MCP, choix du moteur IA | ✅ |
| **Paiement en ligne** | Stripe | 🔜 ticket #90 |

## Démarrage rapide

```bash
git clone https://github.com/zehair-louzza/Blueseatra.git && cd Blueseatra

# API
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # renseigner DATABASE_URL, JWT_SECRET, APP_ENCRYPTION_KEY, HERMES_BASE_URL
uvicorn server:app --port 8001 --reload

# Site
cd ../frontend && npm install --legacy-peer-deps
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

Le détail (variables, base locale, tests) est dans le [guide développeur](./docs/guide-developpeur.md).

## Architecture

<img src="docs/assets/schema-architecture.png" alt="Architecture Blueseatra : Vercel, Render, Supabase, passerelle Hermès et VPS OVH" width="100%">

<img src="docs/assets/schema-parcours-complet.png" alt="Parcours complet d'un devis, de la réception au PDF final : qui agit, qui réagit" width="100%">

Détail des dix phases, vues Supabase et Render : [Infrastructure et parcours complet d'un devis](./docs/infrastructure.md).

<img src="docs/assets/schema-chiffrage.png" alt="Chiffrage sur sources activables" width="100%">

<img src="docs/assets/schema-recherche-rls.png" alt="Recherche fournisseurs sous RLS : fonctions sécurisées puis relecture sous RLS" width="100%">

<details>
<summary>Vue texte (Mermaid)</summary>

```mermaid
flowchart LR
    U[Navigateur] -->|HTTPS| V[Vercel<br>site React]
    U -->|/api| R[Render<br>API FastAPI]
    R -->|rôle blueseatra_app + RLS| S[(Supabase<br>PostgreSQL 17)]
    R -->|HTTPS + clé| O[VPS OVH<br>Ollama]
    R -.-> N[n8n]
```

</details>

**Principes**
- L'IA ne fixe jamais un prix.
- Chaque entreprise est isolée dans le code et dans la base ; les rares fonctions qui contournent la RLS (recherche) vérifient elles-mêmes l'entreprise.
- Rien n'est supprimé en silence.
- Un devis ne part qu'après validation humaine.

Détails : [architecture.md](./docs/architecture.md).

## Documentation

| Pour | Document |
|---|---|
| Utiliser l'application | [Manuel d'utilisation](./docs/manuel-utilisateur.md) |
| Comprendre le système | [Architecture](./docs/architecture.md) · [Infrastructure et parcours complet d'un devis](./docs/infrastructure.md) · [Décisions (ADR)](./docs/decisions) |
| Développer | [Guide développeur](./docs/guide-developpeur.md) · [Référence API](./docs/reference-api.md) · [Contribuer](./CONTRIBUTING.md) |
| Mettre en production | [Exploitation](./docs/exploitation.md) · [DEPLOIEMENT.md](./DEPLOIEMENT.md) |
| Offres et prix | [Tarification](./docs/tarification-2026-09.md) |
| Module Clients | [Spécification](./docs/specs/module-clients.md) |
| Sécurité | [SECURITY.md](./SECURITY.md) · [Audit d'isolation](./docs/audit-isolation-tenants-2026-09-12.md) |
| Tout le reste | [Index de la documentation](./docs/README.md) |

## Qualité et sécurité

| Contrôle | Où |
|---|---|
| Isolation entre entreprises (statique et réelle) | `backend/tests_security`, workflow `securite.yml` |
| Fonctions de recherche sous RLS : isolation, injection, droits, exactitude (base jetable) | `backend/tests_security/test_offres_candidates_sql.py`, workflow `tests-metier.yml` |
| Règles de relance, quotas, migration Clients sur PostgreSQL 17 | `backend/tests_clients`, `backend/tests_quotas`, workflow `tests-metier.yml` |
| Lint, cohérence des migrations, recherche de secrets | workflow `ci-infra.yml` |
| Relecture obligatoire des zones sensibles | [`CODEOWNERS`](./.github/CODEOWNERS) |
| Secrets IA des entreprises chiffrés (Fernet), mots de passe bcrypt, JWT | `backend/server.py` |

## Écosystème

| Dépôt | Rôle |
|---|---|
| **Blueseatra** (ce dépôt) | Application : API, site, base |
| [ovh-ai-stack](https://github.com/zehair-louzza/ovh-ai-stack) | Moteur IA auto-hébergé (Ollama, Caddy, supervision) |
| [Fournisseur-Blueseatra](https://github.com/zehair-louzza/Fournisseur-Blueseatra) | Collecte et normalisation des tarifs fournisseurs |

## Feuille de route

- [x] Catalogue fournisseurs commun et comparateur
- [x] Refonte visuelle et tarification
- [x] Compteurs de consommation (mode observation)
- [x] Module Clients et relances
- [x] Registre et quotas ([#89](https://github.com/zehair-louzza/Blueseatra/issues/89)), blocage activable
- [x] Recherche fournisseurs rapide sous RLS, filtre par famille
- [ ] Paiement Stripe et recharges ([#90](https://github.com/zehair-louzza/Blueseatra/issues/90))
- [ ] Envoi des relances par e-mail depuis Blueseatra

---

<div align="center">
<sub>© 2025-2026 Blueseatra. Code propriétaire, tous droits réservés. Voir <a href="./LICENSE">LICENSE</a>.</sub>
</div>
