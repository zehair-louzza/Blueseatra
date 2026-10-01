"""English versions of the diagrams shown in README.en.md.

Same drawing code and style as generer_schemas.py (imported from it), with
English text. Writes docs/assets/schema-<name>-en.png next to the French
files. Keep the facts in sync with generer_schemas.py when either changes.

Usage: python scripts/docs/generer_schemas_en.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generer_schemas import (  # noqa: E402
    ACCENT_BG, AMBER, AMBER_BG, ARROW, BODY, F_BOX_BODY, F_BOX_TITLE, F_FOOT, FOOT, GREEN_BG, HEADING,
    Canvas,
)


def build_architecture_en() -> None:
    c = Canvas(1400, 900)
    c.title("Blueseatra architecture",
            "Production as of 01/10/2026  |  Vercel  |  Render  |  Supabase  |  OVH VPS")

    c.zone((30, 100, 1370, 260), "User and website")
    c.zone((30, 280, 1370, 480), "API and data")
    c.zone((30, 500, 1370, 800), "AI engine (always through the Hermès gateway)")

    c.box((60, 140, 400, 240), "Browser", ["www.blueseatra.com", "React 18, FR / EN"])
    c.box((520, 140, 900, 240), "Vercel", ["Static site + CDN", "auto-deploy from main"], fill=ACCENT_BG)
    c.box((1000, 140, 1340, 240), "GitHub", ["zehair-louzza/Blueseatra", "merge to main = deploy"])
    c.arrow([(400, 190), (520, 190)], "HTTPS", (430, 166))
    c.arrow([(1000, 190), (900, 190)])

    c.box((60, 320, 400, 420), "FastAPI API (Render)", ["blueseatra-api.onrender.com",
                                                         "Frankfurt, Python 3.11, 114 routes"])
    c.box((520, 320, 900, 420), "Supabase PostgreSQL 17", ["blueseatra schema, RLS per company",
                                                           "blueseatra_app role, 22 migrations"])
    c.box((1000, 320, 1340, 441), "Supplier catalogues", ["~970,000 offers, 9 distributors",
                                                          "activatable: chiffrage_sources",
                                                          "import: Fournisseur-Blueseatra"],
          fill=AMBER_BG, tag="QUOTING", tag_color=AMBER)
    c.arrow([(230, 240), (230, 320)], "/api + token", (242, 268))
    c.arrow([(400, 370), (520, 370)], "asyncpg", (420, 346))
    c.arrow([(1000, 370), (900, 370)])

    c.arrow([(150, 420), (150, 560)], "all AI calls", (162, 436))
    c.box((60, 560, 400, 681), "Hermès gateway", ["hermes.blueseatra.com",
                                                  "POST /v1/chat/completions",
                                                  "X-Api-Key, no tools"], fill=ACCENT_BG)
    c.box((520, 540, 900, 772), "custom:ollama  (OVH VPS)", [
        ("glm-ocr", "local OCR (default)"),
        ("qwen2.5:7b", "extraction, structuring"),
        ("qwen2.5vl:7b", "vision (photo, image PDF)"),
        ("gpt-oss:20b", "graded reasoning"),
        ("glm-4.7-flash", "work description"),
        ("hermes3", "last resort"),
        ("1 model", "loaded in RAM at a time"),
    ], col2=140)
    c.box((1000, 560, 1340, 660), "custom:mistral", ["Mistral API (text only)",
                                                     "429 retries: 2, 4, 8, 16 s"])
    c.arrow([(400, 620), (520, 620)])
    c.arrow([(400, 590), (460, 590), (460, 524), (1170, 524), (1170, 560)])

    c.text((40, 822), "OCR always runs locally: an image is never sent to Mistral; only the text read "
                      "on the VPS goes to the chosen provider.", F_FOOT, FOOT)
    c.text((40, 848), "The AI reads and structures; it never sets a price. Supabase pg_cron wakes "
                      "the API every 13 min. n8n: optional webhook per company.", F_FOOT, FOOT)
    c.save("schema-architecture-en.png")


def build_chiffrage_en() -> None:
    c = Canvas(1400, 590)
    c.title("Quoting on activatable sources",
            "Each company chooses its sources; switching one off never deletes anything.")

    c.box((40, 110, 400, 214), "Internal catalogue", ["imported CSV, versions",
                                                     "switch on the Catalogues page"])
    c.box((40, 246, 400, 371), "Supplier catalogues", ["Rexel, Prolians, Point.P, YESSS...",
                                                       "one toggle per supplier",
                                                       "state: chiffrage_sources table"],
          fill=AMBER_BG, tag="ACTIVATABLE", tag_color=AMBER)

    c.box((520, 110, 880, 371), "Search under RLS", [
        "for each line of the request,",
        "one branch per activated source:",
        "",
        "1. offres_candidates: trigram",
        "   index, 200 ids per source,",
        "   current company or shared only",
        "2. records read back by id, under RLS",
        "3. sorted by price on that small set",
        "\"prise\": > 30 s (empty) → 2.3 s",
    ], fill=ACCENT_BG)
    c.arrow([(400, 162), (520, 162)])
    c.arrow([(400, 308), (520, 308)])

    c.box((1000, 110, 1360, 214), "Draft quote", ["internal catalogue first",
                                                  "price source traced (pricing_snapshot)"])
    c.box((1000, 246, 1360, 371), "Quote editor", ["supplier items: amber badge",
                                                   "net price, unit, brand, reference",
                                                   "lines without offer: to confirm"])
    c.arrow([(880, 162), (1000, 162)])
    c.arrow([(880, 308), (1000, 308)])

    c.zone((40, 400, 1360, 550), "Generation rules")
    c.text((60, 432), "Internal catalogue active", F_BOX_TITLE)
    c.text((60, 460), "matched against the catalogue,", F_BOX_BODY, BODY)
    c.text((60, 481), "completed by active sources", F_BOX_BODY, BODY)
    c.text((500, 432), "No catalogue, active sources", F_BOX_TITLE)
    c.text((500, 460), "active sources generate the quote;", F_BOX_BODY, BODY)
    c.text((500, 481), "no match: lines to confirm", F_BOX_BODY, BODY)
    c.text((960, 432), "Neither catalogue nor source", F_BOX_TITLE)
    c.text((960, 460), "refused with a clear message:", F_BOX_BODY, BODY)
    c.text((960, 481), "import or activate a catalogue", F_BOX_BODY, BODY)
    c.text((60, 514), "A supplier-side incident never blocks generation (silent fallback). "
                      "Every toggle is recorded in the audit log.", F_BOX_BODY, FOOT)
    c.save("schema-chiffrage-en.png")


def build_recherche_rls_en() -> None:
    c = Canvas(1400, 640)
    c.title("Supplier search under RLS",
            "The trigram index becomes usable again, and isolation keeps both of its locks.")
    c.box((40, 110, 330, 252), "Screen", ["price comparison,", "quote item picker,", "generation, catalogue,",
                                          "Family menu"])
    c.box((370, 110, 680, 252), "API", ["terms normalised as JSON,", "\\b → \\y (PostgreSQL words),",
                                        "company resolved server-side,", "never taken from the client"])
    c.box((720, 110, 1040, 252), "SECURITY DEFINER function", ["rejects any company other than", "the current one or shared;",
                                                               "trigram or price index;", "returns ids only"],
          fill=ACCENT_BG, tag="OUTSIDE RLS", tag_color=AMBER)
    c.box((1080, 110, 1360, 252), "Records read back", ["by id,", "UNDER RLS, with explicit", "company filter:",
                                                        "second lock"], fill=GREEN_BG)
    for a, b in ((330, 370), (680, 720), (1040, 1080)):
        c.arrow([(a, 181), (b, 181)])

    c.zone((40, 290, 1360, 470), "Search functions (empty search_path; first 3: SECURITY DEFINER, blueseatra_app only)")
    cols = [
        (60, "offres_candidates", ["price comparison, quote", "item picker, generation;", "optional family filter"]),
        (390, "catalogue_page", ["word search inside a", "catalogue, page sorted", "by price, capped total"]),
        (720, "familles_catalogue", ["families of a catalogue:", "skip scan of the index,", "one read per family"]),
        (1050, "recherche_conditions", ["pattern rules (LIKE, ~),", "escaped %L literals;", "internal, not callable"]),
    ]
    for x, titre, lignes in cols:
        c.text((x, 330), titre, F_BOX_TITLE)
        for i, l in enumerate(lignes):
            c.text((x, 360 + 21 * i), l, F_BOX_BODY, BODY)

    c.zone((40, 490, 1360, 610), "Measured live from the browser, before → after (Rexel, 747,771 offers)")
    c.text((60, 530), "\"disjoncteur 16a courbe c\" in a catalogue: 26.6 s → 1.4 s      rare term: 43.9 s → 0.8 s      "
                      "item picker \"prise\": > 30 s → 2.3 s", F_BOX_BODY, HEADING)
    c.text((60, 556), "comparison \"dalle LED 600x600\": 27 s → 0.9 s      family list: 75 s → 3.4 s      "
                      "\"courbe c\": 0 → 320 offers (\\b)", F_BOX_BODY, HEADING)
    c.save("schema-recherche-rls-en.png")


if __name__ == "__main__":
    build_architecture_en()
    build_chiffrage_en()
    build_recherche_rls_en()
