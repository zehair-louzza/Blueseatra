"""Génère le modèle Excel du format unique des catalogues fournisseurs."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BLEU = "1B3F73"
GRIS = "F3F5F8"
BORD = Side(style="thin", color="D0D7DE")

# (colonne, groupe, obligatoire, règle, exemple)
COLONNES = [
    ("gtin", "A. Identité", "si connu", "8, 12, 13 ou 14 chiffres, clé GS1 vérifiée, complété à 14 chiffres", "03245060343880"),
    ("gtin_rejete", "A. Identité", "non", "Code fourni mais invalide, conservé tel quel", ""),
    ("marque", "A. Identité", "oui", "Nom canonique (table des marques)", "Legrand"),
    ("marque_source", "A. Identité", "oui", "Marque telle que fournie", "LEGRAND S.N.C."),
    ("ref_fabricant", "A. Identité", "si connue", "Référence fabricant telle qu'imprimée, sans préfixe distributeur", "034388"),
    ("ref_fabricant_cle", "A. Identité", "calculée", "Majuscules, sans séparateurs ni zéros de tête", "34388"),
    ("cle_produit", "A. Identité", "calculée", "GTIN:<gtin>, sinon MR:<marque>:<réf>, sinon vide", "GTIN:03245060343880"),
    ("niveau_identification", "A. Identité", "calculée", "GTIN, MARQUE_REF ou AUCUN", "GTIN"),
    ("fournisseur", "B. Offre", "oui", "Liste fermée des fournisseurs", "YESSS"),
    ("ref_fournisseur", "B. Offre", "oui", "Code article du distributeur, unique chez lui", "BLI525509"),
    ("url_fiche", "B. Offre", "conseillé", "Lien vers la fiche produit (pas une catégorie)", ""),
    ("date_tarif", "B. Offre", "oui", "AAAA-MM-JJ", "2026-09-23"),
    ("disponibilite", "B. Offre", "non", "STOCK, COMMANDE, ARRETE, INCONNU", "INCONNU"),
    ("designation_source", "C. Description", "oui", "Texte du fournisseur, jamais modifié", "Barrette à cosses Cosga avec platine métal 150x45mm et fixation par vis Ø3,5mm"),
    ("designation", "C. Description", "calculée", "<Type> <marque> <gamme> <caractéristiques clés>", "Barrette de coupure Legrand Cosga platine métal 150 x 45 mm"),
    ("texte_recherche", "C. Description", "calculée", "Minuscules, sans accents, unités collées, abréviations dépliées", "barrette coupure legrand cosga platine metal 150x45mm"),
    ("classe_etim", "D. Classement", "conseillé", "Code de classe ETIM", ""),
    ("type_produit", "D. Classement", "oui", "Nom court de la classe (liste fermée)", "Barrette de coupure"),
    ("famille", "D. Classement", "oui", "Famille TCE commune (liste fermée)", "Électricité – distribution et tableaux"),
    ("famille_source", "D. Classement", "oui", "Famille du fournisseur, conservée", "BARRETTES"),
    ("sous_famille_source", "D. Classement", "non", "Sous-famille du fournisseur, conservée", ""),
    ("poles", "E. Caractéristiques", "si lu", "1P, 1P+N, 2P, 3P, 3P+N, 4P", ""),
    ("calibre_a", "E. Caractéristiques", "si lu", "Ampères (nombre)", ""),
    ("courbe", "E. Caractéristiques", "si lu", "B, C, D, K, Z", ""),
    ("pouvoir_coupure_ka", "E. Caractéristiques", "si lu", "kA (nombre)", ""),
    ("sensibilite_ma", "E. Caractéristiques", "si lu", "mA (nombre)", ""),
    ("type_differentiel", "E. Caractéristiques", "si lu", "AC, A, F, B, Asi", ""),
    ("section_mm2", "E. Caractéristiques", "si lu", "mm² (nombre)", ""),
    ("nb_conducteurs", "E. Caractéristiques", "si lu", "Nombre", ""),
    ("composition_cable", "E. Caractéristiques", "si lu", "ex. 3G2.5", ""),
    ("tension_v", "E. Caractéristiques", "si lu", "V (nombre)", ""),
    ("puissance_w", "E. Caractéristiques", "si lu", "W (nombre)", ""),
    ("flux_lm", "E. Caractéristiques", "si lu", "lm (nombre)", ""),
    ("temperature_couleur_k", "E. Caractéristiques", "si lu", "K (nombre)", ""),
    ("indice_ip", "E. Caractéristiques", "si lu", "ex. IP65", ""),
    ("indice_ik", "E. Caractéristiques", "si lu", "ex. IK08", ""),
    ("longueur_mm", "E. Caractéristiques", "si lu", "mm (nombre)", "150"),
    ("largeur_mm", "E. Caractéristiques", "si lu", "mm (nombre)", "45"),
    ("hauteur_mm", "E. Caractéristiques", "si lu", "mm (nombre)", ""),
    ("diametre_mm", "E. Caractéristiques", "si lu", "mm (nombre)", ""),
    ("couleur", "E. Caractéristiques", "si lu", "Liste fermée", ""),
    ("matiere", "E. Caractéristiques", "si lu", "Liste fermée", "acier"),
    ("attributs_autres", "E. Caractéristiques", "non", 'JSON {"code ETIM": valeur}', ""),
    ("unite_base", "F. Unités et prix", "oui", "U, M, M2, M3, KG, L, PAIRE", "U"),
    ("conditionnement", "F. Unités et prix", "oui", "UNITE, BOITE, SAC, ROULEAU, TOURET, CARTON, LOT, BIDON, PALETTE", "UNITE"),
    ("qte_par_conditionnement", "F. Unités et prix", "oui", "Nombre d'unités de base achetées", "1"),
    ("unite_source", "F. Unités et prix", "oui", "Unité telle que fournie", "1"),
    ("prix_net_ht", "F. Unités et prix", "oui", "Prix d'achat HT du conditionnement (€)", "54.0319"),
    ("prix_public_ht", "F. Unités et prix", "si connu", "Prix public HT du conditionnement (€)", ""),
    ("prix_net_ht_unite_base", "F. Unités et prix", "calculée", "prix_net_ht / qte_par_conditionnement : le prix comparé", "54.0319"),
    ("eco_contribution_ht", "F. Unités et prix", "si connue", "Séparée du prix (€)", ""),
    ("taux_tva", "F. Unités et prix", "oui", "20, 10, 5.5, 0", "20"),
    ("statut_prix", "F. Unités et prix", "oui", "NET_CLIENT, PUBLIC, PROMO, SANS_PRIX", "NET_CLIENT"),
    ("anomalies", "G. Qualité", "calculée", "Codes séparés par | (voir la liste)", ""),
    ("score_qualite", "G. Qualité", "calculée", "0 à 100", "85"),
]
NOMS = [c[0] for c in COLONNES]

LISTES = {
    "fournisseur": ["Rexel", "Prolians", "Point.P", "YESSS", "La Plateforme du Bâtiment", "SFIC",
                    "Au Forum du Bâtiment", "Chausson Matériaux", "Icilux"],
    "niveau_identification": ["GTIN", "MARQUE_REF", "AUCUN"],
    "disponibilite": ["STOCK", "COMMANDE", "ARRETE", "INCONNU"],
    "famille": ["Électricité – protection", "Électricité – appareillage", "Électricité – distribution et tableaux",
                "Câbles et conducteurs", "Conduits et cheminement", "Éclairage", "Courants faibles et VDI",
                "Sécurité incendie et alarme", "Chauffage", "Climatisation et ventilation",
                "Plomberie – tubes et raccords", "Sanitaire et robinetterie", "Évacuation", "Quincaillerie",
                "Fixation et visserie", "Outillage", "EPI", "Plâtrerie et isolation", "Menuiserie et fermetures",
                "Peinture et revêtements muraux", "Revêtements de sols", "Gros œuvre et maçonnerie",
                "Couverture et étanchéité", "Consommables et produits d'entretien"],
    "poles": ["1P", "1P+N", "2P", "3P", "3P+N", "4P"],
    "courbe": ["B", "C", "D", "K", "Z"],
    "type_differentiel": ["AC", "A", "F", "B", "Asi"],
    "unite_base": ["U", "M", "M2", "M3", "KG", "L", "PAIRE"],
    "conditionnement": ["UNITE", "BOITE", "SAC", "ROULEAU", "TOURET", "CARTON", "LOT", "BIDON", "PALETTE"],
    "taux_tva": ["20", "10", "5.5", "0"],
    "statut_prix": ["NET_CLIENT", "PUBLIC", "PROMO", "SANS_PRIX"],
    "anomalies": ["SANS_PRIX", "PRIX_NET_SUP_PUBLIC", "PRIX_EXTREME", "GTIN_CLE", "REF_DOUBLON",
                  "DESIGNATION_AMPUTEE", "UNITE_INCONNUE", "UNITE_SUPPOSEE", "ECART_PRIX_PRODUIT", "CONFLIT_ATTRIBUT"],
}

UNITES = [  # unite_source -> unite_base, conditionnement, qte
    ("Pièce / pièce / u / Unité / 1", "U", "UNITE", "1"),
    ("Cent / 100 / Boîte de 100", "U", "BOITE", "100"),
    ("Mille / 1000", "U", "BOITE", "1000"),
    ("Sachet de 10 / Lot de 10", "U", "LOT", "10"),
    ("Paire", "PAIRE", "UNITE", "1"),
    ("Mètre / m", "M", "UNITE", "1"),
    ("Rouleau de 50 m", "M", "ROULEAU", "50"),
    ("Mètre carré / m²", "M2", "UNITE", "1"),
    ("Mètre cube", "M3", "UNITE", "1"),
    ("Kilogramme", "KG", "UNITE", "1"),
    ("Sac de 25 kg", "KG", "SAC", "25"),
    ("Bidon de 5 L", "L", "BIDON", "5"),
    ("Boîte / Carton / Lot / Paquet sans quantité", "U", "(à préciser)", "(à préciser) : anomalie UNITE_INCONNUE"),
]


def ligne(**v):
    return [v.get(n, "") for n in NOMS]


# Exemples réels (catalogues du 23/09/2026), mis au format.
EXEMPLES = []
for f, src_label, marque_src, unite_src, prix, fam in [
    ("Rexel", "Barrette à cosses Cosga avec platine métal 150x45mm et fixation par vis D=3,5mm", "Legrand", "Pièce", "43.1138", "Distribution et gestion de l'énergie"),
    ("Point.P", "Barrette de coupure Cosga - platine métal - 150x45 mm", "LEGRAND", "Pièce", "48.67", "Electricité, ventilation"),
    ("YESSS", "Barrette à cosses Cosga avec platine métal 150x45mm et fixation par vis Ø3,5mm", "LEGRAND S.N.C.", "1", "54.0319", "BARRETTES"),
]:
    EXEMPLES.append(ligne(
        gtin="03245060343880", marque="Legrand", marque_source=marque_src, ref_fabricant="034388",
        ref_fabricant_cle="34388", cle_produit="GTIN:03245060343880", niveau_identification="GTIN",
        fournisseur=f, date_tarif="2026-09-23", disponibilite="INCONNU", designation_source=src_label,
        designation="Barrette de coupure Legrand Cosga platine métal 150 x 45 mm",
        texte_recherche="barrette coupure legrand cosga platine metal 150x45mm",
        type_produit="Barrette de coupure", famille="Électricité – distribution et tableaux", famille_source=fam,
        longueur_mm="150", largeur_mm="45", matiere="acier", unite_base="U", conditionnement="UNITE",
        qte_par_conditionnement="1", unite_source=unite_src, prix_net_ht=prix, prix_net_ht_unite_base=prix,
        taux_tva="20", statut_prix="NET_CLIENT", score_qualite="85"))

for f, src_label, marque_src, unite_src, prix, pdc, anomalies in [
    ("Rexel", "Disjoncteur DNX³ 4500 - vis/vis - 1P+N 230V~ 16A - 4,5kA - courbe C - 1 module", "Legrand", "Pièce", "9.1584", "4.5", "CONFLIT_ATTRIBUT"),
    ("YESSS", "Disjoncteur Phase+Neutre DNX³4500 6kA arrivée et sortie borne à vis  -  1P+N 230V~ 16A courbe C  -  1 module", "LEGRAND S.N.C.", "1", "28.6402", "6", "CONFLIT_ATTRIBUT|ECART_PRIX_PRODUIT"),
]:
    EXEMPLES.append(ligne(
        gtin="03245064067744", marque="Legrand", marque_source=marque_src, ref_fabricant="406774",
        ref_fabricant_cle="406774", cle_produit="GTIN:03245064067744", niveau_identification="GTIN",
        fournisseur=f, date_tarif="2026-09-23", disponibilite="INCONNU", designation_source=src_label,
        designation="Disjoncteur Legrand DNX³ 4500 1P+N 16 A courbe C vis/vis",
        texte_recherche="disjoncteur legrand dnx3 4500 1p+n 16a courbe c vis vis",
        classe_etim="EC000042", type_produit="Disjoncteur modulaire", famille="Électricité – protection",
        famille_source="Distribution et gestion de l'énergie" if f == "Rexel" else "",
        poles="1P+N", calibre_a="16", courbe="C", pouvoir_coupure_ka=pdc, tension_v="230",
        unite_base="U", conditionnement="UNITE", qte_par_conditionnement="1", unite_source=unite_src,
        prix_net_ht=prix, prix_net_ht_unite_base=prix, taux_tva="20", statut_prix="NET_CLIENT",
        anomalies=anomalies, score_qualite="90"))


def entete(ws, valeurs, largeurs=None):
    ws.append(valeurs)
    for i, _ in enumerate(valeurs, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=BLEU)
        c.alignment = Alignment(vertical="center", wrap_text=True)
        c.border = Border(bottom=BORD)
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30
    for i, w in enumerate(largeurs or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


wb = Workbook()

ws = wb.active
ws.title = "Lisez-moi"
ws.column_dimensions["A"].width = 92
textes = [
    ("Format unique des catalogues fournisseurs Blueseatra — version 1.0 du 2 octobre 2026", True),
    ("", False),
    ("Une ligne = une offre : un produit vendu par un fournisseur à un prix donné.", False),
    ("Feuille « Modèle » : à remplir (en-têtes figés, listes déroulantes sur les colonnes à valeurs fermées).", False),
    ("Feuille « Colonnes » : la règle de chaque colonne, son groupe, si elle est obligatoire, et un exemple.", False),
    ("Feuille « Listes » : les valeurs autorisées et la table de correspondance des unités.", False),
    ("Feuille « Exemple réel » : 5 offres de vos catalogues mises au format (2 produits Legrand chez 2 ou 3 fournisseurs).", False),
    ("", False),
    ("Règles d'or", True),
    ("1. Ne jamais écraser la source : chaque valeur nettoyée garde sa colonne _source.", False),
    ("2. Une colonne vide reste vide : jamais N/A, - ou 0. Un prix absent n'est jamais 0.", False),
    ("3. Décimales avec un point. Dates AAAA-MM-JJ. GTIN en texte sur 14 chiffres.", False),
    ("4. On compare prix_net_ht_unite_base, jamais prix_net_ht : une boîte de 100 n'est pas une pièce.", False),
    ("5. Une caractéristique n'est remplie que si elle est lue dans la source. Rien n'est deviné.", False),
    ("", False),
    ("Trois niveaux de comparaison", True),
    ("Identique certain : même GTIN valide → une seule ligne produit, un prix par fournisseur.", False),
    ("Identique probable : même marque canonique + même ref_fabricant_cle → une seule ligne, marquée « même référence ».", False),
    ("Équivalent technique : même type_produit + mêmes caractéristiques clés, autre marque → lignes séparées, jamais fusionnées.", False),
    ("Jamais de rapprochement sur la seule ressemblance des désignations.", False),
]
for t, gras in textes:
    ws.append([t])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=gras, size=13 if gras else 11, color=BLEU if gras else "1F2328")
    ws.cell(row=ws.max_row, column=1).alignment = Alignment(wrap_text=True, vertical="top")

wsm = wb.create_sheet("Modèle")
entete(wsm, NOMS, [max(14, min(34, len(n) + 4)) for n in NOMS])

wsc = wb.create_sheet("Colonnes")
entete(wsc, ["Colonne", "Groupe", "Obligatoire", "Règle", "Exemple"], [30, 20, 13, 70, 48])
for i, c in enumerate(COLONNES, 2):
    wsc.append(list(c))
    for j in range(1, 6):
        cell = wsc.cell(row=i, column=j)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if i % 2 == 0:
            cell.fill = PatternFill("solid", fgColor=GRIS)
    wsc.cell(row=i, column=1).font = Font(bold=True, name="Consolas")

wsl = wb.create_sheet("Listes")
col = 1
for nom, valeurs in LISTES.items():
    wsl.cell(row=1, column=col, value=nom)
    for k, v in enumerate(valeurs, 2):
        wsl.cell(row=k, column=col, value=v)
    wsl.column_dimensions[get_column_letter(col)].width = max(14, max(len(v) for v in valeurs) + 2)
    col += 1
for i in range(1, col):
    c = wsl.cell(row=1, column=i)
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=BLEU)
wsl.freeze_panes = "A2"
debut = col + 1
for j, h in enumerate(["unite_source (exemples)", "unite_base", "conditionnement", "qte_par_conditionnement"]):
    c = wsl.cell(row=1, column=debut + j, value=h)
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="0E7490")
    wsl.column_dimensions[get_column_letter(debut + j)].width = [44, 12, 16, 40][j]
for k, u in enumerate(UNITES, 2):
    for j, v in enumerate(u):
        wsl.cell(row=k, column=debut + j, value=v)

# Listes déroulantes sur le modèle
for nom, valeurs in LISTES.items():
    if nom not in NOMS or nom == "anomalies":
        continue
    idx = list(LISTES).index(nom) + 1
    lettre = get_column_letter(idx)
    dv = DataValidation(type="list", formula1=f"=Listes!${lettre}$2:${lettre}${len(valeurs) + 1}",
                        allow_blank=True, showErrorMessage=True,
                        error=f"Valeur hors liste pour {nom}", errorTitle="Format unique")
    wsm.add_data_validation(dv)
    dv.add(f"{get_column_letter(NOMS.index(nom) + 1)}2:{get_column_letter(NOMS.index(nom) + 1)}100000")
for n in NOMS:
    if n in ("gtin", "ref_fabricant", "ref_fabricant_cle", "ref_fournisseur", "date_tarif"):
        for r in range(2, 3):
            pass
        wsm.column_dimensions[get_column_letter(NOMS.index(n) + 1)].number_format = "@"

wse = wb.create_sheet("Exemple réel")
entete(wse, NOMS, [max(14, min(34, len(n) + 4)) for n in NOMS])
for k, r in enumerate(EXEMPLES, 2):
    wse.append(r)
    for j in range(1, len(NOMS) + 1):
        cell = wse.cell(row=k, column=j)
        cell.alignment = Alignment(vertical="top", wrap_text=NOMS[j - 1] in ("designation_source", "designation"))
        if NOMS[j - 1] in ("gtin", "ref_fabricant", "ref_fabricant_cle", "date_tarif"):
            cell.number_format = "@"
        if NOMS[j - 1] == "anomalies" and cell.value:
            cell.fill = PatternFill("solid", fgColor="FFF4E5")
wse.column_dimensions[get_column_letter(NOMS.index("designation_source") + 1)].width = 60
wse.column_dimensions[get_column_letter(NOMS.index("designation") + 1)].width = 48

wb.save("docs/specs/modele-format-unique-catalogue.xlsx")
print("ok", len(NOMS), "colonnes,", len(EXEMPLES), "exemples")
