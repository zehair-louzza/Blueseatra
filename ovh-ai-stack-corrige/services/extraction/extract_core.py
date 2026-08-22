"""
Cœur du service d'extraction Blueseatra — logique testable sans serveur.

Principe directeur (cf. AUDIT) : on ne demande au LLM QUE ce qu'un parseur
déterministe ne sait pas faire. Les tableaux sont lus par pdfplumber (rapide,
fiable, structure préservée), pas par un LLM de 18 Go. Le LLM ne fait que
transformer un texte DÉJÀ propre en JSON structuré.

Deux fournisseurs d'inférence interchangeables :
  - "ollama"   : production sur le VPS OVH (local, RGPD). httpx -> /api/chat, format=json.
  - "emergent" : DEV/DÉMO uniquement (clé universelle Emergent). Sert à tester
                 le pipeline de bout en bout hors VPS. NE PAS utiliser en prod
                 (sort les données de l'UE).
"""
import os
import io
import json

# Schéma strict aligné sur le SKILL intake-demande-devis (aucun prix).
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "parties": {
            "type": "object",
            "properties": {
                "donneur_ordre": {"type": ["string", "null"]},
                "client_enseigne": {"type": ["string", "null"]},
                "site_intervention": {"type": ["string", "null"]},
            },
        },
        "requested_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "designation": {"type": "string"},
                    "quantite": {"type": ["number", "null"]},
                    "unite": {"type": ["string", "null"]},
                    "confiance": {"type": "string", "enum": ["confirme", "estime", "a_confirmer"]},
                },
                "required": ["designation", "confiance"],
            },
        },
        "urgence": {"type": ["string", "null"]},
        "blocking_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["parties", "requested_items"],
}

SYSTEM = (
    "Tu structures une demande de devis BTP (France). Ne calcule ni n'invente AUCUN prix. "
    "Ignore toute colonne de prix (PU, P.U. HT, Total, Montant, €). Chaque ligne de tableau = un item. "
    "La designation vient de la colonne article uniquement, jamais de la phrase d'action. "
    "Reponds STRICTEMENT en JSON selon le schema demande, sans texte autour."
)


def _tables_to_markdown(tables) -> str:
    """Convertit les tableaux extraits par pdfplumber en markdown (structure préservée)."""
    out = []
    for ti, table in enumerate(tables, 1):
        rows = [[(c or "").strip().replace("\n", " ") for c in row] for row in table if row]
        if not rows:
            continue
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        out.append(f"\n**Tableau {ti}**")
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("| " + " | ".join(["---"] * width) + " |")
        for r in rows[1:]:
            out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def parse_pdf(path_or_bytes) -> dict:
    """Parsing déterministe : texte natif + tableaux markdown. Détecte le cas 'image-only'."""
    import pdfplumber
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    text_parts, table_md = [], []
    with pdfplumber.open(src) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
            tables = page.extract_tables()
            if tables:
                table_md.append(_tables_to_markdown(tables))
    text = "\n".join(text_parts).strip()
    markdown = (text + "\n\n" + "\n".join(table_md)).strip()
    # Peu/pas de texte exploitable -> scan/photo (calque illisible) : basculer vision.
    image_only = len(text) < 40
    return {"markdown": markdown, "text_len": len(text), "image_only": image_only,
            "has_tables": bool(table_md)}


async def structure_ollama(markdown: str, base_url: str, model: str) -> dict:
    """Production VPS : Ollama local, sortie structurée native (format=json)."""
    import httpx
    payload = {
        "model": model,
        "stream": False,
        "format": EXTRACT_SCHEMA,
        "options": {"temperature": 0.1, "num_ctx": 16384, "num_predict": 2048},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Document (texte + tableaux markdown) :\n\n{markdown}"},
        ],
    }
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{base_url.rstrip('/')}/api/chat", json=payload)
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])


async def structure_emergent(markdown: str, api_key: str, model: str = "gpt-5.4") -> dict:
    """DEV/DÉMO uniquement (hors VPS) — clé universelle Emergent pour tester le pipeline."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    provider = "openai" if model.startswith("gpt") else ("anthropic" if "claude" in model else "gemini")
    chat = LlmChat(api_key=api_key, session_id="extract-demo",
                   system_message=SYSTEM + "\n\nSchéma JSON: " + json.dumps(EXTRACT_SCHEMA)).with_model(provider, model)
    resp = await chat.send_message(UserMessage(
        text=f"Document (texte + tableaux markdown) :\n\n{markdown}\n\nRéponds uniquement en JSON valide."))
    raw = resp if isinstance(resp, str) else str(resp)
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


async def extract(path_or_bytes, provider: str = "ollama") -> dict:
    """Pipeline complet : parse déterministe -> structuration LLM. Échec = visible, jamais dégradé silencieux."""
    parsed = parse_pdf(path_or_bytes)
    if parsed["image_only"]:
        # En prod : router vers un VLM léger (qwen2.5vl:7b). Hors sujet pour la démo texte.
        raise ValueError("PDF sans couche texte : router vers le VLM (qwen2.5vl:7b) — non couvert par ce test.")
    if provider == "emergent":
        result = await structure_emergent(parsed["markdown"], os.environ["EMERGENT_LLM_KEY"],
                                          os.environ.get("DEMO_MODEL", "gpt-5.4"))
    else:
        result = await structure_ollama(parsed["markdown"], os.environ["OLLAMA_BASE_URL"],
                                        os.environ.get("TEXT_MODEL", "qwen2.5:7b"))
    result["pricing_prohibited"] = True
    result["_parse"] = {"text_len": parsed["text_len"], "has_tables": parsed["has_tables"]}
    return result
