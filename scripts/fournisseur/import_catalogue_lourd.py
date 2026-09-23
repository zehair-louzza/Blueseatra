#!/usr/bin/env python3
"""Import securise d'un catalogue fournisseurs volumineux (CSV / XLSX).

POURQUOI CE SCRIPT EXISTE
-------------------------
Le site accepte 15 Mo par fichier et lit tout en memoire. Le catalogue
consolide fait ~944 000 lignes (144 Mo en XLSX) : ni le service Render
gratuit (512 Mo, 0,15 CPU) ni l'endpoint d'upload ne peuvent le traiter.
Ce script tourne sur le poste de l'administrateur, lit le fichier en
FLUX (jamais charge entier en memoire) et ecrit par lots dans Supabase.

GARANTIES
---------
1. Rien n'est visible pour les chiffreurs avant `activer`. Chaque import
   cree une NOUVELLE version de catalogue par fournisseur ; la recherche
   ne lit que la version active (catalogs.active_version_id). Un import
   interrompu ne pollue donc jamais les resultats.
2. L'activation est une seule transaction : tous les fournisseurs du
   fichier basculent ensemble, ou aucun.
3. Retour arriere en une commande (`annuler`) : l'ancienne version est
   conservee, on repointe simplement le catalogue dessus.
4. Reprise apres coupure : les identifiants d'offres sont deterministes
   (empreinte du fichier + numero de ligne). Relancer `importer` reprend
   apres la derniere ligne validee.
5. Cloisonnement : les ecritures passent sous le role blueseatra_app
   (NOBYPASSRLS) avec app.tenant_id pose -> RLS refuse toute ligne d'un
   autre tenant, meme en cas de bogue du script.
6. Aucun secret en argument : l'URL de connexion est lue dans la variable
   d'environnement BLUESEATRA_IMPORT_DATABASE_URL, TLS impose hors local.

COMMANDES
---------
  analyser  fichier                       -> validation de 100 % des lignes (rapport JSON
                                             + anomalies.csv), AUCUNE connexion base
  importer  fichier --tenant ID           -> ecrit une version NON active
  statut    --import-id ID --tenant ID
  activer   --import-id ID --tenant ID    -> bascule atomique
  annuler   --import-id ID --tenant ID    -> revient aux versions precedentes
  purger    --import-id ID --tenant ID --confirmer
                                          -> supprime les lignes d'un import
                                             NON actif (echec ou annule)

Dependances poste admin : pip install openpyxl psycopg2-binary
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Limites de securite
# ---------------------------------------------------------------------------
TAILLE_MAX_FICHIER = 2 * 1024 ** 3          # 2 Go (plafond epic #87)
XLSX_MAX_DECOMPRESSE = 6 * 1024 ** 3        # garde-fou zip bomb
XLSX_RATIO_MAX = 150                         # ratio decompresse/compresse par entree
XLSX_MAX_ENTREES = 5000
LIGNES_MAX = 3_000_000
LIGNES_ENTETE_MAX = 30                       # l'entete est cherchee dans les 30 premieres lignes
TAILLE_LOT = 5000
OCTETS_PAR_LIGNE_ESTIMES = 1250              # mesure reelle : 60 Mo / 49 200 offres
PLAFOND_BASE_GO = 7.0                        # plan Pro : 8 Go de disque inclus
BAISSE_MAX_SANS_FORCER = 0.5                 # refuse d'activer si -50 % de lignes

VARCHAR = {"raw_reference": 160, "raw_unit": 60, "brand": 120,
           "manufacturer_ref": 120, "ean": 20}
LIBELLE_MAX = 2000

# ---------------------------------------------------------------------------
# Detection des colonnes
# ---------------------------------------------------------------------------
SYNONYMES: dict[str, list[str]] = {
    "fournisseur": ["fournisseur", "enseigne", "distributeur", "supplier", "nom fournisseur"],
    "famille": ["famille", "categorie", "rayon"],
    "sous_famille": ["sous famille", "sous categorie"],
    "designation": ["designation", "libelle", "description", "libelle article",
                    "designation article", "produit", "nom produit"],
    "marque": ["marque", "fabricant", "brand", "marque fabricant"],
    "ref_fournisseur": ["reference fournisseur", "ref fournisseur", "code article",
                        "reference", "ref", "sku", "code produit", "ref article"],
    "ref_fabricant": ["reference fabricant", "ref fabricant", "ref constructeur",
                      "reference constructeur", "ref fab"],
    "ean": ["code ean", "ean", "ean13", "gtin", "code barre", "gencod"],
    "prix_net": ["prix net ht", "prix net", "prix ht", "prix", "tarif net",
                 "prix remise", "prix achat ht", "prix unitaire ht", "net ht"],
    "prix_public": ["prix public ht", "prix public", "ppht", "prix catalogue", "prix brut"],
    "unite": ["unite de vente", "unite", "uv", "unite vente"],
    "url": ["url", "lien", "url produit", "lien produit"],
    "date_prix": ["date prix", "date tarif", "date de prix", "date"],
    "conditionnement": ["conditionnement", "qte conditionnement", "colisage",
                        "quantite par conditionnement"],
}
OBLIGATOIRES = ("designation",)


def sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c))


def norme_entete(s) -> str:
    s = sans_accents(s if s is not None else "").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


_SYN_NORM = {champ: [norme_entete(x) for x in lst] for champ, lst in SYNONYMES.items()}


def detecte_colonnes(entete: list) -> dict[str, int]:
    """Associe chaque champ connu a l'indice de sa colonne.

    Correspondance EXACTE sur l'entete normalisee, jamais par inclusion :
    'prix' ne doit pas capturer 'prix public ht'. Premier champ servi,
    premiere colonne retenue.
    """
    mapping: dict[str, int] = {}
    prises: set[int] = set()
    normes = [norme_entete(h) for h in entete]
    for champ, syns in _SYN_NORM.items():
        for syn in syns:  # ordre = priorite
            for i, h in enumerate(normes):
                if i in prises or not h:
                    continue
                if h == syn:
                    mapping[champ] = i
                    prises.add(i)
                    break
            if champ in mapping:
                break
    return mapping


def normalize_label(s: str) -> str:
    """Meme convention que backend/matching.normalize."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def slug(s: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", " ", sans_accents(s or "").lower()).split())


# ---------------------------------------------------------------------------
# Nettoyage des valeurs
# ---------------------------------------------------------------------------
def texte(v) -> str | None:
    """Valeur de cellule -> texte. Les flottants entiers d'Excel (100021.0,
    3.25e12) redeviennent des entiers : une reference ou un EAN n'a pas de
    decimales."""
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        if v.is_integer():
            return str(int(v))
        return repr(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    s = str(v).strip()
    return s or None


_RE_PRIX = re.compile(r"[^0-9,.\-]")


def prix(v) -> float | None:
    """'1 234,56 EUR', '1.234,56', '12.5', 12.5 -> float. <= 0 -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        s = _RE_PRIX.sub("", str(v).replace("\u00a0", ""))
        if not s or s in "-.,":
            return None
        if "," in s and "." in s:
            # le dernier separateur est le decimal
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
            if s.count(".") > 1:
                return None
        try:
            f = float(s)
        except ValueError:
            return None
    if f != f or f <= 0 or f > 10_000_000:
        return None
    return round(f, 4)


def diagnostic_ean(v) -> tuple[str | None, str | None]:
    """-> (chiffres, verdict). verdict : None si absent, 'ok', 'cle', 'longueur', 'format'.

    Les codes internes de certains fournisseurs ont 8 a 14 chiffres sans
    cle GS1 valide : ils restent utiles pour rapprocher les offres d'un
    MEME fournisseur, d'ou le mode --ean-sans-controle."""
    brut = texte(v)
    if not brut:
        return None, None
    if re.search(r"[A-Za-z]", brut):
        return None, "format"
    s = re.sub(r"\D", "", brut)
    if not s or set(s) == {"0"}:
        return None, "format"
    if len(s) not in (8, 12, 13, 14):
        return s, "longueur"
    chiffres = [int(c) for c in s]
    controle = chiffres.pop()
    total = sum(c * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(chiffres)))
    return s, ("ok" if (10 - total % 10) % 10 == controle else "cle")


def ean_valide(v) -> str | None:
    s, verdict = diagnostic_ean(v)
    return s if verdict == "ok" else None


def quantite(v) -> float:
    try:
        f = float(str(v).replace(",", ".")) if v not in (None, "") else 1.0
    except ValueError:
        return 1.0
    return f if f > 0 else 1.0


def coupe(s: str | None, n: int) -> str | None:
    return s[:n] if s else s


# ---------------------------------------------------------------------------
# Controles du fichier (avant toute lecture)
# ---------------------------------------------------------------------------
class FichierRefuse(Exception):
    pass


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def controle_fichier(chemin: Path) -> dict:
    if not chemin.is_file():
        raise FichierRefuse(f"Fichier introuvable : {chemin}")
    taille = chemin.stat().st_size
    if taille == 0:
        raise FichierRefuse("Fichier vide.")
    if taille > TAILLE_MAX_FICHIER:
        raise FichierRefuse(f"Fichier de {taille/1e6:.0f} Mo : plafond 2 Go.")
    with chemin.open("rb") as f:
        tete = f.read(8)
    ext = chemin.suffix.lower()
    info = {"taille_octets": taille, "extension": ext}
    if ext in (".xlsx", ".xlsm"):
        if tete[:4] != b"PK\x03\x04":
            raise FichierRefuse("Extension .xlsx mais contenu non conforme (pas une archive Office).")
        with zipfile.ZipFile(chemin) as z:
            entrees = z.infolist()
            if len(entrees) > XLSX_MAX_ENTREES:
                raise FichierRefuse(f"{len(entrees)} entrees dans l'archive : suspect.")
            noms = {e.filename.lower() for e in entrees}
            if any(n.endswith("vbaproject.bin") for n in noms):
                raise FichierRefuse("Le classeur contient des macros : enregistrez-le en .xlsx sans macros.")
            total = 0
            for e in entrees:
                total += e.file_size
                if e.compress_size and e.file_size / e.compress_size > XLSX_RATIO_MAX and e.file_size > 50e6:
                    raise FichierRefuse(f"Taux de compression anormal sur {e.filename} (zip bomb ?).")
            if total > XLSX_MAX_DECOMPRESSE:
                raise FichierRefuse(f"{total/1e9:.1f} Go une fois decompresse : plafond {XLSX_MAX_DECOMPRESSE/1e9:.0f} Go.")
            info["xlsx_decompresse_octets"] = total
            info["liens_externes"] = any("externallink" in n for n in noms)
    elif ext in (".csv", ".txt", ".tsv"):
        if b"\x00" in tete:
            raise FichierRefuse("Octets nuls en tete de fichier : ce n'est pas un CSV texte.")
    else:
        raise FichierRefuse("Formats acceptes : .xlsx, .csv (.xls a convertir en .xlsx).")
    return info


# ---------------------------------------------------------------------------
# Lecture en flux
# ---------------------------------------------------------------------------
def lignes_xlsx(chemin: Path, feuille: str | None) -> tuple[list[str], Iterator[tuple]]:
    import openpyxl  # import tardif : `analyser` d'un CSV n'en a pas besoin

    wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    noms = wb.sheetnames
    if feuille and feuille not in noms:
        raise FichierRefuse(f"Feuille '{feuille}' absente. Feuilles : {noms}")
    ws = wb[feuille or noms[0]]
    return noms, ws.iter_rows(values_only=True)


def lignes_csv(chemin: Path) -> tuple[list[str], Iterator[list]]:
    with chemin.open("rb") as f:
        echantillon = f.read(1024 * 1024)
    encodage = "utf-8-sig"
    try:
        echantillon.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        # coupure possible au milieu d'un caractere en fin d'echantillon
        if e.start < len(echantillon) - 4:
            encodage = "cp1252"
    txt = echantillon.decode(encodage, errors="ignore")
    try:
        sep = csv.Sniffer().sniff(txt[:65536], delimiters=";,\t|").delimiter
    except csv.Error:
        sep = ";"
    csv.field_size_limit(10 * 1024 * 1024)

    def gen():
        with chemin.open("r", encoding=encodage, errors="replace", newline="") as f:
            yield from csv.reader(f, delimiter=sep)

    return [f"csv ({encodage}, separateur '{sep}')"], gen()


@dataclass
class Offre:
    ligne: int
    fournisseur: str
    raw_label: str
    raw_reference: str | None
    raw_unit: str | None
    brand: str | None
    manufacturer_ref: str | None
    ean: str | None
    price_ht: float | None
    packaging_qty: float
    product_url: str | None
    source_date: str | None
    raw_row: dict
    ean_verdict: str | None = None
    prix_public: float | None = None


@dataclass
class Lecture:
    feuilles: list[str]
    entete: list[str]
    ligne_entete: int
    mapping: dict[str, int]
    lignes: Iterator[tuple[int, list]]


def ouvre(chemin: Path, feuille: str | None = None) -> Lecture:
    ext = chemin.suffix.lower()
    feuilles, flux = lignes_xlsx(chemin, feuille) if ext in (".xlsx", ".xlsm") else lignes_csv(chemin)
    tampon: list[tuple[int, list]] = []
    entete, ligne_entete, mapping = None, 0, {}
    for n, row in enumerate(flux, start=1):
        row = list(row)
        tampon.append((n, row))
        m = detecte_colonnes(row)
        if len(m) >= 2 and all(c in m for c in OBLIGATOIRES):
            entete, ligne_entete, mapping = row, n, m
            break
        if n >= LIGNES_ENTETE_MAX:
            break
    if entete is None:
        raise FichierRefuse(
            "Entete introuvable dans les 30 premieres lignes : une colonne "
            "'Designation' (ou 'Libelle') est obligatoire.")

    def suite():
        for n, row in flux_restant():
            yield n, row

    def flux_restant():
        n = ligne_entete
        for row in flux:
            n += 1
            yield n, list(row)

    return Lecture(feuilles, [texte(h) or f"colonne_{i+1}" for i, h in enumerate(entete)],
                   ligne_entete, mapping, suite())


def offres(lecture: Lecture, fournisseur_defaut: str | None, date_tarif: str | None,
           rejets: list, max_rejets_gardes: int = 2000,
           ean_sans_controle: bool = False) -> Iterator[Offre]:
    m = lecture.mapping
    entete = lecture.entete
    extras_idx = [i for i in range(len(entete)) if i not in m.values()]

    def cel(row, champ):
        i = m.get(champ)
        return row[i] if i is not None and i < len(row) else None

    compte = 0
    for n, row in lecture.lignes:
        if not any(v not in (None, "") for v in row):
            continue  # ligne vide
        compte += 1
        if compte > LIGNES_MAX:
            raise FichierRefuse(f"Plus de {LIGNES_MAX} lignes : decoupez le fichier.")
        label = texte(cel(row, "designation"))
        four = texte(cel(row, "fournisseur")) or fournisseur_defaut
        motif = None
        if not label:
            motif = "designation vide"
        elif not four:
            motif = "fournisseur absent (colonne vide et pas de --fournisseur)"
        if motif:
            if len(rejets) < max_rejets_gardes:
                rejets.append({"ligne": n, "motif": motif})
            else:
                rejets.append(None)  # compte sans garder le detail
            continue
        ean_brut = texte(cel(row, "ean"))
        chiffres, verdict = diagnostic_ean(ean_brut)
        ean = chiffres if verdict == "ok" else None
        if verdict == "cle" and ean_sans_controle:
            ean = chiffres  # conserve, mais marque ci-dessous
        raw_row = {"_ligne": n}
        for champ in ("famille", "sous_famille"):
            v = texte(cel(row, champ))
            if v:
                raw_row[champ] = v
        pp = prix(cel(row, "prix_public"))
        if pp is not None:
            raw_row["prix_public_ht"] = pp
        if verdict and verdict != "ok":
            raw_row["ean_controle"] = verdict
            if not ean:
                raw_row["ean_invalide"] = ean_brut[:40]
        for i in extras_idx:
            if i < len(row):
                v = texte(row[i])
                if v:
                    raw_row[entete[i][:60]] = v[:500]
        yield Offre(
            ligne=n,
            fournisseur=four.strip()[:200],
            raw_label=label[:LIBELLE_MAX],
            raw_reference=coupe(texte(cel(row, "ref_fournisseur")), VARCHAR["raw_reference"]),
            raw_unit=coupe(texte(cel(row, "unite")), VARCHAR["raw_unit"]),
            brand=coupe(texte(cel(row, "marque")), VARCHAR["brand"]),
            manufacturer_ref=coupe(texte(cel(row, "ref_fabricant")), VARCHAR["manufacturer_ref"]),
            ean=ean,
            price_ht=prix(cel(row, "prix_net")),
            packaging_qty=quantite(cel(row, "conditionnement")),
            product_url=(texte(cel(row, "url")) or None),
            source_date=(texte(cel(row, "date_prix")) or date_tarif),
            raw_row=raw_row,
            ean_verdict=verdict,
            prix_public=pp,
        )


# ---------------------------------------------------------------------------
# analyser : aucun acces reseau
# ---------------------------------------------------------------------------
ANOMALIES = {
    "SANS_PRIX": "prix net absent ou illisible",
    "PRIX_NET_SUP_PUBLIC": "prix net superieur au prix public",
    "PRIX_EXTREME": "prix net < 0,01 EUR ou > 50 000 EUR",
    "SANS_REFERENCE": "reference fournisseur absente",
    "DOUBLON_REFERENCE": "reference deja vue chez ce fournisseur",
    "EAN_CLE": "EAN a 8-14 chiffres dont la cle de controle GS1 est fausse",
    "EAN_LONGUEUR": "EAN dont le nombre de chiffres n'est pas 8, 12, 13 ou 14",
    "EAN_FORMAT": "EAN contenant des lettres ou uniquement des zeros",
    "EAN_DOUBLON": "meme EAN sur deux lignes du meme fournisseur",
    "DESIGNATION_COURTE": "designation de moins de 5 caracteres",
}


def analyser(chemin: Path, feuille: str | None, fournisseur: str | None,
             date_tarif: str | None, sortie: Path | None,
             anomalies_csv: Path | None = None, ean_sans_controle: bool = False) -> dict:
    """Validation de 100 % des lignes, sans aucune connexion reseau.

    Produit le rapport JSON (synthese) et, si demande, un CSV listant
    CHAQUE ligne anormale avec ses codes d'anomalie : c'est ce fichier
    qu'on ouvre dans Excel pour corriger la source avant l'import.
    """
    t0 = time.time()
    info = controle_fichier(chemin)
    info["sha256"] = empreinte(chemin)
    lecture = ouvre(chemin, feuille)
    rejets: list = []
    compteurs = {k: 0 for k in ANOMALIES}
    par_fournisseur: dict[str, dict] = {}
    refs_vues: set[bytes] = set()
    ean_par_fournisseur: dict[str, int] = {}     # ean -> masque de bits des fournisseurs
    ean_vus_meme: set[bytes] = set()
    indices: dict[str, int] = {}
    exemples: list[dict] = []
    lignes = 0
    lignes_anormales = 0

    f_csv = w_csv = None
    if anomalies_csv:
        f_csv = anomalies_csv.open("w", encoding="utf-8-sig", newline="")
        w_csv = csv.writer(f_csv, delimiter=";")
        w_csv.writerow(["ligne", "fournisseur", "reference", "ean_brut", "prix_net", "prix_public",
                        "designation", "anomalies"])
    try:
        for o in offres(lecture, fournisseur, date_tarif, rejets, ean_sans_controle=ean_sans_controle):
            lignes += 1
            four = o.fournisseur
            st = par_fournisseur.setdefault(four, {"lignes": 0, "avec_prix": 0, "ean_presents": 0,
                                                   "ean_valides": 0, "ean_cle_fausse": 0,
                                                   "ean_autres_invalides": 0, "sans_reference": 0})
            st["lignes"] += 1
            idx = indices.setdefault(slug(four), len(indices))
            codes = []
            if o.price_ht is None:
                codes.append("SANS_PRIX")
            else:
                st["avec_prix"] += 1
                if o.prix_public and o.price_ht > o.prix_public * 1.001:
                    codes.append("PRIX_NET_SUP_PUBLIC")
                if o.price_ht < 0.01 or o.price_ht > 50_000:
                    codes.append("PRIX_EXTREME")
            if o.raw_reference:
                cle = hashlib.blake2b(f"{idx}|{o.raw_reference}".encode(), digest_size=8).digest()
                if cle in refs_vues:
                    codes.append("DOUBLON_REFERENCE")
                refs_vues.add(cle)
            else:
                codes.append("SANS_REFERENCE")
                st["sans_reference"] += 1
            v = o.ean_verdict
            if v:
                st["ean_presents"] += 1
                if v == "ok":
                    st["ean_valides"] += 1
                elif v == "cle":
                    st["ean_cle_fausse"] += 1
                    codes.append("EAN_CLE")
                else:
                    st["ean_autres_invalides"] += 1
                    codes.append("EAN_LONGUEUR" if v == "longueur" else "EAN_FORMAT")
            ean_utile = o.ean  # valide, ou cle fausse conservee en mode souple
            if ean_utile:
                cle_e = hashlib.blake2b(f"{idx}|{ean_utile}".encode(), digest_size=8).digest()
                if cle_e in ean_vus_meme:
                    codes.append("EAN_DOUBLON")
                ean_vus_meme.add(cle_e)
                if v == "ok":
                    ean_par_fournisseur[ean_utile] = ean_par_fournisseur.get(ean_utile, 0) | (1 << idx)
            if len(o.raw_label) < 5:
                codes.append("DESIGNATION_COURTE")
            for c in codes:
                compteurs[c] += 1
            if codes:
                lignes_anormales += 1
                if w_csv:
                    w_csv.writerow([o.ligne, four, o.raw_reference or "",
                                    o.raw_row.get("ean_invalide", o.ean or ""),
                                    o.price_ht if o.price_ht is not None else "",
                                    o.prix_public if o.prix_public is not None else "",
                                    o.raw_label[:120], " ".join(codes)])
            if len(exemples) < 5:
                exemples.append({k: val for k, val in o.__dict__.items() if k != "raw_row"})
            if lignes % 100_000 == 0:
                print(f"  ... {lignes:,} lignes validees ({time.time()-t0:.0f} s)", file=sys.stderr)
        if w_csv:
            for r in rejets:
                if r:
                    w_csv.writerow([r["ligne"], "", "", "", "", "", "", "REJET: " + r["motif"]])
    finally:
        if f_csv:
            f_csv.close()

    # EAN communs a plusieurs fournisseurs = comparaison de prix directe possible
    multi = sum(1 for m in ean_par_fournisseur.values() if m & (m - 1))
    for four, st in par_fournisseur.items():
        n = st["lignes"] or 1
        st["taux_prix_pct"] = round(100 * st["avec_prix"] / n, 1)
        st["taux_ean_valides_pct"] = round(100 * st["ean_valides"] / n, 1)

    colonnes = {champ: lecture.entete[i] for champ, i in lecture.mapping.items()}
    bloquants = []
    if "prix_net" not in lecture.mapping:
        bloquants.append("Aucune colonne de prix net reconnue.")
    if lignes and compteurs["SANS_PRIX"] / lignes > 0.5:
        bloquants.append(f"{compteurs['SANS_PRIX']} lignes sans prix (> 50 %).")
    if lignes == 0:
        bloquants.append("Aucune ligne exploitable.")
    rapport = {
        "fichier": chemin.name,
        **info,
        "feuilles": lecture.feuilles,
        "ligne_entete": lecture.ligne_entete,
        "colonnes_reconnues": colonnes,
        "colonnes_non_reconnues": [h for i, h in enumerate(lecture.entete)
                                   if i not in lecture.mapping.values()],
        "lignes": lignes,
        "lignes_rejetees": len(rejets),
        "exemples_rejets": [r for r in rejets if r][:20],
        "lignes_avec_anomalie": lignes_anormales,
        "anomalies": {k: {"lignes": compteurs[k], "definition": ANOMALIES[k]} for k in ANOMALIES},
        "ean": {
            "mode": "sans controle de cle (codes internes conserves)" if ean_sans_controle
                    else "controle GS1 strict (cle fausse -> EAN non importe, conserve dans raw_row)",
            "presents": sum(st["ean_presents"] for st in par_fournisseur.values()),
            "valides_gs1": sum(st["ean_valides"] for st in par_fournisseur.values()),
            "cle_fausse": compteurs["EAN_CLE"],
            "longueur_ou_format_invalide": compteurs["EAN_LONGUEUR"] + compteurs["EAN_FORMAT"],
            "ean_distincts_valides": len(ean_par_fournisseur),
            "ean_communs_a_plusieurs_fournisseurs": multi,
        },
        "par_fournisseur": dict(sorted(par_fournisseur.items(), key=lambda x: -x[1]["lignes"])),
        "estimation_base_mo": round(lignes * OCTETS_PAR_LIGNE_ESTIMES / 1e6),
        "verdict": "BLOQUANT" if bloquants else ("A_VERIFIER" if lignes_anormales else "OK"),
        "bloquants": bloquants,
        "fichier_anomalies": str(anomalies_csv) if anomalies_csv else None,
        "exemples": exemples,
        "duree_s": round(time.time() - t0, 1),
    }
    if sortie:
        sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return rapport


# ---------------------------------------------------------------------------
# Base de donnees
# ---------------------------------------------------------------------------
ENV_DSN = "BLUESEATRA_IMPORT_DATABASE_URL"
COLONNES_COPY = ("id", "tenant_id", "supplier_id", "catalog_id", "version_id", "raw_label",
                 "raw_reference", "raw_unit", "raw_row", "label_norm", "brand",
                 "manufacturer_ref", "ean", "packaging_qty", "price_ht", "product_url",
                 "source_date", "source_filename", "is_active")


def dsn_securise() -> str:
    dsn = os.environ.get(ENV_DSN, "").strip()
    if not dsn:
        raise SystemExit(
            f"Variable {ENV_DSN} absente. Definissez-la dans le terminal (jamais dans "
            "un fichier versionne) avec l'URL 'Session pooler' de Supabase.")
    local = (re.search(r"@(localhost|127\.0\.0\.1|\[::1\])[:/]", dsn)
             or dsn.startswith("postgresql:///") or re.search(r"[?&]host=/", dsn))
    if not local and "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    if not local and re.search(r"sslmode=(disable|allow|prefer)", dsn):
        raise SystemExit("TLS obligatoire hors poste local : retirez sslmode=disable/allow/prefer.")
    return dsn


def connexion(tenant: str, sans_role: bool):
    import psycopg2

    cx = psycopg2.connect(dsn_securise(), application_name="import_catalogue_lourd",
                          connect_timeout=20)
    cx.autocommit = False
    # Obligatoire : sur un poste Windows l'encodage client par defaut peut
    # etre WIN1252 ou ASCII -> "Désignation" ferait echouer l'import.
    cx.set_client_encoding("UTF8")
    with cx.cursor() as cur:
        cur.execute("SET statement_timeout = '300s'")
        cur.execute("SELECT 1 FROM blueseatra.tenants WHERE id = %s", (tenant,))
        if not cur.fetchone():
            raise SystemExit(f"Tenant {tenant} inconnu.")
        if not sans_role:
            try:
                cur.execute("SET ROLE blueseatra_app")
            except Exception as e:  # noqa: BLE001
                raise SystemExit(
                    "Impossible de passer sous le role blueseatra_app (RLS). Utilisez "
                    "l'utilisateur postgres du Session pooler, ou --sans-role en "
                    f"connaissance de cause. Detail : {e}")
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant,))
    cx.commit()
    return cx


def ids_import(sha: str, tenant: str) -> str:
    return f"i{sha[:12]}-{tenant[:8]}"


def fichier_etat(import_id: str) -> Path:
    return Path(f".import_{import_id}.json")


def charge_etat(import_id: str) -> dict:
    p = fichier_etat(import_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def sauve_etat(import_id: str, etat: dict) -> None:
    p = fichier_etat(import_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


@dataclass
class Cible:
    supplier_id: str
    catalog_id: str
    version_id: str
    nom: str
    lignes: int = 0


@dataclass
class Contexte:
    import_id: str
    tenant: str
    source_filename: str
    mapping_json: dict
    cibles: dict[str, Cible] = field(default_factory=dict)  # slug -> cible
    fournisseurs_existants: dict[str, tuple[str, str]] = field(default_factory=dict)


def adopte_catalogue_orphelin(cur, tenant: str, supplier_id: str, nom: str) -> str | None:
    """Offres historiques pointant vers un catalogue jamais cree.

    Constate en production (tenant ANELEC Test : 24 600 offres avec
    catalog_id = lp_c_9171d808 absent de catalogs). Sans correction, un
    import creerait un NOUVEAU catalogue et ces anciennes offres resteraient
    visibles a cote des nouvelles (doublons). On cree donc le catalogue et
    sa version manquants avec LEURS identifiants d'origine, version active :
    la visibilite ne change pas, et l'activation pourra ensuite archiver
    proprement l'ancien tarif.
    """
    cur.execute("""SELECT o.catalog_id, o.version_id, count(*) FROM blueseatra.supplier_offers o
                   WHERE o.tenant_id = %s AND o.supplier_id = %s AND o.is_active
                     AND o.catalog_id IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM blueseatra.catalogs c WHERE c.id = o.catalog_id)
                   GROUP BY 1, 2""", (tenant, supplier_id))
    orphelins = cur.fetchall()
    if not orphelins:
        return None
    if len(orphelins) > 1 or orphelins[0][1] is None:
        raise SystemExit(f"Fournisseur {nom} : offres historiques incoherentes {orphelins} ; "
                         "correction manuelle necessaire avant import.")
    catalog_id, version_id, n = orphelins[0]
    horodatage = "to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')"
    cur.execute(f"""INSERT INTO blueseatra.catalogs (id, tenant_id, name, client_code, active_version_id, created_at)
                    VALUES (%s,%s,%s,'FOURNISSEUR',%s,{horodatage})""",
                (catalog_id, tenant, f"Tarif {nom}"[:200], version_id))
    cur.execute(f"""INSERT INTO blueseatra.catalog_versions
                      (id, tenant_id, catalog_id, version_number, status, item_count, error_count,
                       mapping, created_at, activated_at)
                    SELECT %s,%s,%s,1,'active',%s,0,%s,{horodatage},{horodatage}
                    WHERE NOT EXISTS (SELECT 1 FROM blueseatra.catalog_versions WHERE id = %s)""",
                (version_id, tenant, catalog_id, n,
                 json.dumps({"origine": "catalogue orphelin adopte par import_catalogue_lourd"}), version_id))
    print(f"  catalogue historique {catalog_id} recree ({n:,} offres, version {version_id})", file=sys.stderr)
    return catalog_id


def prepare_cible(cur, ctx: Contexte, nom: str) -> Cible:
    cle = slug(nom)
    if cle in ctx.cibles:
        return ctx.cibles[cle]
    if cle in ctx.fournisseurs_existants:
        supplier_id, nom_base = ctx.fournisseurs_existants[cle]
    else:
        supplier_id, nom_base = str(uuid.uuid4()), nom
        cur.execute(
            "INSERT INTO blueseatra.suppliers (id, tenant_id, name, slug) VALUES (%s,%s,%s,%s)",
            (supplier_id, ctx.tenant, nom, cle[:120]))
        ctx.fournisseurs_existants[cle] = (supplier_id, nom)
    adopte_catalogue_orphelin(cur, ctx.tenant, supplier_id, nom_base)
    # catalogue : celui des offres deja actives du fournisseur, sinon par nom, sinon nouveau
    cur.execute("""
        SELECT c.id FROM blueseatra.catalogs c
        WHERE c.tenant_id = %s AND c.id IN (
            SELECT DISTINCT o.catalog_id FROM blueseatra.supplier_offers o
            WHERE o.tenant_id = %s AND o.supplier_id = %s AND o.catalog_id IS NOT NULL)
        ORDER BY c.created_at DESC LIMIT 1""", (ctx.tenant, ctx.tenant, supplier_id))
    r = cur.fetchone()
    if not r:
        cur.execute("""SELECT id FROM blueseatra.catalogs
                       WHERE tenant_id = %s AND client_code = 'FOURNISSEUR' AND name = %s
                       LIMIT 1""", (ctx.tenant, f"Tarif {nom_base}"))
        r = cur.fetchone()
    if r:
        catalog_id = r[0]
    else:
        catalog_id = str(uuid.uuid4())
        cur.execute("""INSERT INTO blueseatra.catalogs (id, tenant_id, name, client_code, created_at)
                       VALUES (%s,%s,%s,'FOURNISSEUR', to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"'))""",
                    (catalog_id, ctx.tenant, f"Tarif {nom_base}"[:200]))
    version_id = f"{ctx.import_id}-v{len(ctx.cibles) + 1}"
    cur.execute("SELECT id FROM blueseatra.catalog_versions WHERE id = %s", (version_id,))
    if not cur.fetchone():
        cur.execute("SELECT coalesce(max(version_number),0)+1 FROM blueseatra.catalog_versions WHERE catalog_id = %s",
                    (catalog_id,))
        numero = cur.fetchone()[0]
        cur.execute("""INSERT INTO blueseatra.catalog_versions
                       (id, tenant_id, catalog_id, version_number, status, item_count, error_count,
                        columns, mapping, source_filename, created_at)
                       VALUES (%s,%s,%s,%s,'importing',0,0,%s,%s,%s,
                               to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"'))""",
                    (version_id, ctx.tenant, catalog_id, numero,
                     json.dumps(ctx.mapping_json.get("entete", []), ensure_ascii=False),
                     json.dumps({**ctx.mapping_json, "import_id": ctx.import_id,
                                 "fournisseur": nom_base}, ensure_ascii=False),
                     ctx.source_filename[:250]))
    c = Cible(supplier_id, catalog_id, version_id, nom_base)
    ctx.cibles[cle] = c
    return c


def _csv_copy(lignes: list[tuple]) -> io.StringIO:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for row in lignes:
        w.writerow(["\\N" if v is None else v for v in row])
    buf.seek(0)
    return buf


TYPES_COPY = {"raw_row": "jsonb", "packaging_qty": "double precision",
              "price_ht": "double precision", "is_active": "boolean"}


def ecrit_lot(cur, lot: list[tuple]) -> None:
    """COPY vers une table TEMPORAIRE puis INSERT ... SELECT.

    PostgreSQL refuse COPY FROM sur une table soumise a RLS ("COPY FROM
    not supported with row-level security"). Passer par une table
    temporaire garde la vitesse de COPY ET fait verifier chaque ligne par
    la politique WITH CHECK au moment de l'INSERT : une ligne d'un autre
    tenant fait echouer tout le lot.
    """
    colonnes = ", ".join(COLONNES_COPY)
    definition = ", ".join(f"{c} {TYPES_COPY.get(c, 'text')}" for c in COLONNES_COPY)
    cur.execute(f"CREATE TEMP TABLE IF NOT EXISTS tmp_import_offres ({definition}) ON COMMIT DELETE ROWS")
    cur.copy_expert(f"COPY tmp_import_offres ({colonnes}) FROM STDIN WITH (FORMAT csv, NULL '\\N')",
                    _csv_copy(lot))
    cur.execute(f"INSERT INTO blueseatra.supplier_offers ({colonnes}) SELECT {colonnes} FROM tmp_import_offres")
    if cur.rowcount != len(lot):
        raise RuntimeError(f"Lot incomplet : {cur.rowcount} lignes inserees sur {len(lot)}.")


def importer(chemin: Path, tenant: str, feuille: str | None, fournisseur: str | None,
             date_tarif: str | None, sans_role: bool, taille_lot: int = TAILLE_LOT,
             ean_sans_controle: bool = False) -> dict:
    t0 = time.time()
    info = controle_fichier(chemin)
    sha = empreinte(chemin)
    import_id = ids_import(sha, tenant)
    lecture = ouvre(chemin, feuille)
    mapping_json = {"entete": lecture.entete,
                    "colonnes": {c: lecture.entete[i] for c, i in lecture.mapping.items()},
                    "sha256": sha, "ligne_entete": lecture.ligne_entete,
                    "ean_sans_controle": ean_sans_controle}
    cx = connexion(tenant, sans_role)
    cur = cx.cursor()

    # garde-fou disque
    cur.execute("SELECT pg_database_size(current_database())")
    taille_base = cur.fetchone()[0]
    estimation = info.get("xlsx_decompresse_octets", info["taille_octets"])  # borne haute grossiere
    lignes_estimees = max(1, estimation // 400)
    if (taille_base + lignes_estimees * OCTETS_PAR_LIGNE_ESTIMES) / 1024 ** 3 > PLAFOND_BASE_GO:
        print(f"ATTENTION : base {taille_base/1e9:.2f} Go + estimation haute "
              f"{lignes_estimees*OCTETS_PAR_LIGNE_ESTIMES/1e9:.2f} Go > {PLAFOND_BASE_GO} Go. "
              "Surveillez le disque dans le tableau de bord Supabase.", file=sys.stderr)

    ctx = Contexte(import_id, tenant, chemin.name, mapping_json)
    cur.execute("SELECT id, name FROM blueseatra.suppliers WHERE tenant_id = %s", (tenant,))
    ctx.fournisseurs_existants = {slug(n): (i, n) for i, n in cur.fetchall()}

    etat = charge_etat(import_id)
    # reprise : cibles deja creees + derniere ligne reellement en base
    for cle, c in etat.get("cibles", {}).items():
        ctx.cibles[cle] = Cible(**c)
    derniere = 0
    if ctx.cibles:
        cur.execute("""SELECT coalesce(max((raw_row->>'_ligne')::int), 0)
                       FROM blueseatra.supplier_offers
                       WHERE tenant_id = %s AND version_id = ANY(%s)""",
                    (tenant, [c.version_id for c in ctx.cibles.values()]))
        derniere = cur.fetchone()[0]
        cur.execute("""SELECT id FROM blueseatra.catalog_versions
                       WHERE id = ANY(%s) AND status IN ('active','archived','purged')""",
                    ([c.version_id for c in ctx.cibles.values()],))
        if cur.fetchall():
            raise SystemExit("Cet import a deja ete active ou purge : rien a reprendre.")
        print(f"Reprise de l'import {import_id} apres la ligne {derniere}.", file=sys.stderr)
    cx.commit()

    rejets: list = []
    lot: list[tuple] = []
    ecrites = 0
    for o in offres(lecture, fournisseur, date_tarif, rejets, ean_sans_controle=ean_sans_controle):
        if o.ligne <= derniere:
            continue
        c = prepare_cible(cur, ctx, o.fournisseur)
        c.lignes += 1
        lot.append((f"{import_id}-{o.ligne}", tenant, c.supplier_id, c.catalog_id, c.version_id,
                    o.raw_label, o.raw_reference, o.raw_unit,
                    json.dumps(o.raw_row, ensure_ascii=False), normalize_label(o.raw_label),
                    o.brand, o.manufacturer_ref, o.ean, o.packaging_qty, o.price_ht,
                    o.product_url, o.source_date, chemin.name[:250], True))
        if len(lot) >= taille_lot:
            ecrit_lot(cur, lot)
            cx.commit()
            ecrites += len(lot)
            lot.clear()
            sauve_etat(import_id, {"import_id": import_id, "tenant": tenant, "sha256": sha,
                                   "cibles": {k: v.__dict__ for k, v in ctx.cibles.items()}})
            debit = ecrites / max(1e-6, time.time() - t0)
            print(f"  ... {ecrites:,} offres ecrites ({debit:,.0f}/s)", file=sys.stderr)
    if lot:
        ecrit_lot(cur, lot)
        ecrites += len(lot)
    cx.commit()

    # bilan par version, statut 'ready' (toujours NON visible)
    bilan = {}
    nb_rejets = len(rejets)
    for c in ctx.cibles.values():
        cur.execute("SELECT count(*) FROM blueseatra.supplier_offers WHERE tenant_id=%s AND version_id=%s",
                    (tenant, c.version_id))
        n = cur.fetchone()[0]
        cur.execute("UPDATE blueseatra.catalog_versions SET status='ready', item_count=%s, error_count=%s WHERE id=%s",
                    (n, nb_rejets, c.version_id))
        bilan[c.nom] = n
    cx.commit()
    sauve_etat(import_id, {"import_id": import_id, "tenant": tenant, "sha256": sha, "termine": True,
                           "cibles": {k: v.__dict__ for k, v in ctx.cibles.items()}})
    if rejets:
        Path(f"rejets_{import_id}.json").write_text(
            json.dumps([r for r in rejets if r], ensure_ascii=False, indent=1), encoding="utf-8")
    cx.close()
    return {"import_id": import_id, "offres_ecrites_cette_session": ecrites,
            "par_fournisseur": bilan, "rejets": nb_rejets,
            "duree_s": round(time.time() - t0, 1), "visible": False,
            "etape_suivante": f"activer --import-id {import_id} --tenant {tenant}"}


def _versions(cur, import_id: str, tenant: str) -> list[dict]:
    cur.execute("""SELECT v.id, v.catalog_id, v.status, v.item_count, v.mapping, c.active_version_id
                   FROM blueseatra.catalog_versions v
                   JOIN blueseatra.catalogs c ON c.id = v.catalog_id AND c.tenant_id = v.tenant_id
                   WHERE v.tenant_id = %s AND v.id LIKE %s ORDER BY v.id""",
                (tenant, f"{import_id}-v%"))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def statut(import_id: str, tenant: str, sans_role: bool) -> list[dict]:
    cx = connexion(tenant, sans_role)
    with cx.cursor() as cur:
        vs = _versions(cur, import_id, tenant)
    cx.close()
    return [{"version": v["id"], "fournisseur": (v["mapping"] or {}).get("fournisseur"),
             "statut": v["status"], "lignes": v["item_count"],
             "visible": v["active_version_id"] == v["id"]} for v in vs]


def activer(import_id: str, tenant: str, sans_role: bool, forcer: bool) -> dict:
    cx = connexion(tenant, sans_role)
    cur = cx.cursor()
    try:
        vs = _versions(cur, import_id, tenant)
        if not vs:
            raise SystemExit("Aucune version pour cet import.")
        pas_pretes = [v["id"] for v in vs if v["status"] != "ready"]
        if pas_pretes:
            raise SystemExit(f"Versions non pretes (import incomplet ?) : {pas_pretes}")
        resume = []
        for v in vs:
            cur.execute("SELECT id FROM blueseatra.catalogs WHERE id=%s FOR UPDATE", (v["catalog_id"],))
            cur.execute("SELECT count(*) FROM blueseatra.supplier_offers WHERE tenant_id=%s AND version_id=%s",
                        (tenant, v["id"]))
            n = cur.fetchone()[0]
            if n != v["item_count"] or n == 0:
                raise SystemExit(f"{v['id']} : {n} lignes en base, {v['item_count']} attendues. Activation refusee.")
            ancienne = v["active_version_id"]
            n_old = 0
            if ancienne:
                cur.execute("SELECT count(*) FROM blueseatra.supplier_offers WHERE tenant_id=%s AND version_id=%s",
                            (tenant, ancienne))
                n_old = cur.fetchone()[0]
                if n_old and n < n_old * BAISSE_MAX_SANS_FORCER and not forcer:
                    raise SystemExit(
                        f"{v['id']} : {n} lignes contre {n_old} dans la version active "
                        "(baisse > 50 %). Verifiez le fichier ou relancez avec --forcer.")
                cur.execute("UPDATE blueseatra.catalog_versions SET status='archived' WHERE id=%s", (ancienne,))
            mapping = dict(v["mapping"] or {})
            mapping["version_precedente"] = ancienne
            cur.execute("""UPDATE blueseatra.catalog_versions
                           SET status='active', mapping=%s,
                               activated_at=to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"')
                           WHERE id=%s""", (json.dumps(mapping, ensure_ascii=False), v["id"]))
            cur.execute("UPDATE blueseatra.catalogs SET active_version_id=%s WHERE id=%s AND tenant_id=%s",
                        (v["id"], v["catalog_id"], tenant))
            resume.append({"fournisseur": mapping.get("fournisseur"), "lignes": n,
                           "remplace": ancienne, "lignes_avant": n_old})
        cx.commit()
        return {"active": True, "versions": resume}
    except BaseException:
        cx.rollback()
        raise
    finally:
        cx.close()


def annuler(import_id: str, tenant: str, sans_role: bool) -> dict:
    cx = connexion(tenant, sans_role)
    cur = cx.cursor()
    try:
        vs = _versions(cur, import_id, tenant)
        faits = []
        for v in vs:
            if v["active_version_id"] != v["id"]:
                continue
            precedente = (v["mapping"] or {}).get("version_precedente")
            if precedente:
                cur.execute("SELECT status FROM blueseatra.catalog_versions WHERE id=%s", (precedente,))
                st = cur.fetchone()
                if st and st[0] == "purged":
                    raise SystemExit(f"L'ancien tarif {precedente} a ete supprime par `nettoyer` : "
                                     "retour arriere impossible, reimportez l'ancien fichier.")
            cur.execute("UPDATE blueseatra.catalogs SET active_version_id=%s WHERE id=%s AND tenant_id=%s",
                        (precedente, v["catalog_id"], tenant))
            cur.execute("UPDATE blueseatra.catalog_versions SET status='ready' WHERE id=%s", (v["id"],))
            if precedente:
                cur.execute("UPDATE blueseatra.catalog_versions SET status='active' WHERE id=%s", (precedente,))
            faits.append({"version": v["id"], "retour_a": precedente})
        cx.commit()
        return {"annule": faits}
    except BaseException:
        cx.rollback()
        raise
    finally:
        cx.close()


def purger(import_id: str, tenant: str, sans_role: bool, confirmer: bool) -> dict:
    if not confirmer:
        raise SystemExit("Suppression definitive : ajoutez --confirmer.")
    cx = connexion(tenant, sans_role)
    cur = cx.cursor()
    vs = _versions(cur, import_id, tenant)
    actives = [v["id"] for v in vs if v["active_version_id"] == v["id"]]
    if actives:
        raise SystemExit(f"Versions actives {actives} : lancez d'abord `annuler`.")
    total = 0
    for v in vs:
        while True:
            cur.execute("""DELETE FROM blueseatra.supplier_offers WHERE id IN (
                             SELECT id FROM blueseatra.supplier_offers
                             WHERE tenant_id=%s AND version_id=%s LIMIT 10000)""", (tenant, v["id"]))
            n = cur.rowcount
            cx.commit()
            total += n
            if n == 0:
                break
        cur.execute("UPDATE blueseatra.catalog_versions SET status='purged', item_count=0 WHERE id=%s", (v["id"],))
        cx.commit()
    cx.close()
    return {"lignes_supprimees": total, "versions": [v["id"] for v in vs]}


def nettoyer(import_id: str, tenant: str, sans_role: bool, confirmer: bool) -> dict:
    """Supprime DEFINITIVEMENT les anciens tarifs remplaces par cet import.

    Conditions : toutes les versions de l'import sont actives (activer
    reussi). Seules les versions `version_precedente` enregistrees par
    `activer` sont supprimees : les autres fournisseurs du tenant ne sont
    pas touches. Apres nettoyage, `annuler` n'est plus possible.
    """
    if not confirmer:
        raise SystemExit("Suppression definitive de l'ancien tarif : ajoutez --confirmer.")
    cx = connexion(tenant, sans_role)
    cur = cx.cursor()
    vs = _versions(cur, import_id, tenant)
    inactives = [v["id"] for v in vs if v["active_version_id"] != v["id"]]
    if not vs or inactives:
        raise SystemExit(f"Import non active ({inactives or 'aucune version'}) : lancez d'abord `activer`.")
    bilan = []
    for v in vs:
        ancienne = (v["mapping"] or {}).get("version_precedente")
        if not ancienne or ancienne == v["id"]:
            continue
        total = 0
        while True:
            cur.execute("""DELETE FROM blueseatra.supplier_offers WHERE id IN (
                             SELECT id FROM blueseatra.supplier_offers
                             WHERE tenant_id=%s AND version_id=%s LIMIT 10000)""", (tenant, ancienne))
            n = cur.rowcount
            cx.commit()
            total += n
            if n == 0:
                break
        cur.execute("UPDATE blueseatra.catalog_versions SET status='purged', item_count=0 "
                    "WHERE id=%s AND tenant_id=%s", (ancienne, tenant))
        cx.commit()
        bilan.append({"fournisseur": (v["mapping"] or {}).get("fournisseur"),
                      "ancienne_version": ancienne, "lignes_supprimees": total})
    cx.close()
    return {"nettoye": bilan, "lignes_supprimees": sum(b["lignes_supprimees"] for b in bilan)}


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)

    def commun_fichier(s):
        s.add_argument("fichier", type=Path)
        s.add_argument("--feuille")
        s.add_argument("--fournisseur", help="Nom du fournisseur si le fichier n'a pas de colonne Fournisseur")
        s.add_argument("--date-tarif", help="Date de validite des prix (AAAA-MM-JJ) si absente du fichier")
        s.add_argument("--ean-sans-controle", action="store_true",
                       help="Conserver les EAN/codes internes a 8-14 chiffres meme si la cle GS1 est fausse")

    a = sp.add_parser("analyser")
    commun_fichier(a)
    a.add_argument("--rapport", type=Path, default=Path("rapport_analyse.json"))
    a.add_argument("--anomalies", type=Path, default=Path("anomalies.csv"),
                   help="CSV (ouvrable dans Excel) listant chaque ligne anormale")
    i = sp.add_parser("importer")
    commun_fichier(i)
    i.add_argument("--tenant", required=True)
    i.add_argument("--lot", type=int, default=TAILLE_LOT)
    for nom in ("statut", "activer", "annuler", "purger", "nettoyer"):
        s = sp.add_parser(nom)
        s.add_argument("--import-id", required=True)
        s.add_argument("--tenant", required=True)
        if nom == "activer":
            s.add_argument("--forcer", action="store_true")
        if nom in ("purger", "nettoyer"):
            s.add_argument("--confirmer", action="store_true")
    for s in sp.choices.values():
        if s.prog.split()[-1] != "analyser":
            s.add_argument("--sans-role", action="store_true",
                           help="Ne pas passer sous blueseatra_app (deconseille)")
    args = p.parse_args(argv)

    try:
        if args.cmd == "analyser":
            r = analyser(args.fichier, args.feuille, args.fournisseur, args.date_tarif, args.rapport,
                         args.anomalies, args.ean_sans_controle)
            r = {k: v for k, v in r.items() if k != "exemples"}
        elif args.cmd == "importer":
            r = importer(args.fichier, args.tenant, args.feuille, args.fournisseur,
                         args.date_tarif, args.sans_role, args.lot, args.ean_sans_controle)
        elif args.cmd == "statut":
            r = statut(args.import_id, args.tenant, args.sans_role)
        elif args.cmd == "activer":
            r = activer(args.import_id, args.tenant, args.sans_role, args.forcer)
        elif args.cmd == "annuler":
            r = annuler(args.import_id, args.tenant, args.sans_role)
        elif args.cmd == "nettoyer":
            r = nettoyer(args.import_id, args.tenant, args.sans_role, args.confirmer)
        else:
            r = purger(args.import_id, args.tenant, args.sans_role, args.confirmer)
    except FichierRefuse as e:
        print(f"REFUSE : {e}", file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
