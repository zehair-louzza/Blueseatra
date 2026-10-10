"""Import catalogue depuis Excel (ticket #86) : lecture_tableur.py.

Tests sans base ni réseau : les classeurs sont fabriqués en mémoire.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lecture_tableur as lt  # noqa: E402

openpyxl = pytest.importorskip("openpyxl")


def _xlsx(feuilles: dict[str, list[list]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nom, lignes in feuilles.items():
        ws = wb.create_sheet(nom)
        for l in lignes:
            ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


CATALOGUE = [
    ["Tarif fournisseur 2026"],                    # titre au-dessus du tableau
    [],
    ["Désignation", "Réf.", "Prix HT", "Unité", "Date"],
    ["Disjoncteur 1P+N 16A courbe C", "406774", 9.16, "U", dt.date(2026, 10, 2)],
    ["Câble R2V 3G2,5", 12345, 1.0, "M", None],
    [None, None, None, None, None],                 # ligne vide ignorée
    ["Gaine ICTA 20", "ICTA20", 0.1 + 0.2, "M", None],
]


def test_format_lu_dans_le_contenu():
    assert lt.format_fichier(_xlsx({"A": [["a", "b"]]}), "tarif.xlsx") == "xlsx"
    assert lt.format_fichier(b"a;b\n1;2\n", "tarif.csv") == "csv"
    assert lt.format_fichier(lt.SIGNATURE_XLS + b"\x00" * 100, "vieux.xls") == "xls"
    with pytest.raises(lt.FichierRefuse, match="pas un classeur"):
        lt.format_fichier(b"a;b\n1;2\n", "faux.xlsx")
    with pytest.raises(lt.FichierRefuse):
        lt.format_fichier(b"\x00\x01\x02binaire", "image.csv")


def test_xlsx_entete_detecte_sous_le_titre_et_valeurs_propres():
    df, infos = lt.lire_classeur(_xlsx({"Tarif": CATALOGUE}), "xlsx")
    assert infos["format"] == "xlsx" and infos["feuille"] == "Tarif" and infos["ligne_entete"] == 3
    assert list(df.columns) == ["Désignation", "Réf.", "Prix HT", "Unité", "Date"]
    assert len(df) == 3                                   # ligne vide retirée
    l0, l1, l2 = df.to_dict(orient="records")
    assert l0["Prix HT"] == "9.16" and l0["Date"] == "2026-10-02"
    assert l1["Réf."] == "12345" and l1["Prix HT"] == "1"  # pas « 12345.0 » ni « 1.0 »
    assert l2["Prix HT"] == "0.3" and l2["Date"] == ""
    assert all(isinstance(v, str) for v in l0.values())


def test_choix_de_la_feuille_et_feuille_sans_tableau_ignoree():
    contenu = _xlsx({"Couverture": [["Logo"], ["Société"]], "Prix": CATALOGUE[2:], "Autre": [["x", "y"], [1, 2]]})
    df, infos = lt.lire_classeur(contenu, "xlsx")
    assert infos["feuilles"] == ["Couverture", "Prix", "Autre"] and infos["feuille"] == "Prix"
    df, infos = lt.lire_classeur(contenu, "xlsx", feuille="Autre")
    assert infos["feuille"] == "Autre" and list(df.columns) == ["x", "y"]
    with pytest.raises(lt.FichierRefuse, match="n'existe pas"):
        lt.lire_classeur(contenu, "xlsx", feuille="Inconnue")


def test_entetes_vides_ou_en_double_nommes():
    df, _ = lt.lire_classeur(_xlsx({"A": [["Prix", None, "Prix", "Libellé"], [1, 2, 3, "x"]]}), "xlsx")
    assert list(df.columns) == ["Prix", "colonne_2", "Prix (2)", "Libellé"]


def test_aucun_tableau():
    with pytest.raises(lt.FichierRefuse, match="Aucun tableau"):
        lt.lire_classeur(_xlsx({"A": [["seul"]] * 5}), "xlsx")


def test_macros_refusees():
    sain = _xlsx({"A": [["a", "b"], [1, 2]]})
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(sain)) as src, zipfile.ZipFile(buf, "w") as dst:
        for e in src.infolist():
            dst.writestr(e, src.read(e.filename))
        dst.writestr("xl/vbaProject.bin", b"macro")
    with pytest.raises(lt.FichierRefuse, match="macros"):
        lt.lire_classeur(buf.getvalue(), "xlsx")


def test_archive_qui_n_est_pas_un_classeur():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "rien")
    with pytest.raises(lt.FichierRefuse, match="pas un classeur"):
        lt.lire_classeur(buf.getvalue(), "xlsx")


def test_zip_bomb_refusee(monkeypatch):
    sain = _xlsx({"A": [["a", "b"], [1, 2]]})
    monkeypatch.setattr(lt, "XLSX_MAX_DECOMPRESSE", 1000)     # un vrai classeur dépasse 1 ko
    with pytest.raises(lt.FichierRefuse, match="décompressé"):
        lt.lire_classeur(sain, "xlsx")


def test_texte_cellule():
    assert lt.texte_cellule(None) == "" and lt.texte_cellule(float("nan")) == ""
    assert lt.texte_cellule(8.0) == "8" and lt.texte_cellule(8.66) == "8.66"
    assert lt.texte_cellule(True) == "1"
    assert lt.texte_cellule(dt.datetime(2026, 10, 2, 0, 0)) == "2026-10-02"
    assert lt.texte_cellule("  ABC  ") == "ABC"
    assert len(lt.texte_cellule("x" * 50_000)) == lt.MAX_CELLULE


def test_xls_97_2003():
    xlwt = pytest.importorskip("xlwt")
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Tarif")
    for r, ligne in enumerate([["Désignation", "Prix HT"], ["Disjoncteur 16A", 9.16], ["Câble", 2.0]]):
        for c, v in enumerate(ligne):
            ws.write(r, c, v)
    buf = io.BytesIO()
    wb.save(buf)
    contenu = buf.getvalue()
    assert lt.format_fichier(contenu, "vieux.xls") == "xls"
    df, infos = lt.lire_classeur(contenu, "xls")
    assert infos["format"] == "xls" and infos["feuille"] == "Tarif"
    assert df.to_dict(orient="records") == [{"Désignation": "Disjoncteur 16A", "Prix HT": "9.16"},
                                            {"Désignation": "Câble", "Prix HT": "2"}]


def test_xls_illisible():
    with pytest.raises(lt.FichierRefuse, match=r"\.xls"):
        lt.lire_classeur(lt.SIGNATURE_XLS + b"\x00" * 600, "xls")
