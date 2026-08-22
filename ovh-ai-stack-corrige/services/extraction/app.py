"""
API du service d'extraction — wrapper FastAPI autour de extract_core.
Déployé sur le VPS derrière Caddy. Le PDF brut ne va jamais au chat Ollama :
il est parsé (pdfplumber) puis seul le texte propre + tableaux markdown sont
envoyés à un petit modèle rapide en `format=json`.

Brancher une file d'attente (Redis/RQ, n8n, ou table Supabase + worker) devant
`/extract` pour absorber 10-100 utilisateurs en asynchrone (voir docs/AUDIT.md).
"""
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException

import extract_core

app = FastAPI(title="Blueseatra extraction")


@app.get("/health")
async def health():
    return {"status": "ok", "provider": os.environ.get("EXTRACT_PROVIDER", "ollama"),
            "text_model": os.environ.get("TEXT_MODEL", "qwen2.5:7b")}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop volumineux (max 15 Mo).")
    try:
        # extract_core lit le PDF depuis les octets en mémoire (fichier jamais persisté — RGPD).
        return await extract_core.extract(data, provider=os.environ.get("EXTRACT_PROVIDER", "ollama"))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        # Jamais de repli heuristique silencieux : échec visible (cf. incident LOT_20).
        raise HTTPException(502, f"echec_extraction: {type(e).__name__}: {e}")
