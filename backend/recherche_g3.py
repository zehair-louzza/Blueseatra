"""Chaîne G3 : demande de devis en texte libre -> articles du catalogue, à valider.

POURQUOI
--------
Mesure du 08-09/10/2026 sur 17 demandes réelles (40 besoins, vérité terrain
annotée à la main) :
  - recherche par mots seule (méthode F)           25/40 besoins, précision 0,23
  - extraction par LLM puis recherche (F)          30/40, précision 0,40
  - G3 (ce module)                                 33/40, précision 0,535
  - plafond : bon article parmi les 20 candidats   37/40
Les modèles locaux du VPS restent en dessous (gpt-oss:20b 21/40,
glm-4.7-flash 16/40) : G3 est prévu pour un modèle externe, avec le texte
masqué (masquage_rgpd, appliqué automatiquement par ai_service) et une
validation humaine obligatoire.

ÉTAPES
------
1. Minimisation : seule la description des travaux est gardée (en-tête,
   coordonnées et signature retirés) avant l'extraction.
2. Extraction : le LLM liste les FOURNITURES nécessaires (désignations de
   catalogue courtes).
3. Candidats : pour chaque fourniture, union de la recherche par mots pondérée
   (IDF, début de mot, synonymes BTP) et de BM25 sur le catalogue du tenant,
   20 candidats au maximum.
4. Choix : le LLM choisit au plus 3 codes PARMI les candidats ; tout code
   inventé est ignoré. Si l'appel échoue ou si le modèle ne retient aucun
   candidat : 1 suggestion de repli (meilleur candidat par mots), marquée
   « repli ». C'est la version mesurée (33/40) : sans ce repli, 29/40.
5. Résultat toujours « à valider » : rien n'entre dans un devis sans
   validation par le chiffreur.

Le catalogue est évalué en mémoire (quelques milliers d'articles au plus) ;
aucune saisie n'est transmise à la base.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Awaitable, Callable, Dict, Iterable, List

MAX_DEMANDE = 20_000
MAX_PRODUITS = 30
N_CANDIDATS = 20
CHAMPS = ("item_label", "family", "category", "brand", "reference")

CONSIGNE_EXTRACTION = (
    "Tu es métreur dans le bâtiment (second œuvre, maintenance). Lis la demande de travaux et liste les FOURNITURES "
    "(produits physiques à acheter chez un distributeur) nécessaires pour la réaliser. Une entrée par produit, formulée "
    "comme une désignation de catalogue courte en français (nom du produit + caractéristique utile, ex. « cylindre "
    "européen 30x30 », « chauffe-eau électrique 100 L », « cheville à expansion placo »). Inclure les fournitures "
    "directement impliquées par la tâche (ex. refixer → chevilles et vis). Exclure main-d'œuvre, déplacement, "
    "nettoyage, administratif. Traduire les termes étrangers. Les marqueurs entre crochets ([adresse_1]…) remplacent "
    "des informations confidentielles : ne les recopie pas. Réponds uniquement par un objet JSON "
    '{"produits": [{"designation": "...", "quantite": "..."}]}.')
CONSIGNE_CHOIX = (
    "Pour le produit demandé, choisis dans la liste de candidats du catalogue les articles qui conviennent réellement "
    "(même type de produit ; une variante proche est acceptable). Maximum 3 codes, du meilleur au moins bon. Si aucun "
    'ne convient, renvoie une liste vide. N\'invente aucun code. Réponds uniquement par un objet JSON {"codes": ["..."]}.')
SCHEMA_EXTRACTION = {"type": "object", "properties": {"produits": {"type": "array", "items": {
    "type": "object", "properties": {"designation": {"type": "string"}, "quantite": {"type": "string"}},
    "required": ["designation"]}}}, "required": ["produits"]}
SCHEMA_CHOIX = {"type": "object", "properties": {"codes": {"type": "array", "items": {"type": "string"}}},
                "required": ["codes"]}

AppelIA = Callable[[str, str, dict], Awaitable[dict]]

# --------------------------------------------------------------------------- normalisation
MOTS_VIDES = set("""
a au aux avec ce ces cet cette d de des du en et il ils elle la le les leur leurs ma mes mon ne ni nos notre nous on
ou par pas pour qu que qui sa se ses son sur ta te tes ton tu un une vos votre vous y l n s c j m
""".split())
MOTS_DEVIS = set("""
remplacement remplacer remplace mise mettre place fourniture fournir pose poser installation installer prevoir
prevoi merci devi chiffrer chiffrage intervention intervenir travaux travail remise etat reprise reprendre refection
refixer retirer retrait suite besoin souhaitons souhaite option total soit quelque certain ensemble presence attente
utilisation existant existante ancien ancienne supplementaire nouveau nouvelle dispositif demande prestation
prestations realiser chaque cote procede proceder afin etre faut faudrait permettre doit servir cas idee suivant
suivante concernant comprenant notamment necessaire selon precise detaille
""".split())
SYNONYMES = {
    "toilette": ["wc"], "sanitaire": ["wc"], "cuvette": ["wc"], "ballon": ["chauffe"], "cumulus": ["chauffe"],
    "luminaire": ["spot", "downlight", "dalle", "hublot"], "lumineux": ["spot", "downlight"],
    "eclairage": ["spot", "downlight"], "plafonnier": ["downlight", "hublot"], "electrique": ["courant"],
    "valve": ["clapet", "vanne"], "check": ["clapet"], "return": ["anti", "retour"], "bonde": ["siphon"],
    "volige": ["tasseau", "panneau"], "planche": ["panneau", "tasseau"], "placo": ["plaque", "platre"],
    "ba13": ["plaque", "platre"], "rebouchage": ["enduit"], "reboucher": ["enduit"], "trou": ["enduit"],
    "fissure": ["enduit"], "peindre": ["peinture"], "repeindre": ["peinture"], "cablage": ["cable"],
    "fil": ["cable"], "boucher": ["deboucheur"], "debordement": ["deboucheur", "furet"], "bouche": ["deboucheur"],
    "rongeur": ["grille", "bas"], "fixer": ["cheville", "vis"], "refixer": ["cheville", "vis"],
    "fixation": ["cheville", "vis"], "etagere": ["cheville"], "cadre": ["cheville", "vis"], "galva": ["galvanise"],
    "fermeture": ["cadenas", "verrou"], "aureole": ["peinture"], "tache": ["peinture"], "moquette": ["sol"],
}
_DEBUT_TRAVAUX = re.compile(
    r"(?i)(travaux suivants\s*:?|description de l.intervention[^:]*:|description\s*:?|"
    r"objet de la (?:demande|consultation)|p[ée]rim[èe]tre des travaux|description pr[ée]cise des travaux demand[ée]s)")
_FIN_TRAVAUX = re.compile(
    r"(?i)(devis gratuit|cordialement|avec mes remerciements|date de passage|date d.intervention|"
    r"seuil d.intervention|intervention planifi|merci de bien d[ée]tailler|merci de d[ée]tailler|date de retour souhait)")
_LIGNE_ADMIN = re.compile(
    r"(?i)(@|https?://|www\.|t[ée]l(?:[ée]phone)?\s*[.:]|\biban\b|\bbic\b|siret|siren|tva|"
    r"\b\d{5}\b\s+[A-Z]|n°\s*dossier|capital de|^\s*client\s*:|^\s*site\s*:)")


def extraire_travaux(texte: str) -> str:
    """Description des travaux seule (en-tête, coordonnées et signature retirés)."""
    t = (texte or "")[:MAX_DEMANDE]
    debut = _DEBUT_TRAVAUX.search(t)
    if debut:
        t = t[debut.end():]
        fin = _FIN_TRAVAUX.search(t)
        if fin and fin.start() > 0:
            t = t[:fin.start()]
    return "\n".join(l for l in re.split(r"[\r\n]+", t) if l.strip() and not _LIGNE_ADMIN.search(l))


def _sans_accent(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c)).lower()


def _singulier(mot: str) -> str:
    return mot[:-1] if len(mot) >= 4 and mot.isalpha() and mot[-1] in "sx" else mot


def mots(texte: str, garder_vocabulaire_devis: bool = False) -> List[str]:
    t = _sans_accent(texte or "").replace("²", "2").replace("³", "3")
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    sortie = []
    for brut in re.split(r"[^a-z0-9.+]+", t):
        m = brut.strip(".+")
        if not m or m in MOTS_VIDES or (m.isalpha() and len(m) < 3):
            continue
        if not garder_vocabulaire_devis and (m in MOTS_DEVIS or _singulier(m) in MOTS_DEVIS):
            continue
        sortie.append(_singulier(m))
    return sortie


def _requete(produit: str) -> List[str]:
    bruts = mots(produit, garder_vocabulaire_devis=True)
    return list(dict.fromkeys(mots(produit) + [s for m in bruts for s in SYNONYMES.get(m, [])]))


# --------------------------------------------------------------------------- index
class Index:
    """Catalogue du tenant : recherche par mots pondérée (méthode F) + BM25."""

    def __init__(self, articles: Iterable[Dict]):
        self.articles = [a for a in articles if a.get("item_code") and a.get("item_label")]
        self.jetons = [mots(" ".join(str(a.get(c) or "") for c in CHAMPS)) for a in self.articles]
        self.ensembles = [set(j) for j in self.jetons]
        self.titres = [set(mots(str(a.get("item_label") or ""))) for a in self.articles]
        self._n = max(len(self.articles), 1)
        self._cache: Dict[str, tuple] = {}
        self._long_moy = (sum(len(j) for j in self.jetons) / self._n) or 1.0
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] | None = None
        for js in self.ensembles:
            for j in js:
                self._df[j] = self._df.get(j, 0) + 1

    @staticmethod
    def _correspond(mot: str, jeton: str) -> bool:
        if mot.isdigit() or jeton.isdigit():
            return mot == jeton
        if jeton.startswith(mot):
            return True
        return len(jeton) >= 4 and mot.startswith(jeton) and len(mot) - len(jeton) <= 2

    def _poids(self, mot: str) -> tuple:
        if mot not in self._cache:
            idx = frozenset(i for i, js in enumerate(self.ensembles) if any(self._correspond(mot, j) for j in js))
            self._cache[mot] = (math.log(self._n / len(idx)) if idx else 0.0, idx)
        return self._cache[mot]

    def par_mots(self, produit: str, limite: int = 12, score_min: float = 1.0) -> List[int]:
        scores: Dict[int, float] = {}
        for m in _requete(produit):
            idf, idx = self._poids(m)
            for i in idx:
                dans_titre = any(self._correspond(m, j) for j in self.titres[i])
                scores[i] = scores.get(i, 0.0) + (idf if dans_titre else idf / 2)
        classes = sorted(scores.items(), key=lambda kv: (-kv[1], str(self.articles[kv[0]]["item_code"])))
        return [i for i, s in classes if s >= score_min][:limite]

    def bm25(self, produit: str, limite: int = 12, k1: float = 1.5, b: float = 0.75, eps: float = 0.25) -> List[int]:
        """BM25 Okapi (même formule que rank_bm25.BM25Okapi, mesurée le 08/10/2026)."""
        if self._idf is None:
            idf = {m: math.log(self._n - df + 0.5) - math.log(df + 0.5) for m, df in self._df.items()}
            moyenne = sum(idf.values()) / max(len(idf), 1)
            self._idf = {m: (v if v >= 0 else eps * moyenne) for m, v in idf.items()}
        mots_requete = mots(produit) + [s for m in mots(produit, garder_vocabulaire_devis=True)
                                        for s in SYNONYMES.get(m, [])]
        scores = []
        for i, js in enumerate(self.jetons):
            s = 0.0
            for m in mots_requete:
                tf = js.count(m)
                if tf:
                    s += self._idf.get(m, 0.0) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(js) / self._long_moy))
            if s > 0:
                scores.append((s, i))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [i for _, i in scores[:limite]]

    def candidats(self, produit: str, n: int = N_CANDIDATS) -> List[Dict]:
        vus, sortie = set(), []
        for i in self.par_mots(produit) + self.bm25(produit):
            if i not in vus:
                vus.add(i)
                sortie.append(self.articles[i])
        return sortie[:n]


# --------------------------------------------------------------------------- chaîne
def _article(a: Dict) -> Dict:
    return {k: a.get(k) for k in ("item_code", "item_label", "unit", "unit_price_ht", "family", "brand")}


async def suggerer(demande: str, catalogue: List[Dict], appel_ia: AppelIA) -> Dict:
    """Suggestions d'articles pour une demande ; toujours à valider par le chiffreur."""
    index = Index(catalogue or [])
    if not index.articles:
        return {"statut": "erreur", "erreur": "Aucun catalogue actif.", "lignes": []}
    travaux = extraire_travaux(demande)
    if not travaux.strip():
        return {"statut": "a_valider", "lignes": [], "remarque": "Aucune description de travaux repérée."}
    try:
        brut = await appel_ia(CONSIGNE_EXTRACTION, travaux, SCHEMA_EXTRACTION)
        produits = [p for p in (brut or {}).get("produits", []) if isinstance(p, dict)
                    and str(p.get("designation") or "").strip()][:MAX_PRODUITS]
    except Exception as exc:
        return {"statut": "erreur", "erreur": f"Extraction impossible : {str(exc)[:160]}", "lignes": []}

    lignes = []
    for p in produits:
        designation = str(p["designation"]).strip()[:200]
        cands = index.candidats(designation)
        ligne = {"produit": designation, "quantite": str(p.get("quantite") or "").strip()[:40] or None,
                 "articles": [], "source": "aucun", "a_valider": True}
        if cands:
            liste = [{"code": a["item_code"], "article": a["item_label"]} for a in cands]
            try:
                rep = await appel_ia(CONSIGNE_CHOIX, json.dumps({"produit": designation, "candidats": liste},
                                                                ensure_ascii=False), SCHEMA_CHOIX)
                valides = {a["item_code"]: a for a in cands}
                codes = [c for c in dict.fromkeys(str(c) for c in (rep or {}).get("codes", [])) if c in valides][:3]
                ligne["articles"] = [_article(valides[c]) for c in codes]
                ligne["source"] = "ia" if codes else "aucun"
            except Exception:
                pass
            if not ligne["articles"]:
                meilleur = index.par_mots(designation, limite=1)
                if meilleur:
                    ligne["articles"] = [_article(index.articles[meilleur[0]])]
                    ligne["source"] = "repli"
        lignes.append(ligne)
    return {"statut": "a_valider", "lignes": lignes}
