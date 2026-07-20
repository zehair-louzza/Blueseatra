"""Multilingual document understanding service - provider-agnostic.
Default engine: Hermes AI (Ollama) running locally on OVH VPS.
A tenant can override provider/model/key via Settings (Integrations).
"""
import os
import io
import json
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

# ── Fallback cloud providers ─────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

DEFAULT_PROVIDER = "hermes"
DEFAULT_MODEL = HERMES_DEFAULT_MODEL

EXTRACTION_SYSTEM = """You are Blueseatra's document understanding engine for a B2B facility-maintenance quoting platform.
You receive INCOMING quote requests (\"demande de devis\"), mission orders (\"ordre de mission\"), emails or photos in ANY language.
Your job: extract structured data and return ONLY valid JSON.

Extract:
- client_name, client_email, client_phone, client_address
- work_type (e.g. plomberie, electricite, peinture, menuiserie, climatisation)
- description (full description of work requested)
- location (site address if different from client)
- urgency (urgent | normal | planifie)
- estimated_budget (if mentioned)
- requested_date (if mentioned)
- line_items: list of {description, quantity, unit}

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
  \"line_items\": []
}"""


async def resolve_ai_config(tenant_settings: dict) -> tuple[str, str, str]:
    """Return (provider, model, api_key) for this tenant."""
    provider = tenant_settings.get("ai_provider") or DEFAULT_PROVIDER
    model = tenant_settings.get("ai_model") or DEFAULT_MODEL
    api_key = tenant_settings.get("ai_key") or ""

    # Normalize provider name
    provider = provider.lower()

    # For hermes/ollama - no API key needed (local VPS)
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

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{HERMES_BASE_URL}/api/chat",
            json=payload,
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

    user_message = f"Extract structured data from this quote request:\n\n{raw_text}"

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
        return json.loads(cleaned)
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
