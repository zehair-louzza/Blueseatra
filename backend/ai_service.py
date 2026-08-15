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


async def resolve_ai_config(tenant_settings: dict) -> tuple[str, str, str]:
    """Return (provider, model, api_key) for this tenant."""
    provider = tenant_settings.get("ai_provider") or DEFAULT_PROVIDER
    model = tenant_settings.get("ai_model") or DEFAULT_MODEL
    api_key = tenant_settings.get("ai_key") or ""

    # Normalize provider name
    provider = provider.lower()

    # Hermes/Ollama: tenant key unused; gateway auth is HERMES_API_KEY.
    if provider == "hermes":
        model = model or HERMES_DEFAULT_MODEL

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

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 2048,
        },
    }
    # qwen3.6 thinks by default and wraps JSON in <think> — disable for extraction.
    if model.startswith("qwen3"):
        payload["think"] = False

    headers = {}
    if HERMES_API_KEY:
        headers["X-Api-Key"] = HERMES_API_KEY

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{HERMES_BASE_URL.rstrip('/')}/api/chat",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


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


async def extract_request_data(
    raw_text: str,
    tenant_settings: dict,
    image_bytes: bytes | None = None,
) -> dict:
    """Main entry point: extract structured quote data from raw text/image."""
    provider, model, api_key = await resolve_ai_config(tenant_settings)

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
        # If Hermes is unavailable, return empty structure with error flag
        return {
            "client_name": "",
            "client_email": "",
            "client_phone": "",
            "client_address": "",
            "work_type": "",
            "description": raw_text[:500],
            "location": "",
            "urgency": "normal",
            "estimated_budget": None,
            "requested_date": None,
            "line_items": [],
            "_error": f"AI engine unavailable: {str(e)}",
        }

    # Parse JSON response
    try:
        # Strip markdown code blocks if present
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return _normalize_extracted(json.loads(cleaned))
    except json.JSONDecodeError:
        return {
            "client_name": "",
            "client_email": "",
            "client_phone": "",
            "client_address": "",
            "work_type": "",
            "description": raw_text[:500],
            "location": "",
            "urgency": "normal",
            "estimated_budget": None,
            "requested_date": None,
            "line_items": [],
            "_raw_ai_response": raw_response[:1000],
        }


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
