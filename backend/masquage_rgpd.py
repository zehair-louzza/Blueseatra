"""Masquage RGPD des textes envoyés à un modèle d'IA hors du VPS.

POURQUOI
--------
Mistral (UE) et OpenCode Free (États-Unis) reçoivent le texte des demandes
de devis. Ces textes contiennent des adresses de sites, des noms de clients et
de donneurs d'ordre, des prénoms, des téléphones, des SIRET et des IBAN.
Ce module remplace ces informations par des marqueurs (« [adresse_1] »,
« [personne_2] »…) AVANT l'envoi, puis remet les vraies valeurs dans la
réponse du modèle, sur le serveur Blueseatra. Les correspondances ne
quittent jamais le serveur.

CE QUI EST MASQUÉ
-----------------
- Adresses : numéro et type de voie, code postal et ville, ZA/ZI/centre
  commercial, BP.
- Noms connus : clients, contacts, chantiers (sites) et sociétés déjà
  enregistrés dans Blueseatra, quelle que soit la casse ou l'accentuation,
  et tout nom lu dans un champ « Client : », « Site : »… de la demande.
- Personnes : signature après « Cordialement », champs « Interlocuteur : »,
  « Contact : », civilités (M., Mme…), prénoms du fichier INSEE suivis du nom.
- Identifiants : e-mail, site web, téléphone, SIRET/SIREN, IBAN, BIC, TVA,
  numéros de dossier ou de commande.
- En-tête des bons de commande (avant la description des travaux) : noms en
  majuscules (raisons sociales, enseignes, codes magasin).

CONTRÔLE AVANT ENVOI
--------------------
verifier_avant_envoi() relance tous les détecteurs sur le texte masqué ; s'il
reste la moindre détection, l'appel externe est refusé (FuitePossible). Ce
contrôle ne voit que ce que les détecteurs savent reconnaître : un nom de
famille inconnu, écrit seul en minuscules au milieu d'une phrase, n'est pas
détectable. Seul un modèle hébergé sur le VPS garantit l'absence totale de
transfert ; voir docs/rgpd-masquage.md.

Prénoms : fichier des prénoms INSEE 2025 (Licence Ouverte 2.0), prénoms
attribués au moins 1 000 fois depuis 1900, sans les homonymes de mots
courants (pierre, rose, marine, blanche…) : donnees_rgpd/prenoms_fr.txt.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, Iterable, List

MAX_TEXTE = 200_000


class FuitePossible(RuntimeError):
    """Le texte masqué contient encore une information détectable."""


@dataclass
class Entites:
    """Noms déjà connus de Blueseatra pour le tenant (valeurs brutes)."""
    sites: List[str] = field(default_factory=list)
    donneurs_ordre: List[str] = field(default_factory=list)
    clients: List[str] = field(default_factory=list)
    personnes: List[str] = field(default_factory=list)
    adresses: List[str] = field(default_factory=list)
    identifiants: List[str] = field(default_factory=list)   # e-mails, téléphones, SIRET connus


@dataclass
class Resultat:
    texte: str
    correspondances: Dict[str, str]      # marqueur -> valeur d'origine

    def categories(self) -> Dict[str, int]:
        compte: Dict[str, int] = {}
        for marqueur in self.correspondances:
            cat = marqueur[1:].rsplit("_", 1)[0]
            compte[cat] = compte.get(cat, 0) + 1
        return compte


# --------------------------------------------------------------------------- outils
def _plat(c: str) -> str:
    """Un caractère -> un caractère sans accent, en minuscule (longueur conservée)."""
    d = unicodedata.normalize("NFKD", c)
    base = d[0] if d else c
    return base.lower() if len(base.lower()) == 1 else c.lower()


def _aplatir(texte: str) -> str:
    return "".join(_plat(c) for c in texte)


@lru_cache(maxsize=1)
def prenoms() -> frozenset:
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees_rgpd", "prenoms_fr.txt")
    with open(chemin, encoding="utf-8") as f:
        return frozenset(l.strip() for l in f if l.strip())


_MARQUEUR = re.compile(r"\[[a-z_]+_\d+\]")


class _Masqueur:
    def __init__(self) -> None:
        self.correspondances: Dict[str, str] = {}
        self._par_valeur: Dict[tuple, str] = {}
        self._compteurs: Dict[str, int] = {}

    def marqueur(self, categorie: str, valeur: str) -> str:
        cle = (categorie, _aplatir(re.sub(r"\s+", " ", valeur.strip())))
        if cle not in self._par_valeur:
            n = self._compteurs.get(categorie, 0) + 1
            self._compteurs[categorie] = n
            m = f"[{categorie}_{n}]"
            self._par_valeur[cle] = m
            self.correspondances[m] = valeur.strip()
        return self._par_valeur[cle]

    def remplacer(self, texte: str, motif: re.Pattern, categorie: str, groupe: int = 0,
                  garde: Callable[[re.Match], bool] | None = None) -> str:
        def _sub(mt: re.Match) -> str:
            valeur = mt.group(groupe)
            if not valeur or not valeur.strip() or _MARQUEUR.fullmatch(valeur.strip()):
                return mt.group(0)
            if garde and not garde(mt):
                return mt.group(0)
            debut, fin = mt.span(groupe)
            d0 = debut - mt.start(0)
            f0 = fin - mt.start(0)
            brut = mt.group(0)
            # Espaces et ponctuation finale gardés hors du marqueur.
            coeur = valeur.rstrip(" \t.,;:-–")
            reste = valeur[len(coeur):]
            return brut[:d0] + self.marqueur(categorie, coeur) + reste + brut[f0:]
        return motif.sub(_sub, texte)


# --------------------------------------------------------------------------- détecteurs
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+|\b[a-z0-9][a-z0-9\-]{1,62}\.(?:fr|com|net|org|eu|io|biz|info)\b(?:/[^\s]*)?")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b")
_BIC = re.compile(r"(?i)\bBIC\s*:?\s*([A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b")
_TVA = re.compile(r"\bFR\s?[0-9A-Z]{2}\s?\d{3}\s?\d{3}\s?\d{3}\b")
_SIRET = re.compile(r"(?<![\d,.])\d{3}[ .]?\d{3}[ .]?\d{3}(?:[ .]?\d{3}[ .]?\d{2}|[ .]?\d{5})?(?![\d,.])")
_TEL = re.compile(r"(?:\+33\s?(?:\(0\)\s?)?|(?<![\d,.])0)[1-9](?:[\s.\-]?\d{2}){4}(?![\d]|[,.]\d)")
_TEL_TRONQUE = re.compile(r"(?<![\d,.])0[1-9](?:[\s.]\d{2}){2,3}[\s.]\d{1,2}(?![\d]|[,.]\d)")
_NUMERO = re.compile(
    r"(?i)\b(?:n[°o]|num(?:[ée]ro)?|r[ée]f(?:[ée]rence)?s?\.?|dossier|commande|ticket|bon|ot|di|intervention)"
    r"(?:\s*(?:n[°o]|de|du|dossier|commande|di|:))*\s*:?\s*([A-Z0-9][A-Z0-9/\-]{3,}\d[A-Z0-9/\-]*|\d{4,})")
_CHIFFRES_LONGS = re.compile(r"(?<![\d,.])\d{7,}(?![\d,.])")

_VOIES = (r"rue|avenue|av\.|bd|boulevard|place|all[ée]e|chemin|impasse|quai|route|rte|faubourg|fbg|villa|"
          r"cit[ée]|sentier|esplanade|parvis|promenade|rond-point|chauss[ée]e|lieu-dit|hameau|r[ée]sidence|square|cours")
_ADRESSE_VOIE = re.compile(rf"(?i)\b\d{{1,4}}\s?(?:bis|ter)?\s*,?\s+(?:{_VOIES})(?![a-zà-ÿ])[^\n,;()]*")
# Voie sans numéro (« avenue Parmentier ») : nom propre obligatoire juste après ; « place » exclue (« mise en place »).
_VOIE_NOM = re.compile(
    r"\b(?:[Rr]ue|[Aa]venue|[Aa]v\.|[Bb]oulevard|[Bb]d|[Aa]ll[ée]e|[Ii]mpasse|[Qq]uai|[Cc]hemin|[Cc]ours|[Rr]oute)"
    r"\s+(?:(?:de\s+la|de\s+l['’]|du|des|de|d['’])\s*)?[A-ZÀ-Ý][\w'’\-]+(?:[ \t]+(?:de\s+|du\s+|des\s+)?[A-ZÀ-Ý][\w'’\-]+)*")
_ADRESSE_ZONE = re.compile(
    r"\b(?:Z\.?\s?A\.?\s?C?\.?|Z\.?\s?I\.?|C\.?\s?C\.?|C\.\s?[Cc]ial\.?|[Zz]one (?:[Ii]ndustrielle|[Aa]rtisanale|"
    r"[Cc]ommerciale|d.[Aa]ctivit[ée]s?))\s+[A-ZÀ-Ý][^\n,;()\-–]*"
    r"|(?i:\bcentre\s+commercial)\b[^\n,;()]*"
    r"|(?:(?:[A-ZÀ-Ý]|d['’][A-ZÀ-Ý])[\w'’\-]*[ \t]+){1,4}(?i:shopping\s+cent(?:re|er)|centre\s+commercial)\b")
_UNITES = {"btu", "kw", "kva", "kwh", "watt", "watts", "volt", "volts", "lumen", "lumens", "lux", "tr", "mm", "cm"}
_CP_VILLE = re.compile(
    r"\b(?:F-)?((?:0[1-9]|[1-8]\d|9[0-5]|97)\d{3})\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+(?:[ \-]+(?:(?:sur|sous|en|l[eè]s|le|la|de|du|des|d'|l'|SUR|SOUS|EN|LES|LE|LA|DE|DU|DES)[ \-]+)?[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]*)*(?:\s+CEDEX(?:\s+\d+)?)?)")
_BP = re.compile(r"\b(?:BP|CS|TSA)\s?\d{2,6}\b")

_CHAMPS = [
    (r"client(?: final)?|enseigne|magasin|boutique", "client"),
    (r"nom du site|site(?: d.intervention)?|chantier|lieu d.intervention|lieu", "site"),
    (r"adresse(?: du site| du chantier| d.intervention| de facturation| de livraison)?", "adresse"),
    (r"interlocuteur|contact(?: sur site)?|personne [àa] contacter(?: sur site)?|demandeur|responsable(?: du site| magasin)?|"
     r"g[ée]rant|[àa] l.attention de|technicien|nom|pr[ée]nom", "personne"),
    (r"donneur d.ordre|soci[ée]t[ée]|raison sociale|prestataire|destinataire|entreprise", "donneur_ordre"),
]
_CHAMP = re.compile(
    r"(?im)^[ \t•\-–*]*(" + "|".join(f"(?:{m})" for m, _ in _CHAMPS) + r")\s*:\s*([^\n\r]+)")
_POLITESSE = re.compile(
    r"(?im)^[ \t]*(?:bien |tr[èe]s )?(?:cordialement|bien [àa] vous|salutations(?: distingu[ée]es)?|"
    r"sinc[èe]res salutations|bonne (?:journ[ée]e|soir[ée]e)|merci d.avance|avec mes remerciements[^\n,]*)[ \t]*[,.]?[ \t]*([^\n\r]*)$")
_POLITESSE_LIGNE = re.compile(
    r"(?i:\b(?:cordialement|bien [àa] vous|salutations(?: distingu[ée]es)?))[ \t]*[,.]?[ \t]+"
    r"([A-ZÀ-Ý][\w'’\-]+(?:[ \t]+[A-ZÀ-Ý][\w'’\-]+)?)")
_AVANT_BOILERPLATE = re.compile(
    r"(?m)^[ \t]*([A-ZÀ-Ý][a-zà-ÿ'’\-]{2,19}(?:[ \t]+[A-ZÀ-Ý][a-zà-ÿ'’\-]{2,19})?)[ \t\r]*\n"
    r"(?=[ \t]*(?i:devis\s+gratuit\s+[àa]\s+(?:adresser|retourner)))")
_REPRESENTE = re.compile(
    r"(?i:\brepr[ée]sent[ée]e?s?\s+par|\bde\s+la\s+part\s+de)\s+((?:[A-ZÀ-Ý][\w'’\-]+[ \t]?){1,3})")
_CIVILITE = re.compile(
    r"\b(?:M\.|Mr\.?|Mme\.?|Mlle\.?|Monsieur|Madame|Mademoiselle|Me|Dr\.?)\s+((?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+\s?){1,3})")
_SALUT = re.compile(r"\b(?:Bonjour|Bonsoir|Salut|Cher|Chère)\s+([A-ZÀ-Ý][a-zà-ÿ'’\-]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+)?)")
_MOT_NOM = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’]+(?:-[A-ZÀ-Ý][A-Za-zÀ-ÿ'’]+)?"
_PRENOM_NOM = re.compile(rf"\b({_MOT_NOM})((?:[ \t]+(?:de |du |le |van |el |ben )?{_MOT_NOM}){{0,2}})")
_SANS_NOM = {"iban", "bic", "siret", "siren", "tva", "naf", "ape", "madame", "monsieur", "merci", "devis", "bonjour", "client", "site", "rue", "avenue", "france",
             "cordialement", "travaux", "date", "le", "la", "les"}

_DEBUT_TRAVAUX = re.compile(
    r"(?i)(travaux suivants\s*:?|description de l.intervention[^:\n]*:|description\s*:|objet de la (?:demande|consultation)|"
    r"p[ée]rim[èe]tre des travaux|description pr[ée]cise des travaux|merci de nous chiffrer)")
_MAJUSCULES = re.compile(
    r"\b[A-ZÀ-Ý][A-ZÀ-Ý0-9&'’.\-]+(?![a-zà-ÿ])(?:[ \t]+[A-ZÀ-Ý0-9][A-ZÀ-Ý0-9&'’.\-/]*(?![a-zà-ÿ]))*")
# Mots des bons de commande souvent écrits avec une majuscule, jamais des noms.
_MOTS_COURANTS = set("""
demande devis dossier code client site date nos references reference rappeler facturation prestataire intervention
travaux suivants suivant retour souhaitee planifiee passage objet description service tribunal tribunaux commerce
personne contacter nature surface type zone zones contraintes acces contact telephone mail adresse identification
informations information demandeur societe responsable projet entreprise signature cachet conditions particulieres
delai validite acompte solde montant total sous designation unite quantite bon commande renovation electricite
peinture plomberie menuiserie maconnerie lot page document tableau main oeuvre deplacement forfait bureaux important
imperatif merci attention toute tout aucune aucun facture factures prestations prestation rubrique gratuit
exclusivement urgent options option hypotheses exclusions elements presentation attendue metres precisions couleurs
teinte essais obligatoire observations selon phasage partielle appartement estimee generale technique techniques
devise contrat article articles taux applicable modalite paiement seuil rappel tarifs grille formule prete envoyer
document demonstration fictives valeur contractuelle accord entreprise portable fixe fax bonjour madame monsieur
la le les de des du et en sur pour par au aux un une ou
""".split())
_SIGLES_TECHNIQUES = {"led", "pvc", "wc", "vmc", "cvc", "ba13", "inox", "cuivre", "per", "multicouche", "rj45",
                      "ip44", "ip65", "epi", "bi", "pmr", "nf", "ce", "erp", "ssi", "baes", "baeh", "cta", "pac", "ecs", "tgbt", "tableau"}
_ORPHELIN_ADRESSE = re.compile(
    r"(?<![\w\]])(?:(?:0[1-9]|[1-8]\d|9[0-5]|97)\d{3}|\d{1,4}\s?(?:bis|ter)?\s*,)(?=[ \t]*\[(?:adresse|nom|client|site)_\d+\])")
_MAJ_AUTORISEES = {"FRANCE", "TVA", "SIRET", "SIREN", "IBAN", "BIC", "NAF", "APE", "SARL", "SAS", "SASU", "EURL",
                   "SA", "HT", "TTC", "DI", "CGI", "EUR", "N°", "DEVIS", "GRATUIT", "CLIENT", "SITE", "TEL", "TÉL",
                   "E-MAIL", "EMAIL", "FAX", "OT", "BC", "SVP", "PDF", "URGENT", "EXCLUSIVEMENT", "NB", "RAS"}


def _flexible(valeur: str) -> re.Pattern | None:
    """Motif d'une valeur connue, sur le texte APLATI (sans accents, minuscules)."""
    mots = re.findall(r"[0-9a-z]+", _aplatir(valeur))
    if not mots or sum(len(m) for m in mots) < 3:
        return None
    return re.compile(r"(?<![0-9a-z])" + r"[\W_]{0,3}".join(re.escape(m) for m in mots) + r"(?![0-9a-z])")


def _masquer_connus(ms: _Masqueur, texte: str, valeurs: Iterable[tuple]) -> str:
    uniques = {}
    for cat, v in valeurs:
        v = (v or "").strip()
        if len(v) >= 3 and not _MARQUEUR.fullmatch(v):
            uniques.setdefault(_aplatir(v), (cat, v))
    for _, (cat, v) in sorted(uniques.items(), key=lambda kv: -len(kv[0])):
        motif = _flexible(v)
        if motif is None:
            continue
        plat = _aplatir(texte)
        morceaux, pos = [], 0
        for mt in motif.finditer(plat):
            morceaux.append(texte[pos:mt.start()])
            morceaux.append(ms.marqueur(cat, v))
            pos = mt.end()
        if morceaux:
            morceaux.append(texte[pos:])
            texte = "".join(morceaux)
    return texte


def _est_prenom(mot: str) -> bool:
    premier = _aplatir(mot.split("-")[0])
    return premier in prenoms() and premier not in _SANS_NOM


def _connus(entites: Entites | None) -> List[tuple]:
    if not entites:
        return []
    valeurs = [("site", s) for s in entites.sites] + [("donneur_ordre", s) for s in entites.donneurs_ordre]
    valeurs += [("client", s) for s in entites.clients] + [("personne", s) for s in entites.personnes]
    valeurs += [("identifiant", s) for s in entites.identifiants]
    for a in entites.adresses:
        valeurs.append(("adresse", a))
        valeurs += [("adresse", p) for p in re.split(r"[,\n]", a or "") if len(p.strip()) >= 6]
    for p in entites.personnes:   # « M. Martinot » : le nom seul aussi
        valeurs += [("personne", n) for n in re.findall(r"[A-Za-zÀ-ÿ'’\-]{4,}", p or "") if not _est_prenom(n)]
    return valeurs


def masquer(texte: str | None, entites: Entites | None = None) -> Resultat:
    """Remplace les informations personnelles par des marqueurs réversibles."""
    t = (texte or "")[:MAX_TEXTE]
    if not t.strip():
        return Resultat(t, {})
    ms = _Masqueur()
    connus = _connus(entites)

    # 1. Identifiants techniques.
    t = ms.remplacer(t, _EMAIL, "email")
    t = ms.remplacer(t, _URL, "web")
    t = ms.remplacer(t, _IBAN, "iban")
    t = ms.remplacer(t, _BIC, "bic", groupe=1)
    t = ms.remplacer(t, _TVA, "tva")
    t = ms.remplacer(t, _TEL, "tel")
    t = ms.remplacer(t, _TEL_TRONQUE, "tel")
    t = ms.remplacer(t, _SIRET, "siret")
    t = ms.remplacer(t, _NUMERO, "numero", groupe=1, garde=lambda m: sum(c.isdigit() for c in m.group(1)) >= 4)
    t = ms.remplacer(t, _CHIFFRES_LONGS, "numero")

    # 2. Adresses (avant les noms connus : « 406, avenue X » reste d'un seul tenant).
    t = ms.remplacer(t, _ADRESSE_VOIE, "adresse")
    t = ms.remplacer(t, _VOIE_NOM, "adresse")
    t = ms.remplacer(t, _ADRESSE_ZONE, "adresse")
    t = ms.remplacer(t, _CP_VILLE, "adresse", garde=lambda m: _aplatir(m.group(2).split()[0]) not in _UNITES)
    t = ms.remplacer(t, _BP, "adresse")

    # 3. Champs nommés : la valeur est masquée ici ET partout ailleurs dans le texte.
    lus = []
    for mt in _CHAMP.finditer(t):
        etiquette = mt.group(1).lower()
        cat = next(c for motif, c in _CHAMPS if re.fullmatch(motif, etiquette, re.I))
        # La valeur s'arrête à la fin de la phrase (« Site : X. Devis à Y »).
        valeur = re.split(r"\.\s|\s[-–]\s|;|\s{3,}|\t", mt.group(2))[0].strip(" .")
        if valeur and not _MARQUEUR.fullmatch(valeur) and re.search(r"[A-Za-zÀ-ÿ]{2}", valeur):
            lus.append((cat, valeur))
    # 4. Noms connus du SaaS et noms lus dans les champs, du plus long au plus court.
    t = _masquer_connus(ms, t, connus + lus)

    # 5. Raisons sociales, enseignes et codes magasin en majuscules : en-tête du bon
    #    de commande et lignes administratives (coordonnées, « à adresser à … »),
    #    puis chaque nom trouvé est masqué partout ailleurs.
    t, noms = _masquer_majuscules(ms, t)
    t = _masquer_connus(ms, t, [("nom", n) for n in noms])

    # 6. Personnes : signature, civilité, salutation, prénom + nom.
    t = _masquer_signature(ms, t)
    t = ms.remplacer(t, _POLITESSE_LIGNE, "personne", groupe=1)
    t = ms.remplacer(t, _AVANT_BOILERPLATE, "personne", groupe=1)
    t = ms.remplacer(t, _REPRESENTE, "personne", groupe=1)
    t = ms.remplacer(t, _CIVILITE, "personne", groupe=1)
    t = ms.remplacer(t, _SALUT, "personne", groupe=1, garde=lambda m: _aplatir(m.group(1).split()[0]) not in _SANS_NOM)
    t = ms.remplacer(t, _PRENOM_NOM, "personne", garde=lambda m: _est_prenom(m.group(1)))

    # 7. Restes collés à une adresse masquée : « 75002 [adresse_2] », « 406, [adresse_1] ».
    t = ms.remplacer(t, _ORPHELIN_ADRESSE, "adresse")
    return Resultat(t, ms.correspondances)


def _masquer_signature(ms: _Masqueur, t: str) -> str:
    lignes = t.split("\n")
    i = 0
    while i < len(lignes):
        mt = _POLITESSE.match(lignes[i])
        if mt:
            reste = mt.group(1).strip()
            if reste and not _MARQUEUR.fullmatch(reste) and len(reste) <= 60:
                lignes[i] = lignes[i][:mt.start(1)] + ms.marqueur("personne", reste)
            vues, j = 0, i + 1
            while j < len(lignes) and vues < 3:
                ligne = lignes[j].strip()
                if ligne:
                    vues += 1
                    if len(ligne) <= 50 and ":" not in ligne and not _MARQUEUR.fullmatch(ligne):
                        nu = _MARQUEUR.sub("", ligne).strip(" \r\t-–,/")
                        if nu:
                            lignes[j] = lignes[j].replace(nu, ms.marqueur("personne", nu), 1)
                j += 1
        i += 1
    return "\n".join(lignes)


_LIGNE_ADMIN = re.compile(r"(?i)\[(?:tel|email|web|iban|bic|tva|siret|adresse|client|site|nom|donneur_ordre)_\d+\]|"
                         r"\b(?:adresser|retourner|envoyer)\b[^\n]*\b[àa]\b")
_COORDONNEES = re.compile(r"\[(?:tel|email|web|siret|tva|iban|adresse)_\d+\]")
# Deux mots capitalisés ou plus (« Westfield Forum des Halles », « Atelier Technique Vornier »).
_NOM_PROPRE = re.compile(
    r"\b[A-ZÀ-Ý][\w'’\-]*(?:[ \t]+(?:(?:de|des|du|la|le|les|et|&|sur|en)[ \t]+|d['’]|l['’])?(?:\d+[ \t]+)?[A-ZÀ-Ý][\w'’\-]*)+")


def _hors_nom(bloc: str) -> bool:
    """Vrai si le bloc n'est fait que de mots autorisés, de sigles techniques ou de mesures."""
    mots = [m.strip(".:,;()") for m in re.split(r"[ \t]+", bloc) if m.strip(".:,;()")]
    return all(m.upper() in _MAJ_AUTORISEES or _aplatir(m) in _SIGLES_TECHNIQUES or any(c.isdigit() for c in m)
               or _aplatir(m) in _SANS_NOM or _aplatir(m) in _MOTS_COURANTS or len(m) <= 2
               for p in mots for m in re.split(r"[-/’']", p) if m)


def _masquer_majuscules(ms: _Masqueur, t: str) -> tuple:
    debut = _DEBUT_TRAVAUX.search(t)
    fin_entete = debut.start() if debut else 0
    noms: List[str] = []

    def _sub(mt: re.Match) -> str:
        bloc = mt.group(0).strip(" .-–,")
        if not re.search(r"[A-ZÀ-Ý]{2}|[a-zà-ÿ]", bloc) or _hors_nom(bloc):
            return mt.group(0)
        noms.append(bloc)
        return mt.group(0).replace(bloc, ms.marqueur("nom", bloc), 1)

    lignes = t.splitlines(keepends=True)
    contact = {i + d for i, l in enumerate(lignes) if _COORDONNEES.search(l) for d in (-2, -1, 0, 1)}
    sortie, pos = [], 0
    for i, ligne in enumerate(lignes):
        admin = pos < fin_entete or i in contact or _LIGNE_ADMIN.search(ligne)
        if admin:
            ligne = _MAJUSCULES.sub(_sub, ligne)
            ligne = _NOM_PROPRE.sub(_sub, ligne)
        sortie.append(ligne)
        pos += len(lignes[i])
    return "".join(sortie), noms


def restaurer(texte: str | None, correspondances: Dict[str, str]) -> str:
    """Remet les vraies valeurs dans la réponse du modèle (sur le serveur)."""
    if not texte or not correspondances:
        return texte or ""
    return _MARQUEUR.sub(lambda m: correspondances.get(m.group(0), m.group(0)), texte)


def verifier_avant_envoi(texte: str | None, entites: Entites | None = None) -> None:
    """Refuse l'envoi si un détecteur trouve encore quelque chose (FuitePossible).

    Le message d'erreur cite les catégories, jamais les valeurs."""
    reste = masquer(texte, entites)
    if reste.correspondances:
        raise FuitePossible("Masquage incomplet, envoi externe refusé : " +
                            ", ".join(f"{c} ({n})" for c, n in sorted(reste.categories().items())))
