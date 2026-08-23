#!/usr/bin/env python3
"""Complement aout 2026 du dossier MIN Projet 1 (26 juin 2026)."""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
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
SCREENS = ASSETS / "screens"
OUT = DOCS / "Dossier_Consulting_Blueseatra_Complement_Aout_2026.pdf"
FONT_DIR = Path("/tmp/fonts")
FONT_DIR.mkdir(exist_ok=True)

NAVY = HexColor("#0B4F54")
TEAL = HexColor("#1A7A7A")
INK = HexColor("#1c2834")
MUTE = HexColor("#5b6772")
LINE = HexColor("#D4D1CA")
ROW = HexColor("#F3F6F7")
BOX = HexColor("#E8F2F2")

SOURCES = [
    ("Ollama gemma4:26b", "https://ollama.com/library/gemma4:26b"),
    ("Gemma + Ollama", "https://ai.google.dev/gemma/docs/integrations/ollama"),
    ("Hermes API server", "https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server"),
    ("Hermes Docker", "https://hermes-agent.nousresearch.com/docs/user-guide/docker"),
    ("Hermes configuring models", "https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models"),
    ("CNIL RGPD", "https://www.cnil.fr"),
    ("Facturation electronique", "https://www.impots.gouv.fr"),
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
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=FB, fontSize=14, leading=18, textColor=NAVY, spaceBefore=10, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FB, fontSize=11.5, leading=15, textColor=NAVY, spaceBefore=7, spaceAfter=4),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontName=FN, fontSize=9.3, leading=13.2, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=5.5),
        "li": ParagraphStyle("li", parent=base["BodyText"], fontName=FN, fontSize=9.2, leading=12.6, textColor=INK, spaceAfter=2),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontName=FN, fontSize=7.8, leading=10.8, textColor=INK),
        "cellh": ParagraphStyle("cellh", parent=base["BodyText"], fontName=FB, fontSize=7.8, leading=10.8, textColor=white),
        "cap": ParagraphStyle("cap", parent=base["BodyText"], fontName=FN, fontSize=8, leading=11, textColor=MUTE, spaceAfter=7, alignment=TA_CENTER),
        "foot": ParagraphStyle("foot", parent=base["Normal"], fontName=FN, fontSize=7.4, leading=10, textColor=MUTE),
        "cover": ParagraphStyle("cover", parent=base["Title"], fontName=FB, fontSize=20, leading=25, textColor=NAVY, alignment=TA_CENTER),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName=FN, fontSize=11, leading=15, textColor=TEAL, alignment=TA_CENTER),
        "center": ParagraphStyle("center", parent=base["Normal"], fontName=FN, fontSize=9.3, leading=13, textColor=MUTE, alignment=TA_CENTER),
        "toc": ParagraphStyle("toc", parent=base["Normal"], fontName=FN, fontSize=10, leading=15.5, textColor=INK),
        "box": ParagraphStyle("box", parent=base["BodyText"], fontName=FN, fontSize=9, leading=12.6, textColor=INK, alignment=TA_JUSTIFY),
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
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, ROW]),
            ]
        )
    )
    return t


def fitted(path, w=170 * mm, max_h=78 * mm):
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


def collect_screens():
    found = []
    for folder in [SCREENS, Path("/tmp"), Path("/home/user/workspace")]:
        if not folder.exists():
            continue
        for p in folder.rglob("*.png"):
            name = p.name.lower()
            if any(k in name for k in ("login-preview", "ollama-config")):
                found.append(p)
    # also landing product photos
    for p in [LAND / "hero-desk.jpg", LAND / "catalog.jpg", LAND / "chantier.jpg"]:
        if p.exists():
            found.append(p)
    uniq = []
    seen = set()
    for p in found:
        if p.name not in seen:
            uniq.append(p)
            seen.add(p.name)
    return uniq[:6]


def header_footer(c, doc):
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(16 * mm, A4[1] - 12 * mm, A4[0] - 16 * mm, A4[1] - 12 * mm)
    c.setFillColor(NAVY)
    c.setFont(FN, 8)
    c.drawString(16 * mm, A4[1] - 10 * mm, "Dossier de Consulting  —  Blueseatra")
    c.drawRightString(A4[0] - 16 * mm, A4[1] - 10 * mm, "Complement aout 2026")
    c.setFillColor(MUTE)
    c.setFont(FN, 8)
    c.drawCentredString(A4[0] / 2, 10 * mm, f"Page {doc.page}")
    c.setFont(FN, 6.5)
    c.drawString(16 * mm, 6 * mm, "Sources officielles en derniere page")
    c.restoreState()


def cover_footer(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, 0, A4[0], 22 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FN, 8)
    c.drawCentredString(A4[0] / 2, 10 * mm, "Projet 1 actualise  ·  MBA ESG Paris  ·  MBDIA")
    c.restoreState()


def story():
    s = []
    logo = BRAND / "blueseatra-lockup.png"
    if logo.exists():
        s.append(Spacer(1, 18 * mm))
        s.append(Image(str(logo), width=82 * mm, height=27 * mm, hAlign="CENTER"))
    s.append(Spacer(1, 10 * mm))
    s.append(P("DOSSIER DE CONSULTING", "sub"))
    s.append(Spacer(1, 3 * mm))
    s.append(P("Complement d'actualisation", "cover"))
    s.append(Spacer(1, 3 * mm))
    s.append(P("Du cadrage du 26 juin 2026 a la plateforme deployee", "sub"))
    s.append(Spacer(1, 10 * mm))
    s.append(P("Projet 1 — Cadrage strategique, diagnostic, puis realisation", "center"))
    s.append(P("MBA ESG Paris — Galileo Global Education", "center"))
    s.append(P("RNCP niveau 7 — Manager de l'Innovation Numerique — MBDIA", "center"))
    s.append(Spacer(1, 6 * mm))
    s.append(P("Candidat : Louzza Zehair", "center"))
    s.append(P("Responsable de programme : M. Olivier Jarrar", "center"))
    s.append(P("Commanditaire : ANELEC TECHNIQUE ET CONCEPT — M. Anouar Bejtetyene", "center"))
    s.append(P("Date : 17 aout 2026  ·  Promotion MBDIA Janvier 2026", "center"))
    s.append(PageBreak())

    s.append(P("Sommaire", "h1"))
    for line in [
        "1. Ce complement actualise le cadrage sans l'annuler",
        "2. Les hypotheses d'hebergement de juin ont ete tranchees",
        "2b. Brief : installation complete du VPS OVH",
        "2c. Chronologie des abandons et remplacements",
        "3. La chaine applicative est en production partielle",
        "4. L'IA locale remplace Oracle Cloud et le ZimaBoard",
        "5. Le moteur de devis refuse d'inventer un prix",
        "6. Les instances se deploient par quatre voies distinctes",
        "7. La securite deployee precise le plan C1.5",
        "8. L'etat live documente l'avancement du Projet 1",
        "9. Les ecarts restants cadrent la suite du fil rouge",
        "10. Conclusion pour le jury",
        "11. Sources",
    ]:
        s.append(P(line, "toc"))
    s.append(Spacer(1, 5 * mm))
    s.append(P(
        "Le dossier MIN du 26 juin 2026 reste le livrable de cadrage (C1.1, C1.2, C1.3, C1.5). "
        "Le present texte n'invente aucun nouvel indicateur commercial. Les volumes sont ceux "
        "de Supabase et de GitHub au 17 aout 2026. Les hypotheses de ROI du cadrage "
        "(economie theorique, +10 a +15 points) restent des cibles a mesurer, pas des resultats."
    ))

    s.append(P("1. Ce complement actualise le cadrage sans l'annuler", "h1"))
    s.append(P(
        "Le 26 juin 2026, le Projet 1 a pose une problematique, une lettre de mission, "
        "un diagnostic de maturite (environ 1,8 / 5), une opportunite IA, un plan SMART "
        "et une politique de securite. Trois points ouverts y figuraient : l'hebergement "
        "cible (ZimaBoard + Oracle ou cloud manage), n8n encore a deployer, et ANELEC "
        "presentee comme PME-cible avec des hypotheses a valider."
    ))
    s.append(P(
        "Entre le 26 juin et le 17 aout, le candidat a execute le scenario B qu'il "
        "recommandait : MVP puis catalogue, human-in-the-loop, souverainete UE. "
        "Ce complement documente ce qui a ete tranche, construit, mesure, et ce qui "
        "reste hors perimetre (facturation, CRM, WhatsApp, ERP)."
    ))
    s.append(table(
        [
            ["Point du cadrage (26 juin)", "Etat au 17 aout"],
            ["React / Hostinger", "Live : blueseatra.com HTTP 200, landing PR 26"],
            ["FastAPI / Render", "Live : blueseatra-api healthy, auto-deploy main"],
            ["Supabase 14 tables RLS", "Projet xmsxlochasjauhnxarvc, PG 17.6, ACTIVE_HEALTHY"],
            ["n8n sur ZimaBoard", "n8n sur VPS OVH ; pack P1 livre, workflows inactifs"],
            ["Oracle Cloud gratuit", "Abandonne (souverainete). IA sur OVH Roubaix"],
            ["Hebergement non tranche", "Tranche : Hostinger + Render + Supabase UE + OVH"],
            ["MVP extraction + devis", "Chaine live : demande, matching, PDF, test BS-2026-0017"],
            ["Catalogue CSV", "704 articles, import ouvert, picker corrige (PR 23)"],
        ],
        [78 * mm, 92 * mm],
    ))

    s.append(P("2. Les hypotheses d'hebergement de juin ont ete tranchees", "h1"))
    s.append(P(
        "L'annexe H de juin decrivait une chaine cible n8n / ZimaBoard et une inference "
        "Oracle gratuite. Le 14 juillet, l'architecture officielle conserve Hostinger, "
        "Render et Supabase, et deplace l'IA vers un VPS OVH. Oracle US est abandonne. "
        "Le ZimaBoard n'est plus dans le chemin de production. La frugalite demeure, "
        "mais elle n'est plus gratuite : 24 Go de RAM, Caddy, Docker, un seul gros modele charge."
    ))
    s.append(P(
        "Cette decision sert trois criteres du cadrage C1.5 : cout maitrise, localisation UE, "
        "reversibilite. Elle abandonne l'argument « offre gratuite » du resume executif de juin. "
        "Un expert prefere un cout connu et souverain a une gratuite hors UE."
    ))

    s.append(P("2b. Brief : installation complete du VPS OVH", "h1"))
    s.append(P(
        "Hote : ubuntu@vps-b377201e.vps.ovh.net, IP 162.19.44.2, Ubuntu 24.04, "
        "8 vCPU, 24 Go RAM, 200 Go NVMe, swap 4 Go, Docker 29.7 + Compose v5. "
        "Depot : zehair-louzza/ovh-ai-stack. Un seul point d'entree Internet : Caddy :80/:443. "
        "Ollama, Hermes et n8n restent sur le reseau Docker."
    ))
    s.append(P("Etapes deja faites", "h2"))
    s.append(table(
        [
            ["Etape", "Contenu", "Controle"],
            ["DNS Hostinger", "A ia / n8n / hermes → 162.19.44.2", "Let's Encrypt"],
            ["SSH", "Cle ed25519 ~/.ssh/ovh_vps, IdentitiesOnly", "ssh ovh-vps"],
            ["Durcissement", "UFW 22/80/443, no-new-privileges", "ufw status"],
            ["Secrets", ".env hors Git, openssl rand -hex 32", "jamais dans le chat"],
            ["Compose", "caddy, ollama 18g, hermes 2g, n8n", "docker compose ps"],
            ["Modeles", "ollama pull gpt-oss:20b, qwen2.5vl:7b, qwen2.5:7b, hermes3", "ollama list"],
            ["Hermes YAML", "model.default=gpt-oss:20b, provider custom, pas auto", "hermes doctor"],
            ["API Hermes", "API_SERVER_ENABLED, 8642 interne, Bearer", "health 0.20.1"],
            ["Git VPS", "cle github_ovh_ai_stack, force-recreate apres pull", "git log"],
        ],
        [36 * mm, 78 * mm, 56 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Commandes cibles (VPS, une a la fois). "
        "GIT_SSH_COMMAND='ssh -i ~/.ssh/github_ovh_ai_stack -o IdentitiesOnly=yes' git pull. "
        "docker compose up -d --force-recreate hermes. "
        "docker compose exec ollama ollama pull gpt-oss:20b. "
        "Ne jamais publier 11434 ni 8642. HERMES_MODEL=gpt-oss:20b dans .env."
    ))
    cfg = SCREENS / "ollama-config.jpg"
    if cfg.exists():
        s.append(fitted(cfg, 150 * mm, 70 * mm))
        s.append(P(
            "Figure D. Capture hermes model dans le conteneur. A ne pas suivre : "
            "le wizard propose anthropic/claude-opus-4.6, provider none / auto, "
            "et 127.0.0.1:11434. La config validee reste Ollama Docker "
            "(http://ollama:11434/v1, api_key ollama-local, gpt-oss:20b).",
            "cap",
        ))
    s.append(P(
        "Interdit : hermes doctor --fix (monte read-only), provider auto "
        "(OpenRouter / Nous hors UE), coller OLLAMA_API_KEY ou API_SERVER_KEY. "
        "Apres checkout Git, recreer le conteneur : l'inode du YAML bind-monte change."
    ))

    s.append(P("2c. Chronologie des abandons et remplacements", "h1"))
    s.append(P(
        "Rien n'a ete coupe par caprice. Chaque abandon libere une contrainte "
        "(souverainete, marque, RAM, schema) et un remplacement la ferme. "
        "Le dossier de juin documente encore Oracle et le ZimaBoard : c'est l'etat "
        "du cadrage, pas l'etat deployee."
    ))
    s.append(table(
        [
            ["Date", "Abandonne", "Pourquoi", "Remplace par"],
            ["24-25 juin 2026", "MongoDB (proto)", "Pas de RLS metier, schema trop souple pour le devis", "Supabase Postgres, schema blueseatra, pg_adapter"],
            ["26 juin 2026", "Cas fictif BTP Solutions", "Dossier MBA sans commanditaire reel", "ANELEC TECHNIQUE ET CONCEPT"],
            ["11 juil. 2026", "Branding Emergent (badge, scripts, titre)", "Le SaaS ne s'appartenait pas", "Identite Blueseatra (plus tard logo lockup)"],
            ["14-20 juil. 2026", "Provider Emergent + EMERGENT_LLM_KEY + wheel emergentintegrations", "LLM tiers, pas de routage, hors these souverainete", "Hermes / Ollama sur VPS, defaut ai_provider=hermes"],
            ["14-20 juil. 2026", "Oracle Cloud comme hote IA", "Hors UE, dependance, ADR-001", "OVH Roubaix 162.19.44.2"],
            ["14-20 juil. 2026", "Provider oracle dans FastAPI", "Meme motif souverainete", "hermes + filet litellm par tenant"],
            ["Ete 2026", "ZimaBoard pour n8n / stockage", "Seconde machine inutile, trop juste", "n8n.blueseatra.com sur le meme VPS"],
            ["Ete 2026", "Kubernetes / ingress unique", "Costume trop large pour le Projet 1", "Hostinger statique + Render + Caddy"],
            ["15 aout 2026", "Modeles 70B / 72B dans l'UI", "Incompatibles avec 24 Go RAM", "14B / 26B MoE / 27B, un seul charge"],
            ["16-17 aout 2026", "qwen3.6:27b comme modele principal Hermes", "Besoin d'un raisonneur distinct, ADR-003", "gemma4:26b (model + reasoning_effort high)"],
            ["17 aout 2026", "provider: auto et wizard hermes model (Claude Opus)", "Fuite OpenRouter / Nous, hors UE", "provider custom, http://ollama:11434/v1, ollama-local"],
            ["Non retenu", "DeepSeek-R1 32B comme raisonneur", "Trop lourd a cote de Gemma 17 Go", "Gemma 4 26B-A4B seul en principal"],
            ["23 aout 2026", "gemma4:26b, qwen3.6:27b, qwen3:14b, deepseek-r1:14b, qwen2.5:14b, Phi-4-vision-15B", "63 Go a liberer, aucun ne raisonne + a la vision a la fois", "gpt-oss:20b (raisonnement gradue) ; qwen2.5:7b / qwen2.5vl:7b (extraction)"],
        ],
        [32 * mm, 48 * mm, 46 * mm, 44 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Ce qui n'a jamais ete abandonne : FastAPI calcule les prix, validation humaine, "
        "catalogue du tenant, Hostinger, Render, Supabase UE, JWT, RLS. "
        "Emergent, Oracle et le ZimaBoard etaient des echafaudages. "
        "Le batiment, c'est le moteur de devis."
    ))

    s.append(P("3. La chaine applicative est en production partielle", "h1"))
    s.append(fitted(ASSETS / "schema-architecture.png", 172 * mm, 78 * mm))
    s.append(P("Figure A. Architecture deployee au 17 aout 2026 (as-is).", "cap"))
    s.append(P(
        "Le site public n'est plus une intention. La landing explique collecter, lire, "
        "rapprocher, controler, editer. La console /app porte demandes, catalogues, "
        "editeur, membres, audit, parametres. Le billing reste un placeholder, hors v2, "
        "conforme au cadrage qui ne monétisait pas encore."
    ))
    screens = collect_screens()
    shown = 0
    for p in screens:
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"} and shown < 3:
            s.append(fitted(p, 160 * mm, 72 * mm))
            s.append(P(f"Figure site : {p.stem.replace('-', ' ')}.", "cap"))
            shown += 1
    s.append(P(
        "GitHub Blueseatra : 26 pull requests fusionnees entre le 15 et le 17 aout "
        "(Hermes authentifie, extraction UI, lots TCE, MO, TVA, logo, landing). "
        "La PR 27 (documentation v2) etait encore ouverte au moment de ce complement. "
        "ovh-ai-stack PR 1 est fusionnee (slots Hermes)."
    ))

    s.append(P("4. L'IA locale remplace Oracle Cloud et le ZimaBoard", "h1"))
    s.append(fitted(ASSETS / "schema-routage.png", 172 * mm, 40 * mm))
    s.append(P("Figure B. Routage extract / reason / repli.", "cap"))
    s.append(P(
        "Hermes Agent n'a pas de slots nommes extraction, generation, raisonnement. "
        "Les roles Blueseatra s'appuient sur les cles officielles.<super>5</super>"
    ))
    s.append(table(
        [
            ["Role", "Modele", "Chemin"],
            ["Extraction", "qwen2.5:7b (texte) / qwen2.5vl:7b (fichier)", "FastAPI → Ollama /api/chat"],
            ["Raisonnement", "gpt-oss:20b, think low/medium/high", "FastAPI → Ollama /api/chat direct"],
            ["Repli", "hermes3 (sans raisonnement natif)", "Ollama"],
            ["Prix / TVA / marge", "aucun LLM", "FastAPI uniquement"],
        ],
        [48 * mm, 62 * mm, 60 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Mise a jour du 23 aout 2026 : gemma4:26b, qwen3.6:27b, qwen3:14b, deepseek-r1:14b, qwen2.5:14b et "
        "Phi-4-reasoning-vision-15B ont ete supprimes du VPS (63 Go liberes). gpt-oss:20b (20,9B parametres, "
        "MXFP4, deja installe) reprend le raisonnement : seul modele restant avec capacite thinking confirmee "
        "(`ollama show gpt-oss:20b`), mais il ne peut pas la desactiver -- seulement en regler la profondeur "
        "via HERMES_REASONING_EFFORT. OLLAMA_MAX_LOADED_MODELS=1. "
        "provider: auto est interdit. litellm reste un filet par tenant, jamais une source de prix."
    ))

    s.append(P("5. Le moteur de devis refuse d'inventer un prix", "h1"))
    s.append(fitted(ASSETS / "schema-parcours.png", 172 * mm, 46 * mm))
    s.append(P("Figure C. Parcours operateur. Le dernier mot reste humain.", "cap"))
    s.append(P(
        "Le cadrage de juin identifiait le risque principal : hallucination sur les prix. "
        "La realisation en fait une frontiere systeme. L'IA extrait et decompose "
        "(ballon ECS → ballon, groupe de securite, flexibles). matching.py ne lit que "
        "le catalogue. La validation gele pricing_snapshot. Le devis test BS-2026-0017 "
        "(697,69 EUR HT, brouillon) montre une decomposition, pas une preuve que Hermes "
        "a toujours ete appele."
    ))
    s.append(P(
        "AS-IS Tolteck du cadrage : sortie propre, amont manuel. TO-BE partiel : amont "
        "assiste dans Blueseatra, validation humaine, PDF Pro Forma. Tolteck n'est pas "
        "encore bascule ; le complement ne pretend pas une migration terminee."
    ))

    s.append(P("6. Les instances se deploient par quatre voies distinctes", "h1"))
    s.append(table(
        [
            ["Instance", "URL / identifiant", "Deploiement"],
            ["Frontend", "blueseatra.com", "Manuel yarn build + upload Hostinger"],
            ["API", "blueseatra-api.onrender.com", "Auto-deploy Render sur merge main"],
            ["Postgres", "xmsxlochasjauhnxarvc eu-west-1", "Migrations SQL, pooler :6543"],
            ["Ollama", "ia.blueseatra.com", "Compose VPS, mem_limit 18g"],
            ["Hermes", "hermes.blueseatra.com", "force-recreate ; 8642 interne"],
            ["n8n", "n8n.blueseatra.com", "Installe ; P1 inactif"],
        ],
        [32 * mm, 68 * mm, 70 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Controles de la seance : API {status: healthy}, site HTTP 200, Hermes /health "
        "sans cle = Unauthorized (expose et protege). Integrations actives : JWT maison, "
        "CSV, PDF, MCP lecture seule, webhook n8n sortant. Non allumees : mails, Drive, CRM."
    ))

    s.append(P("7. La securite deployee precise le plan C1.5", "h1"))
    s.append(P(
        "Les cinq principes de juin tiennent : human-in-the-loop, privacy by design, "
        "frugalite, iteratif, souverainete. Les mesures concrètes sont plus precises."
    ))
    s.append(table(
        [
            ["Risque du cadrage", "Mesure deployee au 17 aout"],
            ["Acces non autorise", "JWT fort, bcrypt, role relu en base, CORS explicite"],
            ["Cloisonnement tenant", "Filtre tenant_id + RLS ; public = deny-all"],
            ["Table users", "Policies service_role only (password_hash)"],
            ["Secrets", "Fernet ; cles hors Git ; double auth Caddy + Bearer"],
            ["Localisation", "Hostinger, Render UE, Supabase Irlande, OVH Roubaix"],
            ["Ports modeles", "11434 et 8642 non publies"],
            ["Hallucination prix", "Aucun LLM dans matching ni totaux"],
            ["MCP", "Lecture seule, tenant ANELEC Test"],
        ],
        [52 * mm, 118 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Advisors securite Supabase : 0 lint. Point ouvert : hors users, plusieurs tables "
        "blueseatra ont une policy authenticated ALL. Inoffensif tant que l'app ne passe "
        "pas par PostgREST. A durcir avant d'ouvrir l'API Data. "
        "render.yaml mentionne encore un DB_SCHEMA historique public : a aligner."
    ))

    s.append(P("8. L'etat live documente l'avancement du Projet 1", "h1"))
    s.append(P(
        "Supabase, 17 aout 2026. Projet cree le 21 juin. 7 tenants starter "
        "(blueseatra, ANELEC Test, ANELEC TECHNIQUE ET CONCEPT, Hanoutbrahim, Eventcater, "
        "2 x Blueseatra Check). 704 articles. 9 demandes (5 done, 1 needs_review, 3 failed). "
        "19 devis (18 brouillons, 1 valide). 99 audits. schema public : 14 tables a 0 ligne."
    ))
    s.append(P(
        "Ces volumes decrivent un laboratoire vivant, pas une base clients. "
        "Ils permettent toutefois de sortir de la limite methodologique de juin "
        "(« entreprise cliente simulee ») : ANELEC est desormais un tenant reel du SaaS, "
        "meme si les hypothese d'effectif et de CA du cadrage restent des hypotheses."
    ))

    s.append(P("9. Les ecarts restants cadrent la suite du fil rouge", "h1"))
    s.append(table(
        [
            ["Ecart", "Lecture pour le fil rouge"],
            ["n8n P1 inactif", "Projet 4 : activer un seul canal (webhook site)"],
            ["3 demandes failed", "Projet 3C : mesurer le raisonneur, pas le supposer"],
            ["18 devis draft / 1 valide", "Conduite du changement encore devant"],
            ["Doublons Blueseatra Check", "Hygiene data"],
            ["Frontend manuel", "Industrialiser le build avant demo longue"],
            ["Billing placeholder", "Hors these technique du Projet 1"],
            ["KPI +10-15 pts non mesures", "Rester des cibles ; ne pas les presenter comme acquis"],
        ],
        [58 * mm, 112 * mm],
    ))
    s.append(Spacer(1, 3 * mm))
    s.append(P(
        "Le cadrage ouvrait sur les Projets 2, 3C et 4. Ce qui a ete livre en juillet-aout "
        "anticipe une partie du 3C (conception technique) et du 4 (deploiement). "
        "Il ne remplace pas une idéation utilisateur formelle (Projet 2) ni un tableau "
        "de bord de transformation (phase 3 du plan de juin)."
    ))

    s.append(P("10. Conclusion pour le jury", "h1"))
    s.append(P(
        "Le dossier du 26 juin posait une question : comment reduire le temps de devis "
        "sans laisser l'IA signer un tarif, dans une PME comme ANELEC ? "
        "Le 17 aout, la reponse n'est plus seulement strategique. Une chaine existe : "
        "site, API, catalogue, extraction, matching, PDF, isolation UE."
    ))
    s.append(P(
        "Nous recommandons au jury de juger trois choses. Un : la these human-in-the-loop "
        "est codee, pas seulement ecrite. Deux : les points ouverts de juin (hebergement, "
        "Oracle, ZimaBoard) ont ete tranches dans le bon sens (souverainete). "
        "Trois : les KPI commerciaux du cadrage ne sont pas encore mesures ; "
        "les presenter comme des resultats serait une faute."
    ))
    s.append(P(
        "Le complement confirme le GO motive de juin, en le rendant plus exigeant : "
        "activer un canal n8n, aligner render.yaml, durcir les policies authenticated, "
        "mesurer Hermes, puis seulement parler de taux de transformation."
    ))

    s.append(P("11. Sources", "h1"))
    s.append(P(
        "Dossier source : LOUZZA-Zehair_PROJET-1_MIN_26-juin-2026.pdf. "
        "Depots : zehair-louzza/Blueseatra, zehair-louzza/ovh-ai-stack. "
        "Cartographie v2, Guide n8n P1, ADR-001 a ADR-004. Sources publiques :"
    ))
    for i, (name, url) in enumerate(SOURCES, 1):
        s.append(P(f'{i}. {name} : <a href="{url}" color="blue">{url}</a>', "foot"))
    return s


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        title="Blueseatra — Complement dossier consulting aout 2026",
        author="Perplexity Computer",
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    doc.build(story(), onFirstPage=cover_footer, onLaterPages=header_footer)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
