"""Regenere les schemas PNG utilises par build_docs_v2.py / build_complement_min.py /
build_rapport_jury.py, avec le contenu IA a jour (23 aout 2026 : gpt-oss:20b
raisonneur, qwen2.5:7b/qwen2.5vl:7b extraction, hermes3 repli -- gemma4:26b et
qwen3.6:27b supprimes du VPS).

Style aligne sur les schemas existants : fond creme (#F7F4EE), boites blanches a
bordure navy, titres navy gras, texte secondaire gris, fleches teal.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"

BG = (247, 244, 238)
BORDER = (25, 43, 68)
HEADING = (25, 43, 68)
BODY = (91, 103, 114)
ARROW = (67, 140, 136)
WHITE = (255, 255, 255)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = _font(30, bold=True)
F_SUB = _font(17)
F_BOX_TITLE = _font(19, bold=True)
F_BOX_BODY = _font(15)
F_FOOT = _font(16)


def _box(draw: ImageDraw.ImageDraw, xy, title: str, lines: list[str]) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=10, fill=WHITE, outline=BORDER, width=2)
    draw.text((x0 + 20, y0 + 18), title, font=F_BOX_TITLE, fill=HEADING)
    ty = y0 + 50
    for line in lines:
        draw.text((x0 + 20, ty), line, font=F_BOX_BODY, fill=BODY)
        ty += 22


def _arrow(draw: ImageDraw.ImageDraw, x0: int, x1: int, y: int) -> None:
    draw.line((x0, y, x1 - 12, y), fill=ARROW, width=3)
    draw.polygon([(x1, y), (x1 - 14, y - 7), (x1 - 14, y + 7)], fill=ARROW)


def build_routage() -> None:
    img = Image.new("RGB", (1400, 380), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 25), "Routage IA", font=F_TITLE, fill=HEADING)

    boxes = [
        (40, 82, 400, 200, "FastAPI extract", [
            "POST ia.blueseatra.com/api/chat",
            "qwen2.5:7b (texte) / qwen2.5vl:7b (fichier)",
        ]),
        (500, 82, 900, 200, "FastAPI reason", [
            "POST hermes.blueseatra.com/v1 (gateway)",
            "X-Api-Key + Bearer + X-Hermes-Session-Id",
            "hermes-agent = gpt-oss:20b (think gradue)",
        ]),
        (1000, 82, 1360, 200, "Repli", [
            "Ollama gpt-oss:20b (direct, si gateway echoue)",
            "puis hermes3 (sans raisonnement natif)",
        ]),
    ]
    for x0, y0, x1, y1, title, lines in boxes:
        _box(d, (x0, y0, x1, y1), title, lines)
    _arrow(d, 400, 500, 141)
    _arrow(d, 900, 1000, 141)

    d.text((40, 240), "OLLAMA_MAX_LOADED_MODELS=1. Un seul gros modele en RAM (24 Go).",
            font=F_FOOT, fill=(28, 40, 52))
    img.save(ASSETS / "schema-routage.png")
    print("wrote", ASSETS / "schema-routage.png")


def build_parcours() -> None:
    img = Image.new("RGB", (1400, 420), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 25), "Parcours devis", font=F_TITLE, fill=HEADING)

    steps = [
        ("1 Collecter", ["mail PDF photo"]),
        ("2 Lire", ["qwen2.5vl:7b"]),
        ("3 Rapprocher", ["catalogue"]),
        ("4 Controler", ["Hermes / gpt-oss"]),
        ("5 Editer", ["FastAPI prix"]),
        ("6 PDF", ["vous validez"]),
    ]
    box_w, gap, x0, y0, y1 = 200, 24, 40, 82, 200
    x = x0
    centers = []
    for title, lines in steps:
        _box(d, (x, y0, x + box_w, y1), title, lines)
        centers.append((x, x + box_w))
        x += box_w + gap
    for (_, xe), (xs2, _) in zip(centers[:-1], centers[1:]):
        _arrow(d, xe, xs2, (y0 + y1) // 2 + 3)

    d.text((40, 230), "Les prix, la TVA et la marge restent dans FastAPI. L'IA ne signe pas.",
            font=F_FOOT, fill=(28, 40, 52))
    img.save(ASSETS / "schema-parcours.png")
    print("wrote", ASSETS / "schema-parcours.png")


def build_architecture() -> None:
    img = Image.new("RGB", (1400, 720), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 25), "Architecture Blueseatra v2", font=F_TITLE, fill=HEADING)
    d.text((40, 62), "Hostinger  |  Render  |  Supabase  |  OVH VPS", font=F_SUB, fill=BODY)

    row1 = [
        (40, 108, 320, 200, "Navigateur", ["blueseatra.com  (React)"]),
        (400, 108, 700, 200, "FastAPI Render", ["blueseatra-api.onrender.com"]),
        (800, 108, 1080, 200, "Supabase", ["Postgres EU  schema blueseatra"]),
    ]
    for x0, y0, x1, y1, title, lines in row1:
        _box(d, (x0, y0, x1, y1), title, lines)
    d.line((660, 154, 796, 154), fill=ARROW, width=3)
    d.polygon([(800, 154), (786, 147), (786, 161)], fill=ARROW)
    # FastAPI Render (bas, x=550) descend jusqu'a une jonction, puis se separe
    # vers Ollama (x=180) et vers Hermes gateway (x=550, meme colonne).
    d.line((550, 200, 550, 245), fill=ARROW, width=3)
    d.line((180, 245, 550, 245), fill=ARROW, width=3)
    d.line((180, 245, 180, 285), fill=ARROW, width=3)
    d.polygon([(180, 292), (173, 278), (187, 278)], fill=ARROW)
    d.line((550, 245, 550, 285), fill=ARROW, width=3)
    d.polygon([(550, 292), (543, 278), (557, 278)], fill=ARROW)

    row2 = [
        (40, 292, 320, 370, "Ollama", ["ia.blueseatra.com  /api/chat"]),
        (400, 292, 700, 370, "Hermes gateway", ["hermes.blueseatra.com  /v1"]),
        (800, 292, 1080, 370, "n8n", ["n8n.blueseatra.com"]),
    ]
    for x0, y0, x1, y1, title, lines in row2:
        _box(d, (x0, y0, x1, y1), title, lines)

    d.text((40, 408), "Modeles locaux (un charge a la fois)", font=F_BOX_TITLE, fill=HEADING)
    row3 = [
        (40, 448, 300, 526, "qwen2.5:7b", ["extraction (texte)"]),
        (330, 448, 590, 526, "qwen2.5vl:7b", ["extraction (fichier, vision)"]),
        (620, 448, 880, 526, "gpt-oss:20b", ["raisonnement (low/med/high)"]),
        (910, 448, 1170, 526, "hermes3", ["compat / fallback"]),
    ]
    for x0, y0, x1, y1, title, lines in row3:
        _box(d, (x0, y0, x1, y1), title, lines)

    d.text((40, 570), "Caddy TLS + X-Api-Key. Port 11434 et 8642 non publies. Donnees client dans l'UE.",
            font=F_FOOT, fill=(28, 40, 52))
    d.text((40, 598), "23 aout 2026 : gemma4:26b, qwen3.6:27b, qwen3:14b, deepseek-r1:14b, qwen2.5:14b et",
            font=F_FOOT, fill=(28, 40, 52))
    d.text((40, 622), "Phi-4-reasoning-vision-15B supprimes (63 Go liberes) -- 4 modeles ci-dessus restants.",
            font=F_FOOT, fill=(28, 40, 52))
    img.save(ASSETS / "schema-architecture.png")
    print("wrote", ASSETS / "schema-architecture.png")


if __name__ == "__main__":
    build_routage()
    build_parcours()
    build_architecture()
