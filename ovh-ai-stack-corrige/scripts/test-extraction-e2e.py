#!/usr/bin/env python3
"""
Test e2e de l'extraction RÉELLE contre votre VPS OVH (ia.blueseatra.com).
À lancer depuis Render (shell) ou votre poste — PAS depuis ce pod (l'IA locale
n'y est pas joignable). Mesure le temps + affiche le JSON structuré.

Usage :
  export OLLAMA_URL="https://ia.blueseatra.com"
  export OLLAMA_API_KEY="<votre OLLAMA_API_KEY>"     # en-tête X-Api-Key
  export MODEL="qwen2.5:7b"
  # (optionnel) un vrai PDF tabulaire :
  export PDF="/chemin/vers/devis.pdf"
  python3 test-extraction-e2e.py

Sans PDF, un tableau de devis réaliste est utilisé.
"""
import os
import sys
import json
import time
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ia.blueseatra.com").rstrip("/")
API_KEY = os.environ.get("OLLAMA_API_KEY", "")
MODEL = os.environ.get("MODEL", "qwen2.5:7b")
PDF = os.environ.get("PDF")

SCHEMA = {
    "type": "object",
    "properties": {
        "requested_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "designation": {"type": "string"},
                    "quantite": {"type": ["number", "null"]},
                    "unite": {"type": ["string", "null"]},
                },
                "required": ["designation"],
            },
        }
    },
    "required": ["requested_items"],
}

SAMPLE = """Structure cette demande de devis en JSON. Ignore toute colonne de prix.
| Désignation | Qté | Unité | P.U. HT | Total HT |
| Pose de spots LED encastrés 230V | 12 | u | 24,50 | 294,00 |
| Remplacement tableau électrique | 1 | ens | 680,00 | 680,00 |
| Câble R2V 3G2.5 | 80 | ml | 1,90 | 152,00 |
| Main d'oeuvre électricien | 16 | h | 42,00 | 672,00 |"""


def get_content():
    if PDF:
        import pdfplumber  # pip install pdfplumber
        parts = []
        with pdfplumber.open(PDF) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
                for t in page.extract_tables() or []:
                    parts.append("\n".join(" | ".join((c or "") for c in row) for row in t))
        return "Structure cette demande en JSON (ignore les prix) :\n\n" + "\n".join(parts)
    return SAMPLE


def call(content, timeout):
    payload = {
        "model": MODEL, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0.1, "num_ctx": 16384},
        "messages": [{"role": "user", "content": content}],
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Api-Key": API_KEY},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    return body, time.perf_counter() - t0


def main():
    if not API_KEY:
        print("⚠️  OLLAMA_API_KEY vide — Caddy renverra 401. Exportez-la d'abord.")
    print(f"Cible : {OLLAMA_URL}  | modèle : {MODEL}")

    print("\n[warm-up] chargement du modèle en RAM (peut être long au 1er appel)...")
    try:
        _, dt = call("réponds juste OK", timeout=600)
        print(f"    warm-up OK en {dt:.1f}s")
    except Exception as e:
        print(f"    warm-up ÉCHEC : {e}")
        sys.exit(1)

    print("\n[extraction] tableau de devis -> JSON...")
    body, dt = call(get_content(), timeout=600)
    content = body.get("message", {}).get("content", "")
    try:
        data = json.loads(content)
    except Exception:
        data = {"_raw": content}
    items = data.get("requested_items", [])

    print(f"\n⏱️  Durée extraction : {dt:.1f} s  |  {len(items)} lignes")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])

    print("\n--- Verdict ---")
    if dt < 15:
        print(f"✅ {dt:.1f}s : rapide. Vous pouvez monter OLLAMA_NUM_PARALLEL à 3-4.")
    elif dt < 60:
        print(f"🟠 {dt:.1f}s : acceptable en async. Garder OLLAMA_NUM_PARALLEL=2.")
    else:
        print(f"🔴 {dt:.1f}s : trop lent. Vérifier le modèle (doit être qwen2.5:7b, pas gemma4:26b) "
              f"et la RAM libre. Envisager un GPU L4.")


if __name__ == "__main__":
    main()
