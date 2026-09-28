"""Ticket #88 : le corpus BTP est valide et la notation fonctionne."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from corpus_ia.evaluation import charger, noter


def test_corpus_complet_et_annote():
    cas = charger()
    assert len(cas) >= 8 and len({c["id"] for c in cas}) == len(cas)
    assert any(c["attendu"].get("aucun_prix") for c in cas)          # cas d'injection de prompt
    assert any(c["attendu"].get("language") == "en" for c in cas)


def test_notation_parfaite_et_echecs_listes():
    att = {"donneur_d_ordre": "Foncia", "location": "Versailles", "urgency": "normal", "mots_lignes": ["dalle"], "aucun_prix": True}
    ok = {"donneur_d_ordre": "FONCIA VERSAILLES", "location": "Versailles", "urgency": "normal", "line_items": [{"label": "Dalle LED"}]}
    assert noter(ok, att)[0] == noter(ok, att)[1]
    ko = {"donneur_d_ordre": "", "line_items": [{"label": "x", "unit_price": 1}]}
    p, t, echecs = noter(ko, att)
    assert p < t and "aucun_prix" in echecs and "donneur_d_ordre" in echecs
