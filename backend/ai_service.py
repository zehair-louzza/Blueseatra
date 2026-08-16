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
MODEL_ALIASES = {"hermes-3": "hermes3", "hermes3": "hermes3"}
# Shared with Caddy on ovh-ai-stack (header X-Api-Key). Empty in local dev.
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")

# ── Fallback cloud providers ─────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

DEFAULT_PROVIDER = "hermes"
DEFAULT_MODEL = HERMES_DEFAULT_MODEL

EXTRACTION_SYSTEM = """You are Blueseatra's document understanding engine for a B2B facility-maintenance quoting platform.
You receive INCOMING quote requests (\"demande de devis\"), mission orders (\"ordre de mission\"), emails or photos in ANY language.
Your job: extract structured data and return ONLY valid JSON.

You MAY use the technical web context provided (DTU, phasage, spec produit, lots TCE).
You MUST NEVER output a price, tariff, amount, euro, HT, TTC, or market estimate.
Prices come ONLY from the Blueseatra catalog after extraction. If an article is unknown, still list it in line_items.

CRITICAL — materials, not a rewrite:
- Read the request, determine the trade context, then list the CONCRETE materials and accessories needed to execute the work.
- FORBIDDEN: a single line_item that merely copies the request title (e.g. only \"Remplacement du ballon d'eau chaude 100L\").
- Example: replacing a 100L water heater → ballon ECS 100L, groupe de sécurité, flexibles sanitaires, vannes d'arrêt, joints, raccords.
- Example: replacing 3 LED spots → 3 spots LED 230V + accessoires de pose si nécessaires.
- Reason first, then output JSON only.

Extract:
- client_name, client_email, client_phone, client_address
- work_type (e.g. plomberie, electricite, peinture, menuiserie, climatisation)
- description (full description of work requested)
- location (site address if different from client)
- urgency (urgent | normal | planifie)
- estimated_budget (if mentioned in the source text only — copy the mention, do not invent)
- requested_date (if mentioned)
- di_number (if mentioned)
- line_items: list of {description, quantity, unit} — every prestation, even if unknown to the catalog
- labor_hours: realistic man-hours for install+pose+cleanup (number, no price)
- travel_days: on-site days (integer)
- crew_size: 1 if < 6h else 2

Return ONLY this JSON structure with no markdown, no explanation:
{
  \"client_name\": \"\",
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
  \"line_items\": []
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
    return name.startswith("qwen3") or name.startswith("gemma4")


async def resolve_ai_config(
    tenant_settings: dict,
    role: str = "extract",
) -> tuple[str, str, str]:
    """Return (provider, model, api_key) for this tenant.

    role=extract → qwen2.5:14b (parse rapide).
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
            model = HERMES_EXTRACT_MODEL if role == "extract" else HERMES_REASONING_MODEL

    return provider, model, api_key


async def _call_hermes_ollama(
    model: str,
    system_prompt: str,
    user_message: str,
    image_b64: str | None = None,
) -> str:
    """Call Hermes AI via Ollama REST API on OVH VPS."""
    messages = [
        {"role": "system", "content": system_prompt},
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

    url = f"{HERMES_BASE_URL.rstrip('/')}/api/chat"
    last_err = None
    models = []
    for m in [model, *HERMES_FALLBACK_MODELS]:
        alias = MODEL_ALIASES.get((m or "").strip(), m)
        if alias and alias not in models:
            models.append(alias)
    async with httpx.AsyncClient(timeout=180.0) as client:
        for current in models:
            payload["model"] = current
            if _wants_think(current):
                payload["think"] = True
            else:
                payload.pop("think", None)
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 400 and payload.pop("think", None) is not None:
                    response = await client.post(url, json=payload, headers=headers)
                if response.status_code >= 400:
                    last_err = f"HTTP {response.status_code} ({current}): {(response.text or '')[:180]}"
                    continue
                data = response.json()
                msg = data.get("message") or {}
                content = (msg.get("content") or "").strip()
                if content:
                    return content
                last_err = f"reponse vide ({current})"
            except Exception as exc:
                last_err = f"{type(exc).__name__} ({current}): {exc or repr(exc)}"
                continue
    raise RuntimeError(last_err or "aucun modele Ollama n'a repondu")


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
    di = _m(r"N°\s*Dossier\s*DI\s*:\s*([0-9A-Za-z-]+)") or _m(r"\bDI\s*:?\s*([0-9]{6,})")
    deadline = _m(r"retour souhaitée? le\s*:\s*([^\n]+)") or _m(r"Date de la demande\s*:\s*([^\n]+)")
    phone = _m(r"Tél(?:éphone)?\s*[:.]\s*([^\n]+)")
    email = _m(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})")
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
        "donneur_d_ordre": client,
        "client_final": client,
        "intervention_site": site,
        "intervention_address": site,
    }


async def extract_request_data(
    raw_text: str,
    tenant_settings: dict,
    image_bytes: bytes | None = None,
) -> dict:
    """Main entry point: extract structured quote data from raw text/image."""
    provider, model, api_key = await resolve_ai_config(tenant_settings, role="extract")

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

    try:
        if provider == "hermes":
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
        fallback = _fallback_extract(raw_text)
        fallback["_warning"] = f"IA indisponible ({detail}). Extraction automatique de secours."
        fallback["confidence"] = 0.45
        return _normalize_extracted(fallback)

    # Parse JSON response
    try:
        cleaned = _strip_think(raw_response)
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = _normalize_extracted(_parse_json_object(cleaned))
        return await expand_work_into_materials(parsed, tenant_settings)
    except json.JSONDecodeError:
        fallback = _fallback_extract(raw_text)
        fallback["_warning"] = "Reponse IA illisible. Extraction automatique de secours."
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
            raw = await _call_hermes_ollama(model, EXPAND_SYSTEM, user)
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
    client = data.get("donneur_d_ordre") or data.get("client_final") or data.get("client_name") or data.get("client") or ""
    site = data.get("intervention_address") or data.get("intervention_site") or data.get("location") or data.get("client_address") or ""
    data.setdefault("donneur_d_ordre", client)
    data.setdefault("client_final", client)
    data.setdefault("intervention_site", site)
    data.setdefault("intervention_address", site)
    data.setdefault("language", data.get("language") or "fr")
    if data.get("confidence") is None and client:
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
    return data


async def extract_from_text(text: str, tenant_settings: dict, session_id: str | None = None) -> dict:
    """Adapter used by server.process_request."""
    return await extract_request_data(text or "", tenant_settings)


async def extract_from_image(image_bytes: bytes, tenant_settings: dict, session_id: str | None = None) -> dict:
    """Adapter used by server.process_request for photos."""
    return await extract_request_data("", tenant_settings, image_bytes=image_bytes)


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


def extract_docx_text(content: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs).strip()
