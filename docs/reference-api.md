# Référence API

Générée automatiquement depuis le schéma OpenAPI de `backend/server.py` : **99 routes**. Ne pas modifier à la main : relancer `python scripts/docs/generer_reference_api.py`.

- Base : `https://blueseatra-api.onrender.com/api`
- Authentification : en-tête `Authorization: Bearer <jeton>` obtenu par `POST /api/auth/login`, et en-tête `X-Tenant-Id` pour choisir l'entreprise quand l'utilisateur en a plusieurs.
- Sans jeton, les routes protégées répondent `401`. Un identifiant d'une autre entreprise répond `404`.
- Documentation interactive : `/docs` (Swagger) sur une instance locale.

## Authentification et compte

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/auth/me` | Me |
| `POST` | `/api/auth/signup` | Signup |
| `POST` | `/api/auth/switch-tenant/{tenant_id}` | Switch Tenant |

## Entreprises et membres

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/members` | List Members |
| `POST` | `/api/members` | Add Member |
| `DELETE` | `/api/members/{user_id}` | Remove Member |
| `PATCH` | `/api/members/{user_id}` | Update Member |

## Demandes et extraction IA

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/requests` | List Requests |
| `POST` | `/api/requests` | Create Request |
| `DELETE` | `/api/requests/{request_id}` | Delete Request |
| `GET` | `/api/requests/{request_id}` | Get Request |
| `PATCH` | `/api/requests/{request_id}` | Update Request |
| `POST` | `/api/requests/{request_id}/deep-vision` | Deep Vision Escalation |
| `GET` | `/api/requests/{request_id}/file` | Get Request File |
| `POST` | `/api/requests/{request_id}/process` | Reprocess Request |

## Devis

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/quotes` | List Quotes |
| `POST` | `/api/quotes/draft` | Create Quote Draft |
| `DELETE` | `/api/quotes/{quote_id}` | Delete Quote |
| `GET` | `/api/quotes/{quote_id}` | Get Quote |
| `PATCH` | `/api/quotes/{quote_id}` | Update Quote |
| `POST` | `/api/quotes/{quote_id}/client` | Lier Devis |
| `POST` | `/api/quotes/{quote_id}/duplicate` | Duplicate Quote |
| `POST` | `/api/quotes/{quote_id}/issue` | Issue |
| `GET` | `/api/quotes/{quote_id}/pdf` | Quote Pdf |
| `POST` | `/api/quotes/{quote_id}/rematch` | Rematch Quote |
| `POST` | `/api/quotes/{quote_id}/reopen` | Reopen Quote |
| `POST` | `/api/quotes/{quote_id}/send` | Send Quote |
| `GET` | `/api/quotes/{quote_id}/suivi` | Suivi |
| `POST` | `/api/quotes/{quote_id}/validate` | Validate Quote |
| `GET` | `/api/quotes/{quote_id}/versions` | List Quote Versions |
| `GET` | `/api/quotes/{quote_id}/versions/compare` | Compare Quote Versions |

## Catalogues sur mesure

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/catalog-template.csv` | Catalog Template |
| `GET` | `/api/catalog/active` | Catalog Active |
| `GET` | `/api/catalog/search` | Catalog Search |
| `GET` | `/api/catalogs` | List Catalogs |
| `POST` | `/api/catalogs/import` | Import Catalog |
| `POST` | `/api/catalogs/import/preview` | Import Preview |
| `DELETE` | `/api/catalogs/{catalog_id}` | Delete Catalog |
| `PATCH` | `/api/catalogs/{catalog_id}` | Update Catalog |
| `POST` | `/api/catalogs/{catalog_id}/activate/{version_id}` | Activate Version |
| `POST` | `/api/catalogs/{catalog_id}/deactivate` | Deactivate Catalog |
| `GET` | `/api/catalogs/{catalog_id}/items` | Catalog Items |
| `GET` | `/api/import-jobs/{job_id}/errors` | Import Errors |

## Catalogue fournisseurs commun

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/fournisseurs/catalogue` | Catalogue Fournisseurs |
| `GET` | `/api/fournisseurs/catalogue-commun` | Catalogue Commun Etat |
| `POST` | `/api/fournisseurs/catalogue-commun/afficher` | Catalogue Commun Afficher |
| `POST` | `/api/fournisseurs/catalogue-commun/afficher-pour-tous` | Catalogue Commun Afficher Tous |
| `POST` | `/api/fournisseurs/catalogue-commun/masquer` | Catalogue Commun Masquer |
| `POST` | `/api/fournisseurs/catalogue-commun/masquer-pour-tous` | Catalogue Commun Masquer Tous |
| `GET` | `/api/fournisseurs/catalogue/{cle}/familles` | Catalogue Familles |
| `GET` | `/api/fournisseurs/catalogue/{cle}/produits` | Catalogue Produits |
| `GET` | `/api/fournisseurs/liste` | Fournisseurs Liste |
| `GET` | `/api/fournisseurs/recherche` | Fournisseurs Recherche |

## Module Clients

| Méthode | Route | Rôle |
|---|---|---|
| `PATCH` | `/api/chantiers/{chantier_id}` | Modifier Chantier |
| `POST` | `/api/chantiers/{chantier_id}/archiver` | Archiver Chantier |
| `GET` | `/api/clients` | Lister |
| `POST` | `/api/clients` | Creer |
| `GET` | `/api/clients-export.csv` | Exporter |
| `POST` | `/api/clients/import` | Importer |
| `POST` | `/api/clients/import/preview` | Import Apercu |
| `POST` | `/api/clients/reprise-devis-existants` | Reprise |
| `GET` | `/api/clients/{client_id}` | Lire |
| `PATCH` | `/api/clients/{client_id}` | Modifier |
| `POST` | `/api/clients/{client_id}/archiver` | Archiver |
| `GET` | `/api/clients/{client_id}/chantiers` | Chantiers |
| `POST` | `/api/clients/{client_id}/chantiers` | Creer Chantier |
| `GET` | `/api/clients/{client_id}/contacts` | Contacts |
| `POST` | `/api/clients/{client_id}/contacts` | Creer Contact |
| `GET` | `/api/clients/{client_id}/devis` | Devis Du Client |
| `GET` | `/api/clients/{client_id}/echanges` | Echanges |
| `POST` | `/api/clients/{client_id}/echanges` | Ajouter Echange |
| `POST` | `/api/clients/{client_id}/restaurer` | Restaurer |
| `GET` | `/api/clients/{client_id}/resume` | Resume |
| `PATCH` | `/api/contacts/{contact_id}` | Modifier Contact |
| `POST` | `/api/contacts/{contact_id}/anonymiser` | Anonymiser |
| `POST` | `/api/contacts/{contact_id}/archiver` | Archiver Contact |
| `GET` | `/api/regles-relance` | Lire Regles |
| `PUT` | `/api/regles-relance` | Ecrire Regles |
| `GET` | `/api/relances` | Relances |
| `POST` | `/api/relances/{rid}/annuler` | Annuler |
| `POST` | `/api/relances/{rid}/faite` | Faite |
| `POST` | `/api/relances/{rid}/reporter` | Reporter |
| `GET` | `/api/suggestions-clients` | Suggestions |
| `POST` | `/api/suggestions-clients/{sid}/accepter` | Accepter |
| `POST` | `/api/suggestions-clients/{sid}/annuler-rattachement` | Annuler Auto |
| `POST` | `/api/suggestions-clients/{sid}/rejeter` | Rejeter |

## Offre et consommation

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/abonnement/consommation` | Abonnement Consommation |
| `GET` | `/api/abonnement/historique` | Abonnement Historique |

## Paramètres et intégrations

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/company-profile` | Company Profile Get |
| `PUT` | `/api/company-profile` | Company Profile Put |
| `GET` | `/api/settings/integrations` | Get Settings |
| `PUT` | `/api/settings/integrations` | Update Settings |

## Journal d'audit

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/audit` | Audit Logs |

## Tableau de bord

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/dashboard` | Dashboard |

## Supervision

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/` | Root |
| `GET` | `/api/health` | Health |

## Pont MCP

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/mcp` | Mcp Endpoint |
| `POST` | `/mcp` | Mcp Endpoint |
