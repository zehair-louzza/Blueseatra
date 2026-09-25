"""Génère docs/reference-api.md à partir des routes réellement déclarées par FastAPI.

Usage (depuis la racine du dépôt, avec les variables d'environnement du backend) :
    python scripts/docs/generer_reference_api.py
Aucune connexion à la base n'est nécessaire : seul le schéma OpenAPI est lu.
"""
import os, sys, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:1/db")
import server  # noqa: E402

GROUPES = [
    ("auth", "Authentification et compte"), ("me", "Authentification et compte"), ("tenants", "Entreprises et membres"),
    ("members", "Entreprises et membres"), ("requests", "Demandes et extraction IA"), ("quotes", "Devis"),
    ("catalogs", "Catalogues sur mesure"), ("pricing", "Catalogues sur mesure"), ("import", "Catalogues sur mesure"),
    ("catalogue-commun", "Catalogue fournisseurs commun"), ("fournisseurs", "Catalogue fournisseurs commun"),
    ("clients", "Module Clients"), ("clients-export.csv", "Module Clients"), ("suggestions-clients", "Module Clients"),
    ("relances", "Module Clients"), ("regles-relance", "Module Clients"), ("abonnement", "Offre et consommation"),
    ("settings", "Paramètres et intégrations"), ("company", "Paramètres et intégrations"), ("audit", "Journal d'audit"),
    ("dashboard", "Tableau de bord"), ("health", "Supervision"), ("", "Supervision"),
    ("catalog", "Catalogues sur mesure"), ("catalog-template.csv", "Catalogues sur mesure"),
    ("contacts", "Module Clients"), ("chantiers", "Module Clients"), ("mcp", "Pont MCP"),
    ("rgpd", "RGPD"), ("exploitation", "Supervision"),
]
def groupe(path):
    seg = path.removeprefix("/api/").lstrip("/").split("/")[0]
    for k, g in GROUPES:
        if seg == k:
            return g
    for k, g in GROUPES:
        if k and seg.startswith(k):
            return g
    return "Autres"

spec = server.app.openapi()
par = collections.OrderedDict((g, []) for _, g in GROUPES)
par["Autres"] = []
n = 0
for path, ops in spec["paths"].items():
    for m, op in ops.items():
        if m not in ("get", "post", "put", "patch", "delete"):
            continue
        n += 1
        resume = (op.get("summary") or op.get("operationId") or "").replace("|", "/")
        par[groupe(path)].append((path, m.upper(), resume))
out = ["# Référence API", "",
       f"Générée automatiquement depuis le schéma OpenAPI de `backend/server.py` : **{n} routes**. "
       "Ne pas modifier à la main : relancer `python scripts/docs/generer_reference_api.py`.", "",
       "- Base : `https://blueseatra-api.onrender.com/api`",
       "- Authentification : en-tête `Authorization: Bearer <jeton>` obtenu par `POST /api/auth/login`, "
       "et en-tête `X-Tenant-Id` pour choisir l'entreprise quand l'utilisateur en a plusieurs.",
       "- Sans jeton, les routes protégées répondent `401`. Un identifiant d'une autre entreprise répond `404`.",
       "- Documentation interactive : `/docs` (Swagger) sur une instance locale.", ""]
for g, rows in par.items():
    if not rows:
        continue
    out += [f"## {g}", "", "| Méthode | Route | Rôle |", "|---|---|---|"]
    for p, m, r in sorted(rows):
        out.append(f"| `{m}` | `{p}` | {r} |")
    out.append("")
open(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "reference-api.md"), "w").write("\n".join(out))
print(n, {g: len(r) for g, r in par.items() if r})
