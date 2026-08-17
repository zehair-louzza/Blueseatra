#!/usr/bin/env python3
"""Rapport de jury Blueseatra — architecture, genese, cible."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from PIL import Image as PILImage
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
OUT = DOCS / "Blueseatra_Rapport_Jury_Architecture.pdf"
FONT_DIR = Path("/tmp/fonts")
FONT_DIR.mkdir(exist_ok=True)

NAVY = HexColor("#193852")
TEAL = HexColor("#438C88")
INK = HexColor("#1c2834")
MUTE = HexColor("#5b6772")
LINE = HexColor("#D4D1CA")
ROW = HexColor("#F3F6F7")

SOURCES = [
    ("Ollama gemma4:26b", "https://ollama.com/library/gemma4:26b"),
    ("Gemma + Ollama", "https://ai.google.dev/gemma/docs/integrations/ollama"),
    ("Hermes API server", "https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server"),
    ("Hermes Docker", "https://hermes-agent.nousresearch.com/docs/user-guide/docker"),
    ("Hermes model config", "https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models"),
    ("Ollama library", "https://ollama.com"),
]


def register_fonts():
    files = {
        "Inter": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.ttf",
        "Inter-Bold": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Bold.ttf",
    }
    for name, url in files.items():
        dest = FONT_DIR / f"{name}.ttf"
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception:
                return False
        if dest.exists():
            pdfmetrics.registerFont(TTFont(name, str(dest)))
    return True


HAS = register_fonts()
FN = "Inter" if HAS else "Helvetica"
FB = "Inter-Bold" if HAS else "Helvetica-Bold"


def styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=FB, fontSize=15, leading=19, textColor=NAVY, spaceBefore=11, spaceAfter=7),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FB, fontSize=12, leading=16, textColor=NAVY, spaceBefore=8, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=FB, fontSize=10.5, leading=14, textColor=TEAL, spaceBefore=6, spaceAfter=3),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontName=FN, fontSize=9.4, leading=13.4, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6),
        "li": ParagraphStyle("li", parent=base["BodyText"], fontName=FN, fontSize=9.3, leading=12.8, textColor=INK, spaceAfter=2),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontName=FN, fontSize=8, leading=11, textColor=INK),
        "cellh": ParagraphStyle("cellh", parent=base["BodyText"], fontName=FB, fontSize=8, leading=11, textColor=white),
        "cap": ParagraphStyle("cap", parent=base["BodyText"], fontName=FN, fontSize=8, leading=11, textColor=MUTE, spaceAfter=8, alignment=TA_CENTER),
        "foot": ParagraphStyle("foot", parent=base["Normal"], fontName=FN, fontSize=7.5, leading=10, textColor=MUTE),
        "cover": ParagraphStyle("cover", parent=base["Title"], fontName=FB, fontSize=22, leading=27, textColor=NAVY, alignment=TA_CENTER),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName=FN, fontSize=11.5, leading=15, textColor=TEAL, alignment=TA_CENTER),
        "center": ParagraphStyle("center", parent=base["Normal"], fontName=FN, fontSize=9.5, leading=13, textColor=MUTE, alignment=TA_CENTER),
        "toc": ParagraphStyle("toc", parent=base["Normal"], fontName=FN, fontSize=10, leading=16, textColor=INK),
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
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, ROW]),
            ]
        )
    )
    return t


def fitted(path, w=170 * mm, max_h=88 * mm):
    p = Path(path)
    if not p.exists():
        return Spacer(1, 1)
    iw, ih = PILImage.open(p).size
    h = w * (ih / iw)
    if h > max_h:
        h = max_h
        w = h * (iw / ih)
    im = Image(str(p), width=w, height=h)
    im.hAlign = "CENTER"
    return im


def header_footer(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FN, 8)
    c.drawString(16 * mm, A4[1] - 8 * mm, "Blueseatra  Rapport de jury")
    c.drawRightString(A4[0] - 16 * mm, A4[1] - 8 * mm, "Aout 2026")
    c.setFillColor(MUTE)
    c.setFont(FN, 8)
    c.drawString(16 * mm, 10 * mm, "MBA ESG Paris  ·  Confidentiel jury")
    c.drawRightString(A4[0] - 16 * mm, 10 * mm, str(doc.page))
    c.setStrokeColor(LINE)
    c.line(16 * mm, 14 * mm, A4[0] - 16 * mm, 14 * mm)
    if doc.page > 1:
        c.setFont(FN, 6.5)
        c.drawString(16 * mm, 6 * mm, "Sources officielles en derniere page")
    c.restoreState()


def cover_footer(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, 0, A4[0], 24 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FN, 8)
    c.drawCentredString(A4[0] / 2, 12 * mm, "ANELEC TECHNIQUE ET CONCEPT  ·  commanditaire  ·  Projet 1")
    c.restoreState()


def story():
    s = []
    logo = BRAND / "blueseatra-lockup.png"
    if logo.exists():
        s.append(Spacer(1, 22 * mm))
        s.append(Image(str(logo), width=88 * mm, height=29 * mm, hAlign="CENTER"))
    s.append(Spacer(1, 12 * mm))
    s.append(P("Rapport d'architecture et de trajectoire produit", "cover"))
    s.append(Spacer(1, 4 * mm))
    s.append(P("De la genese au produit cible", "sub"))
    s.append(Spacer(1, 3 * mm))
    s.append(P("Analyse experte pour presentation de jury", "sub"))
    s.append(Spacer(1, 12 * mm))
    s.append(P("MBA ESG Paris  ·  Big Data et Intelligence Artificielle", "center"))
    s.append(P("Candidat : Louzza Zehair", "center"))
    s.append(P("Commanditaire : ANELEC TECHNIQUE ET CONCEPT", "center"))
    s.append(P("Responsable de programme : M. Olivier Jarrar", "center"))
    s.append(Spacer(1, 6 * mm))
    s.append(P("Version 1  ·  17 aout 2026", "center"))
    s.append(P("Document autonome, fondé sur le depot, la cartographie v2 et les ADR", "center"))
    s.append(PageBreak())

    s.append(P("Sommaire", "h1"))
    for line in [
        "1. Note de lecture et posture de l'expert",
        "2. Synthese executive",
        "3. Problematique metier et positionnement",
        "4. Chronologie : les etapes reellement suivies",
        "5. Architecture as-is du site et de la plateforme",
        "6. Moteur de devis : ce que l'IA ne doit pas faire",
        "7. Orchestration IA souveraine",
        "7b. Instances, integrations et deploiement",
        "8. Donnees, isolation et RGPD",
        "9. Analyse experte : decisions, forces, dettes",
        "10. Produit cible et feuille de route",
        "11. Recommandations au jury et conclusion",
        "12. Sources",
    ]:
        s.append(P(line, "toc"))
    s.append(Spacer(1, 6 * mm))
    s.append(P(
        "Ce rapport n'invente aucun indicateur commercial. Les volumes cites sont ceux "
        "du snapshot live Supabase et GitHub du 17 aout 2026. Les ecarts connus (n8n encore inactif, "
        "facturation hors perimetre, qualite d'extraction encore fragile) sont assumes."
    ))

    s.append(P("1. Note de lecture et posture de l'expert", "h1"))
    s.append(P(
        "Blueseatra n'est pas un generateur de devis magique. C'est un systeme d'exploitation "
        "du devis B2B pour PME du batiment, du TCE et de la maintenance. L'IA lit une demande "
        "desordonnee. Le moteur tarifaire calcule. L'operateur signe. Cette separation est "
        "la these architecturale du projet, et c'est elle que le jury doit juger."
    ))
    s.append(P(
        "Le present document adopte le point de vue d'un architecte produit et systemes : "
        "ce qui a ete construit, pourquoi, ce qui tient, ce qui reste fragile, et ce que "
        "devient le produit s'il atteint sa cible v2. Le candidat n'est pas evalue ici "
        "sur une promesse marketing. Il l'est sur une chaine reelle, deployee, avec des "
        "contraintes de RAM, de souverainete et de multi-tenant."
    ))
    s.append(P(
        "Le dossier MBA est limite au Projet 1. ANELEC TECHNIQUE ET CONCEPT est le "
        "commanditaire et l'entreprise d'etude, a la place de l'ancien cas fictif "
        "BTP Solutions. Le diplome vise est un MBA Big Data et IA, ESG Paris, horizon 2027."
    ))

    s.append(P("2. Synthese executive", "h1"))
    s.append(P(
        "En six mois, le projet est passe d'une intention (transformer une demande brute "
        "en brouillon de devis) a une plateforme multi-tenant en production partielle : "
        "frontend public sur Hostinger, API FastAPI sur Render (Francfort), PostgreSQL "
        "Supabase en Union europeenne, inference locale sur VPS OVH Roubaix."
    ))
    s.append(bullets([
        "Produit : SaaS B2B multi-tenant. Catalogue du tenant = seule source de prix.",
        "Site : landing + console (demandes, catalogues, editeur, PDF, audit, membres).",
        "IA : extraction qwen2.5:14b via Ollama ; raisonnement via Hermes (gemma4:26b).",
        "Regle non negociable : FastAPI calcule HT, TVA, marge, heures et deplacement.",
        "Cible v2 : n8n devient le hub d'entree ; objet canonique unique par canal.",
        "Etat honnete : le cœur devis existe ; l'intake omnicanal et la facturation non.",
    ]))
    s.append(P(
        "Le verdict d'expert : l'architecture est juste pour un produit reglementaire "
        "de devis. La dette n'est pas conceptuelle, elle est operationnelle : deploiement "
        "frontend manuel, Render Free qui s'endort, schema render.yaml encore ambigu, "
        "workflows n8n livres mais inactifs."
    ))

    s.append(P("3. Problematique metier et positionnement", "h1"))
    s.append(P("3.1 Le vrai probleme", "h2"))
    s.append(P(
        "Chez une PME TCE, le devis n'est pas un document. C'est le goulot. La demande "
        "arrive en email, PDF scanne, photo de chantier, SMS ou appel note a la main. "
        "L'operateur reconstitue le besoin, cherche dans un tarif Excel, invente parfois "
        "une ligne, oublie un accessoire, se trompe de TVA, puis perd deux heures a "
        "mettre en page. Le risque n'est pas seulement le temps. C'est le prix faux, "
        "donc la marge ou le litige."
    ))
    s.append(P(
        "Les outils existants (ERP, tableurs, logiciels de devis generalistes) exigent "
        "que l'humain structure d'abord. Blueseatra inverse la charge : le systeme "
        "structure, l'humain controle. Mais il refuse de laisser un LLM signer un tarif. "
        "C'est la difference entre un demonstrateur IA et un produit industrialisable."
    ))
    s.append(P("3.2 Pour qui", "h2"))
    s.append(P(
        "Le persona primaire est l'exploitant ou le charge d'affaires d'une PME "
        "multi-techniques (electricite, plomberie, CVC, second oeuvre, maintenance). "
        "ANELEC fournit le cas reel : catalogues heterogenes, demandes peu normees, "
        "besoin de mentions legales francaises (SIRET, assurance, validite, acceptation)."
    ))
    s.append(P("3.3 Ce que le produit vend vraiment", "h2"))
    s.append(P(
        "Pas une IA. Un brouillon defensible. Le temps gagne n'est pas un pourcentage "
        "affiche : il est dans la suppression de la ressaisie et du recopie de titre. "
        "Un ballon ECS ne devient pas une ligne unique. Il devient ballon, groupe de "
        "securite, flexibles, vannes, joints. Le catalogue dit le prix. L'editeur permet "
        "de corriger. Le PDF n'apparait qu'apres validation humaine."
    ))

    s.append(P("4. Chronologie : les etapes reellement suivies", "h1"))
    s.append(P(
        "Le jury doit voir une trajectoire, pas une stack tombee du ciel. Les dates "
        "ci-dessous sont celles du dossier, des sessions de conception et du depot Git."
    ))
    s.append(table(
        [
            ["Periode", "Etape", "Decision"],
            ["Avr-mai 2026", "Cadrage MBA ESG / RNCP", "Projet academique Big Data et IA"],
            ["21 juin 2026", "Vision produit", "SaaS multi-tenant, canaux multiples, IA lit, moteur calcule"],
            ["26 juin 2026", "Dossier Projet 1", "ANELEC commanditaire, cas fictif abandonne"],
            ["24-25 juin", "Socle en ligne", "React Hostinger, FastAPI Render, schema blueseatra"],
            ["25 juin", "Premier parcours live", "Signup, API, dashboard confirmes"],
            ["Juin-juil.", "Cœur metier", "Catalogue ouvert, editeur v2, PDF, RBAC, audit, i18n"],
            ["Juin-juil.", "Migration donnees", "MongoDB vers Supabase via pg_adapter, RLS deny-all"],
            ["14 juil.", "Architecture officielle", "Emergent abandonne, IA sur VPS OVH"],
            ["Mi-juil.", "Souverainete", "Oracle US abandonne, UE uniquement"],
            ["15 aout", "Stack OVH validee", "Ollama + Caddy, extraction locale HTTP 200"],
            ["16 aout", "Cartographie v2", "n8n, objet canonique, 3 roles IA"],
            ["16-17 aout", "Hermes gateway", "API chat, PR 22, Gemma 4 26B-A4B"],
            ["17 aout", "Produit visible", "Logo, landing, picker, devis test BS-2026-0017"],
        ],
        [32 * mm, 52 * mm, 86 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P("4.1 Ce que cette trajectoire enseigne", "h2"))
    s.append(P(
        "Trois virages meritent d'etre nommes. Premier : sortir du cas fictif pour un "
        "commanditaire reel. Sans ANELEC, le catalogue ouvert et les lots TCE n'auraient "
        "pas de contrainte. Deuxieme : quitter Emergent et Mongo. Un prototype cloud "
        "unique cache les questions de souverainete, de cout token et de schema. "
        "Troisieme : accepter 24 Go de RAM. Cette contrainte a force le routage multi-modeles "
        "au lieu d'un 70B impossible. C'est de l'ingenierie, pas de la demonstration."
    ))

    s.append(P("5. Architecture as-is du site et de la plateforme", "h1"))
    s.append(P(
        "Le site public (https://blueseatra.com) n'est plus une page d'attente. Depuis "
        "la PR 26, la landing explique le parcours collecter, lire, rapprocher, controler, "
        "editer. Derriere, la console /app porte le produit. Le frontend est un build "
        "React 18 + Tailwind, uploade manuellement sur Hostinger. Ce choix est frugal. "
        "Il est aussi une dette : chaque PR UI exige yarn build puis un depot FTP/SFTP."
    ))
    s.append(fitted(ASSETS / "schema-architecture.png", 172 * mm, 82 * mm))
    s.append(P("Figure 1. Architecture deployee au 17 aout 2026.", "cap"))
    s.append(table(
        [
            ["Couche", "Ou", "Role aujourd'hui"],
            ["React + landing", "Hostinger / blueseatra.com", "Acquisition, auth, editeur"],
            ["FastAPI", "Render Francfort", "Metier, matching, PDF, JWT, MCP"],
            ["PostgreSQL 17", "Supabase eu-west-1", "14 tables, schema blueseatra"],
            ["Ollama", "ia.blueseatra.com", "Inference /api/chat, 1 modele charge"],
            ["Hermes 0.20.1", "hermes.blueseatra.com", "Gateway /v1/chat/completions"],
            ["n8n", "n8n.blueseatra.com", "Installe, pack P1 inactif"],
            ["Caddy", "VPS 162.19.44.2", "TLS, X-Api-Key, aucun port modele public"],
        ],
        [38 * mm, 58 * mm, 74 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P("5.1 Pourquoi cette topologie", "h2"))
    s.append(P(
        "Un monolith Kubernetes aurait ete un costume trop large. Le candidat a separe "
        "ce qui change a des rythmes differents. L'UI change souvent et peut etre statique. "
        "L'API porte l'etat et les secrets. La base exige des sauvegardes et une region UE. "
        "L'IA exige du GPU-less RAM et ne doit pas quitter le VPS. n8n est volontairement "
        "hors du chemin critique du prix."
    ))
    s.append(P(
        "VPS : Ubuntu 24.04, 8 vCPU, 24 Go RAM, 200 Go NVMe, swap 4 Go, IP 162.19.44.2. "
        "Ollama : mem_limit 18g, OLLAMA_MAX_LOADED_MODELS=1, contexte 8192, KEEP_ALIVE 10 min. "
        "Hermes : API_SERVER_HOST=0.0.0.0 dans Docker seulement, port 8642 non publie. "
        "Auth publique double : Caddy X-Api-Key puis Bearer Hermes.<super>3</super>"
    ))
    s.append(P("5.2 Modules du site", "h2"))
    s.append(table(
        [
            ["Route", "Fonction"],
            ["/", "Landing produit (parcours, valeur, photos, CTA)"],
            ["/login /signup", "Compte + premier tenant"],
            ["/app", "Tableau de bord"],
            ["/app/requests", "Intake + extraction"],
            ["/app/catalogs", "Versions, mapping CSV, activation"],
            ["/app/quotes/:id", "Editeur : lots, TVA, picker, validation"],
            ["/app/members /audit /settings", "RBAC, journal, IA, n8n, profil societe"],
            ["/app/billing", "Placeholder, hors v2"],
        ],
        [58 * mm, 112 * mm],
    ))

    s.append(P("6. Moteur de devis : ce que l'IA ne doit pas faire", "h1"))
    s.append(fitted(ASSETS / "schema-parcours.png", 172 * mm, 48 * mm))
    s.append(P("Figure 2. Parcours operateur. Le dernier mot reste humain.", "cap"))
    s.append(P(
        "Le pipeline FastAPI est le cœeur de these. Une demande (PDF, image, texte, DOCX) "
        "est extraite vers requests.extracted. matching.build_quote_lines ne lit que le "
        "catalogue actif. estimate_chantier propose des heures. _auto_labor_and_travel "
        "ajoute main-d'œuvre et deplacement. wrap_in_lots range en lots TCE. "
        "recompute_totals fige HT, TVA (20 / 10 / 5,5 / 0), marge interne. "
        "A la validation, pricing_snapshot gele les prix. Toute evolution = nouvelle version."
    ))
    s.append(P(
        "Types de lignes : material, labor, travel, note, page_break, lot, sublot. "
        "Lots automatiques : Gros œuvre, Platrerie, Electricite, Plomberie, CVC, Sols, "
        "Peinture, Serrurerie, Maintenance. Baremes skill (non contractuels, internes) : "
        "spot 0,45 h/u, ballon ECS 4,5 h, min visite 2 h, +1,25 h install/repli, "
        "max 7 h/j, MO arrondie a l'heure superieure. Defaut interne 42 EUR HT/h, "
        "40 EUR HT/jour IDF, coefficient fournitures 1,40. Ces chiffres sont des "
        "parametres de moteur, pas des engagements commerciaux."
    ))
    s.append(P(
        "Le 17 aout, le devis test BS-2026-0017 (ballon ECS, 697,69 EUR HT, brouillon) "
        "montre que la decomposition materiaux fonctionne. Il ne prouve pas, a lui seul, "
        "que le chemin Hermes a ete emprunte : l'extraction 14B suffit parfois. Un expert "
        "ne confond pas un brouillon reussi et une preuve d'orchestration."
    ))

    s.append(P("7. Orchestration IA souveraine", "h1"))
    s.append(fitted(ASSETS / "schema-routage.png", 172 * mm, 42 * mm))
    s.append(P("Figure 3. Routage extract / reason / repli.", "cap"))
    s.append(P(
        "Hermes Agent n'a pas de slots nommes extraction, generation, raisonnement. "
        "La configuration officielle n'expose que model, delegation, auxiliary et "
        "fallback_providers.<super>5</super> Le projet mappe donc des roles Blueseatra "
        "sur ces cles, sans inventer d'API."
    ))
    s.append(table(
        [
            ["Role Blueseatra", "Modele", "Chemin"],
            ["Extraction / classement", "qwen2.5:14b", "FastAPI → Ollama /api/chat"],
            ["Raisonnement materiaux", "gemma4:26b via hermes-agent", "FastAPI → Hermes /v1 + Bearer"],
            ["Repli raisonnement", "gemma4:26b puis qwen3.6:27b", "Ollama direct"],
            ["Vision (si image)", "gemma4:26b", "auxiliary.vision, pas de VL dedie"],
            ["Prix / TVA / marge", "aucun LLM", "FastAPI uniquement"],
        ],
        [52 * mm, 58 * mm, 60 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Gemma 4 26B-A4B est un MoE 25,2B parametres / 3,8B actifs, tag officiel "
        "gemma4:26b, quantification Q4_K_M, environ 17 Go.<super>1</super> "
        "Il tient dans 24 Go a condition qu'aucun second gros modele ne soit charge. "
        "provider: auto est interdit : la decouverte auxiliaire Hermes irait vers "
        "OpenRouter ou Nous Portal, donc hors UE."
    ))
    s.append(P(
        "Le fallback cloud litellm (OpenAI / Anthropic / Gemini) existe par tenant, "
        "chiffre Fernet. Il est un filet, jamais une source de prix. Si le VPS tombe, "
        "l'extraction peut continuer. Le tarif, lui, reste local et deterministe."
    ))

    s.append(P("7b. Instances, integrations et modes de deploiement", "h1"))
    s.append(P(
        "Quatre instances distinctes, quatre rythmes de deploiement. C'est volontaire."
    ))
    s.append(table(
        [
            ["Instance", "Hote / URL", "Comment ca se deploie"],
            ["Frontend SPA", "Hostinger / blueseatra.com (HTTP 200)", "Manuel : git pull, yarn build, upload public_html"],
            ["API FastAPI", "Render Francfort / blueseatra-api (healthy)", "Auto-deploy sur merge main, uvicorn, /api/health"],
            ["Postgres", "Supabase eu-west-1 xmsxlochasjauhnxarvc", "Migrations SQL ; pooler :6543 ; pas de PostgREST metier"],
            ["IA locale", "VPS OVH 162.19.44.2", "git pull + docker compose --force-recreate hermes"],
            ["Ollama", "ia.blueseatra.com", "Compose mem_limit 18g, 1 modele charge"],
            ["Hermes", "hermes.blueseatra.com", "API 8642 interne, Caddy TLS + double cle"],
            ["n8n", "n8n.blueseatra.com", "Meme VPS ; pack P1 inactif"],
        ],
        [36 * mm, 72 * mm, 62 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Integrations actives : JWT maison (pas Auth Supabase), catalogue CSV, "
        "PDF ReportLab, MCP lecture seule POST /mcp (tenant ANELEC Test), "
        "webhook n8n sortant par tenant, litellm en filet cloud. "
        "GitHub : 26 PR fusionnees sur Blueseatra, PR 27 docs encore ouverte ; "
        "ovh-ai-stack PR 1 fusionnee (slots Hermes). "
        "Cible non allumee : Gmail, Outlook, Zoho, IMAP, Drive, CRM, WhatsApp, ERP."
    ))
    s.append(P(
        "Controles live de cette seance : API Render {status: healthy}, "
        "site public HTTP 200, Hermes /health refuse sans cle (donc expose mais protege), "
        "advisors securite Supabase : 0 lint."
    ))

    s.append(P("8. Donnees, isolation et RGPD", "h1"))
    s.append(P(
        "14 tables dans le schema blueseatra. Un clone vide existe encore dans public "
        "(0 ligne), vestige de migration. Le backend parle en role service, jamais via "
        "PostgREST. Isolation : filtre applicatif tenant_id + RLS deny-all. "
        "JSONB pour extracted, lines, pricing_snapshot, attributes, mapping."
    ))
    s.append(P(
        "Snapshot live Supabase (17 aout 2026, projet xmsxlochasjauhnxarvc, "
        "region eu-west-1, Postgres 17.6, statut ACTIVE_HEALTHY). "
        "7 tenants starter : blueseatra, ANELEC Test, ANELEC TECHNIQUE ET CONCEPT, "
        "Hanoutbrahim, Eventcater, 2 x Blueseatra Check (doublon a nettoyer). "
        "704 articles, 9 demandes (5 done, 1 needs_review, 3 failed), "
        "19 devis (18 brouillons, 1 valide), 99 entrees d'audit. "
        "schema public : 14 tables clones a 0 ligne. "
        "Ces volumes decrivent un laboratoire vivant, pas encore une base clients."
    ))
    s.append(P(
        "Donnees personnelles : Hostinger, Render UE, Supabase Irlande, OVH Roubaix. "
        "Caddy : HSTS, X-Frame-Options DENY, Referrer-Policy no-referrer. JWT fort au boot. "
        "RLS : schema public = deny_all. Table users = service_role only. "
        "Les autres tables blueseatra ont une policy authenticated ALL : inoffensif tant "
        "que l'app ne passe pas par PostgREST, dangereux si quelqu'un ouvre l'API Data. "
        "Le backend parle en role service + filtre tenant_id. "
        "MCP : lecture seule. n8n cible : une boite = un tenant."
    ))

    s.append(P("9. Analyse experte : decisions, forces, dettes", "h1"))
    s.append(P("9.1 Decisions qui tiennent", "h2"))
    s.append(bullets([
        "Separarer probabiliste et deterministe. C'est la seule facon de vendre un devis a un artisan sans trahir sa marge.",
        "Catalogue ouvert (item_label obligatoire, le reste en attributs). Les PME n'ont pas le meme Excel.",
        "Souverainete UE et interdiction de provider auto. Argument B2B plus fort qu'un LLM plus grand.",
        "Un seul gros modele en RAM. Contrainte transformee en architecture, pas en excuse.",
        "Objet canonique avant les connecteurs. Sans lui, chaque CRM casse le moteur.",
        "pg_adapter : migration Mongo sans reecrire server.py. Pragmatique, reversible, documentee.",
    ]))
    s.append(P("9.2 Dettes a nommer devant le jury", "h2"))
    s.append(table(
        [
            ["Ecart", "Impact", "Lecture experte"],
            ["n8n P1 inactif", "Intake v2 encore papier", "Le pack existe ; l'activation est un chantier ops, pas un concept"],
            ["render.yaml DB_SCHEMA=public", "Risque de lire le clone vide", "A corriger avant tout onboarding client"],
            ["3 demandes failed / 15 drafts", "Extraction encore fragile", "Normal a ce stade ; le raisonneur doit etre mesure, pas suppose"],
            ["Frontend Hostinger manuel", "UI live parfois en retard du Git", "Acceptable en Projet 1, pas en SaaS vendu"],
            ["Render Free peut dormir", "Latence a froid", "A budgeeter un always-on avant demo jury longue"],
            ["Billing placeholder", "Pas de modele de revenu code", "Hors these technique ; a traiter en strategie, pas en sprint"],
            ["MCP lecture seule", "L'agent ne cree pas de devis", "Sain pour la securite ; limiter la tentation d'automatiser la signature"],
        ],
        [48 * mm, 48 * mm, 74 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P("9.3 Ce que le projet demontre academiquement", "h2"))
    s.append(P(
        "Sur le referentiel Big Data et IA, le dossier n'est pas un notebook. Il montre "
        "un systeme : ingestion, modeles heterogenes, persistance, isolation, audit, "
        "contrainte materielle, gouvernance du prix. Le candidat a du arbitrer entre "
        "beaute du modele et responsabilite du devis. C'est exactement le type de "
        "conflit qu'un MBA IA doit apprendre a trancher."
    ))

    s.append(P("10. Produit cible et feuille de route", "h1"))
    s.append(P(
        "La cible v2 ne remplace pas le cœur. Elle change l'entree et la sortie. "
        "Aujourd'hui l'humain colle un PDF dans l'UI. Demain n8n recoit le mail, le "
        "formulaire site, le fichier Drive, plus tard le deal CRM. Tout devient le "
        "meme objet : tenant_id, source_type, contact, message_text, attachments, "
        "site_address, requested_service, urgency, thread_id, received_at. "
        "Statuts anti-rejeu : recu, analyse, a valider, devis genere."
    ))
    s.append(table(
        [
            ["Vague", "Livrable", "Statut"],
            ["P1", "Hub + webhook site + Gmail / Outlook / Zoho / IMAP", "JSON livres, inactifs"],
            ["P1", "Drive / OneDrive dossier demandes", "Specifie, non construit"],
            ["Fait", "Slots Hermes 14B / Gemma / repli 27B", "Branche, a mesurer en prod"],
            ["P2", "HubSpot, Zoho CRM, Pipedrive", "Backlog"],
            ["P3", "WhatsApp Business Cloud", "Backlog terrain"],
            ["P4", "ERP (Odoo / ERPNext) apres devis valide", "Interdit tant que le devis n'est pas stable"],
            ["P5", "Slack / Teams pour validation humaine", "Notification, pas de prix"],
            ["Hors v2", "Stripe, Salesforce, SAP, Shopify", "Explicite"],
        ],
        [22 * mm, 92 * mm, 56 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Le produit final, au sens jury, n'est pas un ERP. C'est une usine a brouillons "
        "defensables, branchee sur les canaux ou vivent deja les PME, avec un humain "
        "qui valide et un PDF Pro Forma qui sort. Si cette phrase tient, l'architecture "
        "a reussi. Si l'on promet un devis autonome sans controle, le projet a echoue "
        "ethiquement, meme si le modele est brillant."
    ))

    s.append(P("11. Recommandations au jury et conclusion", "h1"))
    s.append(P("11.1 Comment evaluer ce dossier", "h2"))
    s.append(bullets([
        "Juger la these (IA lit, moteur calcule, humain signe), pas le nombre de connecteurs allumes.",
        "Verifier le live : signup, une demande, un brouillon, un PDF. C'est le minimum honnete.",
        "Distinguer code merge et UI Hostinger. Une PR fusionnee n'est pas forcement en production front.",
        "Exiger le plan de correction render.yaml et l'activation d'un seul canal n8n, pas dix.",
        "Ne pas demander un 70B. Demander pourquoi 14B + 26B MoE + deterministe.",
    ]))
    s.append(P("11.2 Prochaines actions (ordre expert)", "h2"))
    s.append(P(
        "1) Aligner DB_SCHEMA sur blueseatra. 2) Activer uniquement le hub n8n et le "
        "webhook site sur le tenant ANELEC Test. 3) Mesurer si Hermes est vraiment "
        "appele (logs, latence, cas ambigus). 4) Automatiser le build Hostinger. "
        "5) Nettoyer les tenants doublons. 6) Garder le billing hors these jusqu'a "
        "ce que le devis soit fiable."
    ))
    s.append(P("11.3 Conclusion", "h2"))
    s.append(P(
        "Blueseatra est, a la date de ce rapport, un produit imparfait et une architecture "
        "juste. Le candidat a construit le morceau difficile : un moteur de devis qui "
        "refuse de mentir, une isolation multi-tenant, une IA locale sous contrainte "
        "reelle, et une cible d'ingestion qui ne casse pas ce moteur. Le reste est de "
        "l'execution. Pour un Projet 1 de MBA Big Data et IA, c'est le bon objet : "
        "pas un modele hors-sol, un systeme au service d'une PME nommee."
    ))
    s.append(P(
        "Le jury peut donc trancher sur une question simple. Face a une photo de "
        "ballon d'eau chaude, le systeme propose-t-il un tarif invente, ou un brouillon "
        "sur le catalogue ANELEC qu'un humain peut signer ? Tout le reste du rapport "
        "n'est que l'explication de cette question."
    ))

    s.append(P("12. Sources", "h1"))
    s.append(P(
        "Les faits internes viennent du depot zehair-louzza/Blueseatra, du depot "
        "ovh-ai-stack, de la Cartographie Blueseatra v2 (16 aout 2026), du Guide "
        "import n8n P1 et des ADR-001 a ADR-004. Sources publiques :"
    ))
    for i, (name, url) in enumerate(SOURCES, 1):
        s.append(P(f'{i}. {name} : <a href="{url}" color="blue">{url}</a>', "foot"))
    return s


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        title="Blueseatra — Rapport de jury : architecture et trajectoire produit",
        author="Perplexity Computer",
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(story(), onFirstPage=cover_footer, onLaterPages=header_footer)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
