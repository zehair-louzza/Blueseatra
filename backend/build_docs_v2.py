#!/usr/bin/env python3
"""Build Blueseatra Documentation FR + EN PDFs (August 2026 v2)."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
BRAND = ROOT / "frontend/public/brand"
LAND = ROOT / "frontend/public/landing"
FONT_DIR = Path("/tmp/fonts")
FONT_DIR.mkdir(exist_ok=True)

NAVY = HexColor("#193852")
TEAL = HexColor("#438C88")
INK = HexColor("#1c2834")
MUTE = HexColor("#5b6772")
PAPER = HexColor("#F7F4EE")
LINE = HexColor("#D4D1CA")
ROW = HexColor("#F3F6F7")

SOURCES = [
    ("Ollama gemma4:26b", "https://ollama.com/library/gemma4:26b"),
    ("Gemma + Ollama", "https://ai.google.dev/gemma/docs/integrations/ollama"),
    ("Hermes API server", "https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server"),
    ("Hermes Docker", "https://hermes-agent.nousresearch.com/docs/user-guide/docker"),
    ("Hermes configuring models", "https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models"),
]


def register_fonts():
    files = {
        "Inter": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.ttf",
        "Inter-Bold": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Bold.ttf",
    }
    ok = True
    for name, url in files.items():
        dest = FONT_DIR / f"{name}.ttf"
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception:
                ok = False
                break
        if dest.exists():
            pdfmetrics.registerFont(TTFont(name, str(dest)))
    return ok


HAS_INTER = register_fonts()
FN = "Inter" if HAS_INTER else "Helvetica"
FB = "Inter-Bold" if HAS_INTER else "Helvetica-Bold"


def styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=FB, fontSize=16, leading=20, textColor=NAVY, spaceBefore=12, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FB, fontSize=13, leading=17, textColor=NAVY, spaceBefore=10, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=FB, fontSize=11, leading=14, textColor=TEAL, spaceBefore=8, spaceAfter=4),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontName=FN, fontSize=9.5, leading=13.5, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6),
        "li": ParagraphStyle("li", parent=base["BodyText"], fontName=FN, fontSize=9.5, leading=13, textColor=INK, spaceAfter=2),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontName=FN, fontSize=8, leading=11, textColor=INK),
        "cellh": ParagraphStyle("cellh", parent=base["BodyText"], fontName=FB, fontSize=8, leading=11, textColor=white),
        "cap": ParagraphStyle("cap", parent=base["BodyText"], fontName=FN, fontSize=8, leading=11, textColor=MUTE, spaceAfter=8),
        "foot": ParagraphStyle("foot", parent=base["Normal"], fontName=FN, fontSize=7.5, leading=10, textColor=MUTE),
        "cover": ParagraphStyle("cover", parent=base["Title"], fontName=FB, fontSize=26, leading=32, textColor=NAVY, alignment=TA_CENTER),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName=FN, fontSize=12, leading=16, textColor=TEAL, alignment=TA_CENTER),
        "center": ParagraphStyle("center", parent=base["Normal"], fontName=FN, fontSize=10, leading=14, textColor=MUTE, alignment=TA_CENTER),
    }


S = styles()


def P(text, st="p"):
    return Paragraph(text, S[st])


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, S["li"]), leftIndent=8, bulletColor=TEAL) for i in items],
        bulletType="bullet",
        start="-",
        leftIndent=12,
        bulletFontName=FN,
        bulletFontSize=9,
    )


def table(rows, widths=None):
    header, body = rows[0], rows[1:]
    data = [[Paragraph(c, S["cellh"]) for c in header]]
    for r in body:
        data.append([Paragraph(c, S["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, ROW]),
    ]
    t.setStyle(TableStyle(cmds))
    return t


def fitted(path, w=170 * mm, max_h=95 * mm):
    p = Path(path)
    if not p.exists():
        return Spacer(1, 1)
    from PIL import Image as PILImage
    iw, ih = PILImage.open(p).size
    h = w * (ih / iw)
    if h > max_h:
        h = max_h
        w = h * (iw / ih)
    im = Image(str(p), width=w, height=h)
    im.hAlign = "CENTER"
    return im


def img(path, w=170 * mm):
    return fitted(path, w=w, max_h=88 * mm)


def photo(path, w=170 * mm, ratio=None):
    return fitted(path, w=w, max_h=78 * mm)


def header_footer(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FN, 8)
    c.drawString(16 * mm, A4[1] - 8 * mm, "Blueseatra  Documentation v2")
    c.drawRightString(A4[0] - 16 * mm, A4[1] - 8 * mm, "Aout 2026" if doc.title.endswith("(FR)") else "August 2026")
    c.setFillColor(MUTE)
    c.setFont(FN, 8)
    c.drawString(16 * mm, 10 * mm, "Blueseatra")
    c.drawRightString(A4[0] - 16 * mm, 10 * mm, f"{doc.page}")
    c.setStrokeColor(LINE)
    c.line(16 * mm, 14 * mm, A4[0] - 16 * mm, 14 * mm)
    y = 6 * mm
    # compact sources on later pages
    if doc.page > 1:
        c.setFont(FN, 6.5)
        note = "Sources completes en derniere page" if doc.title.endswith("(FR)") else "Full sources on the last page"
        c.drawString(16 * mm, y, note)
    c.restoreState()


def cover_footer(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, 0, A4[0], 22 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FN, 8)
    c.drawCentredString(A4[0] / 2, 10 * mm, "Hostinger  ·  Render  ·  Supabase  ·  OVH")
    c.restoreState()


def story_fr():
    s = []
    logo = BRAND / "blueseatra-lockup.png"
    if logo.exists():
        s.append(Spacer(1, 28 * mm))
        s.append(Image(str(logo), width=90 * mm, height=30 * mm, hAlign="CENTER"))
    s.append(Spacer(1, 16 * mm))
    s.append(P("Documentation technique et produit", "cover"))
    s.append(Spacer(1, 4 * mm))
    s.append(P("SaaS B2B de devis TCE assiste par IA", "sub"))
    s.append(Spacer(1, 8 * mm))
    s.append(P("Version 2  ·  17 aout 2026", "center"))
    s.append(P("FastAPI · React · Supabase · Ollama · Hermes Agent", "center"))
    s.append(PageBreak())

    s.append(P("1. Presentation", "h1"))
    s.append(P(
        "Blueseatra est une plateforme multi-tenant pour les PME du batiment, du TCE et de la maintenance. "
        "Chaque entreprise dispose d'un espace isole: utilisateurs, catalogue, demandes et devis. "
        "Le produit lit une demande brute (email, PDF, photo, texte) et prepare un brouillon de devis "
        "sur <b>vos</b> prix de catalogue. L'IA n'invente pas de tarif. Vous validez avant envoi."
    ))
    s.append(photo(LAND / "hero-desk.jpg", 160 * mm, 0.52))
    s.append(P("Bureau type: le brouillon est pret, le dernier mot reste humain.", "cap"))

    s.append(P("2. Parcours devis", "h1"))
    s.append(img(ASSETS / "schema-parcours.png", 172 * mm))
    s.append(P(
        "Collecter, lire, rapprocher, controler, editer, PDF. Les calculs (HT, TVA 20/10/5,5/0, marge interne) "
        "restent dans FastAPI. Hermes et Ollama ne signent pas."
    ))

    s.append(P("3. Fonctionnalites", "h1"))
    s.append(bullets([
        "Auth JWT, roles owner / admin / operator / viewer / billing_admin, isolation par tenant_id.",
        "Extraction IA multilingue (PDF, image, texte). Modele leger qwen2.5:14b.",
        "Decomposition materiaux (ballon ECS, accessoires, etc.) au lieu de recopier le titre.",
        "Rapprochement catalogue avec score et motif. Recalcul si le catalogue change.",
        "Lots et sous-lots TCE, heures de main-d'oeuvre, jours de deplacement, equipe.",
        "Editeur: lignes typees, TVA par ligne, marge masquee sur le PDF client, ajout depuis le catalogue.",
        "PDF Pro Forma (SIRET, assurance, validite, acceptation).",
        "Journal d'audit, membres, i18n FR/EN, landing produit, identite visuelle (logo lockup).",
        "MCP lecture seule (demandes, devis, catalogue) pour l'agent Perplexity.",
    ]))

    s.append(P("4. Architecture v2", "h1"))
    s.append(img(ASSETS / "schema-architecture.png", 172 * mm))
    s.append(P(
        "Le frontend vit sur Hostinger (build React manuel). L'API FastAPI tourne sur Render (Francfort). "
        "Postgres est sur Supabase (UE). L'IA locale est sur un VPS OVH Ubuntu 24.04 "
        "(8 vCPU, 24 Go RAM, 200 Go NVMe, IP 162.19.44.2) avec Ollama, Hermes Agent, n8n et Caddy.<super>1</super>"
    ))
    s.append(table(
        [
            ["Couche", "Ou", "Role"],
            ["React + Tailwind", "Hostinger / blueseatra.com", "UI, landing, editeur"],
            ["FastAPI", "Render / blueseatra-api.onrender.com", "Metier, prix, PDF, auth"],
            ["PostgreSQL", "Supabase eu-west-1", "schema blueseatra"],
            ["Ollama", "ia.blueseatra.com", "Inference locale /api/chat"],
            ["Hermes", "hermes.blueseatra.com", "Gateway /v1/chat/completions"],
            ["n8n", "n8n.blueseatra.com", "Ingestion omnicanale (cible)"],
        ],
        [38 * mm, 62 * mm, 70 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Caddy termine le TLS et exige X-Api-Key. Les ports 11434 et 8642 ne sont pas publies. "
        "API_SERVER_HOST=0.0.0.0 uniquement sur le reseau Docker.<super>2</super>"
    ))

    s.append(P("5. Routage IA", "h1"))
    s.append(img(ASSETS / "schema-routage.png", 172 * mm))
    s.append(table(
        [
            ["Role", "Modele", "Chemin"],
            ["Extraction", "qwen2.5:7b (texte) / qwen2.5vl:7b (fichier, vision)", "FastAPI → Ollama /api/chat"],
            ["Raisonnement materiaux", "gpt-oss:20b, think gradue low/medium/high (defaut medium)", "FastAPI → Ollama /api/chat direct"],
            ["Repli raisonnement", "hermes3 (sans raisonnement natif, seul repli fonctionnel restant)", "Ollama"],
            ["Prix / TVA / marge", "deterministe", "FastAPI uniquement"],
        ],
        [48 * mm, 74 * mm, 48 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Mise a jour du 23 aout 2026 (63 Go liberes) : gemma4:26b, qwen3.6:27b, qwen3:14b, deepseek-r1:14b, "
        "qwen2.5:14b et Phi-4-reasoning-vision-15B ont ete supprimes du VPS. gpt-oss:20b (deja installe, 13 Go, "
        "20,9B parametres, quantification MXFP4) reprend le role de raisonnement materiaux : seul modele restant avec capacite \u00abthinking\u00bb "
        "confirmee (`ollama show gpt-oss:20b`), mais ne peut pas desactiver son raisonnement -- seulement en "
        "regler la profondeur via HERMES_REASONING_EFFORT (low/medium/high). Sans vision : l'extraction de "
        "fichier reste sur qwen2.5vl:7b. Hermes n'a pas de slot nomme raisonnement: le modele principal est "
        "celui avec lequel l'agent pense.<super>4</super> OLLAMA_MAX_LOADED_MODELS=1. mem_limit Ollama 18g."
    ))

    s.append(P("5b. Cartographie as-is / cible v2", "h1"))
    s.append(P(
        "Source: Cartographie Blueseatra v2 (16 aout 2026). v1 = console + un LLM pour extraire. "
        "v2 ajoute n8n omnicanal, Hermes multi-modeles, et un objet canonique unique. "
        "Facturation carte hors v2 initiale."
    ))
    s.append(table(
        [
            ["Couche", "As-is", "Cible v2"],
            ["Entree", "Upload / collage UI", "n8n: sites, IMAP, Drive, CRM, WhatsApp"],
            ["Normalisation", "FastAPI requests.extracted", "Objet canonique n8n avant l'IA"],
            ["IA", "Un appel Ollama", "Extracteur 14B, redacteur 27B, raisonneur Gemma"],
            ["Calcul", "matching.py deterministe", "Inchange"],
            ["Sortie", "Editeur + PDF", "Idem + email / CRM / Slack / ERP"],
        ],
        [32 * mm, 62 * mm, 76 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Objet canonique (aucun connecteur ne parle au moteur dans son format natif): "
        "tenant_id, source_type (webform|email|crm|whatsapp|drive|erp|ui), source_ref, "
        "contact_*, message_text, attachments, site_address, requested_service, urgency, thread_id, received_at. "
        "Statuts anti-rejeu: recu, analyse, a valider, devis genere."
    ))
    s.append(P(
        "Moteur devis: types material, labor, travel, note, page_break, lot, sublot. "
        "Lots TCE auto: Gros oeuvre, Platrerie, Electricite, Plomberie, CVC, Sols, Peinture, Serrurerie, Maintenance. "
        "Baremes skill: spot 0,45 h/u, ballon ECS 4,5 h, min visite 2 h, +1,25 h install/repli, max 7 h/j, "
        "MO arrondie a l'heure superieure. Defaut 42 EUR HT/h, 40 EUR HT/jour IDF, fournitures x 1,40."
    ))

    s.append(P("5c. Pack n8n P1", "h1"))
    s.append(P(
        "Source: Guide import n8n P1. Workflows inactifs, aucun secret inclus. "
        "Import un fichier a la fois (menu n8n Import from File)."
    ))
    s.append(table(
        [
            ["Fichier", "Role"],
            ["WF-normalize-ai-quote.json", "Hub Normalize then AI then Quote"],
            ["WF-web-webhook.json", "Sites clients"],
            ["WF-email-imap.json", "IMAP generique"],
            ["WF-email-zoho.json", "Zoho Mail imap.zoho.com:993"],
            ["WF-email-gmail.json", "Gmail"],
            ["WF-email-outlook.json", "Outlook 365"],
        ],
        [72 * mm, 98 * mm],
    ))
    s.append(Spacer(1, 2 * mm))
    s.append(P(
        "Credentials: Blueseatra JWT (Authorization Bearer d'un owner), boite mail par tenant. "
        "Remplacer REMPLACER_TENANT_ID. Activer le hub d'abord, puis un canal test. "
        "Hub: https://n8n.blueseatra.com/webhook/blueseatra-normalize "
        "Site: https://n8n.blueseatra.com/webhook/blueseatra-intake "
        "Le pack ne calcule pas de prix, n'active pas Drive/CRM/WhatsApp (P2+)."
    ))

    s.append(P("6. Modele de donnees", "h1"))
    s.append(P("14 tables PostgreSQL, cles UUID, champs dynamiques en JSONB. Filtrage systematique par tenant_id."))
    s.append(table(
        [
            ["Table", "Role"],
            ["users / tenants / tenant_users", "Comptes, espaces, roles"],
            ["catalogs / catalog_versions / pricing_items", "Catalogue versionne, attributs dynamiques"],
            ["requests", "Demandes + extraction JSONB"],
            ["quotes / quote_versions", "Devis, lignes, snapshot tarifaire"],
            ["import_jobs / import_errors", "Imports CSV"],
            ["audit_logs", "Journal"],
            ["settings_integrations / company_profiles", "IA, n8n, mentions PDF"],
        ],
        [78 * mm, 92 * mm],
    ))

    s.append(P("7. Variables d'environnement", "h1"))
    s.append(P("Backend Render (secrets hors Git):", "h3"))
    s.append(table(
        [
            ["Variable", "Usage"],
            ["DATABASE_URL", "Pooler Supabase :6543"],
            ["JWT_SECRET / APP_ENCRYPTION_KEY", "Auth et secrets au repos"],
            ["HERMES_BASE_URL", "https://ia.blueseatra.com"],
            ["HERMES_API_KEY", "X-Api-Key = OLLAMA_API_KEY VPS"],
            ["HERMES_EXTRACT_MODEL", "qwen2.5:7b"],
            ["HERMES_REASONING_MODEL", "gpt-oss:20b"],
            ["HERMES_REASONING_EFFORT", "medium (low/medium/high)"],
            ["HERMES_GATEWAY_URL", "https://hermes.blueseatra.com"],
            ["HERMES_GATEWAY_KEY", "API_SERVER_KEY du VPS (Bearer)"],
            ["MCP_API_KEY / MCP_TENANT_ID", "Connecteur lecture seule"],
            ["DB_SCHEMA", "blueseatra (attention: render.yaml historique public)"],
        ],
        [62 * mm, 108 * mm],
    ))
    s.append(Spacer(1, 2 * mm))
    s.append(P("VPS ovh-ai-stack: OLLAMA_API_KEY, API_SERVER_KEY, HERMES_MODEL=gpt-oss:20b. Ne jamais coller les cles dans le chat."))

    s.append(P("8. Securite", "h1"))
    s.append(bullets([
        "JWT fort, bcrypt, role relu en base (pas depuis le token seul).",
        "Isolation tenant + 404 inter-espaces.",
        "Cles IA tenant chiffrees Fernet.",
        "CORS origines explicites. Upload 15 Mo.",
        "Caddy: TLS, X-Api-Key, aucun port modele expose.",
        "API Hermes: Bearer distinct, max_concurrent_runs=1, pas de publication 8642.",
        "RLS deny-all cote PostgREST public.",
    ]))

    s.append(P("9. Mode d'emploi", "h1"))
    s.append(bullets([
        "Creer un espace (/signup).",
        "Importer le catalogue CSV (mapping colonnes, activer une version).",
        "Creer une demande (texte ou fichier). L'IA extrait.",
        "Generer un brouillon. Verifier les lignes, lots, TVA.",
        "Ajouter depuis le catalogue si besoin (brouillon uniquement).",
        "Renseigner le profil societe. Valider. Telecharger le PDF.",
    ]))
    s.append(photo(LAND / "catalog.jpg", 150 * mm, 0.72))
    s.append(P("Le catalogue reste la seule source de prix.", "cap"))

    s.append(KeepTogether([
        P("10. API (extrait)", "h1"),
        table(
            [
                ["Methode", "Route", "Role"],
                ["POST", "/api/auth/login", "Connexion"],
                ["POST", "/api/requests", "Nouvelle demande"],
                ["POST", "/api/requests/{id}/process", "Relancer l'extraction"],
                ["POST", "/api/quotes/draft", "Brouillon depuis une demande"],
                ["GET", "/api/catalog/search", "Picker catalogue"],
                ["GET", "/api/quotes/{id}/pdf", "PDF Pro Forma"],
                ["POST", "/mcp", "Outils lecture seule Perplexity"],
            ],
            [28 * mm, 72 * mm, 70 * mm],
        ),
    ]))

    s.append(P("11. Frontend", "h1"))
    s.append(P(
        "Routes: / landing publique, /login /signup, /app tableau de bord, demandes, catalogues, devis, membres, audit, parametres. "
        "Logo dans public/brand/. Landing refondue (PR 26): parcours, temps gagne, fonctions, photos."
    ))
    s.append(photo(LAND / "chantier.jpg", 170 * mm, 0.40))
    s.append(P("Identite: navy #193852, teal #438C88, papier #F7F4EE.", "cap"))

    s.append(P("12. Deploiement", "h1"))
    s.append(bullets([
        "Frontend: git pull && yarn build puis upload Hostinger du dossier build.",
        "Backend: Render auto-deploy depuis main (region Francfort).",
        "IA: git pull sur le VPS (cle github_ovh_ai_stack) puis docker compose up -d --force-recreate hermes.",
        "DNS A: ia / n8n / hermes.blueseatra.com → 162.19.44.2.",
    ]))

    s.append(P("13. Journal aout 2026", "h1"))
    s.append(table(
        [
            ["Date", "Livrable"],
            ["15-16 aout", "Stack OVH, qwen3.6:27b, cartographie v2"],
            ["17 aout", "gemma4:26b installe, ADR-003, API Hermes ADR-004"],
            ["17 aout", "PR 22: extract 14B / reason Gemma via gateway"],
            ["17 aout", "Test devis BS-2026-0017 (ballon ECS)"],
            ["17 aout", "Logo + landing (PR 24, 25, 26)"],
            ["23 aout", "Suppression de 6 modeles VPS (63 Go), repointage extract/vision"],
            ["23 aout", "PR 47: X-Hermes-Session-Id (ADR-005 ovh-ai-stack)"],
            ["23 aout", "PR 48: gpt-oss:20b modele de raisonnement ; PR 49: niveau gradue"],
        ],
        [36 * mm, 134 * mm],
    ))

    s.append(P("14. Sources", "h1"))
    for i, (name, url) in enumerate(SOURCES, 1):
        s.append(P(f'{i}. {name}: <a href="{url}" color="blue">{url}</a>', "foot"))
    return s


def story_en():
    s = []
    logo = BRAND / "blueseatra-lockup.png"
    if logo.exists():
        s.append(Spacer(1, 28 * mm))
        s.append(Image(str(logo), width=90 * mm, height=30 * mm, hAlign="CENTER"))
    s.append(Spacer(1, 16 * mm))
    s.append(P("Product and technical documentation", "cover"))
    s.append(Spacer(1, 4 * mm))
    s.append(P("AI-assisted B2B quoting SaaS for building trades", "sub"))
    s.append(Spacer(1, 8 * mm))
    s.append(P("Version 2  ·  17 August 2026", "center"))
    s.append(P("FastAPI · React · Supabase · Ollama · Hermes Agent", "center"))
    s.append(PageBreak())

    s.append(P("1. Overview", "h1"))
    s.append(P(
        "Blueseatra is a multi-tenant platform for SMEs in construction, multi-trade fit-out and maintenance. "
        "Each company has an isolated workspace: users, catalog, requests and quotes. "
        "The product reads a raw request (email, PDF, photo, text) and prepares a draft quote on <b>your</b> catalog prices. "
        "The AI never invents a tariff. You validate before sending."
    ))
    s.append(photo(LAND / "hero-desk.jpg", 160 * mm, 0.52))
    s.append(P("Typical desk: the draft is ready, the last word stays human.", "cap"))

    s.append(P("2. Quote path", "h1"))
    s.append(img(ASSETS / "schema-parcours.png", 172 * mm))
    s.append(P(
        "Collect, read, match, check, edit, PDF. Amounts (ex-VAT, French VAT 20/10/5.5/0, internal margin) "
        "stay in FastAPI. Hermes and Ollama do not sign."
    ))

    s.append(P("3. Features", "h1"))
    s.append(bullets([
        "JWT auth, roles owner / admin / operator / viewer / billing_admin, tenant_id isolation.",
        "Multilingual AI extraction (PDF, image, text) on qwen2.5:14b.",
        "Material breakdown instead of repeating the title.",
        "Catalog matching with score and reason. Rematch when the catalog changes.",
        "TCE lots and sub-lots, labor hours, travel days, crew size.",
        "Editor: typed lines, per-line VAT, margin hidden on the client PDF, add from catalog.",
        "Pro forma PDF (SIRET, insurance, validity, acceptance).",
        "Audit log, members, FR/EN, product landing, lockup brand.",
        "Read-only MCP (requests, quotes, catalog) for the Perplexity agent.",
    ]))

    s.append(P("4. Architecture v2", "h1"))
    s.append(img(ASSETS / "schema-architecture.png", 172 * mm))
    s.append(P(
        "The frontend lives on Hostinger (manual React build). FastAPI runs on Render (Frankfurt). "
        "Postgres is on Supabase (EU). Local AI sits on an OVH Ubuntu 24.04 VPS "
        "(8 vCPU, 24 GB RAM, 200 GB NVMe, 162.19.44.2) with Ollama, Hermes Agent, n8n and Caddy.<super>1</super>"
    ))
    s.append(table(
        [
            ["Layer", "Where", "Role"],
            ["React + Tailwind", "Hostinger / blueseatra.com", "UI, landing, editor"],
            ["FastAPI", "Render / blueseatra-api.onrender.com", "Domain, prices, PDF, auth"],
            ["PostgreSQL", "Supabase eu-west-1", "blueseatra schema"],
            ["Ollama", "ia.blueseatra.com", "Local inference /api/chat"],
            ["Hermes", "hermes.blueseatra.com", "Gateway /v1/chat/completions"],
            ["n8n", "n8n.blueseatra.com", "Omnichannel intake (target)"],
        ],
        [38 * mm, 62 * mm, 70 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Caddy terminates TLS and requires X-Api-Key. Ports 11434 and 8642 are not published. "
        "API_SERVER_HOST=0.0.0.0 only on the Docker network.<super>2</super>"
    ))

    s.append(P("5. AI routing", "h1"))
    s.append(img(ASSETS / "schema-routage.png", 172 * mm))
    s.append(table(
        [
            ["Role", "Model", "Path"],
            ["Extraction", "qwen2.5:7b (text) / qwen2.5vl:7b (file, vision)", "FastAPI → Ollama /api/chat"],
            ["Materials reasoning", "gpt-oss:20b, graduated think low/medium/high (default medium)", "FastAPI → Ollama /api/chat direct"],
            ["Reasoning fallback", "hermes3 (no native reasoning, only remaining functional fallback)", "Ollama"],
            ["Price / VAT / margin", "deterministic", "FastAPI only"],
        ],
        [48 * mm, 74 * mm, 48 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Updated 23 August 2026 (63 GB freed): gemma4:26b, qwen3.6:27b, qwen3:14b, deepseek-r1:14b, qwen2.5:14b "
        "and Phi-4-reasoning-vision-15B were removed from the VPS. gpt-oss:20b (already installed, 13 GB, 20.9B "
        "parameters, MXFP4 quantization) took over materials reasoning: the only remaining model with confirmed "
        "thinking capability (`ollama show gpt-oss:20b`), but it cannot disable reasoning -- only tune its depth "
        "via HERMES_REASONING_EFFORT (low/medium/high). No vision: file extraction stays on qwen2.5vl:7b. "
        "Hermes has no named reasoning slot: the main model is what the agent thinks with.<super>4</super> "
        "OLLAMA_MAX_LOADED_MODELS=1. Ollama mem_limit 18g."
    ))

    s.append(P("5b. As-is vs v2 map", "h1"))
    s.append(P(
        "Source: Cartographie Blueseatra v2 (16 August 2026). v1 = console + one LLM. "
        "v2 adds n8n omnichannel intake, Hermes multi-model routing, and one canonical request object. "
        "Card billing stays out of the first v2 cut."
    ))
    s.append(table(
        [
            ["Layer", "As-is", "v2 target"],
            ["Intake", "UI upload / paste", "n8n: sites, IMAP, Drive, CRM, WhatsApp"],
            ["Normalize", "FastAPI requests.extracted", "Canonical object in n8n before AI"],
            ["AI", "One Ollama call", "14B extract, 27B writer, Gemma reasoner"],
            ["Pricing", "matching.py deterministic", "Unchanged"],
            ["Output", "Editor + PDF", "Same + email / CRM / Slack / ERP"],
        ],
        [32 * mm, 62 * mm, 76 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Canonical object: tenant_id, source_type, source_ref, contact_*, message_text, attachments, "
        "site_address, requested_service, urgency, thread_id, received_at. "
        "Anti-replay statuses: received, analysed, to validate, quote generated."
    ))
    s.append(P(
        "Quote engine line types: material, labor, travel, note, page_break, lot, sublot. "
        "Auto TCE lots: structure, plaster, electrical, plumbing, HVAC, floors, paint, metalwork, maintenance. "
        "Skill rates: spot 0.45 h/unit, DHW cylinder 4.5 h, min visit 2 h, +1.25 h setup, max 7 h/day, "
        "labor rounded up. Default 42 EUR ex-VAT/h, 40 EUR/day Ile-de-France, supplies x 1.40."
    ))

    s.append(P("5c. n8n P1 pack", "h1"))
    s.append(P(
        "Source: n8n P1 import guide. Workflows ship inactive, no secrets. "
        "Import one file at a time."
    ))
    s.append(table(
        [
            ["File", "Role"],
            ["WF-normalize-ai-quote.json", "Hub Normalize then AI then Quote"],
            ["WF-web-webhook.json", "Client websites"],
            ["WF-email-imap.json", "Generic IMAP"],
            ["WF-email-zoho.json", "Zoho Mail imap.zoho.com:993"],
            ["WF-email-gmail.json", "Gmail"],
            ["WF-email-outlook.json", "Outlook 365"],
        ],
        [72 * mm, 98 * mm],
    ))
    s.append(Spacer(1, 2 * mm))
    s.append(P(
        "Credentials: Blueseatra JWT (owner Bearer) and one mailbox per tenant. "
        "Replace REMPLACER_TENANT_ID. Activate the hub first, then one test channel. "
        "Hub: https://n8n.blueseatra.com/webhook/blueseatra-normalize "
        "Site: https://n8n.blueseatra.com/webhook/blueseatra-intake "
        "The pack does not compute prices and does not enable Drive/CRM/WhatsApp (P2+)."
    ))

    s.append(P("6. Data model", "h1"))
    s.append(P("14 PostgreSQL tables, UUID keys, dynamic fields in JSONB. Every query filters on tenant_id."))
    s.append(table(
        [
            ["Table", "Role"],
            ["users / tenants / tenant_users", "Accounts, workspaces, roles"],
            ["catalogs / catalog_versions / pricing_items", "Versioned catalog, dynamic attributes"],
            ["requests", "Requests + extraction JSONB"],
            ["quotes / quote_versions", "Quotes, lines, price snapshot"],
            ["import_jobs / import_errors", "CSV imports"],
            ["audit_logs", "Audit"],
            ["settings_integrations / company_profiles", "AI, n8n, PDF legal block"],
        ],
        [78 * mm, 92 * mm],
    ))

    s.append(P("7. Environment", "h1"))
    s.append(P("Render backend (secrets stay out of Git):", "h3"))
    s.append(table(
        [
            ["Variable", "Use"],
            ["DATABASE_URL", "Supabase pooler :6543"],
            ["JWT_SECRET / APP_ENCRYPTION_KEY", "Auth and secrets at rest"],
            ["HERMES_BASE_URL", "https://ia.blueseatra.com"],
            ["HERMES_API_KEY", "X-Api-Key = VPS OLLAMA_API_KEY"],
            ["HERMES_EXTRACT_MODEL", "qwen2.5:7b"],
            ["HERMES_REASONING_MODEL", "gpt-oss:20b"],
            ["HERMES_REASONING_EFFORT", "medium (low/medium/high)"],
            ["HERMES_GATEWAY_URL", "https://hermes.blueseatra.com"],
            ["HERMES_GATEWAY_KEY", "VPS API_SERVER_KEY (Bearer)"],
            ["MCP_API_KEY / MCP_TENANT_ID", "Read-only connector"],
            ["DB_SCHEMA", "blueseatra (watch historical public in render.yaml)"],
        ],
        [62 * mm, 108 * mm],
    ))
    s.append(Spacer(1, 2 * mm))
    s.append(P("VPS ovh-ai-stack: OLLAMA_API_KEY, API_SERVER_KEY, HERMES_MODEL=gpt-oss:20b. Never paste keys in chat."))

    s.append(P("8. Security", "h1"))
    s.append(bullets([
        "Strong JWT, bcrypt, role re-read from the database.",
        "Tenant isolation and cross-tenant 404.",
        "Tenant AI keys encrypted with Fernet.",
        "Explicit CORS origins. 15 MB uploads.",
        "Caddy: TLS, X-Api-Key, no model ports exposed.",
        "Hermes API: separate Bearer, max_concurrent_runs=1, 8642 unpublished.",
        "PostgREST public: RLS deny-all.",
    ]))

    s.append(P("9. End-user path", "h1"))
    s.append(bullets([
        "Create a workspace (/signup).",
        "Import the CSV catalog (map columns, activate a version).",
        "Create a request (text or file). AI extracts.",
        "Generate a draft. Check lines, lots, VAT.",
        "Add from catalog if needed (draft only).",
        "Fill the company profile. Validate. Download the PDF.",
    ]))
    s.append(photo(LAND / "catalog.jpg", 150 * mm, 0.72))
    s.append(P("The catalog remains the only price source.", "cap"))

    s.append(KeepTogether([
        P("10. API (excerpt)", "h1"),
        table(
            [
                ["Method", "Route", "Role"],
                ["POST", "/api/auth/login", "Login"],
                ["POST", "/api/requests", "New request"],
                ["POST", "/api/requests/{id}/process", "Re-run extraction"],
                ["POST", "/api/quotes/draft", "Draft from a request"],
                ["GET", "/api/catalog/search", "Catalog picker"],
                ["GET", "/api/quotes/{id}/pdf", "Pro forma PDF"],
                ["POST", "/mcp", "Read-only Perplexity tools"],
            ],
            [28 * mm, 72 * mm, 70 * mm],
        ),
    ]))

    s.append(P("11. Frontend", "h1"))
    s.append(P(
        "Routes: / public landing, /login /signup, /app dashboard, requests, catalogs, quotes, members, audit, settings. "
        "Logo in public/brand/. Landing rewrite (PR 26): path, time saved, features, photos."
    ))
    s.append(photo(LAND / "chantier.jpg", 170 * mm, 0.40))
    s.append(P("Identity: navy #193852, teal #438C88, paper #F7F4EE.", "cap"))

    s.append(P("12. Deployment", "h1"))
    s.append(bullets([
        "Frontend: git pull && yarn build then upload the build folder to Hostinger.",
        "Backend: Render auto-deploy from main (Frankfurt).",
        "AI: git pull on the VPS (github_ovh_ai_stack key) then docker compose up -d --force-recreate hermes.",
        "DNS A: ia / n8n / hermes.blueseatra.com → 162.19.44.2.",
    ]))

    s.append(P("13. August 2026 log", "h1"))
    s.append(table(
        [
            ["Date", "Deliverable"],
            ["15-16 Aug", "OVH stack, qwen3.6:27b, v2 map"],
            ["17 Aug", "gemma4:26b installed, ADR-003, Hermes API ADR-004"],
            ["17 Aug", "PR 22: extract 14B / reason Gemma via gateway"],
            ["17 Aug", "Quote test BS-2026-0017 (DHW cylinder)"],
            ["17 Aug", "Logo + landing (PRs 24, 25, 26)"],
            ["23 Aug", "Removed 6 VPS models (63 GB), repointed extract/vision"],
            ["23 Aug", "PR 47: X-Hermes-Session-Id (ADR-005 ovh-ai-stack)"],
            ["23 Aug", "PR 48: gpt-oss:20b reasoning model; PR 49: graduated level"],
        ],
        [36 * mm, 134 * mm],
    ))

    s.append(P("14. Sources", "h1"))
    for i, (name, url) in enumerate(SOURCES, 1):
        s.append(P(f'{i}. {name}: <a href="{url}" color="blue">{url}</a>', "foot"))
    return s


def build(path: Path, title: str, story, first=cover_footer):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        title=title,
        author="Perplexity Computer",
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(story, onFirstPage=first, onLaterPages=header_footer)


if __name__ == "__main__":
    build(DOCS / "Blueseatra_Documentation_FR.pdf", "Blueseatra Documentation (FR)", story_fr())
    build(DOCS / "Blueseatra_Documentation_EN.pdf", "Blueseatra Documentation (EN)", story_en())
    print("wrote", DOCS / "Blueseatra_Documentation_FR.pdf")
    print("wrote", DOCS / "Blueseatra_Documentation_EN.pdf")
