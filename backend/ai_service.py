"""Multilingual document understanding service - provider-agnostic.
Default engine: Hermes AI (Ollama) running locally on OVH VPS.
A tenant can override provider/model/key via Settings (Integrations).
"""
import os
import io
import json
import re
import base64
import httpx
import quote_scenarios
import asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ── Hermes AI / Ollama (OVH VPS) ────────────────────────────────────────────
HERMES_BASE_URL = os.environ.get("HERMES_BASE_URL", "http://localhost:11434")
HERMES_DEFAULT_MODEL = os.environ.get("HERMES_DEFAULT_MODEL", "hermes-3")
HERMES_EXTRACT_MODEL = os.environ.get("HERMES_EXTRACT_MODEL", "qwen2.5:14b")
HERMES_REASONING_MODEL = os.environ.get("HERMES_REASONING_MODEL", "gemma4:26b")
HERMES_FALLBACK_MODELS = [
    os.environ.get("HERMES_REASONING_MODEL", "gemma4:26b"),
    "qwen3.6:27b",
    os.environ.get("HERMES_EXTRACT_MODEL", "qwen2.5:14b"),
    "hermes3",
    "hermes-3",
]
# Modeles multimodaux (texte + image) confirmes via `ollama show` sur le VPS.
# qwen2.5:14b et hermes3/hermes-3 sont TEXTE SEUL : les appeler avec une
# image renvoie HTTP 400 "Multimodal data provided, but model does not
# support multimodal requests" (incident du 2026-08-18). Ne jamais les inclure
# dans le repli utilise pour l'extraction par vision.
HERMES_VISION_MODEL = os.environ.get("HERMES_VISION_MODEL") or os.environ.get("HERMES_REASONING_MODEL", "gemma4:26b")
HERMES_VISION_FALLBACK_MODELS = [
    os.environ.get("HERMES_REASONING_MODEL", "gemma4:26b"),
    "qwen3.6:27b",
]
MODEL_ALIASES = {"hermes-3": "hermes3", "hermes3": "hermes3"}

# Cascade de STRUCTURATION (texte deja extrait -> JSON final), routage
# sequentiel via Hermes (decision du 2026-08-19). Distincte de la cascade
# OCR ci-dessus : s'applique uniquement au texte deja lisible (sortie OCR,
# ou fichier texte natif comme DOCX/XLSX/CSV/TXT), jamais a une image (ces
# modeles candidats qwen3:14b/deepseek-r1:14b sont TEXTE SEUL, pas
# multimodaux). Motif : en test isole ce jour, gemma4:26b seul a renvoye
# une reponse VIDE a deux reprises sur un document reel (budget de
# raisonnement epuise sans jamais fermer le bloc de reflexion), et
# qwen3.6:27b s'est confirme trop lent (~2 tok/s, jamais termine en moins
# de 10-23 min sur ce document dans plusieurs tentatives). Ordre : les deux
# modeles 14B (plus petits, donc plus rapides sur ce CPU sans GPU) d'abord,
# Gemma en 3e (deja fiable sur la majorite des documents, connu pour ce cas
# limite precis), qwen3.6:27b en tout dernier recours seulement.
HERMES_STRUCTURING_MODEL_1 = os.environ.get("HERMES_STRUCTURING_MODEL_1", "qwen3:14b")
HERMES_STRUCTURING_MODEL_2 = os.environ.get("HERMES_STRUCTURING_MODEL_2", "deepseek-r1:14b")
HERMES_STRUCTURING_MODEL_3 = os.environ.get("HERMES_STRUCTURING_MODEL_3") or os.environ.get("HERMES_REASONING_MODEL", "gemma4:26b")
HERMES_STRUCTURING_MODEL_4 = os.environ.get("HERMES_STRUCTURING_MODEL_4", "qwen3.6:27b")
# Timeouts PROVISOIRES par etage (secondes) : aucun des 4 modeles n'a ete
# mesure jusqu'a une completion reussie sur ce VPS a cette date (tests
# interrompus par l'utilisateur avant la fin, ou reponse vide) -- valeurs
# prudentes basees sur la taille du modele et le comportement observe, PAS
# sur la regle 1.2x-de-l-etape-suivante utilisee pour la cascade OCR (qui
# exige une duree reelle mesuree). A RECALIBRER avec _STRUCTURING_STAGE_MEASURED_SECONDS
# des qu'un test complet jusqu'a completion est disponible pour chaque modele.
_STRUCTURING_CASCADE_TIMEOUTS = {
    "Qwen3-14B": 480.0,
    "DeepSeek-R1-14B": 480.0,
    "Gemma4-26B": 900.0,
    "Qwen3.6-27B": 900.0,
}


def _structuring_cascade_stages() -> list[tuple[str, str, float]]:
    """Etages de la cascade de structuration (label, modele, timeout),
    recalcule a chaque appel (modeles surchargeables par variable
    d'environnement en cours d'execution)."""
    order = [
        ("Qwen3-14B", HERMES_STRUCTURING_MODEL_1),
        ("DeepSeek-R1-14B", HERMES_STRUCTURING_MODEL_2),
        ("Gemma4-26B", HERMES_STRUCTURING_MODEL_3),
        ("Qwen3.6-27B", HERMES_STRUCTURING_MODEL_4),
    ]
    return [
        (label, model, _STRUCTURING_CASCADE_TIMEOUTS.get(label, 900.0))
        for label, model in order
    ]


async def _call_structuring_cascade(system_prompt: str, user_message: str) -> tuple[str, str]:
    """Essaie chaque etage de _structuring_cascade_stages() dans l'ordre ;
    une reponse VIDE compte comme un echec de cet etage (pas seulement une
    exception/timeout), et passe a l'etage suivant -- c'est precisement le
    mode d'echec observe chez gemma4:26b sur certains documents. Renvoie
    (contenu_brut, label_du_modele_qui_a_reussi). Leve RuntimeError si tous
    les etages echouent, avec le detail de chaque echec."""
    errors = []
    for label, model, timeout in _structuring_cascade_stages():
        effective_system_prompt = system_prompt
        if _wants_think(model):
            effective_system_prompt = system_prompt + _THINK_BREVITY_HINT
        payload = {
            "model": MODEL_ALIASES.get((model or "").strip(), model),
            "messages": [
                {"role": "system", "content": effective_system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 4096},
        }
        if _wants_think(model):
            payload["think"] = True
        headers = {}
        if HERMES_API_KEY:
            headers["X-Api-Key"] = HERMES_API_KEY
        url = f"{HERMES_BASE_URL.rstrip('/')}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                errors.append(f"{label}: HTTP {response.status_code}: {(response.text or '')[:180]}")
                continue
            data = response.json()
            msg = data.get("message") or {}
            content = (msg.get("content") or "").strip()
            if content:
                return content, label
            errors.append(f"{label}: reponse vide")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc or repr(exc)}")
    raise RuntimeError("; ".join(errors) if errors else "aucun modele de structuration n'a repondu")
# OCR specialise (PaddleOCR-VL-1.6, 96.33% OmniDocBench v1.6) : premiere
# etape de la cascade d'extraction sur image/PDF illisible. Transcription
# litterale rapide (~100s/page mesure), avant structuration par Gemma en
# appel texte (pas de re-encodage image, donc plus rapide que la vision
# directe). Decision du 2026-08-18 apres evaluation comparative de
# PaddleOCR-VL-1.6, DeepSeek-OCR-2 et Phi-4-reasoning-vision-15B — voir
# le rapport de recherche et 0quater dans le skill intake-demande-devis
# pour le detail des rejets (DeepSeek-OCR-2 : hallucine puis degenere en
# boucle ; Phi-4 : 12,5 min/page et paraphrase au lieu de transcrire).
HERMES_OCR_MODEL = os.environ.get("HERMES_OCR_MODEL", "AuditAid/PaddleOCR-VL-1.6-0.9B:latest")
# Deuxieme etape OCR : LightOnOCR-2-1B, entraine avec une forte couverture
# de documents FRANCAIS (pertinent pour ce cas d'usage), SOTA sur
# OlmOCR-Bench (83.2) a seulement 596M parametres. Sortie Markdown/HTML
# mieux structuree que PaddleOCR (tableaux avec rowspan/colspan corrects),
# mesure a ~200s, aucun echec observe sur nos tests (contrairement a
# Paddle qui a echoue une fois sur une image composite a 3 pages).
HERMES_OCR_SECONDARY_MODEL = os.environ.get("HERMES_OCR_SECONDARY_MODEL", "maternion/LightOnOCR-2:1b")
# Troisieme etape OCR avant le recours a la vision directe de Gemma :
# modele officiel Ollama (pas de GGUF communautaire a risque), qualite
# superieure a Paddle/LightOnOCR sur ce type de document (tableaux
# correctement restructures), mesure a ~246s contre ~600-750s pour
# Gemma-vision. Decision du 2026-08-18 apres comparaison de 8 modeles
# (voir aussi les rejets : DeepSeek-OCR-2, GLM-4.1V-9B-Thinking,
# Granite Vision 3.2-2B — tous invent(ent)/degenerent sur ce type de
# document dense).
HERMES_OCR_ESCALATION_MODEL = os.environ.get("HERMES_OCR_ESCALATION_MODEL", "qwen2.5vl:7b")
# Quatrieme etape OCR, la plus fiable des quatre (meilleure fidelite de
# structure de tableau observee, HTML avec rowspan/colspan correct) mais
# la plus lente des etapes OCR specialisees (quant Q8_0 lourde), ~587s.
# Base sur Qwen2.5-VL-7B, affine par renforcement (RLVR) specifiquement
# pour l'OCR (allenai/olmOCR-2-7B-1025). Decision du 2026-08-19.
HERMES_OCR_TERTIARY_MODEL = os.environ.get("HERMES_OCR_TERTIARY_MODEL", "richardyoung/olmocr2:7b-q8")

# Duree moyenne mesuree en conditions reelles sur ce VPS (2026-08-18/19,
# document de test : PDF francais dense avec tableaux, incident reel
# "LOT_20_LA_SABLIERE"). Sert de base a la regle de timeout par etage
# (decision du 2026-08-19, marge reduite le meme jour de 1.5x a 1.2x) :
# le timeout d'une etape = 1.2x la duree mesuree de l'etape SUIVANTE
# (plus lente mais plus fiable/puissante), jamais une valeur arbitraire
# fixe. Objectif : ne jamais attendre sur un modele bloque/degrade plus
# longtemps que ce qu'il faudrait de toute facon pour que l'etape
# suivante fasse le travail, avec une marge reduite a 20%.
_OCR_STAGE_TIMEOUT_MULTIPLIER = 1.2
# Timeout du DERNIER recours (vision directe de Gemma) : contrairement
# aux etapes OCR ci-dessus, il n'y a pas d'"etape suivante" a mesurer
# pour lui appliquer la regle 1.2x — plafond fixe, aligne sur le timeout
# deja utilise ailleurs pour Gemma en mode raisonnement (voir _wants_think
# dans _call_hermes_ollama). Nomme explicitement plutot que laisse en dur
# dans chaque appelant, pour qu'un changement futur ne se fasse qu'ici.
_OCR_FINAL_FALLBACK_TIMEOUT = 900.0
_OCR_STAGE_MEASURED_SECONDS = {
    "PaddleOCR-VL-1.6": 110,
    "LightOnOCR-2-1B": 200,
    "Qwen2.5-VL-7B": 246,
    "olmOCR-2-7B": 587,
    "Gemma-vision": 650,
}


def _ocr_cascade_stages() -> list[tuple[str, str, float]]:
    """Etages de la cascade OCR (label, modele, timeout en secondes),
    du plus rapide/fiable-suffisant au plus lent, classes par fiabilite
    ET vitesse (decision du 2026-08-19 apres comparaison de 9 modeles) :
    aucun modele hallucinant/degenerant (DeepSeek-OCR-2, Granite Vision
    3.2-2B, GLM-4.1V-9B-Thinking sans vision fonctionnelle) n'entre dans
    cette liste, quelle que soit sa vitesse. Le timeout de chaque etape
    est calcule via la regle 1.2x (voir _OCR_STAGE_MEASURED_SECONDS) sur
    la duree mesuree de l'etape suivante. Recalcule a chaque appel (pas
    mis en cache) : les modeles restent surchargeables par variable
    d'environnement en cours d'execution."""
    order = [
        ("PaddleOCR-VL-1.6", HERMES_OCR_MODEL),
        ("LightOnOCR-2-1B", HERMES_OCR_SECONDARY_MODEL),
        ("Qwen2.5-VL-7B", HERMES_OCR_ESCALATION_MODEL),
        ("olmOCR-2-7B", HERMES_OCR_TERTIARY_MODEL),
    ]
    stages = []
    for i, (label, model) in enumerate(order):
        next_label = order[i + 1][0] if i + 1 < len(order) else "Gemma-vision"
        timeout = round(_OCR_STAGE_TIMEOUT_MULTIPLIER * _OCR_STAGE_MEASURED_SECONDS.get(next_label, 650))
        stages.append((label, model, timeout))
    return stages
# Modele d'escalade manuelle uniquement (jamais automatique) : trop lent
# (~12,5 min/page mesure sur ce materiel) et tendance a paraphraser/resumer
# plutot qu'a transcrire litteralement, ce qui le rend risque pour les
# champs critiques (dates, montants, identifiants de dossier). Reserve a
# un declenchement explicite de l'utilisateur (bouton "analyse approfondie").
HERMES_ESCALATION_VISION_MODEL = os.environ.get(
    "HERMES_ESCALATION_VISION_MODEL", "hf.co/DevQuasar/microsoft.Phi-4-reasoning-vision-15B-GGUF:Q4_K_M"
)
# Shared with Caddy on ovh-ai-stack (header X-Api-Key). Empty in local dev.
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
# Gateway Hermes Agent (OpenAI-compatible). Vide = raisonnement via Ollama.
# https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
HERMES_GATEWAY_URL = os.environ.get("HERMES_GATEWAY_URL", "").rstrip("/")
HERMES_GATEWAY_KEY = os.environ.get("HERMES_GATEWAY_KEY", "")
HERMES_GATEWAY_MODEL = os.environ.get("HERMES_GATEWAY_MODEL", "hermes-agent")

# ── Fallback cloud providers ─────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

DEFAULT_PROVIDER = "hermes"
DEFAULT_MODEL = HERMES_DEFAULT_MODEL

EXTRACTION_SYSTEM = """You are Blueseatra's document understanding engine for a B2B facility-maintenance quoting platform.
You receive INCOMING quote requests (\"demande de devis\"), mission orders (\"ordre de mission\"), emails or photos in ANY language.
The request can arrive through ANY channel (manual upload, WhatsApp message, client website form/widget, email, API) and
in ANY file format (PDF text or scanned/rendered image, DOCX, XLSX/CSV table, plain text, photo). Treat all channels and
formats identically once you receive the text or image — never assume a channel-specific structure.

TABLES: if the input is a rendered page image or a serialized spreadsheet/table (rows shown as \"colonne=valeur\" or
pipe-separated cells), read it row by row. Each data row becomes one line_items entry: description = the row's article/
designation column ONLY (see the article-name rule below, never the full row), quantity = the quantity column if present
(else 1), unit = the unit column if present (else infer). IGNORE any column that looks like a price (\"PU\", \"P.U. HT\",
\"Total\", \"Montant\", \"\u20ac\") \u2014 never read or repeat a number from those columns.

You MAY use the technical web context provided (DTU, phasage, spec produit, lots TCE).
You MUST NEVER output a price, tariff, amount, euro, HT, TTC, or market estimate.
Prices come ONLY from the Blueseatra catalog after extraction. If an article is unknown, still list it in line_items.

CRITICAL — materials, not a rewrite:
- Read the request, determine the trade context, then list the CONCRETE materials and accessories needed to execute the work.
- FORBIDDEN: a single line_item that merely copies the request title (e.g. only \"Remplacement du ballon d'eau chaude 100L\").
- Example: replacing a 100L water heater → ballon ECS 100L, groupe de sécurité, flexibles sanitaires, vannes d'arrêt, joints, raccords.
- Example: replacing 3 LED spots → 3 spots LED 230V + accessoires de pose si nécessaires.
- Reason first, then output JSON only.

PARTIES — never merge these three roles. Names change on every request. Do NOT hardcode a company.
- donneur_d_ordre = who must RECEIVE the quote (billing / legal addressee).
  Detect from THIS document only: "Devis ... a adresser EXCLUSIVEMENT a [NAME]",
  "Donneur d'ordre :", letterhead + IBAN/SIRET of the issuer of the demande.
- client_final / client_name = the enseigne labeled "Client :" (site brand). Not the donneur.
- prestataire = the company asked to quote (the tenant). Not the client, not the donneur.
- location = intervention site address, not the donneur headquarters.

Extract:
- donneur_d_ordre, donneur_email, donneur_address
- client_name (= client_final / enseigne), client_email, client_phone, client_address
- work_type (e.g. plomberie, electricite, peinture, menuiserie, climatisation)
- description (full description of work requested)
- location (site address if different from donneur)
- urgency (urgent | normal | planifie)
- estimated_budget (if mentioned in the source text only — copy the mention, do not invent)
- requested_date (if mentioned)
- di_number (if mentioned)
- line_items: list of {description, quantity, unit} — every prestation, even if unknown to the catalog.
  CRITICAL: description = the ARTICLE NAME ONLY (a noun phrase), not the action sentence.
  Strip verbs like "remplacement de", "pose de", "installation de", "changement de".
  Example: "remplacement total de la pompe de relevage" -> description "pompe de relevage", NOT the full sentence.
  This is required for catalog matching (a full sentence never matches a catalog item).
- labor_hours: realistic man-hours for install+pose+cleanup (number, no price)
- travel_days: on-site days (integer)
- crew_size: DEFAULT 2 (most on-site work needs two technicians for safety and speed). Use 1 ONLY for a small/light job (short duration, roughly <= 3h). Do not default to 1.
- quote_options: REQUIRED when the client asks for exclusive alternatives
  (soit A soit B, ou bien, ou les pieces suivantes, option 1 / option 2).
  Each option is a SEPARATE quote: {label, description, line_items, labor_hours, travel_days, crew_size, excludes}.
  AND / puis / ainsi que = ONE option with several lines. OR / soit = several options.
  Never merge exclusive alternatives into one total.

Return ONLY this JSON structure with no markdown, no explanation:
{
  \"donneur_d_ordre\": \"\",
  \"donneur_email\": \"\",
  \"donneur_address\": \"\",
  \"client_name\": \"\",
  \"client_final\": \"\",
  \"client_email\": \"\",
  \"client_phone\": \"\",
  \"client_address\": \"\",
  \"work_type\": \"\",
  \"description\": \"\",
  \"location\": \"\",
  \"urgency\": \"normal\",
  \"estimated_budget\": null,
  \"requested_date\": null,
  \"di_number\": \"\",
  \"labor_hours\": null,
  \"travel_days\": null,
  \"crew_size\": null,
  \"line_items\": [],
  \"quote_options\": []
}"""

_PRICE_RE = re.compile(
    r"(?i)(\d[\d\s.,]{0,14}\s*(€|eur|euros?|\$|usd)|prix\s*[:=]\s*\d|tarif\s*[:=]\s*\d)"
)


async def _web_context_sans_prix(raw_text: str) -> str:
    """Technical web context only. Any price-like token is stripped."""
    q = " ".join((raw_text or "").split())[:160]
    if len(q) < 12:
        return ""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": f"{q} travaux DTU deroulement -prix -tarif",
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
            r.raise_for_status()
            data = r.json()
        bits = []
        if data.get("AbstractText"):
            bits.append(data["AbstractText"])
        for t in (data.get("RelatedTopics") or [])[:4]:
            if isinstance(t, dict) and t.get("Text"):
                bits.append(t["Text"])
        text = _PRICE_RE.sub("[prix masque]", " ".join(bits))
        return text[:1200].strip()
    except Exception:
        return ""


def _wants_think(model: str) -> bool:
    name = (model or "").lower()
    return (
        name.startswith("qwen3")
        or name.startswith("gemma4")
        or name.startswith("deepseek-r1")
    )


async def resolve_ai_config(
    tenant_settings: dict,
    role: str = "extract",
) -> tuple[str, str, str]:
    """Return (provider, model, api_key) for this tenant.

    role=extract → qwen2.5:14b (parse rapide, texte seul). Réservé au texte
      colle manuellement (pas un fichier importe).
    role=file → HERMES_VISION_MODEL, gemma4:26b par defaut, raisonnement
      toujours actif (_wants_think). Modèle PAR DEFAUT pour tout fichier
      importe (PDF, DOCX, XLSX, CSV, TXT, image) — tableaux inclus — quel
      que soit son etat de lisibilite. Decision du 2026-08-18 : Gemma+
      raisonnement devient le moteur d'extraction par defaut des devis,
      plus fiable sur les tableaux que qwen2.5:14b (texte seul, sans
      raisonnement).
    role=vision → alias de role=file, conserve pour la compatibilite avec
      le code existant qui distinguait "image" de "fichier texte".
    role=reason → gemma4:26b (décomposition matériaux / lots).
    Un tenant qui a choisi un vrai modèle (pas hermes*) garde son override.
    """
    provider = tenant_settings.get("ai_provider") or DEFAULT_PROVIDER
    model = tenant_settings.get("ai_model") or DEFAULT_MODEL
    api_key = tenant_settings.get("ai_key") or ""

    # Normalize provider name
    provider = provider.lower()

    # Hermes/Ollama: tenant key unused; gateway auth is HERMES_API_KEY.
    if provider == "hermes":
        model = model or HERMES_DEFAULT_MODEL
        if (model or "").lower().startswith("hermes"):
            if role in ("vision", "file"):
                model = HERMES_VISION_MODEL
            elif role == "extract":
                model = HERMES_EXTRACT_MODEL
            else:
                model = HERMES_REASONING_MODEL

    return provider, model, api_key


# VPS d'inference CPU-only (pas de GPU, 8 vCPU/22Go RAM) : le mode
# raisonnement de Gemma/Qwen3 peut generer plusieurs milliers de tokens de
# reflexion avant la reponse finale, ce qui a fait grimper une extraction a
# ~11 minutes en test reel (2026-08-18). Cette consigne est ajoutee au
# system prompt UNIQUEMENT quand le modele a le raisonnement actif
# (_wants_think) : elle demande une reflexion breve plutot que de desactiver
# le raisonnement, pour garder le gain de fiabilite sur les tableaux tout en
# reduisant le volume de texte de reflexion genere.
_THINK_BREVITY_HINT = (
    "\n\nMode raisonnement : reflechis brievement (quelques phrases maximum, "
    "pas d'enumeration exhaustive etape par etape) avant de donner ta reponse "
    "finale. La reflexion sert a verifier ton analyse, pas a la detailler."
)


async def _call_hermes_ollama(
    model: str,
    system_prompt: str,
    user_message: str,
    image_b64: str | None = None,
) -> str:
    """Call Hermes AI via Ollama REST API on OVH VPS."""
    effective_system_prompt = system_prompt
    if _wants_think(model):
        effective_system_prompt = system_prompt + _THINK_BREVITY_HINT
    messages = [
        {"role": "system", "content": effective_system_prompt},
    ]

    if image_b64:
        messages.append({
            "role": "user",
            "content": user_message,
            "images": [image_b64],
        })
    else:
        messages.append({"role": "user", "content": user_message})

    model = MODEL_ALIASES.get((model or "").strip(), model)
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 4096,
        },
    }
    # hermes-3 refuse think (400). qwen3 et gemma4 l'acceptent.
    if _wants_think(model):
        payload["think"] = True

    headers = {}
    if HERMES_API_KEY:
        headers["X-Api-Key"] = HERMES_API_KEY

    # VPS CPU-only : Gemma en mode raisonnement peut prendre de 80s a plus de
    # 10 minutes selon la charge et la longueur du raisonnement genere
    # (mesure en conditions reelles le 2026-08-18). Un timeout de 180s
    # provoquait un ReadTimeout sur des extractions parfaitement valides,
    # qui basculaient alors sur l'extracteur de secours degrade -> exactement
    # le probleme signale ("Contenu source" jamais lu par l'IA). Ce timeout
    # ne bloque jamais de requete HTTP utilisateur : l'appel tourne dans une
    # tache d'arriere-plan (voir process_request), un delai genereux est donc
    # sans risque. Calcule par modele plus bas (current_timeout), car la
    # liste de repli peut mixer un modele avec raisonnement et un modele sans.

    url = f"{HERMES_BASE_URL.rstrip('/')}/api/chat"
    last_err = None
    models = []
    # Avec une image, ne jamais retomber sur un modele texte-seul (qwen2.5,
    # hermes3/hermes-3) : ils renvoient HTTP 400 "model does not support
    # multimodal requests" au lieu d'une vraie erreur reseau/timeout, ce qui
    # masque le vrai probleme et gaspille le budget de tentatives.
    fallback_pool = HERMES_VISION_FALLBACK_MODELS if image_b64 else HERMES_FALLBACK_MODELS
    for m in [model, *fallback_pool]:
        alias = MODEL_ALIASES.get((m or "").strip(), m)
        if alias and alias not in models:
            models.append(alias)
    for current in models:
        payload["model"] = current
        if _wants_think(current):
            payload["think"] = True
        else:
            payload.pop("think", None)
        # HERMES_BASE_URL a eu un enregistrement DNS A parasite pointant vers
        # un hebergement mutualise sans rapport (voir incident du 2026-08-18) :
        # le round-robin DNS envoyait ~1 requete sur 2 vers le mauvais serveur,
        # qui repond en HTML au lieu du JSON attendu d'Ollama. Ce n'est PAS une
        # erreur de modele : chaque tentative ouvre un client httpx neuf (donc
        # une nouvelle resolution DNS/connexion) avant d'abandonner ce modele,
        # et le message d'erreur distingue ce cas pour que "IA indisponible"
        # pointe vers un probleme reseau/DNS plutot qu'un faux echec de modele.
        current_timeout = 900.0 if _wants_think(current) else 180.0
        # Un raisonnement lent-mais-reussi n'est PAS le meme probleme qu'un
        # routage DNS parasite (reponse HTML instantanee, voir
        # _looks_like_wrong_server) : retenter le MEME modele apres un vrai
        # ReadTimeout ne fait que doubler/tripler une attente deja tres
        # longue sans rien resoudre. Seule la detection "mauvais serveur"
        # justifie une nouvelle tentative sur le meme modele ; tout autre
        # echec (timeout, erreur HTTP, reponse vide) passe directement au
        # modele suivant de la liste de repli.
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=current_timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 400 and payload.pop("think", None) is not None:
                        response = await client.post(url, json=payload, headers=headers)
                if _looks_like_wrong_server(response):
                    last_err = (
                        f"routage DNS incorrect vers {HERMES_BASE_URL} (reponse HTML au lieu de JSON Ollama, "
                        f"tentative {attempt + 1}/3) ({current})"
                    )
                    continue  # nouvelle tentative = nouvelle resolution DNS possible
                if response.status_code >= 400:
                    last_err = f"HTTP {response.status_code} ({current}): {(response.text or '')[:180]}"
                    break
                data = response.json()
                msg = data.get("message") or {}
                content = (msg.get("content") or "").strip()
                if content:
                    return content
                last_err = f"reponse vide ({current})"
                break
            except Exception as exc:
                last_err = f"{type(exc).__name__} ({current}): {exc or repr(exc)}"
                break  # pas de retry sur le meme modele : voir commentaire ci-dessus
    raise RuntimeError(last_err or "aucun modele Ollama n'a repondu")


def _looks_like_wrong_server(response) -> bool:
    """Detecte une reponse HTML (page d'erreur d'un autre serveur) la ou
    Ollama repond toujours en JSON. Signale un probleme de routage/DNS plutot
    qu'une erreur applicative normale."""
    ctype = (response.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        return False
    body_start = (response.text or "").lstrip()[:100].lower()
    return body_start.startswith("<!doctype html") or body_start.startswith("<html")


async def _call_hermes_gateway(
    system_prompt: str,
    user_message: str,
) -> str:
    """Call Hermes Agent via POST /v1/chat/completions behind Caddy."""
    if not HERMES_GATEWAY_URL:
        raise RuntimeError("HERMES_GATEWAY_URL vide")
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["X-Api-Key"] = HERMES_API_KEY
    if HERMES_GATEWAY_KEY:
        headers["Authorization"] = f"Bearer {HERMES_GATEWAY_KEY}"
    payload = {
        "model": HERMES_GATEWAY_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
    }
    url = f"{HERMES_GATEWAY_URL}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=360.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(
                f"HTTP {response.status_code} (gateway): {(response.text or '')[:180]}"
            )
        data = response.json()
    content = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip()
    if not content:
        raise RuntimeError("reponse gateway vide")
    return content


async def _call_reason(
    model: str,
    system_prompt: str,
    user_message: str,
) -> str:
    """Raisonnement : gateway Hermes si configuré, sinon Ollama."""
    if HERMES_GATEWAY_URL:
        try:
            return await _call_hermes_gateway(system_prompt, user_message)
        except Exception:
            pass
    return await _call_hermes_ollama(model, system_prompt, user_message)


async def _call_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
    image_b64: str | None = None,
) -> str:
    """Fallback: call OpenAI API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    content: list = [{"type": "text", "text": user_message}]
    if image_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        })

    payload = {
        "model": model or "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _fallback_extract(raw_text: str) -> dict:
    """Extraction deterministe si Ollama/Hermes ne repond pas. Aucun prix."""
    text = (raw_text or "").replace("\r\n", "\n")
    def _m(pat, flags=re.I):
        m = re.search(pat, text, flags)
        return (m.group(1).strip() if m else "")

    client = _m(r"Client\s*:\s*([^\n]+)") or _m(r"client_final\s*:\s*([^\n]+)")
    donneur = (
        _m(r"adresser\s+EXCLUSIVEMENT\s+[àa]\s+([A-Z0-9][A-Z0-9 .,'-]{1,80}?)(?:\s+-\s+|\s+et\s+à|\n|$)")
        or _m(r"Donneur\s+d['’]ordre\s*:\s*([^\n]+)")
        or _m(r"Destinataire\s+du\s+devis\s*:\s*([^\n]+)")
    )
    if donneur:
        donneur = re.sub(r"\s{2,}", " ", donneur).strip(" -.,")
    donneur_email = ""
    excl = re.search(r"adresser\s+EXCLUSIVEMENT.{0,200}?([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, re.I | re.S)
    if excl:
        donneur_email = excl.group(1)
    labeled_email = _m(r"E-?Mail\s*:\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})")
    email = labeled_email or _m(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})")
    if email and donneur_email and email.lower() == donneur_email.lower():
        email = "" if (not labeled_email or labeled_email.lower() == donneur_email.lower()) else labeled_email

    di = _m(r"N°\s*Dossier\s*DI\s*:\s*([0-9A-Za-z-]+)") or _m(r"\bDI\s*:?\s*([0-9]{6,})")
    deadline = _m(r"retour souhaitée? le\s*:\s*([^\n]+)") or _m(r"Date de la demande\s*:\s*([^\n]+)")
    phone = _m(r"Tél(?:éphone)?\s*[:.]\s*([^\n]+)")
    site = ""
    sm = re.search(r"Site d'intervention(.*?)Demande de devis", text, re.I | re.S)
    if sm:
        block = sm.group(1)
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        skip = {"prestataire", "anelec", "france", "téléphone", "tel portable", "e-mail"}
        kept = [ln for ln in lines if not any(ln.lower().startswith(s) for s in skip) and "@" not in ln]
        # often: ANELEC block then client site block — take last address-like chunk
        site = "\n".join(kept[-5:]) if kept else ""
    desc = ""
    dm = re.search(r"Demande de devis[^\n]*\n(.*)$", text, re.I | re.S)
    if dm:
        desc = re.sub(r"\n{3,}", "\n\n", dm.group(1)).strip()
        desc = desc[:800]
    if not desc:
        desc = text[:400].strip()
    work = "electricite" if re.search(r"spot|led|ballon|plomberie", desc, re.I) else "maintenance"
    if re.search(r"vitrine|volige|profil", desc, re.I):
        work = "serrurerie"
    return {
        "client_name": client,
        "client_email": email,
        "client_phone": phone,
        "client_address": "",
        "work_type": work,
        "description": desc or "Travaux selon demande",
        "location": site,
        "urgency": "normal",
        "estimated_budget": None,
        "requested_date": deadline,
        "di_number": di,
        "line_items": [{"description": desc.split(".")[0][:160], "quantity": 1, "unit": "ens"}] if desc else [],
        "donneur_d_ordre": donneur,
        "donneur_email": donneur_email,
        "client_final": client,
        "intervention_site": site,
        "intervention_address": site,
        "quote_options": quote_scenarios.detect_exclusive_options(text),
    }


async def extract_request_data(
    raw_text: str,
    tenant_settings: dict,
    image_bytes: bytes | None = None,
    from_file: bool = False,
) -> dict:
    """Main entry point: extract structured quote data from raw text/image.

    from_file=True dès que le contenu provient d'un fichier importe (PDF,
    DOCX, XLSX, CSV, TXT, image) plutot que d'un texte colle a la main.
    Decision produit du 2026-08-18 : Gemma (gemma4:26b, raisonnement
    toujours actif) est le moteur d'extraction PAR DEFAUT pour tout fichier,
    tableaux inclus — qwen2.5:14b (rapide, sans raisonnement, texte seul)
    reste reserve au texte colle manuellement. Une image exige de toute
    facon un modele multimodal (HTTP 400 sinon, incident du 2026-08-18) :
    role="file" couvre les deux cas.
    """
    role = "file" if (image_bytes or from_file) else "extract"
    provider, model, api_key = await resolve_ai_config(tenant_settings, role=role)

    image_b64 = None
    if image_bytes:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    web_ctx = await _web_context_sans_prix(raw_text)
    user_message = f"Extract structured data from this quote request:\n\n{raw_text}"
    if web_ctx:
        user_message += (
            "\n\nContexte technique internet (SANS aucun prix — ne pas en deduire un tarif):\n"
            + web_ctx
        )

    # Cascade de structuration sequentielle (decision du 2026-08-19) : ne
    # s'applique QUE lorsqu'il n'y a pas d'image (texte deja lisible, sortie
    # OCR ou fichier texte natif) et que le fournisseur reste hermes/ollama
    # (un tenant qui a explicitement choisi OpenAI garde ce choix, pas de
    # cascade locale). Une image passe toujours par le chemin existant
    # (gemma4:26b + son pool de secours vision) car qwen3:14b/deepseek-r1:14b
    # sont des modeles TEXTE SEUL, sans capacite multimodale.
    use_structuring_cascade = (
        from_file and image_b64 is None and provider in ("hermes", "ollama")
    )

    structuring_engine = None
    try:
        if use_structuring_cascade:
            raw_response, structuring_engine = await _call_structuring_cascade(
                system_prompt=EXTRACTION_SYSTEM,
                user_message=user_message,
            )
        elif provider == "hermes":
            raw_response = await _call_hermes_ollama(
                model=model,
                system_prompt=EXTRACTION_SYSTEM,
                user_message=user_message,
                image_b64=image_b64,
            )
        elif provider == "openai":
            raw_response = await _call_openai(
                api_key=api_key or OPENAI_API_KEY,
                model=model,
                system_prompt=EXTRACTION_SYSTEM,
                user_message=user_message,
                image_b64=image_b64,
            )
        else:
            # Generic Ollama-compatible endpoint for other local models
            raw_response = await _call_hermes_ollama(
                model=model,
                system_prompt=EXTRACTION_SYSTEM,
                user_message=user_message,
                image_b64=image_b64,
            )
    except Exception as e:
        detail = f"{type(e).__name__}: {e or repr(e)}"
        # Regle produit du 2026-08-18 : un fichier importe (from_file=True ou
        # image) ne doit JAMAIS etre "devine" par l'extracteur heuristique de
        # secours (regex sur le texte brut) — c'est exactement ce qui produisait
        # une extraction vide/plausible en apparence alors que l'IA n'avait
        # jamais reellement lu le contenu (incident "LOT_20_LA_SABLIERE").
        # Pour un fichier, un echec de Gemma doit rester un echec visible
        # (statut "failed"), jamais un resultat degrade qui a l'air valide.
        # Le texte colle manuellement (from_file=False) garde le filet de
        # securite heuristique : il n'y a pas d'alternative IA-only pour ce
        # canal et un resultat partiel reste mieux qu'un blocage total.
        if from_file or image_bytes:
            return {"_error": f"Extraction Gemma indisponible ({detail}). Aucune extraction de secours "
                                "n'est utilisee pour un fichier importe : reimportez ou reessayez.",
                    "line_items": [], "confidence": 0.0}
        try:
            fallback = _fallback_extract(raw_text)
        except Exception as fe:
            fallback = {"description": (raw_text or "")[:400], "line_items": [], "_warning": f"IA indisponible ({detail}). Secours aussi en echec ({type(fe).__name__})."}
        fallback["_warning"] = fallback.get("_warning") or f"IA indisponible ({detail}). Extraction automatique de secours."
        fallback["confidence"] = 0.45
        return _normalize_extracted(fallback)

    # Parse JSON response
    try:
        cleaned = _strip_think(raw_response)
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = _normalize_extracted(_parse_json_object(cleaned))
        if structuring_engine:
            parsed["_structuring_engine"] = structuring_engine
        return await expand_work_into_materials(parsed, tenant_settings)
    except json.JSONDecodeError:
        # Meme regle : une reponse Gemma illisible sur un fichier importe ne
        # doit jamais etre remplacee par une extraction heuristique degradee.
        if from_file or image_bytes:
            return {"_error": "Reponse de Gemma illisible (JSON invalide) sur ce fichier. "
                                "Aucune extraction de secours n'est utilisee : reessayez.",
                    "line_items": [], "confidence": 0.0,
                    "_raw_ai_response": (raw_response or "")[:1000]}
        try:
            fallback = _fallback_extract(raw_text)
        except Exception as fe:
            fallback = {"description": (raw_text or "")[:400], "line_items": [], "_warning": f"Reponse IA illisible. Secours en echec ({type(fe).__name__})."}
        fallback["_warning"] = fallback.get("_warning") or "Reponse IA illisible. Extraction automatique de secours."
        fallback["confidence"] = 0.45
        fallback["_raw_ai_response"] = (raw_response or "")[:1000]
        return _normalize_extracted(fallback)


def _strip_think(text: str) -> str:
    text = text or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.S | re.I)
    return text.strip()


def _parse_json_object(text: str) -> dict:
    text = (text or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("no object", text, 0)
    return json.loads(text[start:end + 1])


def _is_restatement(extracted: dict) -> bool:
    items = extracted.get("line_items") or []
    desc = (extracted.get("description") or "").strip().lower()
    if len(items) == 0:
        return True
    if len(items) > 2:
        return False
    lab = (items[0].get("label") or items[0].get("description") or "").strip().lower()
    if not lab:
        return True
    return lab == desc or lab in desc or desc in lab


EXPAND_SYSTEM = """Tu es métreur TCE. On te donne une demande de travaux.
Raisonne, puis sors UNIQUEMENT un JSON :
{"line_items":[{"description":"article concret","quantity":1,"unit":"u","category":"plomberie sanitaire"}]}

Règles:
- Décompose en fournitures / accessoires nécessaires à l'exécution.
- INTERDIT de recopier le titre de la demande comme seule ligne.
- Aucun prix, aucun €, aucun tarif.
- Quantités minimales réalistes.
- Si une liste d'articles catalogue (libellés seulement) est fournie, préfère ces libellés.
"""


async def expand_work_into_materials(extracted: dict, tenant_settings: dict, catalog_labels: list | None = None) -> dict:
    """Turn a copied request title into concrete material lines. No prices."""
    extracted = dict(extracted or {})
    if not _is_restatement(extracted):
        return extracted
    desc = extracted.get("description") or ""
    labels = [str(x).strip() for x in (catalog_labels or []) if x][:80]
    user = f"Demande: {desc}\nType: {extracted.get('work_type') or ''}\n"
    if labels:
        user += "Articles catalogue (libellés seulement, SANS prix):\n- " + "\n- ".join(labels)
    try:
        provider, model, api_key = await resolve_ai_config(tenant_settings, role="reason")
        if provider == "openai":
            raw = await _call_openai(api_key or OPENAI_API_KEY, model, EXPAND_SYSTEM, user)
        else:
            raw = await _call_reason(model, EXPAND_SYSTEM, user)
        data = _parse_json_object(_strip_think(raw))
        items = data.get("line_items") or []
        if len(items) >= 2:
            extracted["line_items"] = items
            extracted["_expanded"] = True
    except Exception:
        pass
    return _normalize_extracted(extracted)


def _normalize_extracted(data: dict) -> dict:
    """Map Hermes/Ollama keys onto the UI / devis schema."""
    if not isinstance(data, dict):
        return data
    enseigne = (data.get("client_final") or data.get("client_name") or data.get("client") or "").strip()
    donneur = (data.get("donneur_d_ordre") or data.get("donneur") or "").strip()
    if donneur and enseigne and donneur.lower() == enseigne.lower():
        # do not keep a collapsed party; prefer explicit Client: as enseigne
        enseigne = enseigne
    if not enseigne:
        enseigne = donneur
        donneur = donneur
    site = data.get("intervention_address") or data.get("intervention_site") or data.get("location") or data.get("client_address") or ""
    data["client_final"] = enseigne
    data["client_name"] = enseigne
    if donneur:
        data["donneur_d_ordre"] = donneur
    else:
        data.setdefault("donneur_d_ordre", "")
    data.setdefault("intervention_site", site)
    data.setdefault("intervention_address", site)
    data.setdefault("language", data.get("language") or "fr")
    if data.get("confidence") is None and (enseigne or donneur):
        data["confidence"] = 0.7
    lines = []
    for li in data.get("line_items") or []:
        if not isinstance(li, dict):
            continue
        row = dict(li)
        row["label"] = row.get("label") or row.get("description") or ""
        row["qty"] = row.get("qty") if row.get("qty") is not None else row.get("quantity")
        lines.append(row)
    if lines:
        data["line_items"] = lines
    for k in ("labor_hours", "travel_days", "crew_size"):
        if data.get(k) in ("", "null"):
            data[k] = None
    if not isinstance(data.get("quote_options"), list):
        data["quote_options"] = []
    return data


async def extract_from_text(
    text: str,
    tenant_settings: dict,
    session_id: str | None = None,
    from_file: bool = False,
) -> dict:
    """Adapter used by server.process_request.

    from_file=True pour tout texte issu d'un fichier importe (PDF, DOCX,
    XLSX, CSV, TXT) plutot que colle a la main — route alors vers Gemma
    (role="file", raisonnement actif) au lieu de qwen2.5:14b. Voir
    extract_request_data pour la justification complete.
    """
    return await extract_request_data(text or "", tenant_settings, from_file=from_file)


async def _call_ocr_model(image_bytes: bytes, model: str, timeout: float = 240.0) -> str:
    """Transcription litterale via un modele OCR/vision specialise (pas de
    raisonnement general) : rapide et fidele au pixel, mais ne structure
    rien. Utilisee pour chaque etape OCR de la cascade (PaddleOCR-VL-1.6,
    puis Qwen2.5-VL-7B en second avis) ; jamais la reponse finale.
    Leve une exception sur tout echec (reseau, HTTP, reponse vide) ; c'est
    au niveau appelant (extract_from_image) de decider du secours."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": (
                "Transcribe all text from this document image exactly as written, "
                "preserving layout, tables and reading order. Do not summarize, "
                "translate, or add any text that is not visible in the image."
            ),
            "images": [image_b64],
        }],
        "stream": False,
    }
    headers = {}
    if HERMES_API_KEY:
        headers["X-Api-Key"] = HERMES_API_KEY
    url = f"{HERMES_BASE_URL.rstrip('/')}/api/chat"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"{model} HTTP {response.status_code}: {(response.text or '')[:180]}")
    data = response.json()
    content = ((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError(f"{model}: reponse vide")
    return content


def _ocr_result_acceptable(text: str) -> bool:
    """Filtre deterministe apres l'etape PaddleOCR : rejette un resultat
    trop court ou charabia (memes signes que _looks_garbled, mais applique
    a la SORTIE de l'OCR plutot qu'au calque texte PDF d'origine — detecte
    un echec de l'OCR lui-meme, ex. image trop degradee)."""
    s = (text or "").strip()
    if len(s) < 40:
        return False
    return not _looks_garbled(s)


def _extraction_seems_incomplete(extracted: dict, source_text: str) -> bool:
    """Deuxieme filtre deterministe, applique APRES que Gemma ait structure
    le texte OCR en JSON : sert de juge peu couteux (pas d'appel IA
    supplementaire) pour decider si le resultat est exploitable ou s'il
    faut escalader vers la vision directe. Un texte OCR substantiel sans
    aucune ligne ni description exploitee est le signe le plus net d'une
    structuration ratee malgre une transcription correcte."""
    if extracted.get("_error"):
        return True
    if (extracted.get("confidence") or 0) < 0.3:
        return True
    has_substantial_text = len((source_text or "").strip()) > 200
    line_items = extracted.get("line_items") or []
    description = (extracted.get("description") or "").strip()
    if has_substantial_text and not line_items and not description:
        return True
    return False


async def _try_ocr_stage(image_bytes: bytes, model: str, tenant_settings: dict, timeout: float = 240.0) -> tuple[dict | None, str | None, str | None]:
    """Tente une etape OCR+structuration complete avec un modele donne.
    Renvoie (resultat, texte_ocr, erreur) : resultat est None si l'etape
    doit etre consideree en echec (erreur OCR, texte inutilisable, ou
    structuration jugee incomplete par _extraction_seems_incomplete) —
    dans ce cas l'appelant passe a l'etape suivante de la cascade. Le
    timeout est calcule par l'appelant selon la regle 1.2x (voir
    _ocr_cascade_stages) : ne pas attendre sur ce modele plus longtemps
    que necessaire pour de toute facon passer a l'etape suivante."""
    try:
        ocr_text = await _call_ocr_model(image_bytes, model, timeout=timeout)
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e or repr(e)}"
    if not _ocr_result_acceptable(ocr_text):
        return None, ocr_text, None
    result = await extract_request_data(ocr_text, tenant_settings, from_file=True)
    if _extraction_seems_incomplete(result, ocr_text):
        return None, ocr_text, None
    return result, ocr_text, None


async def extract_from_image(image_bytes: bytes, tenant_settings: dict, session_id: str | None = None) -> dict:
    """Adapter used by server.process_request for photos and rendered PDF
    pages. Cascade IA-uniquement, decision du 2026-08-18 (comparaison de 8
    modeles — voir 0quater du skill intake-demande-devis pour le detail) :

    1. PaddleOCR-VL-1.6 transcrit l'image en texte litteral (le plus
       rapide, specialise OCR, ~110s/page mesure, mais a echoue une fois
       sur une image composite a plusieurs pages).
    2. LightOnOCR-2-1B (entraine avec une forte couverture de documents
       francais, SOTA OlmOCR-Bench a seulement 596M parametres), sortie
       mieux structuree (Markdown/HTML avec tableaux corrects), ~200s.
    3. Qwen2.5-VL-7B (officiel Ollama, qualite superieure sur ce type de
       document), ~246s.
    4. olmOCR-2-7B (meilleure fidelite de structure de tableau observee),
       ~587s.

    Apres chaque etape : filtre deterministe (_ocr_result_acceptable) sur
    le texte OCR, puis structuration par Gemma en appel TEXTE (role="file")
    — pas de re-encodage d'image — et deuxieme filtre deterministe
    (_extraction_seems_incomplete) sur le JSON resultant. Si une etape
    echoue, depasse son timeout (regle 1.2x, voir _ocr_cascade_stages), ou
    produit un resultat insuffisant, passage a l'etape suivante.

    5. Secours final : vision directe de Gemma sur l'image (comportement
       historique avant cette cascade, ~600-750s mesure), utilise si
       aucune des quatre etapes OCR precedentes n'a produit un resultat
       exploitable.

    Chaque etape reste 100% IA (jamais d'heuristique de secours sur le
    contenu du fichier, conformement a la regle 0ter/0quater du skill
    intake-demande-devis). Phi-4-reasoning-vision-15B n'est PAS dans cette
    cascade automatique : voir escalate_to_deep_vision pour l'escalade
    manuelle explicite. DeepSeek-OCR-2, GLM-4.1V-9B-Thinking et Granite
    Vision 3.2-2B ont ete evalues et rejetes (invention de contenu et/ou
    degenerescence en boucle sur ce type de document dense).
    """
    last_ocr_text = None
    errors = []
    for label, model, timeout in _ocr_cascade_stages():
        result, ocr_text, error = await _try_ocr_stage(image_bytes, model, tenant_settings, timeout=timeout)
        if ocr_text is not None:
            last_ocr_text = ocr_text
        if error:
            errors.append(f"{label}: {error}")
        if result is not None:
            result["_ocr_engine"] = label
            result["_ocr_text"] = ocr_text
            return result

    # Secours final : vision directe de Gemma. Atteint si aucune etape OCR
    # n'a produit un resultat exploitable (erreurs listees dans errors, ou
    # structuration jugee incomplete malgre un texte OCR correct).
    fallback = await extract_request_data("", tenant_settings, image_bytes=image_bytes)
    if errors:
        fallback["_ocr_fallback_reason"] = (
            "Etapes OCR indisponibles (" + "; ".join(errors) + ") — secours vision directe Gemma."
        )
    else:
        fallback["_ocr_fallback_reason"] = (
            "Extraction structuree jugee incomplete a partir des etapes OCR — "
            "secours vision directe Gemma."
        )
    if last_ocr_text:
        fallback["_ocr_text"] = last_ocr_text
    fallback["_ocr_engine"] = HERMES_VISION_MODEL
    return fallback


async def escalate_to_deep_vision(image_bytes: bytes, tenant_settings: dict) -> dict:
    """Escalade manuelle uniquement (jamais appelee automatiquement par le
    pipeline) : Phi-4-reasoning-vision-15B, reserve aux cas ou Gemma et
    PaddleOCR-VL-1.6 echouent tous les deux ou restent insuffisants selon
    l'utilisateur. Tres lent (~12,5 min/page mesure) et a tendance a
    paraphraser/resumer plutot qu'a transcrire litteralement — le resultat
    doit etre presente comme un complement a comparer, jamais comme un
    remplacement silencieux de l'extraction Gemma/PaddleOCR existante."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": HERMES_ESCALATION_VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": (
                "Extract all text and structured information from this document image. "
                "Do not invent content that is not visible in the image."
            ),
            "images": [image_b64],
        }],
        "stream": False,
        "options": {"num_predict": 2000},
    }
    headers = {}
    if HERMES_API_KEY:
        headers["X-Api-Key"] = HERMES_API_KEY
    url = f"{HERMES_BASE_URL.rstrip('/')}/api/chat"
    async with httpx.AsyncClient(timeout=1200.0) as client:
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"Escalade vision HTTP {response.status_code}: {(response.text or '')[:180]}")
    data = response.json()
    content = ((data.get("message") or {}).get("content") or "").strip()
    return {
        "engine": HERMES_ESCALATION_VISION_MODEL,
        "content": content,
        "warning": (
            "Analyse approfondie generee par un modele de raisonnement visuel lent, "
            "a tendance a paraphraser plutot qu'a transcrire litteralement — a comparer "
            "avec l'extraction principale, ne pas utiliser seule comme source de verite."
        ),
    }


async def _ocr_page_text(image_bytes: bytes) -> tuple[str | None, str | None, str | None]:
    """Tente l'OCR d'UNE page via la cascade a 4 etages
    (_ocr_cascade_stages : PaddleOCR-VL-1.6 -> LightOnOCR-2-1B ->
    Qwen2.5-VL-7B -> olmOCR-2-7B), transcription litterale seule, pas de
    structuration JSON — celle-ci se fait une seule fois sur le texte
    combine de toutes les pages, voir extract_from_pdf_pages. Chaque
    etape a son propre timeout selon la regle 1.2x. Renvoie
    (texte, moteur, erreur) ; texte est None si toutes les etapes ont
    echoue ou produit un texte inutilisable pour cette page precise."""
    errors = []
    for label, model, timeout in _ocr_cascade_stages():
        try:
            text = await _call_ocr_model(image_bytes, model, timeout=timeout)
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__}: {e or repr(e)}")
            continue
        if _ocr_result_acceptable(text):
            return text, label, None
    return None, None, "; ".join(errors) if errors else None


async def extract_from_pdf_pages(pages: list[bytes], tenant_settings: dict, session_id: str | None = None) -> dict:
    """Traite chaque page d'un PDF INDIVIDUELLEMENT plutot qu'empilees en
    une seule image composite. Decision du 2026-08-19 : une image
    composite multi-pages peut depasser les limites de
    resolution/aspect-ratio de certains modeles OCR specialises (observe
    en conditions reelles : echec HTTP 500 de PaddleOCR-VL-1.6 sur une
    image a 3 pages empilees, alors qu'il reussit systematiquement page
    par page sur le meme document). Traiter page par page isole aussi le
    cout d'un secours vision a la seule page qui echoue, plutot que de
    refaire tout le document en vision directe si une seule page pose
    probleme.

    Pour chaque page : cascade OCR (_ocr_page_text). Si toutes les etapes
    echouent pour cette page, secours vision directe de Gemma UNIQUEMENT
    sur cette page (transcription litterale, pas de structuration).
    Le texte de toutes les pages est ensuite concatene et structure en
    UNE SEULE fois par Gemma (evite de payer N fois le cout de
    structuration).
    """
    page_texts = []
    engines_used = []
    fallback_pages = []
    for i, page_bytes in enumerate(pages):
        text, engine, _error = await _ocr_page_text(page_bytes)
        if not text:
            try:
                text = await _call_ocr_model(page_bytes, HERMES_VISION_MODEL, timeout=_OCR_FINAL_FALLBACK_TIMEOUT)
                engine = HERMES_VISION_MODEL
                fallback_pages.append(i + 1)
            except Exception:
                text = None
        if text:
            page_texts.append(f"--- Page {i + 1} ---\n{text}")
            if engine and engine not in engines_used:
                engines_used.append(engine)

    if not page_texts:
        return {
            "_error": "Aucune page n'a pu etre lue par un modele IA (OCR specialise ou vision directe).",
            "line_items": [], "confidence": 0.0,
        }

    combined_text = "\n\n".join(page_texts)
    result = await extract_request_data(combined_text, tenant_settings, from_file=True)
    result["_ocr_engine"] = " + ".join(engines_used) if engines_used else HERMES_VISION_MODEL
    result["_ocr_text"] = combined_text
    if fallback_pages:
        result["_ocr_fallback_reason"] = (
            f"Page(s) {', '.join(map(str, fallback_pages))} illisible(s) par les modeles OCR specialises — "
            "lecture visuelle directe par Gemma pour cette/ces page(s) uniquement."
        )
    return result


def render_pdf_pages_to_images(content: bytes, max_pages: int = 4, scale: float = 2.0) -> list[bytes]:
    """Rend chaque page en image INDIVIDUELLE (jamais empilees) — voir
    extract_from_pdf_pages pour la justification. Renvoie une liste
    d'octets JPEG, une entree par page."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(io.BytesIO(content))
    n = min(len(pdf), max_pages)
    images = []
    max_h = 3000  # cap resolution par page — la plupart des modeles vision limitent la taille d'image
    for i in range(n):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil().convert("RGB")
        page.close()
        if img.height > max_h:
            ratio = max_h / img.height
            img = img.resize((int(img.width * ratio), max_h))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        images.append(buf.getvalue())
    pdf.close()
    if not images:
        raise ValueError("PDF vide ou illisible")
    return images


def extract_pdf_text(content: bytes) -> str:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(io.BytesIO(content))
    parts = []
    for page in pdf:
        textpage = page.get_textpage()
        parts.append(textpage.get_text_bounded())
        textpage.close()
        page.close()
    pdf.close()
    return "\n".join(parts).strip()


def _looks_garbled(text: str) -> bool:
    """Detecte un calque texte PDF illisible (police subset sans table
    ToUnicode correcte, PDF genere par certains outils/imprimantes qui
    n'exposent pas le vrai Unicode). Symptome : beaucoup de caracteres de
    controle et tres peu de mots reconnaissables, meme si le rendu visuel
    (image de la page) est parfaitement lisible.

    Voir skill intake-demande-devis / detection-format.md pour la logique
    generale d'extraction multi-format.
    """
    s = (text or "").strip()
    if len(s) < 20:
        return False  # trop court pour juger ; le pipeline gere le vide separement
    total = len(s)
    control = sum(1 for c in s if ord(c) < 32 and c not in "\n\r\t")
    letters = sum(1 for c in s if c.isalpha())
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", s)
    word_chars = sum(len(w) for w in words)
    if control / total > 0.03:
        return True
    if letters / total < 0.35:
        return True
    if word_chars / total < 0.25:
        return True
    return False


def render_pdf_to_composite_image(content: bytes, max_pages: int = 4, scale: float = 2.0) -> bytes:
    """Rend les premieres pages d'un PDF en UNE image composite (empilees
    verticalement) pour l'extraction visuelle par le modele multimodal,
    utilise quand le calque texte est illisible ou absent (PDF scanne,
    police sans correspondance Unicode, tableau vectoriel). Renvoie des
    octets JPEG."""
    import pypdfium2 as pdfium
    from PIL import Image

    pdf = pdfium.PdfDocument(io.BytesIO(content))
    n = min(len(pdf), max_pages)
    imgs = []
    for i in range(n):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        imgs.append(bitmap.to_pil().convert("RGB"))
        page.close()
    pdf.close()
    if not imgs:
        raise ValueError("PDF vide ou illisible")
    width = max(im.width for im in imgs)
    gap = 8
    total_height = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
    composite = Image.new("RGB", (width, total_height), "white")
    y = 0
    for im in imgs:
        if im.width != width:
            ratio = width / im.width
            im = im.resize((width, int(im.height * ratio)))
        composite.paste(im, (0, y))
        y += im.height + gap
    max_h = 6000  # cap resolution — la plupart des modeles vision limitent la taille d'image
    if composite.height > max_h:
        ratio = max_h / composite.height
        composite = composite.resize((int(composite.width * ratio), max_h))
    buf = io.BytesIO()
    composite.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def pdf_needs_vision_fallback(raw_text: str) -> bool:
    """True si le texte extrait du calque PDF est illisible ou vide et
    qu'il faut basculer sur un rendu visuel (voir render_pdf_to_composite_image)."""
    return not (raw_text or "").strip() or _looks_garbled(raw_text)


def extract_docx_text(content: bytes) -> str:
    """Paragraphes ET tableaux (une demande de devis en tableau Word etait
    silencieusement ignoree : seuls les paragraphes etaient lus)."""
    from docx import Document
    doc = Document(io.BytesIO(content))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        parts.append("")
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def extract_xlsx_text(content: bytes) -> str:
    """Serialise chaque feuille en lignes 'colonne=valeur' pour que le
    modele lise la structure tabulaire sans halluciner de fusion de
    colonnes. Aucune formule n'est evaluee cote agent : openpyxl renvoie
    les valeurs calculees (data_only=True) deja mises en cache par Excel."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    parts = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        parts.append(f"=== Feuille: {ws.title} ===")
        header = [str(h).strip() if h is not None else "" for h in rows[0]]
        for row in rows[1:]:
            cells = [str(v).strip() if v is not None else "" for v in row]
            if not any(cells):
                continue
            pairs = [f"{h}={v}" for h, v in zip(header, cells) if h and v]
            parts.append(" | ".join(pairs) if pairs else " | ".join(c for c in cells if c))
    wb.close()
    return "\n".join(parts).strip()


def extract_csv_text(content: bytes) -> str:
    """CSV/TSV -> lignes 'colonne=valeur', meme logique que extract_xlsx_text
    pour une lecture tabulaire coherente quel que soit le format source."""
    import csv
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = content.decode("utf-8", errors="replace")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    if "\t" in sample and sample.count("\t") > sample.count(delimiter):
        delimiter = "\t"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return ""
    header = [c.strip() for c in rows[0]]
    parts = []
    for row in rows[1:]:
        pairs = [f"{h}={v.strip()}" for h, v in zip(header, row) if h and v.strip()]
        parts.append(" | ".join(pairs) if pairs else " | ".join(c.strip() for c in row if c.strip()))
    return "\n".join(parts).strip()


def extract_plain_text(content: bytes) -> str:
    """Fichier .txt brut, encodage detecte au mieux (UTF-8 puis Latin-1)."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace").strip()
