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

EXTRACTION_SYSTEM = """You are Blueseatra's document understanding engine for a B2B quoting platform.
Extract a structured business request from the provided content, which may be in ANY language.
Return ONLY valid minified JSON (no markdown, no commentary) with EXACTLY this schema:
{
 "language": "ISO 639-1 code of the source content",
 "client": "string or null",
 "site": "string or null",
 "description": "short summary in the source language",
 "urgency": "low|normal|high",
 "constraints": ["string"],
 "keywords": ["string"],
 "line_items": [
   {"label": "string", "category": "string or null", "qty": number, "unit": "hr|m2|ml|u|ens or null", "dimensions": "string or null", "notes": "string or null"}
 ],
 "confidence": number between 0 and 1
}
Rules: Never invent prices. Infer qty/unit only when clearly stated; otherwise qty=1 and unit=null.
Categories should be lowercase business families (e.g. peinture, placo, fibre, maintenance, deplacement, main_oeuvre, protection, consommables)."""


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
