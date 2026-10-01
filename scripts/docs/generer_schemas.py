"""Regenere les schemas PNG de la documentation (docs/assets/schema-*.png).

Utilises par les pages GitHub (README.md, docs/architecture.md) et par les
generateurs PDF (build_docs_v2.py, build_complement_min.py,
build_rapport_jury.py).

Etat au 01/10/2026 :
- frontend sur Vercel (deploiement auto depuis main), API FastAPI sur Render,
  base Supabase (schema blueseatra, RLS par entreprise) ;
- toute l'IA passe par la passerelle Hermes (POST /v1/chat/completions), qui
  route vers custom:ollama (VPS OVH) ou custom:mistral ; OCR toujours local
  (GLM-OCR), une image n'est jamais envoyee a Mistral ;
- chiffrage : catalogue interne + catalogues fournisseurs activés par
  l'entreprise (table chiffrage_sources), recherche en deux temps
  (trigramme puis tri prix).

Style : fond creme (#F7F4EE), boites blanches a bordure navy, titres navy
gras, texte secondaire gris, fleches teal. Rendu en x2 pour un affichage net
sur GitHub (ecrans haute densite).

Usage : python scripts/docs/generer_schemas.py
(remplace backend/build_docs_assets.py, conserve pour les anciens PDF ;
ce script-ci ne touche pas backend/, donc pas de redeploiement Render)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parents[2] / "docs" / "assets"
S = 2  # facteur de rendu

BG = (247, 244, 238)
BORDER = (25, 43, 68)
HEADING = (25, 43, 68)
BODY = (91, 103, 114)
FOOT = (28, 40, 52)
ARROW = (67, 140, 136)
WHITE = (255, 255, 255)
ACCENT_BG = (232, 244, 243)   # boite mise en avant (teal tres clair)
AMBER_BG = (253, 243, 224)    # sources fournisseurs (rappel du badge ambre)
AMBER = (180, 110, 20)
ZONE = (233, 228, 218)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if Path(path).exists():
        return ImageFont.truetype(path, size * S)
    return ImageFont.load_default()


F_TITLE = _font(30, bold=True)
F_SUB = _font(16)
F_BOX_TITLE = _font(18, bold=True)
F_BOX_BODY = _font(14)
F_FOOT = _font(15)
F_ZONE = _font(13, bold=True)
F_TAG = _font(12, bold=True)


def _s(v):
    return tuple(int(x * S) for x in v)


class Canvas:
    def __init__(self, w: int, h: int):
        self.img = Image.new("RGB", (w * S, h * S), BG)
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy, txt, font, fill=HEADING):
        self.d.text(_s(xy), txt, font=font, fill=fill)

    def title(self, title: str, sub: str | None = None):
        self.text((40, 26), title, F_TITLE)
        if sub:
            self.text((40, 66), sub, F_SUB, BODY)

    def zone(self, xy, label: str):
        self.d.rounded_rectangle(_s(xy), radius=14 * S, fill=ZONE)
        self.text((xy[0] + 14, xy[1] + 8), label.upper(), F_ZONE, BODY)

    @staticmethod
    def hauteur(n_lignes: int) -> int:
        """Hauteur minimale d'une boite : titre + n lignes + marge basse."""
        return 44 + 21 * n_lignes + 14

    def box(self, xy, title: str, lines: list, fill=WHITE, tag: str | None = None,
            tag_color=ARROW, col2: int | None = None):
        """Boite ; une ligne peut etre un tuple (gauche, droite) aligne sur
        la colonne `col2` (decalage en px depuis le bord gauche)."""
        x0, y0, x1, y1 = xy
        assert y1 - y0 >= self.hauteur(len(lines)), f"boite trop basse : {title}"
        self.d.rounded_rectangle(_s(xy), radius=10 * S, fill=fill, outline=BORDER, width=2 * S)
        self.text((x0 + 18, y0 + 14), title, F_BOX_TITLE)
        ty = y0 + 44
        for line in lines:
            if isinstance(line, tuple):
                self.text((x0 + 18, ty), line[0], F_BOX_BODY, HEADING)
                self.text((x0 + 18 + col2, ty), line[1], F_BOX_BODY, BODY)
            else:
                self.text((x0 + 18, ty), line, F_BOX_BODY, BODY)
            ty += 21
        if tag:
            tw = self.d.textlength(tag, font=F_TAG) / S + 16
            r = (x1 - tw - 10, y0 - 11, x1 - 10, y0 + 11)
            self.d.rounded_rectangle(_s(r), radius=11 * S, fill=tag_color)
            self.text((r[0] + 8, r[1] + 4), tag, F_TAG, WHITE)

    def arrow(self, pts, label: str | None = None, label_xy=None, dashed=False):
        """Polyligne flechee ; la pointe est sur le dernier point."""
        spts = [_s(p) for p in pts]
        for a, b in zip(spts[:-1], spts[1:]):
            if dashed:
                self._dashed(a, b)
            else:
                self.d.line([a, b], fill=ARROW, width=3 * S)
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        if xa == xb:
            sgn = 1 if yb > ya else -1
            tri = [(xb, yb), (xb - 7, yb - 14 * sgn), (xb + 7, yb - 14 * sgn)]
        else:
            sgn = 1 if xb > xa else -1
            tri = [(xb, yb), (xb - 14 * sgn, yb - 7), (xb - 14 * sgn, yb + 7)]
        self.d.polygon([_s(p) for p in tri], fill=ARROW)
        if label:
            self.text(label_xy, label, F_BOX_BODY, ARROW)

    def _dashed(self, a, b, dash=10 * S, gap=7 * S):
        (x0, y0), (x1, y1) = a, b
        length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1
        dx, dy = (x1 - x0) / length, (y1 - y0) / length
        pos = 0.0
        while pos < length:
            end = min(pos + dash, length)
            self.d.line([(x0 + dx * pos, y0 + dy * pos), (x0 + dx * end, y0 + dy * end)],
                        fill=ARROW, width=3 * S)
            pos = end + gap

    def save(self, name: str):
        self.img.save(ASSETS / name, optimize=True)
        print("wrote", ASSETS / name, self.img.size)


# --------------------------------------------------------------------------
def build_architecture() -> None:
    c = Canvas(1400, 900)
    c.title("Architecture Blueseatra",
            "État de production au 01/10/2026  |  Vercel  |  Render  |  Supabase  |  OVH VPS")

    # Zones
    c.zone((30, 100, 1370, 260), "Utilisateur et site")
    c.zone((30, 280, 1370, 480), "API et données")
    c.zone((30, 500, 1370, 800), "Moteur IA (toujours via la passerelle Hermès)")

    # Rangee 1 : navigateur → Vercel <- GitHub
    c.box((60, 140, 400, 240), "Navigateur", ["www.blueseatra.com", "React 18, FR / EN"])
    c.box((520, 140, 900, 240), "Vercel", ["Site statique + CDN", "déploiement auto depuis main"],
          fill=ACCENT_BG, tag="NOUVEAU")
    c.box((1000, 140, 1340, 240), "GitHub", ["zehair-louzza/Blueseatra",
                                             "fusion sur main = déploiement"])
    c.arrow([(400, 190), (520, 190)], "HTTPS", (430, 166))
    c.arrow([(1000, 190), (900, 190)])

    # Rangee 2 : API → Supabase <- catalogues fournisseurs
    c.box((60, 320, 400, 420), "API FastAPI (Render)", ["blueseatra-api.onrender.com",
                                                        "Francfort, Python 3.11, 113 routes"])
    c.box((520, 320, 900, 420), "Supabase PostgreSQL 17", ["schéma blueseatra, RLS par entreprise",
                                                         "rôle blueseatra_app, 18 migrations"])
    c.box((1000, 320, 1340, 441), "Catalogues fournisseurs", ["~970 000 offres, 9 distributeurs",
                                                            "activables : chiffrage_sources",
                                                            "import : Fournisseur-Blueseatra"],
          fill=AMBER_BG, tag="CHIFFRAGE", tag_color=AMBER)
    c.arrow([(230, 240), (230, 320)], "/api + jeton", (242, 268))
    c.arrow([(400, 370), (520, 370)], "asyncpg", (420, 346))
    c.arrow([(1000, 370), (900, 370)])

    # Rangee 3 : Hermès → custom:ollama / custom:mistral
    c.arrow([(150, 420), (150, 560)], "toute l'IA", (162, 436))
    c.box((60, 560, 400, 681), "Passerelle Hermès", ["hermes.blueseatra.com",
                                                     "POST /v1/chat/completions",
                                                     "X-Api-Key, sans outils"], fill=ACCENT_BG)
    c.box((520, 540, 900, 772), "custom:ollama  (VPS OVH)", [
        ("glm-ocr", "OCR local (défaut)"),
        ("qwen2.5:7b", "extraction, structuration"),
        ("qwen2.5vl:7b", "vision (photo, PDF image)"),
        ("gpt-oss:20b", "raisonnement gradué"),
        ("glm-4.7-flash", "rédaction du descriptif"),
        ("hermes3", "dernier recours"),
        ("1 modèle", "chargé à la fois en RAM"),
    ], col2=140)
    c.box((1000, 560, 1340, 660), "custom:mistral", ["API Mistral (texte seul)",
                                                     "relances 429 : 2, 4, 8, 16 s"])
    c.arrow([(400, 620), (520, 620)])
    c.arrow([(400, 590), (460, 590), (460, 524), (1170, 524), (1170, 560)])

    c.text((40, 822), "OCR toujours local : une image n'est jamais envoyée à Mistral ; seul le texte lu "
                      "sur le VPS part vers le fournisseur choisi.", F_FOOT, FOOT)
    c.text((40, 848), "L'IA lit et structure, elle ne fixe jamais un prix. Supabase pg_cron réveille "
                      "l'API toutes les 13 min. n8n : webhook facultatif par entreprise.", F_FOOT, FOOT)
    c.save("schema-architecture.png")


# --------------------------------------------------------------------------
def build_parcours() -> None:
    c = Canvas(1400, 320)
    c.title("Parcours d'une demande jusqu'au devis",
            "De l'e-mail ou du PDF au devis validé : l'IA lit, les règles chiffrent, vous validez.")

    steps = [
        ("1 Collecter", ["e-mail, PDF,", "photo, texte"], WHITE),
        ("2 Lire", ["OCR local", "GLM-OCR"], WHITE),
        ("3 Structurer", ["lots TCE, lignes", "qwen2.5:7b"], WHITE),
        ("4 Rapprocher", ["catalogue interne", "+ sources actives"], AMBER_BG),
        ("5 Chiffrer", ["prix, marge, TVA", "règles FastAPI"], WHITE),
        ("6 Valider", ["brouillon → PDF", "vous décidez"], ACCENT_BG),
    ]
    box_w, gap, y0, y1 = 196, 28, 110, 216
    x = 40
    spans = []
    for title, lines, fill in steps:
        c.box((x, y0, x + box_w, y1), title, lines, fill=fill)
        spans.append((x, x + box_w))
        x += box_w + gap
    for (_, xe), (xs, _) in zip(spans[:-1], spans[1:]):
        c.arrow([(xe, (y0 + y1) // 2), (xs, (y0 + y1) // 2)])

    c.text((40, 246), "Les prix viennent du catalogue interne ou des catalogues fournisseurs activés par "
                      "l'entreprise ; la TVA et la marge", F_FOOT, FOOT)
    c.text((40, 270), "restent dans FastAPI. Échec de lecture : quota remboursé. Le devis reste un "
                      "brouillon tant qu'une personne ne l'a pas validé.", F_FOOT, FOOT)
    c.save("schema-parcours.png")


# --------------------------------------------------------------------------
def build_routage() -> None:
    c = Canvas(1400, 370)
    c.title("Routage IA", "Depuis le 29/09/2026 : plus aucun appel direct du SaaS vers Ollama.")

    c.box((40, 110, 400, 236), "API FastAPI", ["OCR, structuration, extraction,",
                                               "décomposition, rédaction,",
                                               "vision approfondie"])
    c.box((520, 110, 880, 236), "Passerelle Hermès", ["POST /v1/chat/completions",
                                                      "choisit le fournisseur",
                                                      "à chaque requête"], fill=ACCENT_BG)
    c.box((1000, 86, 1360, 169), "custom:ollama", ["modèles du VPS OVH (OCR, texte, vision)"])
    c.box((1000, 185, 1360, 268), "custom:mistral", ["API Mistral, texte uniquement"])
    c.arrow([(400, 173), (520, 173)], "X-Api-Key", (420, 149))
    c.arrow([(880, 160), (940, 160), (940, 127), (1000, 127)])
    c.arrow([(880, 186), (940, 186), (940, 226), (1000, 226)])

    c.text((40, 292), "Sortie contrainte par schéma JSON (json_schema strict), nouvel essai sans schéma si "
                      "la passerelle le refuse.", F_FOOT, FOOT)
    c.text((40, 318), "Sans HERMES_GATEWAY_URL : erreur explicite, pas de repli silencieux. "
                      "BLUESEATRA_IA_VIA_HERMES=0 : retour arrière d'urgence.", F_FOOT, FOOT)
    c.save("schema-routage.png")


# --------------------------------------------------------------------------
def build_chiffrage() -> None:
    c = Canvas(1400, 590)
    c.title("Chiffrage sur sources activables",
            "C'est l'entreprise qui choisit ses sources ; désactiver ne supprime jamais rien.")

    # Colonne gauche : sources
    c.box((40, 110, 400, 214), "Catalogue interne", ["CSV importé, versions",
                                                     "interrupteur sur la page Catalogues"])
    c.box((40, 246, 400, 371), "Catalogues fournisseurs", ["Rexel, Prolians, Point.P, YESSS...",
                                                         "bouton poussoir par fournisseur",
                                                         "état : table chiffrage_sources"],
          fill=AMBER_BG, tag="ACTIVABLE", tag_color=AMBER)

    # Centre : recherche en deux temps
    c.box((520, 110, 880, 371), "Recherche en deux temps", [
        "par libellé de la demande,",
        "UNION ALL d'une branche par source,",
        "tenant exact par branche :",
        "",
        "1. filtre trigramme (index GIN),",
        "   sous-requête sans tri, 200 id max",
        "2. tri par prix sur ce petit résultat",
        "",
        "189 ms au lieu de > 30 s (timeout)",
    ], fill=ACCENT_BG)
    c.arrow([(400, 162), (520, 162)])
    c.arrow([(400, 308), (520, 308)])

    # Droite : résultat
    c.box((1000, 110, 1360, 214), "Devis brouillon", ["catalogue interne prioritaire",
                                                      "provenance tracée (pricing_snapshot)"])
    c.box((1000, 246, 1360, 371), "Éditeur de devis", ["articles fournisseurs : badge ambre",
                                                       "prix net HT, unité, marque, réf.",
                                                       "lignes sans offre : à confirmer"])
    c.arrow([(880, 162), (1000, 162)])
    c.arrow([(880, 308), (1000, 308)])

    # Règles de decision
    c.zone((40, 400, 1360, 550), "Règles de génération")
    c.text((60, 432), "Catalogue interne actif", F_BOX_TITLE)
    c.text((60, 460), "rapprochement sur le catalogue,", F_BOX_BODY, BODY)
    c.text((60, 481), "complété par les sources actives", F_BOX_BODY, BODY)
    c.text((500, 432), "Aucun catalogue, sources actives", F_BOX_TITLE)
    c.text((500, 460), "les sources actives génèrent le devis ;", F_BOX_BODY, BODY)
    c.text((500, 481), "sans correspondance : lignes à confirmer", F_BOX_BODY, BODY)
    c.text((960, 432), "Ni catalogue ni source", F_BOX_TITLE)
    c.text((960, 460), "refus avec message explicite :", F_BOX_BODY, BODY)
    c.text((960, 481), "importer ou activer un catalogue", F_BOX_BODY, BODY)
    c.text((60, 514), "Un incident côté fournisseurs ne bloque jamais la génération (repli silencieux). "
                      "Chaque bascule est journalisée dans l'audit.", F_BOX_BODY, FOOT)
    c.save("schema-chiffrage.png")


if __name__ == "__main__":
    build_architecture()
    build_parcours()
    build_routage()
    build_chiffrage()
