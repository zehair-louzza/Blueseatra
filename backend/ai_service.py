"""Multilingual document understanding service (provider-agnostic).
Defaults to the Emergent universal LLM key + gpt-5.4 (vision-capable).
A tenant can override provider/model/key via Settings (Integrations).
"""
import os
import io
import json
import base64
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.4"

EXTRACTION_SYSTEM = """You are Blueseatra's document understanding engine for a B2B facility-maintenance quoting platform.
You receive INCOMING quote requests ("demande de devis"), mission orders ("ordre de mission"), emails or photos, in ANY language.
These typically come from a maintenance broker (donneur d'ordre, e.g. PRESTA MAINTENANCE, GMS MAINTENANCE) on behalf of an end client / retail brand (enseigne, e.g. SFR, PROMOD).
Extract a structured object and return ONLY valid minified JSON (no markdown, no commentary) with EXACTLY this schema:
{
 "language": "ISO 639-1 code of the source content",
 "doc_type": "demande_devis | ordre_de_mission | email | autre",
 "request_number": "the request/order number (N\u00b0 de la demande / d'ordre de mission) or null",
 "issue_date": "YYYY-MM-DD or null",
 "response_deadline": "YYYY-MM-DD or null (date limite de r\u00e9ponse / date de retour souhait\u00e9e)",
 "donneur_d_ordre": "the broker/issuer the quote must be addressed to, or null",
 "client_final": "the end client / retail brand (enseigne) or null",
 "di_number": "N\u00b0 dossier DI or null",
 "followup_number": "suite intervention n\u00b0 or null",
 "contact": {"name": "string or null", "email": "string or null", "phone": "string or null"},
 "intervention_site": "site / store name (enseigne + magasin) or null",
 "intervention_address": "full address of the lieu d'intervention or null",
 "description": "short summary of the requested works in the source language",
 "urgency": "low|normal|high",
 "required_deliverables": ["what the quote must contain, e.g. dur\u00e9e d'intervention, nombre de techniciens, fournitures avec r\u00e9f\u00e9rences, d\u00e9lai, fiches techniques"],
 "constraints": ["access, horaires, nuit, RAL/color, security, etc."],
 "keywords": ["string"],
 "line_items": [
   {"label": "string (the prestation/work)", "category": "string or null", "qty": number, "unit": "hr|m2|ml|u|ens or null",
    "dimensions": "string or null (e.g. H 1m80 x L 1m00)", "location": "string or null (local/zone/pi\u00e8ce)",
    "specs": "string or null (RAL, mat\u00e9riau, r\u00e9f\u00e9rence)", "notes": "string or null"}
 ],
 "confidence": number between 0 and 1
}
Rules:
- Never invent prices. Infer qty/unit only when clearly stated; otherwise qty=1 and unit=null.
- Split distinct works into separate line_items. Capture dimensions, RAL/colors and material specs in the dedicated fields.
- Categories should be lowercase business families (e.g. serrurerie, peinture, placo, fibre, climatisation, clotures, maintenance, deplacement, main_oeuvre, protection, consommables).
- Dates must be normalized to YYYY-MM-DD when possible."""


def _parse_json(raw: str):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()
    # find outermost JSON object
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)


async def _run_chat(api_key, provider, model, session_id, user_message):
    from emergentintegrations.llm.chat import LlmChat, TextDelta, StreamDone
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=EXTRACTION_SYSTEM,
    ).with_model(provider, model)
    buf = []
    async for ev in chat.stream_message(user_message):
        if isinstance(ev, TextDelta):
            buf.append(ev.content)
        elif isinstance(ev, StreamDone):
            break
    return "".join(buf)


def resolve_ai_config(settings: dict | None):
    """Pick provider/model/key from tenant settings, falling back to Emergent default."""
    settings = settings or {}
    provider = settings.get("ai_provider") or DEFAULT_PROVIDER
    model = settings.get("ai_model") or DEFAULT_MODEL
    key = settings.get("ai_key") or EMERGENT_LLM_KEY
    # If provider is 'emergent', force default provider/model with emergent key
    if provider == "emergent":
        provider, model, key = DEFAULT_PROVIDER, (model or DEFAULT_MODEL), EMERGENT_LLM_KEY
    if not key:
        key = EMERGENT_LLM_KEY
    return provider, model, key


async def extract_from_text(text: str, settings: dict | None = None, session_id: str = "extract"):
    from emergentintegrations.llm.chat import UserMessage
    provider, model, key = resolve_ai_config(settings)
    msg = UserMessage(text=f"Extract the structured request JSON from this content:\n\n{text}")
    raw = await _run_chat(key, provider, model, session_id, msg)
    return _parse_json(raw)


async def extract_from_image(image_bytes: bytes, settings: dict | None = None, session_id: str = "extract-img"):
    from emergentintegrations.llm.chat import UserMessage, ImageContent
    from PIL import Image
    provider, model, key = resolve_ai_config(settings)
    # normalize to JPEG, first frame, reasonable size
    im = Image.open(io.BytesIO(image_bytes))
    if getattr(im, "is_animated", False):
        im.seek(0)
    im = im.convert("RGB")
    im.thumbnail((1600, 1600))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88)
    b64 = base64.b64encode(out.getvalue()).decode()
    msg = UserMessage(
        text="Extract the structured request JSON from this document image.",
        file_contents=[ImageContent(image_base64=b64)],
    )
    raw = await _run_chat(key, provider, model, session_id, msg)
    return _parse_json(raw)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out).strip()


def extract_docx_text(docx_bytes: bytes) -> str:
    import docx
    d = docx.Document(io.BytesIO(docx_bytes))
    return "\n".join(p.text for p in d.paragraphs).strip()
