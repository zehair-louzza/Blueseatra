"""Chaîne G3 : demande en texte libre -> articles du catalogue, toujours à valider. Aucun réseau."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import recherche_g3 as g3

CATALOGUE = [
    {"item_code": "CYL3030", "item_label": "Cylindre européen 30x30 laiton 3 clés", "family": "Serrurerie", "unit": "u", "unit_price_ht": 24.5},
    {"item_code": "CYL3040", "item_label": "Cylindre européen 30x40 nickelé", "family": "Serrurerie", "unit": "u", "unit_price_ht": 27.0},
    {"item_code": "CE100", "item_label": "Chauffe-eau électrique vertical 100 L", "family": "Plomberie", "unit": "u", "unit_price_ht": 289.0},
    {"item_code": "CHEV8", "item_label": "Cheville à expansion placo 8 mm (boîte de 50)", "family": "Fixation", "unit": "bt", "unit_price_ht": 9.9},
    {"item_code": "SPOT7", "item_label": "Spot LED encastré 7 W blanc", "family": "Éclairage", "unit": "u", "unit_price_ht": 12.0},
    {"item_code": "PEINT10", "item_label": "Peinture acrylique blanche mate 10 L", "family": "Peinture", "unit": "pot", "unit_price_ht": 59.0},
]

DEMANDE = ("Demande devis\nClient : LUMIA\nMerci de nous chiffrer les travaux suivants :\n"
           "Remplacement cylindre porte arrière avec 3 clés et remplacement du ballon d'eau chaude 100L.\n"
           "Cordialement,\nSophie")


def _ia_simulee(reponses):
    vus = []

    async def appel(consigne, texte, schema):
        vus.append({"consigne": consigne, "texte": texte})
        r = reponses[len(vus) - 1] if len(vus) - 1 < len(reponses) else reponses[-1]
        if isinstance(r, Exception):
            raise r
        return r
    return appel, vus


def test_candidats_melangent_mots_et_bm25_sans_doublon():
    idx = g3.Index(CATALOGUE)
    codes = [a["item_code"] for a in idx.candidats("cylindre européen 30x30", 20)]
    assert codes[0] == "CYL3030" and len(codes) == len(set(codes)) and len(codes) <= 20


def test_chaine_complete_codes_valides_uniquement_et_validation_humaine():
    appel, vus = _ia_simulee([
        {"produits": [{"designation": "cylindre européen 30x30", "quantite": "1"},
                      {"designation": "chauffe-eau électrique 100 L", "quantite": "1"}]},
        {"codes": ["CYL3030", "INVENTE"]},
        {"codes": ["CE100"]},
    ])
    res = asyncio.run(g3.suggerer(DEMANDE, CATALOGUE, appel))
    assert res["statut"] == "a_valider"
    assert [l["articles"][0]["item_code"] for l in res["lignes"]] == ["CYL3030", "CE100"]
    assert all(l["a_valider"] for l in res["lignes"])
    assert all("INVENTE" not in json.dumps(l) for l in res["lignes"])
    # Minimisation : seule la description des travaux part à l'extraction (pas l'en-tête ni la signature).
    assert "LUMIA" not in vus[0]["texte"] and "Sophie" not in vus[0]["texte"]
    assert "cylindre" in vus[0]["texte"].lower()


def test_repli_une_suggestion_si_le_modele_echoue_au_choix():
    appel, _ = _ia_simulee([{"produits": [{"designation": "cheville placo"}]}, RuntimeError("délai dépassé")])
    res = asyncio.run(g3.suggerer(DEMANDE, CATALOGUE, appel))
    ligne = res["lignes"][0]
    assert ligne["source"] == "repli" and len(ligne["articles"]) == 1 and ligne["articles"][0]["item_code"] == "CHEV8"


def test_repli_aussi_quand_le_modele_ne_retient_aucun_candidat():
    # Version mesurée G3 (33/40) : sans ce repli, 29/40 sur les 17 demandes réelles.
    appel, _ = _ia_simulee([{"produits": [{"designation": "peinture blanche 10 L"}]}, {"codes": []}])
    ligne = asyncio.run(g3.suggerer(DEMANDE, CATALOGUE, appel))["lignes"][0]
    assert ligne["source"] == "repli" and ligne["articles"][0]["item_code"] == "PEINT10"


def test_aucun_article_si_aucun_candidat_dans_le_catalogue():
    appel, _ = _ia_simulee([{"produits": [{"designation": "climatiseur réversible"}]}, {"codes": []}])
    ligne = asyncio.run(g3.suggerer(DEMANDE, CATALOGUE, appel))["lignes"][0]
    assert ligne["articles"] == [] and ligne["source"] == "aucun"


def test_extraction_impossible_renvoie_une_erreur_lisible():
    appel, _ = _ia_simulee([RuntimeError("Hermès indisponible")])
    res = asyncio.run(g3.suggerer(DEMANDE, CATALOGUE, appel))
    assert res["statut"] == "erreur" and res["lignes"] == [] and "indisponible" in res["erreur"]


def test_catalogue_vide_ou_demande_vide():
    appel, vus = _ia_simulee([{"produits": []}])
    assert asyncio.run(g3.suggerer("", CATALOGUE, appel))["lignes"] == []
    assert asyncio.run(g3.suggerer(DEMANDE, [], appel))["statut"] == "erreur"


def test_ordre_des_lignes_conserve_avec_les_choix_en_parallele():
    async def appel(consigne, texte, schema):
        if "produits" in json.dumps(schema):
            return {"produits": [{"designation": d} for d in ("peinture blanche 10 L", "cylindre 30x30", "spot LED 7 W")]}
        produit = json.loads(texte)["produit"]
        await asyncio.sleep(0.03 if "peinture" in produit else 0)   # la 1re réponse arrive en dernier
        return {"codes": [json.loads(texte)["candidats"][0]["code"]]}
    res = asyncio.run(g3.suggerer(DEMANDE, CATALOGUE, appel))
    assert [l["produit"] for l in res["lignes"]] == ["peinture blanche 10 L", "cylindre 30x30", "spot LED 7 W"]
