"""Import de catalogues fournisseurs : CSV et Excel, plusieurs fichiers.

TROIS DIFFERENCES ASSUMEES AVEC L'IMPORT DE L'ONGLET CATALOGUE
--------------------------------------------------------------

1. PLUSIEURS CATALOGUES ACTIFS EN MEME TEMPS
   L'import de catalogue appelle _deactivate_other_catalogs() : un seul
   catalogue de prix peut etre actif, parce qu'un devis se chiffre sur
   UN bareme. C'est juste pour ce cas.

   Pour les fournisseurs, c'est l'inverse du besoin. Un chiffreur
   compare Rexel, Prolians, Point.P, La Plateforme et SFIC
   SIMULTANEMENT. Chaque fournisseur a donc son propre catalogue, tous
   restent actifs, et la recherche les lit ensemble -- ce qui reproduit
   exactement le resultat d'un catalogue consolide, sans imposer de
   fusionner les fichiers a la main.

   Consequence pratique : on peut remplacer le tarif Rexel sans toucher
   aux quatre autres. Avec un fichier consolide unique, la moindre mise
   a jour obligeait a tout reconstruire.

2. EXCEL EN PLUS DU CSV
   _read_csv_robust() ne lit que du CSV (pd.read_csv). Or les tarifs
   fournisseurs arrivent le plus souvent en .xlsx, parfois avec
   plusieurs onglets. openpyxl est donc utilise en mode read_only, qui
   parcourt le fichier en flux au lieu de le charger entierement.

3. INSERTION PAR LOTS
   Un tarif fournisseur compte des dizaines a des centaines de milliers
   de lignes -- 747 771 pour le seul Rexel. Une insertion unique
   saturerait la memoire du service (palier gratuit Render : 512 Mo).
   Les lignes partent donc par paquets de TAILLE_LOT.
"""
from __future__ import annotations

import io
import re
import unicodedata


# ===========================================================================
# Champs standards d'un tarif fournisseur
# ===========================================================================
# Les synonymes couvrent les en-tetes reellement rencontres dans les
# exports des cinq fournisseurs du catalogue consolide, plus les
# variantes courantes. Un synonyme qui ne correspond a rien n'ajoute
# aucun risque ; un synonyme manquant oblige l'utilisateur a associer la
# colonne a la main.
CHAMPS_FOURNISSEUR = [
    {"cle": "designation", "libelle": "Désignation / Libellé", "requis": True,
     "numerique": False,
     "syn": ["designation", "libelle", "libelle produit", "description",
             "denomination", "article", "produit", "nom", "intitule",
             "designation produit", "designation article"]},
    {"cle": "fournisseur", "libelle": "Fournisseur", "requis": False,
     "numerique": False,
     "syn": ["fournisseur", "enseigne", "distributeur", "vendeur",
             "supplier", "negoce"]},
    {"cle": "prix_net_ht", "libelle": "Prix net HT", "requis": False,
     "numerique": True,
     "syn": ["prix net ht", "prix net", "prix client", "prix achat ht",
             "prix achat", "pa ht", "net ht", "tarif net", "prix remise",
             "prix negocie", "prix ht"]},
    {"cle": "prix_public_ht", "libelle": "Prix public HT", "requis": False,
     "numerique": True,
     "syn": ["prix public ht", "prix public", "prix tarif", "tarif public",
             "prix catalogue", "pvp", "prix brut", "prix liste"]},
    {"cle": "reference_fournisseur", "libelle": "Référence fournisseur",
     "requis": False, "numerique": False,
     "syn": ["reference fournisseur", "ref fournisseur", "code article",
             "code produit", "reference", "ref", "code", "sku",
             "reference interne", "ref interne"]},
    {"cle": "reference_fabricant", "libelle": "Référence fabricant",
     "requis": False, "numerique": False,
     "syn": ["reference fabricant", "ref fabricant", "reference constructeur",
             "ref constructeur", "code fabricant", "mpn",
             "reference fournisseur fabricant"]},
    {"cle": "code_ean", "libelle": "Code EAN", "requis": False,
     "numerique": False,
     "syn": ["code ean", "ean", "ean13", "gencod", "gencode", "gtin",
             "code barre", "code barres"]},
    {"cle": "marque", "libelle": "Marque", "requis": False,
     "numerique": False,
     "syn": ["marque", "fabricant", "brand", "constructeur"]},
    {"cle": "famille", "libelle": "Famille", "requis": False,
     "numerique": False,
     "syn": ["famille", "categorie", "rubrique", "univers", "lot",
             "famille produit"]},
    {"cle": "sous_famille", "libelle": "Sous-famille", "requis": False,
     "numerique": False,
     "syn": ["sous famille", "sous categorie", "sous rubrique",
             "sous famille produit"]},
    {"cle": "unite_vente", "libelle": "Unité de vente", "requis": False,
     "numerique": False,
     "syn": ["unite de vente", "unite vente", "unite", "uv", "conditionnement",
             "unit", "cond"]},
    {"cle": "remise", "libelle": "Remise (%)", "requis": False,
     "numerique": True,
     "syn": ["remise", "remise pct", "remise %", "taux remise", "discount"]},
    {"cle": "eco_contribution", "libelle": "Éco-contribution HT",
     "requis": False, "numerique": True,
     "syn": ["eco contribution ht", "eco contribution", "ecoparticipation",
             "eco participation", "deee", "ecotaxe"]},
    {"cle": "quantite_conditionnement", "libelle": "Quantité par conditionnement",
     "requis": False, "numerique": True,
     # "qte conditionnement" manquait : mesure sur le catalogue reel
     # La Plateforme, la colonne "Qte conditionnement" n'etait pas
     # reconnue. Sans elle, une boite de 100 vis est comparee a la vis
     # a l'unite -- le prix au conditionnement passe pour un prix
     # unitaire.
     "syn": ["quantite par conditionnement", "quantite conditionnement",
             "qte conditionnement", "qte de conditionnement", "qte cond",
             "colisage", "pcb", "quantite colis", "par lot",
             "nombre par conditionnement"]},
    {"cle": "quantite_min", "libelle": "Quantité minimum", "requis": False,
     "numerique": True,
     "syn": ["quantite minimum", "qte min", "minimum commande", "mini",
             "quantite mini"]},
    {"cle": "delai", "libelle": "Délai", "requis": False, "numerique": False,
     # "stock" et "disponibilite" retires : ce sont des etats de
     # DISPONIBILITE, pas des delais. La table a une colonne
     # availability dediee. Sur le catalogue La Plateforme, la colonne
     # "Stock depot" etait rangee dans le delai -- une information de
     # stock affichee comme un delai de livraison.
     "syn": ["delai", "delai livraison", "delai approvisionnement",
             "lead time"]},
    {"cle": "disponibilite", "libelle": "Disponibilité / stock", "requis": False,
     "syn": ["disponibilite", "dispo", "stock", "stock depot",
             "stock agence", "stock livraison", "en stock",
             "etat du stock"]},
    {"cle": "url_produit", "libelle": "Lien fiche produit", "requis": False,
     "numerique": False,
     "syn": ["lien fiche produit", "fiche produit", "url", "lien", "url produit",
             "page produit"]},
    {"cle": "date_prix", "libelle": "Date du prix", "requis": False,
     "numerique": False,
     "syn": ["date du prix", "date prix", "date tarif", "date maj",
             "date mise a jour", "validite"]},
]

TAILLE_LOT = 2000

# Limite propre a l'import fournisseur. MAX_UPLOAD_SIZE vaut 15 Mo, ce
# qui convient a un bareme de devis mais pas a un tarif fournisseur : le
# seul export La Plateforme fait 5,6 Mo en CSV, et un tarif Rexel
# complet depasse largement. Reglable par variable d'environnement pour
# ne pas dependre d'un redeploiement.
import os

MAX_IMPORT_FOURNISSEUR = int(
    os.environ.get("MAX_IMPORT_FOURNISSEUR", str(80 * 1024 * 1024)))


# ===========================================================================
# Lecture des fichiers
# ===========================================================================

def _sans_accents(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", str(texte))
    return "".join(c for c in texte if not unicodedata.combining(c))


def normalise_entete(colonne: str) -> str:
    """Normalise un en-tete pour la comparaison aux synonymes."""
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", _sans_accents(colonne).lower()).split())


def est_excel(nom_fichier: str) -> bool:
    return (nom_fichier or "").lower().endswith((".xlsx", ".xlsm", ".xltx"))


def _entetes_et_donnees(feuille, max_lignes_entete=12):
    """Trouve la ligne d'en-tetes et renvoie (entetes, lignes).

    Les classeurs fournisseurs commencent souvent par un titre, une
    date ou une cellule fusionnee. On cherche donc la premiere ligne
    qui ressemble a un en-tete : au moins trois cellules non vides,
    majoritairement du texte.
    """
    entetes = None
    donnees = []
    for i, brut in enumerate(feuille.iter_rows(values_only=True)):
        if entetes is None:
            if i > max_lignes_entete:
                break
            remplies = [c for c in brut if c not in (None, "")]
            if len(remplies) < 3:
                continue
            textuelles = sum(1 for c in remplies
                             if isinstance(c, str) and not c.strip().isdigit())
            if textuelles < max(2, len(remplies) // 2):
                continue  # ligne de chiffres : des donnees, pas des en-tetes
            entetes = [(str(c).strip() if c is not None else f"colonne_{j+1}")
                       for j, c in enumerate(brut)]
            continue
        donnees.append(["" if c is None else str(c).strip() for c in brut])
    return entetes, donnees


def _score_onglet(entetes) -> int:
    """Nombre de champs standards reconnus dans ces en-tetes.

    C'est le critere de choix de l'onglet. Une premiere version retenait
    le premier onglet comportant au moins deux colonnes et une ligne :
    sur un vrai classeur fournisseur, elle a retenu "Lisez-moi" au lieu
    du tarif. Compter les correspondances avec les champs attendus est
    le seul signal fiable -- un onglet de tarif porte des colonnes
    "Designation", "Prix", "Reference", un onglet de garde n'en a
    aucune.
    """
    if not entetes:
        return 0
    mapping = suggere_mapping(list(entetes))
    return sum(1 for v in mapping.values() if v)


def lit_excel(contenu: bytes, onglet: str | None = None):
    """Lit un classeur Excel en FLUX, sans le charger entierement.

    read_only=True fait parcourir le fichier ligne a ligne plutot que de
    construire tout l'arbre en memoire. Indispensable : un tarif
    fournisseur complet depasse le demi-gigaoctet une fois developpe,
    pour 512 Mo disponibles sur le palier gratuit.

    CHOIX DE L'ONGLET
    -----------------
    Sans onglet impose, on retient celui dont les en-tetes reconnaissent
    le PLUS de champs standards. Les classeurs fournisseurs comportent
    couramment "Lisez-moi", "Synthese" ou "Controles qualite" avant le
    tarif lui-meme : retenir le premier onglet exploitable donnait
    "Lisez-moi", mesure sur un vrai fichier.
    """
    import openpyxl
    import pandas as pd

    classeur = openpyxl.load_workbook(
        io.BytesIO(contenu), read_only=True, data_only=True)
    try:
        noms = classeur.sheetnames

        if onglet and onglet in noms:
            entetes, donnees = _entetes_et_donnees(classeur[onglet])
            retenu = onglet
        else:
            meilleur = (0, None, None, None)   # score, nom, entetes, donnees
            for nom in noms:
                entetes, donnees = _entetes_et_donnees(classeur[nom])
                if not entetes or not donnees:
                    continue
                score = _score_onglet(entetes)
                # A score egal, on prefere l'onglet le plus fourni : un
                # onglet de synthese reconnait parfois autant de champs
                # que le tarif, avec dix fois moins de lignes.
                if (score, len(donnees)) > (meilleur[0], len(meilleur[3] or [])):
                    meilleur = (score, nom, entetes, donnees)
            score, retenu, entetes, donnees = meilleur
            if not retenu or score < 2:
                raise ValueError(
                    "Aucun onglet ne ressemble à un tarif : il faut au "
                    "moins une colonne de désignation et une colonne de "
                    f"prix ou de référence. Onglets examinés : "
                    f"{', '.join(noms[:8])}.")

        if not entetes or not donnees:
            raise ValueError(
                f"L'onglet « {retenu} » ne contient pas de tableau "
                f"exploitable (en-têtes + données).")

        largeur = len(entetes)
        normalisees = [(l + [""] * largeur)[:largeur] for l in donnees]
        return pd.DataFrame(normalisees, columns=entetes), retenu, noms
    finally:
        classeur.close()


def lit_csv(contenu: bytes):
    """Lit un CSV quel que soit son separateur et son encodage.

    Meme logique que _read_csv_robust de server.py, reprise ici pour que
    le module reste autonome -- les tarifs fournisseurs francais sont
    souvent en point-virgule et latin-1.
    """
    import pandas as pd

    essais = ({"sep": None, "engine": "python"}, {"sep": ";"},
              {"sep": ","}, {"sep": "\t"}, {"sep": "|"})
    for kwargs in essais:
        for encodage in ("utf-8-sig", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(io.BytesIO(contenu), dtype=str,
                                 keep_default_na=False, encoding=encodage,
                                 **kwargs)
                if len(df.columns) >= 2:
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
            except Exception:
                continue
    raise ValueError(
        "Impossible de lire ce CSV : séparateur ou encodage non reconnu. "
        "Séparateurs testés : automatique, point-virgule, virgule, "
        "tabulation, barre verticale.")


def lit_tableur(contenu: bytes, nom_fichier: str, onglet: str | None = None):
    """Point d'entree unique : CSV ou Excel.

    Rend (DataFrame, onglet_retenu, onglets_disponibles). Les deux
    derniers sont None pour un CSV.
    """
    if len(contenu) > MAX_IMPORT_FOURNISSEUR:
        raise ValueError(
            f"Fichier trop volumineux : "
            f"{len(contenu) / (1024*1024):.0f} Mo pour un maximum de "
            f"{MAX_IMPORT_FOURNISSEUR // (1024*1024)} Mo. Découpez le tarif "
            f"par famille, ou augmentez MAX_IMPORT_FOURNISSEUR.")
    if est_excel(nom_fichier):
        return lit_excel(contenu, onglet)
    df = lit_csv(contenu)
    return df, None, None


# ===========================================================================
# Association automatique des colonnes
# ===========================================================================

def _score_paire(entete_normalise: str, synonyme: str) -> int:
    """Qualite de correspondance entre un en-tete et un synonyme.

    Un synonyme LONG qui correspond est plus informatif qu'un synonyme
    court : "ref fournisseur" identifie la colonne mieux que "code". Le
    score integre donc la specificite du synonyme.

    Et un synonyme place en TETE de l'en-tete l'emporte sur le meme
    synonyme place en fin : dans un en-tete francais, le premier mot est
    le nom principal. "Fournisseur retenu" designe bien un fournisseur ;
    "Designation fournisseur" designe une designation.
    """
    jetons_syn = synonyme.split()
    jetons_col = entete_normalise.split()
    specificite = 10 * len(jetons_syn)

    if entete_normalise == synonyme:
        return 100 + specificite
    if entete_normalise.startswith(synonyme + " "):
        return 60 + specificite - (len(jetons_col) - len(jetons_syn))
    if set(jetons_syn).issubset(set(jetons_col)):
        return 40 + specificite - (len(jetons_col) - len(jetons_syn))
    return 0


def suggere_mapping(colonnes: list[str]) -> dict:
    """Associe chaque champ standard a une colonne du fichier.

    AFFECTATION GLOBALE, PAS CHAMP PAR CHAMP
    ----------------------------------------
    Une premiere version parcourait les champs dans l'ordre et prenait
    la PREMIERE colonne correspondante. Mesure sur un vrai classeur
    fournisseur a 22 colonnes, elle produisait deux erreurs :

      "Fournisseur"           -> "Designation fournisseur"  (au lieu de
                                                             "Fournisseur retenu")
      "Reference fournisseur" -> "Code"                      (au lieu de
                                                             "Ref. fournisseur")

    Dans les deux cas la bonne colonne existait, mais arrivait plus loin
    dans le fichier. Un mauvais prix ou un mauvais fournisseur associe
    fausse toute la comparaison, donc l'ordre des colonnes ne doit
    jouer aucun role.

    On calcule donc TOUTES les paires (champ, colonne), on les trie par
    qualite decroissante, et on affecte gloutonnement. Un champ ou une
    colonne deja pris est ignore.
    """
    normalisees = {col: normalise_entete(col) for col in colonnes}

    paires = []
    for champ in CHAMPS_FOURNISSEUR:
        for col in colonnes:
            meilleur = max(
                (_score_paire(normalisees[col], syn) for syn in champ["syn"]),
                default=0)
            if meilleur > 0:
                paires.append((meilleur, champ["cle"], col))

    # Tri par score decroissant. A score egal, l'ordre des colonnes
    # tranche -- il faut un resultat deterministe.
    paires.sort(key=lambda p: (-p[0], colonnes.index(p[2])))

    mapping: dict[str, str | None] = {c["cle"]: None
                                      for c in CHAMPS_FOURNISSEUR}
    champs_pris: set[str] = set()
    colonnes_prises: set[str] = set()
    for score, cle, col in paires:
        if cle in champs_pris or col in colonnes_prises:
            continue
        mapping[cle] = col
        champs_pris.add(cle)
        colonnes_prises.add(col)

    return mapping


def devine_fournisseur(df, mapping: dict, nom_fichier: str) -> str:
    """Deduit le nom du fournisseur, sans jamais l'inventer.

    Trois sources, par ordre de fiabilite :
      1. une colonne "Fournisseur" dans le fichier, si elle ne contient
         qu'une seule valeur -- cas d'un export propre a un fournisseur ;
      2. le nom du fichier, debarrasse de son extension, des dates et
         des mots de remplissage ;
      3. rien : l'utilisateur devra le saisir. On ne devine pas au
         hasard, un mauvais nom de fournisseur faussant toute la
         comparaison.
    """
    colonne = mapping.get("fournisseur")
    if colonne and colonne in df.columns:
        valeurs = {str(v).strip() for v in df[colonne].dropna()
                   if str(v).strip()}
        if len(valeurs) == 1:
            return valeurs.pop()

    base = re.sub(r"\.(csv|xlsx|xlsm|xltx|txt)$", "", nom_fichier or "",
                  flags=re.I)
    base = re.sub(r"[_\-]+", " ", base)
    # Retire les mots de remplissage ET toutes les formes de date. Un
    # "09-2026" restant donnait "Point.P 09" comme nom de fournisseur :
    # deux exports du meme fournisseur a deux mois d'intervalle auraient
    # cree deux fournisseurs distincts, et la comparaison se serait faite
    # entre eux plutot qu'entre enseignes.
    base = re.sub(r"\b(tarif|tarifs|catalogue|catalog|prix|export|liste|"
                  r"extraction|maj|mise a jour|v\d+|rev\d*)\b", " ", base,
                  flags=re.I)
    # ORDRE IMPORTANT : du motif le plus long au plus court. Sinon
    # "09/2026" est consomme d'abord dans "15/03/2026" et il reste
    # "15/" collé au nom -- observe sur "prolians liste 15/03/2026.csv".
    base = re.sub(r"\b\d{1,2}[-/_ ]\d{1,2}[-/_ ]\d{2,4}\b", " ", base)
    base = re.sub(r"\b\d{1,2}[-/_ ]\d{4}\b", " ", base)   # 09-2026
    base = re.sub(r"\b\d{4}[-/_ ]\d{1,2}\b", " ", base)   # 2026-09
    base = re.sub(r"\b(19|20)\d{2}\b", " ", base)          # annee seule
    base = " ".join(base.split())
    # Un nombre isole en fin de nom n'est jamais un nom d'enseigne.
    base = re.sub(r"[\s\-_/.]*\b\d{1,4}\b[\s\-_/.]*$", "", base).strip()
    base = base.strip(" -_/.")
    return base[:120]


def valeur(ligne, mapping: dict, cle: str) -> str:
    colonne = mapping.get(cle)
    if not colonne:
        return ""
    brut = ligne.get(colonne)
    return "" if brut is None else str(brut).strip()


def nombre(texte: str, defaut=None):
    """Convertit un nombre ecrit a la francaise.

    "1 234,56" et "1.234,56" doivent donner 1234.56. Le separateur de
    milliers varie d'un fournisseur a l'autre, et une virgule prise pour
    un separateur de milliers transformerait 2,5 en 25 -- une erreur de
    prix d'un facteur dix.
    """
    if texte is None:
        return defaut
    t = str(texte).strip()
    if not t:
        return defaut
    t = t.replace("\u202f", "").replace("\u00a0", "").replace(" ", "")
    t = re.sub(r"[^\d,.\-]", "", t)
    if not t:
        return defaut
    if "," in t and "." in t:
        # Le dernier separateur rencontre est le separateur decimal.
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return defaut
