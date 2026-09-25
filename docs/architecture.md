# Architecture

Vue d'ensemble technique de Blueseatra au 25/09/2026. Pour installer et tester, voir [`guide-developpeur.md`](./guide-developpeur.md).

## Vue générale

```mermaid
flowchart LR
    U[Navigateur<br>blueseatra.com] -->|HTTPS| H[Hostinger<br>site React statique]
    U -->|HTTPS /api| R[Render<br>API FastAPI<br>blueseatra-api]
    R -->|asyncpg, rôle blueseatra_app, RLS| S[(Supabase<br>PostgreSQL 17<br>schéma blueseatra)]
    R -->|HTTPS + clé| O[VPS OVH<br>Ollama : lecture, OCR, structuration]
    R -.->|facultatif| N[n8n<br>webhook par entreprise]
    S -->|pg_cron toutes les 13 min| R
    F[Fournisseur-Blueseatra<br>collecte des tarifs] -->|import| S
```

| Couche | Technologie | Hébergement |
|---|---|---|
| Site | React 18, React Router, Tailwind CSS, Radix/shadcn, react-i18next (FR/EN) | Hostinger, dépôt manuel du dossier `build/` |
| API | FastAPI, Python 3.11, Pydantic v2, SQLAlchemy 2 async, asyncpg | Render, Francfort, déploiement automatique depuis `main` (`backend/`) |
| Base | PostgreSQL 17, RLS, pg_cron | Supabase, projet `xmsxlochasjauhnxarvc` |
| IA | Ollama (Hermes, Qwen 2.5 VL, GLM…), repli configurable par entreprise via litellm | VPS OVH, dépôt [`ovh-ai-stack`](https://github.com/zehair-louzza/ovh-ai-stack) |
| PDF | ReportLab (Pro Forma) | API |
| Tarifs fournisseurs | Collecteurs et import volumineux | Dépôt [`Fournisseur-Blueseatra`](https://github.com/zehair-louzza/Fournisseur-Blueseatra) |

## Parcours d'une demande

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant A as API
    participant Q as File d'extraction
    participant IA as VPS OVH
    participant DB as Supabase
    U->>A: POST /api/requests (texte ou fichier)
    A->>DB: quota_reserver (devis_ia, pages)
    A->>Q: mise en file (séquentielle)
    Q->>IA: OCR si nécessaire, puis structuration
    IA-->>Q: client, site, lots, lignes
    Q->>DB: demande « done » ou « needs_review »
    Q->>DB: brouillon de devis (prix du catalogue figés)
    Q->>DB: suggestions de clients (avec preuve)
    Note over Q,DB: échec → quota remboursé par écriture inverse
    U->>A: validation, envoi du devis
    A->>DB: relances planifiées en jours ouvrés
```

## Principes non négociables

1. **L'IA ne fixe jamais un prix.** Elle lit et structure ; les prix viennent des catalogues, puis les remises, marges et TVA sont calculées par des règles (`matching.py`).
2. **Isolation des entreprises à deux niveaux.** Le code filtre `tenant_id`, et PostgreSQL l'impose par RLS sous le rôle `blueseatra_app`. Un identifiant d'une autre entreprise renvoie 404.
3. **Aucune suppression silencieuse.** Le catalogue commun est masquable mais jamais supprimé. Les clients sont archivés et les contacts anonymisés. Le registre de consommation et les échanges clients sont en ajout seul, protégés par un trigger.
4. **Validation humaine.** Un devis reste un brouillon tant qu'une personne ne l'a pas validé.

## Modules du backend

| Fichier | Rôle |
|---|---|
| `server.py` | Application FastAPI : authentification, entreprises, demandes, devis, catalogues, paramètres |
| `ai_service.py` | Lecture IA : cascade OCR, structuration en lots, rôles de modèles |
| `extraction_worker.py` | File d'extraction séquentielle |
| `matching.py` | Rapprochement des lignes avec le catalogue, calcul des totaux |
| `quote_scenarios.py` | Options et variantes de devis |
| `pdf_service.py` | PDF Pro Forma |
| `catalogue_commun.py`, `catalogue_navigation.py`, `fournisseur_recherche.py` | Catalogue fournisseurs commun et comparateur |
| `quotas.py` | Offres, registre de consommation, réservation et remboursement |
| `clients_module.py`, `relances_regles.py` | Module Clients et règles de relance |
| `pg_adapter.py`, `database.py`, `models_sql.py` | Accès PostgreSQL et session par entreprise |
| `mcp_bridge.py` | Pont MCP (`/mcp`) |

## Modèle de données

```mermaid
erDiagram
    tenants ||--o{ tenant_users : membres
    users ||--o{ tenant_users : appartient
    tenants ||--o{ catalogs : possede
    catalogs ||--o{ catalog_versions : versions
    catalog_versions ||--o{ pricing_items : articles
    tenants ||--o{ requests : recoit
    requests ||--o{ quotes : genere
    quotes ||--o{ quote_versions : historique
    tenants ||--o{ clients : fichier
    clients ||--o{ contacts : contacts
    clients ||--o{ chantiers : sites
    clients ||--o{ echanges_clients : journal
    quotes ||--o{ relances : relances
    tenants ||--o| regles_relance : reglages
    requests ||--o{ suggestions_clients : propositions
    tenants ||--o| abonnements : offre
    offres ||--o{ abonnements : grille
    tenants ||--o{ registre_consommation : consommation
    tenants ||--o{ audit_logs : audit
```

Autres tables : `import_jobs`, `import_errors`, `settings_integrations` (clé IA chiffrée Fernet), `company_profiles` et les tables du catalogue fournisseurs : `suppliers`, `supplier_offers`, `canonical_products`, `product_match_rules`, `unit_conversions`, `tenant_catalogue_commun` et `catalogue_commun_masque`.

## Décisions d'architecture

- [`decisions/ADR-OVH-AI-STACK.md`](./decisions/ADR-OVH-AI-STACK.md) : moteur IA auto-hébergé sur OVH
- [`decisions/ADR-OCR-CASCADE.md`](./decisions/ADR-OCR-CASCADE.md) : cascade OCR
- [`decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md`](./decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md) : file d'extraction séquentielle
- [`specs/module-clients.md`](./specs/module-clients.md) : spécification du module Clients
