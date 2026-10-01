"""Genere docs/assets/banniere.jpg, la banniere en tete du README.

- fond papier de la charte (#F7F4EE) pour que le logo garde ses vraies
  couleurs (navy + vague teal) : l'ancienne banniere le passait en
  silhouette blanche sur fond nuit, la vague du B disparaissait ;
- logo officiel : frontend/public/brand/blueseatra-lockup.png ;
- capture actuelle (donnees masquees) du tableau de bord :
  docs/assets/manuel/01-tableau-de-bord.jpg.

Rendu x2 (3200 x 1280) pour un affichage net sur GitHub.
Usage : python scripts/docs/generer_banniere.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RACINE = Path(__file__).resolve().parents[2]
ASSETS = RACINE / "docs" / "assets"
BRAND = RACINE / "frontend" / "public" / "brand"
S = 2
W, H = 1600, 640

PAPIER = (247, 244, 238)
NAVY = (25, 56, 82)
TEAL = (43, 179, 168)
GRIS = (84, 96, 108)
BLANC = (255, 255, 255)
LATO = Path("/usr/share/fonts/truetype/lato")


def police(nom: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(LATO / f"Lato-{nom}.ttf"), taille * S)


def s(*v):
    return tuple(int(x * S) for x in v)


def main() -> None:
    img = Image.new("RGB", s(W, H), PAPIER)
    d = ImageDraw.Draw(img)

    # Fond : grand aplat teal tres clair a droite, bord arrondi, pour poser la capture
    d.rounded_rectangle(s(760, -60, W + 80, H + 60), radius=60 * S, fill=(229, 241, 239))
    # Fines courbes de vague (rappel du logo)
    for i, col in enumerate([(205, 230, 227), (214, 235, 232)]):
        d.arc(s(640 + i * 40, 380 + i * 30, 1900, 1300), 190, 300, fill=col, width=4 * S)

    # Logo officiel
    logo = Image.open(BRAND / "blueseatra-lockup.png").convert("RGBA")
    lh = 86
    lw = int(logo.width * lh / logo.height)
    logo = logo.resize(s(lw, lh), Image.LANCZOS)
    img.paste(logo, s(80, 64), logo)

    # Titre
    f_titre = police("Heavy", 58)
    y = 190
    d.text(s(84, y), "Des demandes brutes", font=f_titre, fill=NAVY)
    y += 70
    d.text(s(84, y), "aux devis ", font=f_titre, fill=NAVY)
    x = 84 + d.textlength("aux devis ", font=f_titre) / S
    d.text(s(x, y), "validés", font=f_titre, fill=TEAL)
    x += d.textlength("validés", font=f_titre) / S
    d.text(s(x, y), ",", font=f_titre, fill=NAVY)
    y += 70
    d.text(s(84, y), "sur vos prix.", font=f_titre, fill=NAVY)

    # Sous-titre
    f_sous = police("Regular", 22)
    y += 92
    for ligne in ("L'IA lit les e-mails, PDF et photos, structure le besoin en",
                  "lots TCE et prépare un devis chiffré avec vos catalogues."):
        d.text(s(86, y), ligne, font=f_sous, fill=GRIS)
        y += 32

    # Pastilles
    f_pas = police("Semibold", 16)
    x, y = 86, y + 26
    for txt in ("IA auto-hébergée chez OVH", "~970 000 références", "Multi-entreprises RLS", "FR · EN"):
        tw = d.textlength(txt, font=f_pas) / S
        bw = tw + 32
        if x + bw > 720:
            x, y = 86, y + 48
        d.rounded_rectangle(s(x, y, x + bw, y + 36), radius=18 * S, fill=BLANC, outline=NAVY, width=S)
        d.text(s(x + 16, y + 8), txt, font=f_pas, fill=NAVY)
        x += bw + 12

    # Capture dans un cadre de navigateur
    cap = Image.open(ASSETS / "manuel" / "01-tableau-de-bord.jpg").convert("RGB")
    fx, fy, fw = 830, 92, 720
    barre = 30
    ch = int(cap.height * fw / cap.width)
    fh = barre + ch
    # Ombre
    ombre = Image.new("RGBA", s(W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ombre)
    od.rounded_rectangle(s(fx + 6, fy + 16, fx + fw + 6, fy + fh + 16), radius=14 * S, fill=(25, 56, 82, 70))
    ombre = ombre.filter(ImageFilter.GaussianBlur(18 * S))
    img.paste(ombre, (0, 0), ombre)
    # Cadre
    cadre = Image.new("RGBA", s(fw, fh), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cadre)
    cd.rounded_rectangle(s(0, 0, fw, fh), radius=14 * S, fill=BLANC)
    cd.rectangle(s(0, barre - 1, fw, barre), fill=(226, 230, 234))
    for i, col in enumerate([(236, 106, 94), (244, 191, 79), (97, 197, 84)]):
        cx = 20 + i * 18
        cd.ellipse(s(cx - 5, barre / 2 - 5, cx + 5, barre / 2 + 5), fill=col)
    cd.rounded_rectangle(s(90, 7, fw - 90, barre - 7), radius=8 * S, fill=(241, 243, 245))
    f_url = police("Regular", 12)
    cd.text(s(fw / 2 - 52, 8), "www.blueseatra.com", font=f_url, fill=GRIS)
    cap = cap.resize(s(fw, ch), Image.LANCZOS)
    cadre.paste(cap, s(0, barre))
    masque = Image.new("L", s(fw, fh), 0)
    ImageDraw.Draw(masque).rounded_rectangle(s(0, 0, fw, fh), radius=14 * S, fill=255)
    img.paste(cadre, s(fx, fy), masque)
    ImageDraw.Draw(img).rounded_rectangle(s(fx, fy, fx + fw, fy + fh), radius=14 * S,
                                          outline=(208, 214, 220), width=S)

    img.save(ASSETS / "banniere.jpg", quality=92, optimize=True)
    print("wrote", ASSETS / "banniere.jpg", img.size)


if __name__ == "__main__":
    main()
