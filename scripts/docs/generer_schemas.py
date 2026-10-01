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
    c.box((520, 110, 880, 371), "Recherche sous RLS", [
        "par libellé de la demande,",
        "une branche par source activée :",
        "",
        "1. offres_candidates : index",
        "   trigramme, 200 id par source,",
        "   tenant courant ou commun seul",
        "2. fiches relues par id, sous RLS",
        "3. tri par prix sur ce petit résultat",
        "« prise » : > 30 s (vide) → 2,3 s",
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


# --------------------------------------------------------------------------
RED_BG = (251, 234, 232)
RED = (176, 58, 46)
GREEN_BG = (230, 244, 234)
GREEN = (46, 125, 70)


def build_livraison() -> None:
    c = Canvas(1400, 560)
    c.title("Chaîne de livraison", "Une fusion sur main déploie automatiquement ; aucune action manuelle sur les serveurs.")
    c.box((40, 110, 290, 231), "1 Branche + PR", ["feat/... ou fix/...", "gabarit de PR", "un test par correctif"])
    c.box((330, 110, 640, 252), "2 Contrôles GitHub", [("ci-infra", "lint, migrations,"), ("", "recherche de secrets"),
                                                          ("securite", "isolation tenant_id"), ("tests-metier", "pytest")], col2=110)
    c.box((680, 110, 930, 231), "3 Fusion sur main", ["squash, branche supprimée", "migration Supabase", "appliquée AVANT"], fill=ACCENT_BG)
    c.box((980, 92, 1360, 196), "Render : API", ["si backend/ change, 2 à 3 min", "/api/health renvoie le commit"])
    c.box((980, 212, 1360, 316), "Vercel : site", ["frontend/ à chaque fusion, 1 à 2 min", "www.blueseatra.com"])
    c.arrow([(290, 170), (330, 170)])
    c.arrow([(640, 170), (680, 170)])
    c.arrow([(930, 150), (955, 150), (955, 144), (980, 144)])
    c.arrow([(930, 190), (955, 190), (955, 264), (980, 264)])
    c.zone((40, 350, 1360, 520), "Retour arrière")
    c.box((60, 390, 470, 494), "API défectueuse", ["Render : Rollback du déploiement", "précédent, ou git revert + fusion"], fill=RED_BG)
    c.box((495, 390, 905, 494), "Site défectueux", ["Vercel : Redeploy du déploiement", "précédent, ou git revert + fusion"], fill=RED_BG)
    c.box((930, 390, 1340, 494), "Migration", ["toujours additive : l'ancien code", "l'ignore ; jamais de DROP en urgence"], fill=RED_BG)
    c.save("schema-livraison.png")


def build_isolation() -> None:
    c = Canvas(1400, 540)
    c.title("Isolation des entreprises", "Deux verrous indépendants : le filtre du code ET la RLS imposée par PostgreSQL.")
    c.box((40, 110, 300, 231), "Requête", ["Authorization: Bearer", "X-Tenant-Id (choix", "de l'entreprise)"])
    c.box((340, 110, 640, 231), "API : tenant résolu", ["côté serveur depuis le jeton", "et l'appartenance du membre,", "jamais pris tel quel du client"])
    c.box((680, 110, 990, 231), "tenant_session()", ["SET app.tenant_id", "rôle blueseatra_app", "(non propriétaire des tables)"], fill=ACCENT_BG)
    c.box((1030, 110, 1360, 231), "PostgreSQL RLS", ["policy : tenant_id =", "current_tenant()", "sur chaque table métier"], fill=ACCENT_BG)
    for a, b in ((300, 340), (640, 680), (990, 1030)):
        c.arrow([(a, 170), (b, 170)])
    c.box((40, 270, 440, 374), "Filtre explicite dans le code", ["WHERE tenant_id = :tenant", "vérifié en CI (workflow securite)"])
    c.box((480, 270, 900, 374), "Identifiant d'une autre entreprise", ["réponse 404, jamais 403 :", "on ne révèle pas son existence"], fill=RED_BG)
    c.box((940, 270, 1360, 374), "Catalogue fournisseurs commun", ["seule donnée partagée, en lecture,", "masquable par entreprise"], fill=AMBER_BG)
    c.text((40, 410), "Même si une requête oubliait le filtre, la RLS ne renverrait aucune ligne d'une autre entreprise ; "
                      "et sans app.tenant_id positionné,", F_FOOT, FOOT)
    c.text((40, 436), "elle ne renvoie rien du tout (get_db() sans tenant est désactivée). Audit d'isolation : "
                      "docs/audit-isolation-tenants-2026-09-12.md.", F_FOOT, FOOT)
    c.text((40, 462), "Seules exceptions à la RLS : 3 fonctions de recherche SECURITY DEFINER, qui vérifient elles-mêmes "
                      "le tenant et ne renvoient que des identifiants,", F_FOOT, FOOT)
    c.text((40, 488), "relus ensuite sous RLS (schéma schema-recherche-rls.png).", F_FOOT, FOOT)
    c.save("schema-isolation.png")


def build_cycle_devis() -> None:
    c = Canvas(1400, 640)
    c.title("Cycle de vie d'un devis et relances", "Chaque validation fige une version ; rien n'est écrasé ni supprimé.")
    c.box((40, 120, 250, 220), "Brouillon", ["modifiable,", "généré ou manuel"])
    c.box((350, 120, 560, 220), "Validé", ["version figée,", "PDF Pro Forma"], fill=ACCENT_BG)
    c.box((660, 120, 870, 220), "Envoyé", ["relances créées", "automatiquement"], fill=AMBER_BG)
    c.box((990, 84, 1200, 142), "Accepté", [], fill=GREEN_BG)
    c.box((990, 156, 1200, 214), "Refusé", [], fill=RED_BG)
    c.box((990, 228, 1200, 286), "Sans suite", [], fill=RED_BG)
    c.arrow([(250, 170), (350, 170)], "Valider", (272, 146))
    c.arrow([(560, 170), (660, 170)], "Envoyer", (580, 146))
    c.arrow([(870, 170), (930, 170), (930, 113), (990, 113)])
    c.arrow([(930, 170), (930, 185), (990, 185)])
    c.arrow([(930, 185), (930, 257), (990, 257)])
    c.arrow([(765, 220), (765, 270), (145, 270), (145, 220)])
    c.text((260, 278), "Remettre en brouillon : nouvelle version, relances annulées", F_BOX_BODY, ARROW)
    c.zone((40, 330, 1360, 600), "Calendrier des relances (jours ouvrés : hors week-ends et 11 jours fériés)")
    rows = [("Devis ordinaire", "J+3, J+7, J+14 après l'envoi, à 9 h"),
            ("Demande urgente", "J+1, J+2, J+4"),
            ("Validité renseignée", "rappel 3 jours ouvrés avant expiration"),
            ("Plus de 10 000 € HT", "appel proposé plutôt qu'un e-mail"),
            ("Contact sans e-mail", "appel")]
    y = 372
    for a_, b_ in rows:
        c.text((60, y), a_, F_BOX_TITLE)
        c.text((330, y + 2), b_, F_BOX_BODY, BODY)
        y += 34
    c.box((860, 365, 1340, 576), "Arrêt des relances", ["devis accepté, refusé ou sans suite",
                                                     "devis remis en brouillon",
                                                     "client archivé ou relances désactivées",
                                                     "opposition RGPD du contact",
                                                     "→ statut « annulée » avec motif,",
                                                     "   jamais supprimées"])
    c.save("schema-cycle-devis.png")


def build_quotas() -> None:
    c = Canvas(1400, 520)
    c.title("Quotas et consommation", "Seul l'automatique est compté ; tout le manuel est illimité dans toutes les offres.")
    c.box((40, 110, 290, 210), "Nouvelle demande", ["texte, PDF, photo", "lue par l'IA"])
    c.box((330, 110, 640, 231), "quota_reserver()", ["1 devis assisté IA", "+ pages lues si photo", "ou PDF scanné"], fill=ACCENT_BG)
    c.box((680, 110, 930, 210), "Lecture IA", ["OCR, structuration,", "brouillon de devis"])
    c.box((980, 92, 1360, 175), "Succès", ["consommation confirmée"], fill=GREEN_BG)
    c.box((980, 190, 1360, 273), "Échec", ["écriture inverse : quota remboursé"], fill=RED_BG)
    c.arrow([(290, 160), (330, 160)])
    c.arrow([(640, 160), (680, 160)])
    c.arrow([(930, 145), (955, 145), (955, 133), (980, 133)])
    c.arrow([(930, 180), (955, 180), (955, 231), (980, 231)])
    c.box((40, 300, 640, 446), "Jamais compté", ["devis manuels, PDF, catalogues internes,",
                                                 "catalogue fournisseurs commun, comparateur de prix,",
                                                 "PDF qui contient déjà du texte (0 page lue)",
                                                 "→ illimité dans toutes les offres"], fill=GREEN_BG)
    c.box((680, 300, 1360, 446), "Registre de consommation", ["écritures ajoutées uniquement (trigger)",
                                                            "correction = écriture inverse, jamais une modification",
                                                            "impayé : suspension, jamais de suppression",
                                                            "historique visible dans Offre et consommation"])
    c.text((40, 470), "Offres : Découverte (essai 14 j, 10 devis IA, 30 pages)  |  Initial 59 €  |  Pilotage 149 €  |  "
                      "Performance 399 €  |  Signature sur devis", F_FOOT, FOOT)
    c.save("schema-quotas.png")


def build_import_catalogue() -> None:
    c = Canvas(1400, 470)
    c.title("Import d'un catalogue tarifaire", "Toujours une nouvelle version en brouillon : l'ancienne reste active tant que vous n'activez pas.")
    steps = [("1 Fichier", ["CSV de n'importe", "quel format"], WHITE),
             ("2 Correspondance", ["colonnes détectées,", "corrigeables"], WHITE),
             ("3 Import", ["version créée", "en brouillon"], WHITE),
             ("4 Contrôle", ["comparaison avec", "la version active"], AMBER_BG),
             ("5 Activé", ["bascule atomique", "de version"], GREEN_BG)]
    x, w, gap = 40, 236, 30
    spans = []
    for t, l, f in steps:
        c.box((x, 110, x + w, 210), t, l, fill=f)
        spans.append((x, x + w))
        x += w + gap
    for (_, a), (b, _) in zip(spans[:-1], spans[1:]):
        c.arrow([(a, 160), (b, 160)])
    c.zone((40, 240, 1360, 430), "Verdict du contrôle")
    c.box((60, 280, 470, 405), "OK", ["rien à signaler :", "activation directe"], fill=GREEN_BG)
    c.box((495, 280, 905, 405), "À vérifier", ["prix manquants, unités inconnues,", "fortes variations de prix", "→ activation possible après revue"], fill=AMBER_BG)
    c.box((930, 280, 1340, 405), "Bloquant", ["version vide, prix négatifs, trop de", "rejets, beaucoup moins d'articles",
                                              "→ « Forcer » : owner ou admin seulement"], fill=RED_BG)
    c.save("schema-import-catalogue.png")


def build_rgpd() -> None:
    c = Canvas(1400, 480)
    c.title("Droits des personnes (RGPD)", "Tout est tracé dans le journal d'audit ; aucune donnée n'est supprimée physiquement.")
    boxes = [("Accès, portabilité", ["art. 15 et 20", "Paramètres → Données", "personnelles → export", "GET /api/rgpd/export"], WHITE),
             ("Effacement", ["art. 17", "Anonymiser par e-mail :", "identité effacée, devis", "et montants conservés"], AMBER_BG),
             ("Opposition", ["art. 21", "« Accepte les relances »", "décoché : relances", "→ tâches internes"], WHITE),
             ("Rectification", ["art. 16", "modifier la fiche", "client ou contact"], WHITE),
             ("Conservation", ["art. 5", "client archivé > 3 ans :", "contact listé pour", "anonymisation"], WHITE)]
    x, w, gap = 40, 246, 22
    for t, l, f in boxes:
        c.box((x, 110, x + w, 252), t, l, fill=f)
        x += w + gap
    c.box((40, 290, 680, 414), "Journal d'audit", ["rgpd.export, rgpd.anonymisation (e-mail pseudonymisé)",
                                                    "ajout seul : aucune fonction de modification",
                                                    "ni d'effacement d'une entrée"], fill=ACCENT_BG)
    c.box((720, 290, 1360, 414), "Mesures de sécurité", ["RLS par entreprise, clés IA chiffrées (Fernet)",
                                                          "mots de passe bcrypt, HTTPS obligatoire",
                                                          "journaux JSON sans e-mail en clair"])
    c.save("schema-rgpd.png")


def build_incident() -> None:
    c = Canvas(1400, 420)
    c.title("Déroulé d'un incident", "Chaque requête porte un request_id : il relie le message d'erreur, les journaux Render et l'audit.")
    steps = [("1 Détecter", ["alerte, client,", "réveil pg_cron KO"], WHITE, "—"),
             ("2 Qualifier", ["/api/health,", "journaux ERROR"], WHITE, "10 min"),
             ("3 Contenir", ["rollback, coupure", "IA, quotas à 0"], RED_BG, "15 min"),
             ("4 Corriger", ["PR + test qui", "reproduit, CI verte"], WHITE, "selon gravité"),
             ("5 Vérifier", ["health sur le commit,", "parcours critique"], GREEN_BG, "10 min"),
             ("6 Post-mortem", ["fiche dans un", "ticket GitHub"], ACCENT_BG, "5 j ouvrés")]
    x, w, gap = 40, 196, 28
    spans = []
    for t, l, f, d in steps:
        c.box((x, 110, x + w, 210), t, l, fill=f)
        c.text((x + 18, 222), d, F_BOX_BODY, ARROW)
        spans.append((x, x + w))
        x += w + gap
    for (_, a), (b, _) in zip(spans[:-1], spans[1:]):
        c.arrow([(a, 160), (b, 160)])
    c.text((40, 270), "Contenir : API en 5xx → Render Rollback  |  quotas qui bloquent → BLUESEATRA_QUOTAS_APPLIQUES=0  |  "
                      "IA en échec → BLUESEATRA_IA_COUPURE=repli", F_FOOT, FOOT)
    c.text((40, 296), "Soupçon de fuite entre entreprises : couper l'accès, conserver les journaux, prévenir sous 72 h "
                      "si des données personnelles sont touchées (art. 33).", F_FOOT, FOOT)
    c.save("schema-incident.png")


def build_recherche_rls() -> None:
    c = Canvas(1400, 640)
    c.title("Recherche fournisseurs sous RLS",
            "L'index trigramme redevient utilisable, et l'isolation garde ses deux verrous.")
    c.box((40, 110, 330, 252), "Écran", ["comparateur de prix,", "sélecteur du devis,", "génération, catalogue,",
                                          "menu Famille"])
    c.box((370, 110, 680, 252), "API", ["termes normalisés en JSON,", "\\b → \\y (mots PostgreSQL),",
                                         "tenant résolu côté serveur,", "jamais pris du client"])
    c.box((720, 110, 1040, 252), "Fonction SECURITY DEFINER", ["refuse tout tenant autre que", "l'entreprise ou le commun ;",
                                                               "index trigramme ou par prix ;", "renvoie des identifiants"],
          fill=ACCENT_BG, tag="HORS RLS", tag_color=AMBER)
    c.box((1080, 110, 1360, 252), "Relecture des fiches", ["par identifiant,", "SOUS RLS, avec filtre", "tenant explicite :",
                                                           "second verrou"], fill=GREEN_BG)
    for a, b in ((330, 370), (680, 720), (1040, 1080)):
        c.arrow([(a, 181), (b, 181)])

    c.zone((40, 290, 1360, 470), "Fonctions de recherche (search_path vide ; les 3 premières : SECURITY DEFINER, réservées à blueseatra_app)")
    cols = [
        (60, "offres_candidates", ["comparateur, sélecteur", "du devis, génération ;", "filtre famille facultatif"]),
        (390, "catalogue_page", ["recherche par mot dans", "un catalogue, page triée", "par prix, total plafonné"]),
        (720, "familles_catalogue", ["familles d'un catalogue :", "parcours en saut de", "l'index, une lecture par famille"]),
        (1050, "recherche_conditions", ["règles des motifs (LIKE, ~),", "littéraux échappés %L ;", "interne, non appelable"]),
    ]
    for x, titre, lignes in cols:
        c.text((x, 330), titre, F_BOX_TITLE)
        for i, l in enumerate(lignes):
            c.text((x, 360 + 21 * i), l, F_BOX_BODY, BODY)

    c.zone((40, 490, 1360, 610), "Mesures en direct depuis le navigateur, avant → après (Rexel, 747 771 offres)")
    c.text((60, 530), "« disjoncteur 16a courbe c » dans un catalogue : 26,6 s → 1,4 s      terme rare : 43,9 s → 0,8 s      sélecteur « prise » : > 30 s → 2,3 s",
           F_BOX_BODY, HEADING)
    c.text((60, 556), "comparateur « dalle LED 600x600 » : 27 s → 0,9 s      liste des familles : 75 s → 3,4 s      "
                      "« courbe c » : 0 → 320 offres (\\b)", F_BOX_BODY, HEADING)
    c.save("schema-recherche-rls.png")


if __name__ == "__main__":
    build_architecture()
    build_parcours()
    build_routage()
    build_chiffrage()
    build_livraison()
    build_isolation()
    build_cycle_devis()
    build_quotas()
    build_import_catalogue()
    build_rgpd()
    build_incident()
    build_recherche_rls()
