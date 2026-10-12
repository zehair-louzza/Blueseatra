"""Tests unitaires de devis_sync : logique pure, sans base de donnees.

Lanceurs : pytest backend/tests/test_devis_sync.py
"""
import asyncio

import devis_sync
import recherche_g3

CATALOGUE = [
    {"item_code": "SPO-001", "item_label": "Spot LED encastrable 7W blanc",
     "unit": "u", "unit_price_ht": 12.5, "family": "eclairage",
     "category": "electricite", "brand": "RZB", "reference": "982552.002"},
    {"item_code": "BAL-100", "item_label": "Chauffe-eau electrique vertical 100 L",
     "unit": "u", "unit_price_ht": 189.0, "family": "sanitaire",
     "category": "plomberie", "brand": "Atlantic", "reference": "CE100V"},
]


def ligne(**kw):
    base = {"line_type": "material",
            "request_label": "remplacement de 3 spots LED encastrables",
            "description": "remplacement de 3 spots LED encastrables",
            "qty": 3, "unit": "u", "status": "to_confirm", "reasons": ["hors_catalogue"]}
    base.update(kw)
    return base


def test_est_a_sourcer():
    assert devis_sync._est_a_sourcer(ligne())
    assert not devis_sync._est_a_sourcer(ligne(status="matched", matched_item_code="SPO-001"))
    assert not devis_sync._est_a_sourcer(ligne(status="proposed"))
    assert not devis_sync._est_a_sourcer(ligne(line_type="lot"))
    assert not devis_sync._est_a_sourcer(ligne(line_type="labor"))
    assert not devis_sync._est_a_sourcer(ligne(line_type="travel"))


def test_suggestion_catalogue_interne():
    index = recherche_g3.Index(CATALOGUE)
    sug = asyncio.run(devis_sync.suggerer_pour_ligne(ligne(), index, avec_fournisseurs=False))
    assert sug is not None
    assert sug["suggested_item_code"] == "SPO-001"
    assert sug["suggested_origine"] == "catalogue"
    assert sug["suggested_unit_price_ht"] == 12.5


def test_suggestion_chauffe_eau():
    index = recherche_g3.Index(CATALOGUE)
    l = ligne(request_label="fourniture et pose d'un chauffe-eau electrique 100 L",
              description="fourniture et pose d'un chauffe-eau electrique 100 L")
    sug = asyncio.run(devis_sync.suggerer_pour_ligne(l, index, avec_fournisseurs=False))
    assert sug is not None
    assert sug["suggested_item_code"] == "BAL-100"


def test_suggestion_libelle_trop_court():
    index = recherche_g3.Index(CATALOGUE)
    l = ligne(request_label="", description="")
    assert asyncio.run(devis_sync.suggerer_pour_ligne(l, index, False)) is None


def test_appliquer_suggestion():
    l = ligne()
    l.update({"suggested_item_code": "SPO-001",
              "suggested_label": "Spot LED encastrable 7W blanc",
              "suggested_unit_price_ht": 12.5, "suggested_unite": "u",
              "suggested_origine": "catalogue"})
    assert devis_sync._appliquer(l)
    assert l["matched_item_code"] == "SPO-001"
    assert l["unit_price_ht"] == 12.5
    assert l["line_ht"] == 37.5          # 3 x 12,5 EUR HT
    assert l["status"] == "proposed"
    assert "sync_demande" in l["reasons"]
    assert "suggested_item_code" not in l


def test_appliquer_sans_suggestion_ou_sans_prix_refuse():
    assert not devis_sync._appliquer(ligne())
    sans_prix = ligne(suggested_item_code="X", suggested_unit_price_ht=None)
    assert not devis_sync._appliquer(sans_prix)
    assert sans_prix["status"] == "to_confirm"  # jamais de prix invente


def test_totaux():
    lines = [ligne(line_ht=10.0), ligne(line_ht=None), ligne(line_ht=2.5)]
    assert devis_sync._totaux(lines) == (12.5, 0.0, 12.5)


def test_libelle_ligne():
    assert devis_sync._libelle_ligne({"request_label": "a", "description": "b"}) == "a"
    assert devis_sync._libelle_ligne({"description": "b"}) == "b"
    assert devis_sync._libelle_ligne({}) == ""
