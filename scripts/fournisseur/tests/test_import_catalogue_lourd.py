"""Tests de import_catalogue_lourd.py.

Tests unitaires : toujours executes.
Tests d'integration : executes si TEST_PG_DSN pointe vers une base
PostgreSQL JETABLE initialisee avec schema_prod_minimal.sql. Ne JAMAIS
pointer TEST_PG_DSN vers Supabase : les tests suppriment des donnees.

    TEST_PG_DSN=postgresql://postgres@localhost:55432/bs pytest scripts/fournisseur/tests -q
"""
from __future__ import annotations

import json
import os
import re
import sys
import zipfile
from pathlib import Path

import pytest

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import import_catalogue_lourd as icl  # noqa: E402

RACINE = ICI.parents[2]


# ---------------------------------------------------------------- unitaires
@pytest.mark.parametrize("brut,attendu", [
    ("1 234,56 €", 1234.56), ("1.234,56", 1234.56), ("12.5", 12.5), (12.5, 12.5),
    ("12,50", 12.5), ("1,234.56", 1234.56), ("0", None), ("-3", None), ("", None),
    ("N/C", None), (None, None), ("1.2.3", None),
])
def test_prix_formats_francais_et_anglais(brut, attendu):
    assert icl.prix(brut) == attendu


def test_ean_controle_la_cle():
    assert icl.ean_valide("4006381333931") == "4006381333931"   # cle correcte
    assert icl.ean_valide("4006381333932") is None              # cle fausse
    assert icl.ean_valide(4006381333931.0) == "4006381333931"   # flottant Excel
    assert icl.ean_valide("abc") is None


def test_references_excel_flottantes_redeviennent_entieres():
    assert icl.texte(100021.0) == "100021"
    assert icl.texte(3.25e12) == "3250000000000"
    assert icl.texte("  ") is None


def test_detection_exacte_ne_confond_pas_prix_et_prix_public():
    m = icl.detecte_colonnes(["Désignation", "Prix public HT", "Prix net HT", "Marque"])
    assert m == {"designation": 0, "prix_public": 1, "prix_net": 2, "marque": 3}


def _xlsx(chemin: Path, lignes: list[list], titre_lignes: int = 2):
    import openpyxl
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Catalogue")
    for _ in range(titre_lignes):
        ws.append(["Catalogue TCE 2026 - export"])
    for l in lignes:
        ws.append(l)
    wb.save(chemin)


ENTETE = ["Fournisseur", "Famille", "Désignation", "Marque", "Référence fournisseur",
          "Référence fabricant", "Code EAN", "Prix net HT", "Prix public HT",
          "Unité de vente", "Couleur"]


def _jeu(n: int, fournisseurs=("Rexel", "La Plateforme du Bâtiment", "Point.P")) -> list[list]:
    rows = [ENTETE]
    for i in range(n):
        f = fournisseurs[i % len(fournisseurs)]
        rows.append([f, "Electricite", f"Disjoncteur 1P+N {10 + i % 30}A courbe C ref{i}",
                     "HAGER", float(100000 + i), f"MF{i}", 4006381333931 if i % 10 == 0 else None,
                     f"{5 + (i % 50)},{i % 100:02d}", 20 + i % 7, "pièce", "blanc"])
    rows.append([None] * len(ENTETE))                      # ligne vide ignoree
    rows.append(["Rexel", "x", None, None, "R-VIDE", None, None, "3", None, None, None])  # rejet
    return rows


def test_analyser_xlsx_en_flux(tmp_path):
    f = tmp_path / "cat.xlsx"
    _xlsx(f, _jeu(300))
    r = icl.analyser(f, None, None, "2026-09-23", tmp_path / "r.json")
    assert r["lignes"] == 300
    assert r["lignes_rejetees"] == 1
    assert r["ligne_entete"] == 3
    assert r["par_fournisseur"]["Rexel"]["lignes"] == 100
    assert r["ean"]["valides_gs1"] == 30
    assert r["colonnes_reconnues"]["prix_net"] == "Prix net HT"
    assert "Couleur" in r["colonnes_non_reconnues"]
    assert json.loads((tmp_path / "r.json").read_text())["lignes"] == 300


def _jeu_ean(tmp_path):
    rows = [["Fournisseur", "Désignation", "Référence fournisseur", "Code EAN", "Prix net HT",
             "Prix public HT"],
            ["Rexel", "Disjoncteur 16A", "R1", "4006381333931", "8,50", "12"],     # ok
            ["Point.P", "Disjoncteur 16A", "P1", "4006381333931", "7,90", "11"],   # meme EAN autre fournisseur
            ["Rexel", "Disjoncteur 20A", "R2", "4006381333932", "9", "12"],        # cle fausse
            ["Rexel", "Disjoncteur 25A", "R3", "12345", "9", "12"],                # longueur
            ["Rexel", "Disjoncteur 32A", "R3", "ABC123", "15", "12"],              # format, doublon ref, net>public
            ["Rexel", "Vis", "R4", None, None, None],                              # sans prix, designation courte
            ["Rexel", "Disjoncteur 40A", "R5", "4006381333931", "9", "12"]]        # EAN doublon meme fournisseur
    f = tmp_path / "ean.xlsx"
    _xlsx(f, rows, titre_lignes=0)
    return f


def test_validation_complete_ean_et_anomalies_ligne_a_ligne(tmp_path):
    import csv as _csv
    f = _jeu_ean(tmp_path)
    r = icl.analyser(f, None, None, None, None, anomalies_csv=tmp_path / "a.csv")
    e = r["ean"]
    assert (e["presents"], e["valides_gs1"], e["cle_fausse"], e["longueur_ou_format_invalide"]) == (6, 3, 1, 2)
    assert e["ean_communs_a_plusieurs_fournisseurs"] == 1
    a = r["anomalies"]
    assert a["EAN_CLE"]["lignes"] == 1 and a["EAN_DOUBLON"]["lignes"] == 1
    assert a["DOUBLON_REFERENCE"]["lignes"] == 1 and a["PRIX_NET_SUP_PUBLIC"]["lignes"] == 1
    assert a["SANS_PRIX"]["lignes"] == 1 and a["DESIGNATION_COURTE"]["lignes"] == 1
    assert r["verdict"] == "A_VERIFIER"
    lignes = list(_csv.reader((tmp_path / "a.csv").open(encoding="utf-8-sig"), delimiter=";"))
    par_ligne = {int(l[0]): l[-1] for l in lignes[1:]}
    assert par_ligne[4] == "EAN_CLE"
    assert set(par_ligne[6].split()) == {"PRIX_NET_SUP_PUBLIC", "DOUBLON_REFERENCE", "EAN_FORMAT"}
    assert 2 not in par_ligne and 3 not in par_ligne   # lignes saines absentes


def test_mode_ean_sans_controle_conserve_les_codes_internes(tmp_path):
    f = _jeu_ean(tmp_path)
    lecture = icl.ouvre(f)
    strict = {o.ligne: o.ean for o in icl.offres(lecture, None, None, [])}
    lecture = icl.ouvre(f)
    souple = {o.ligne: (o.ean, o.raw_row.get("ean_controle"))
              for o in icl.offres(lecture, None, None, [], ean_sans_controle=True)}
    assert strict[4] is None
    assert souple[4] == ("4006381333932", "cle")     # conserve ET marque
    assert souple[5] == (None, "longueur")           # 5 chiffres : jamais un EAN


def test_analyser_csv_point_virgule_cp1252(tmp_path):
    f = tmp_path / "cat.csv"
    contenu = "Désignation;Prix net HT;Marque\nCâble R2V 3G2,5;1,25;NEXANS\n"
    f.write_bytes(contenu.encode("cp1252"))
    r = icl.analyser(f, None, "Rexel", None, None)
    assert r["lignes"] == 1 and r["exemples"][0]["price_ht"] == 1.25
    assert r["exemples"][0]["raw_label"] == "Câble R2V 3G2,5"


def test_refuse_classeur_avec_macros(tmp_path):
    f = tmp_path / "piege.xlsx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("xl/vbaProject.bin", b"\x00" * 10)
    with pytest.raises(icl.FichierRefuse, match="macros"):
        icl.controle_fichier(f)


def test_refuse_faux_xlsx(tmp_path):
    f = tmp_path / "faux.xlsx"
    f.write_text("nom;prix\n")
    with pytest.raises(icl.FichierRefuse, match="non conforme"):
        icl.controle_fichier(f)


def test_refuse_fichier_sans_designation(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a;b\n1;2\n")
    with pytest.raises(icl.FichierRefuse, match="Entete introuvable"):
        icl.analyser(f, None, None, None, None)


def test_tls_impose_hors_local(monkeypatch):
    monkeypatch.setenv(icl.ENV_DSN, "postgresql://u:p@aws-0-eu-west-1.pooler.supabase.com:5432/postgres")
    assert "sslmode=require" in icl.dsn_securise()
    monkeypatch.setenv(icl.ENV_DSN, "postgresql://u:p@db.example.com:5432/postgres?sslmode=disable")
    with pytest.raises(SystemExit):
        icl.dsn_securise()


# -------------------------------------------------------------- integration
DSN = os.environ.get("TEST_PG_DSN")
integration = pytest.mark.skipif(not DSN, reason="TEST_PG_DSN absent")
TA, TB = "aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000002"

# Le filtre de visibilite est lu dans le code de production, pas recopie :
# si quelqu'un le modifie, ce test verifie la nouvelle version.
FILTRE = re.search(r'FILTRE_VERSION_ACTIVE = """(.*?)"""',
                   (RACINE / "backend" / "fournisseur_recherche.py").read_text(), re.S).group(1)


def _sql(q, params=(), role_tenant=None):
    import psycopg2
    cx = psycopg2.connect(DSN)
    try:
        with cx.cursor() as cur:
            if role_tenant:
                cur.execute("SET ROLE blueseatra_app")
                cur.execute("SELECT set_config('app.tenant_id', %s, false)", (role_tenant,))
            cur.execute(q, params)
            r = cur.fetchall() if cur.description else None
        cx.commit()
        return r
    finally:
        cx.close()


def _visibles(tenant, terme="disjoncteur"):
    return _sql(f"""SELECT f.name, count(*) FROM blueseatra.supplier_offers o
                    JOIN blueseatra.suppliers f ON f.id=o.supplier_id
                    WHERE o.tenant_id=%(t)s AND {FILTRE.replace(':tenant_id', '%(t)s')}
                      AND o.recherche_norm LIKE %(m)s
                    GROUP BY f.name ORDER BY 1""", {"t": tenant, "m": f"%{terme}%"}, role_tenant=tenant)


@pytest.fixture
def base(monkeypatch, tmp_path):
    monkeypatch.setenv(icl.ENV_DSN, DSN)
    monkeypatch.chdir(tmp_path)
    for t in ("supplier_offers", "catalog_versions", "catalogs", "suppliers", "tenants"):
        _sql(f"DELETE FROM blueseatra.{t}")
    _sql("INSERT INTO blueseatra.tenants VALUES (%s,'ANELEC','starter'),(%s,'Autre','starter')", (TA, TB))
    # etat de production : La Plateforme deja importee (version active lp_v)
    _sql("INSERT INTO blueseatra.suppliers (id, tenant_id, name, slug) VALUES "
         "('lp_f', %s, 'La Plateforme du Batiment', 'la-plateforme-du-batiment')", (TA,))
    _sql("INSERT INTO blueseatra.catalogs VALUES ('lp_c', %s, 'Tarif La Plateforme du Batiment', "
         "'FOURNISSEUR', 'lp_v', '2026-09-12')", (TA,))
    _sql("INSERT INTO blueseatra.catalog_versions (id, tenant_id, catalog_id, version_number, status, "
         "item_count) VALUES ('lp_v', %s, 'lp_c', 1, 'active', 150)", (TA,))
    for i in range(150):
        _sql("INSERT INTO blueseatra.supplier_offers (id, tenant_id, supplier_id, catalog_id, version_id, "
             "raw_label, price_ht) VALUES (%s, %s, 'lp_f', 'lp_c', 'lp_v', %s, 9.9)",
             (f"lp_{i}", TA, f"Disjoncteur ancien tarif {i}"))
    return tmp_path


@integration
def test_cycle_complet_import_invisible_puis_activation_atomique(base):
    f = base / "catalogue.xlsx"
    _xlsx(f, _jeu(900))
    r = icl.importer(f, TA, None, None, "2026-09-23", sans_role=False, taille_lot=200)
    iid = r["import_id"]
    assert r["par_fournisseur"] == {"Rexel": 300, "La Plateforme du Batiment": 300, "Point.P": 300}
    assert r["rejets"] == 1

    # 1. rien de visible avant activation : seul l'ancien tarif LP ressort
    assert _visibles(TA) == [("La Plateforme du Batiment", 150)]

    # 2. le fournisseur existant est reutilise malgre l'accent (Bâtiment / Batiment)
    assert _sql("SELECT count(*) FROM blueseatra.suppliers WHERE tenant_id=%s", (TA,))[0][0] == 3
    lp = _sql("SELECT catalog_id, count(*) FROM blueseatra.supplier_offers WHERE supplier_id='lp_f' "
              "GROUP BY 1")
    assert lp == [("lp_c", 450)]  # nouvelle version dans le MEME catalogue

    # 3. activation : bascule complete, l'ancien tarif disparait des resultats
    a = icl.activer(iid, TA, sans_role=False, forcer=False)
    assert {v["fournisseur"]: v["lignes"] for v in a["versions"]}["La Plateforme du Batiment"] == 300
    assert _visibles(TA) == [("La Plateforme du Batiment", 300), ("Point.P", 300), ("Rexel", 300)]

    # 4. cloisonnement : l'autre tenant ne voit rien
    assert _visibles(TB) == []

    # 5. donnees normalisees correctes
    ligne = _sql("SELECT raw_reference, ean, price_ht, raw_unit, source_date, raw_row->>'Couleur', "
                 "raw_row->>'prix_public_ht' FROM blueseatra.supplier_offers WHERE id=%s", (f"{iid}-4",))[0]
    assert ligne == ("100000", "4006381333931", 5.0, "pièce", "2026-09-23", "blanc", "20.0")

    # 6. retour arriere en une commande
    icl.annuler(iid, TA, sans_role=False)
    assert _visibles(TA) == [("La Plateforme du Batiment", 150)]

    # 7. purge de l'import annule : l'ancien tarif reste intact
    p = icl.purger(iid, TA, sans_role=False, confirmer=True)
    assert p["lignes_supprimees"] == 900
    assert _visibles(TA) == [("La Plateforme du Batiment", 150)]


@integration
def test_reprise_apres_coupure_sans_doublon(base, monkeypatch):
    f = base / "catalogue.xlsx"
    _xlsx(f, _jeu(1000))
    vrai = icl.ecrit_lot
    appels = {"n": 0}

    def coupe_au_troisieme(cur, lot):
        appels["n"] += 1
        if appels["n"] == 3:
            raise ConnectionError("coupure reseau simulee")
        vrai(cur, lot)

    monkeypatch.setattr(icl, "ecrit_lot", coupe_au_troisieme)
    with pytest.raises(ConnectionError):
        icl.importer(f, TA, None, None, None, sans_role=False, taille_lot=150)
    monkeypatch.setattr(icl, "ecrit_lot", vrai)
    r = icl.importer(f, TA, None, None, None, sans_role=False, taille_lot=150)
    total = _sql("SELECT count(*), count(DISTINCT id) FROM blueseatra.supplier_offers WHERE version_id LIKE %s",
                 (r["import_id"] + "%",))[0]
    assert total == (1000, 1000)
    assert sum(r["par_fournisseur"].values()) == 1000


@integration
def test_activation_refusee_si_le_fichier_a_fondu(base):
    f = base / "petit.xlsx"
    _xlsx(f, _jeu(30, fournisseurs=("La Plateforme du Bâtiment",)))  # 30 lignes contre 150
    r = icl.importer(f, TA, None, None, None, sans_role=False)
    with pytest.raises(SystemExit, match="baisse"):
        icl.activer(r["import_id"], TA, sans_role=False, forcer=False)
    assert _visibles(TA) == [("La Plateforme du Batiment", 150)]  # rien n'a bouge


@integration
def test_rls_bloque_une_ecriture_vers_un_autre_tenant(base):
    import psycopg2
    with pytest.raises(psycopg2.Error, match="row-level security"):
        _sql("INSERT INTO blueseatra.supplier_offers (id, tenant_id, supplier_id, raw_label) "
             "VALUES ('x', %s, 'lp_f', 'intrus')", (TA,), role_tenant=TB)
