# Frontend Blueseatra

SPA React du logiciel de devis assisté par IA — écrans demandes, devis, catalogues (internes et fournisseurs), clients, relances, membres, paramètres, facturation. Interface FR / EN (react-i18next).

## Stack

- **React 18** (Create React App + CRACO), React Router, **Tailwind CSS**, Radix UI / shadcn
- Build : CRA avec `DISABLE_ESLINT_PLUGIN=true`, `legacy-peer-deps`, `ajv@8` épinglé (voir `.npmrc` et `package.json`)
- Hébergement : **Vercel**, projet `blueseatra`, Root Directory `frontend/`, production sur `main` — chaque fusion sur `main` publie le site (domaines `www.blueseatra.com` et `blueseatra.com`)

## Scripts

```bash
npm install
REACT_APP_BACKEND_URL=http://localhost:8001 npm start   # dev server sur :3000
CI=true npm run build                                   # build de production dans build/
npm test                                                # tests Jest
```

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `REACT_APP_BACKEND_URL` | URL de l'API (production : `https://blueseatra-api.onrender.com`) ; un fallback existe dans `src/lib/api.js` |

Authentification maison : jeton `bs_token` en localStorage, en-têtes `Authorization: Bearer` et `X-Tenant-Id` (sélecteur d'entreprise).

## Pages notables

- `src/pages/Catalogs.js` — catalogues internes (import CSV, versions, contrôle avant activation) + interrupteur « Utiliser pour le chiffrage » par catalogue et section « Catalogues fournisseurs » (sources activables pour le chiffrage, bouton « Afficher le catalogue »).
- `src/pages/SupplierCatalog.js` / `SupplierCatalogDialog.js` — catalogue fournisseurs (~967 000 références), bouton poussoir d'activation pour le chiffrage par fournisseur, dialog produits paginé.
- `src/pages/QuoteEditor.js` — éditeur de devis : recherche d'articles mêlant catalogue interne et sources activées, badge ambre sur les articles fournisseurs ; génération avec délai d'attente 300 s.

## Documentation

- [Architecture](../docs/architecture.md) · [Guide développeur](../docs/guide-developpeur.md) · [Manuel d'utilisation](../docs/manuel-utilisateur.md)
- [Déploiement (Vercel / Render / Supabase / OVH)](../DEPLOIEMENT.md)

## Licence

Logiciel propriétaire, tous droits réservés. Titulaire : Zehair Louzza, exploitant le nom commercial « Blueseatra ». Voir [LICENSE](../LICENSE).
