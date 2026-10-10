"""Schémas des dépôts compagnons, dans le style des schémas de Blueseatra.

- Fournisseur-Blueseatra : docs/assets/schema-architecture-fournisseur.png
- ovh-ai-stack : docs/assets/schema-architecture-ovh.png

Usage : python scripts/docs/generer_schemas_ecosysteme.py <dossier_de_sortie>
Puis copier chaque image dans le dossier docs/assets/ du dépôt concerné.
État au 10/10/2026 (compose.yaml et caddy/Caddyfile d'ovh-ai-stack, README de
Fournisseur-Blueseatra).
"""
from __future__ import annotations

import sys
from pathlib import Path

import generer_schemas as g
from generer_schemas import ACCENT_BG, AMBER_BG, Canvas, F_FOOT, FOOT  # noqa: F401


def fournisseur() -> None:
    c = Canvas(1400, 430)
    c.title("Fournisseur Blueseatra : architecture",
            "Achats matériels et comparaison des prix, sur les comptes du SaaS Blueseatra.")
    c.box((40, 110, 320, 237), "Navigateur", ["site React (Render,", "site statique)", "jeton du SaaS"])
    c.box((420, 110, 760, 237), "API FastAPI (Render)", ["catalogue, comparateur,", "estimateur, imports Excel",
                                                          "calculs côté serveur"], fill=ACCENT_BG)
    c.box((860, 92, 1360, 175), "API Blueseatra", ["GET /api/auth/me : seule autorité sur les jetons"])
    c.box((860, 196, 1360, 300), "Supabase PostgreSQL", ["schéma fournisseur, rôle fournisseur_app,",
                                                         "aucun accès au schéma blueseatra"], fill=AMBER_BG)
    c.arrow([(320, 173), (420, 173)], "/api/*", (338, 149))
    c.arrow([(760, 150), (810, 150), (810, 133), (860, 133)], "jeton", (770, 108))
    c.arrow([(760, 196), (810, 196), (810, 248), (860, 248)])
    c.text((40, 330), "Isolation : chaque lecture et écriture passe par db.for_tenant(...). Aucun compte stocké ici.",
           F_FOOT, FOOT)
    c.text((40, 356), "Prix de vente HT = achat HT / (1 − marge) ; TVA 0 / 5,5 / 10 / 20 % ou libre, calculée par "
                      "le serveur.", F_FOOT, FOOT)
    c.text((40, 382), "Le SaaS principal intègre aussi un catalogue fournisseurs commun (9 distributeurs, "
                      "≈ 967 000 offres).", F_FOOT, FOOT)
    c.save("schema-architecture-fournisseur.png")


def ovh() -> None:
    c = Canvas(1400, 560)
    c.title("ovh-ai-stack : architecture du VPS",
            "Seul Caddy écoute sur Internet ; Ollama n'est jamais exposé. VPS OVHcloud en France.")
    c.box((40, 120, 300, 247), "Internet", ["API Blueseatra (Render)", "navigateur (tableau", "de bord)"])
    c.box((380, 120, 700, 268), "Caddy (80 / 443)", ["TLS Let's Encrypt", "en-têtes de sécurité",
                                                     "X-Api-Key (SaaS)", "mot de passe (tableau de bord)"], fill=ACCENT_BG)
    c.zone((760, 96, 1380, 512), "Réseau Docker interne")
    c.box((780, 126, 1360, 209), "hermes-passerelle : 8642", ["entrée du SaaS → Ollama, Mistral ou OpenCode Free"], fill=ACCENT_BG)
    c.box((780, 222, 1360, 305), "hermes : 9119", ["agent et tableau de bord (mot de passe)"])
    c.box((780, 318, 1360, 401), "ollama : 11434", ["modèles locaux (OCR, texte, vision)"])
    c.box((780, 414, 1360, 497), "n8n : 5678", ["flux déterministes (automatisations)"])
    c.arrow([(300, 183), (380, 183)], "HTTPS", (308, 159))
    for y in (167, 263, 359, 455):
        c.arrow([(700, 194), (740, 194), (740, y), (780, y)])
    c.text((40, 300), "Déploiement : GitHub Actions,", F_FOOT, FOOT)
    c.text((40, 324), "commandes « deployer » et", F_FOOT, FOOT)
    c.text((40, 348), "« diagnostic » seulement (ADR-011).", F_FOOT, FOOT)
    c.text((40, 384), "Hermès ne calcule jamais un prix :", F_FOOT, FOOT)
    c.text((40, 408), "les montants restent des règles", F_FOOT, FOOT)
    c.text((40, 432), "fixes du SaaS. Mistral et OpenCode", F_FOOT, FOOT)
    c.text((40, 456), "reçoivent un texte déjà masqué.", F_FOOT, FOOT)
    c.save("schema-architecture-ovh.png")


if __name__ == "__main__":
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sortie.mkdir(parents=True, exist_ok=True)
    g.ASSETS = sortie
    fournisseur()
    ovh()
