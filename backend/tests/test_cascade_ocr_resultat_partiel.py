"""Cascade OCR (07/10/2026) : le premier résultat exploitable n'est plus perdu, les attentes sont
bornées et l'étape en cours est signalée.

Contexte : le 06/10, une photo a tourné plus de 25 min (PaddleOCR + structuration réussis, résultat
écarté, quatre autres étages en échec, secours vision identique à l'étage qui venait d'échouer),
puis a échoué sans rien afficher.
"""
import asyncio
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ai_service as ai  # noqa: E402

REGLAGES = {"ai_provider": "hermes", "ai_model": "gpt-oss:20b", "ocr_model_preference": "paddleocr-vl"}
TEXTE_OCR = "DEMANDE DE DEVIS " + "Remplacer 12 spots LED au RDC. " * 12
PARTIEL = {"confidence": 0.1, "description": "Remplacement de spots", "line_items": [{"label": "spot LED"}]}


def _lancer(ocr, structuration, **options):
    """Exécute extract_from_image avec un OCR et une structuration simulés."""
    appels = {"ocr": [], "structuration": []}
    progres = []

    async def _ocr(image, modele, timeout=0):
        appels["ocr"].append(modele)
        return await ocr(modele)

    async def _structurer(texte, settings, from_file=False, image_bytes=None, **k):
        appels["structuration"].append("image" if image_bytes else "texte")
        return await structuration(texte, image_bytes)

    async def _suivi(infos):
        progres.append(infos)

    with patch.object(ai, "_call_ocr_model", new=_ocr), patch.object(ai, "extract_request_data", new=_structurer):
        try:
            sortie = asyncio.run(ai.extract_from_image(b"img", REGLAGES, on_progress=options.get("suivi", _suivi)))
            erreur = None
        except Exception as exc:  # noqa: BLE001
            sortie, erreur = None, exc
    return sortie, erreur, appels, progres


def test_le_premier_resultat_incomplet_est_conserve_si_les_etages_suivants_echouent():
    async def ocr(modele):
        if "Paddle" in modele:
            return TEXTE_OCR
        raise RuntimeError("ReadTimeout")

    async def structuration(texte, image):
        return dict(PARTIEL)

    sortie, erreur, appels, _ = _lancer(ocr, structuration)
    assert erreur is None
    assert sortie["_ocr_engine"] == "résultat partiel"
    assert sortie["line_items"] == PARTIEL["line_items"]
    assert sortie["confidence"] <= 0.55                        # toujours « à revoir », jamais « done »
    assert "partiel" in sortie["_warning"].lower()
    # le secours « vision directe » (même modèle que l'étage Qwen déjà essayé) n'est PAS relancé
    assert "image" not in appels["structuration"]


def test_sans_aucun_resultat_l_erreur_liste_les_etages_sans_relancer_le_meme_modele():
    async def ocr(modele):
        raise RuntimeError("ReadTimeout")

    async def structuration(texte, image):
        raise AssertionError("ne doit pas être appelé")

    sortie, erreur, appels, _ = _lancer(ocr, structuration)
    assert isinstance(erreur, RuntimeError) and "ReadTimeout" in str(erreur)
    assert len(appels["ocr"]) == len(set(appels["ocr"]))        # aucun modèle appelé deux fois


def test_un_resultat_en_erreur_ou_vide_n_est_jamais_garde_comme_partiel():
    async def ocr(modele):
        return TEXTE_OCR

    async def structuration(texte, image):
        return {"confidence": 0.0, "line_items": [], "description": "", "_error": "JSON invalide"}

    sortie, erreur, _, _ = _lancer(ocr, structuration)
    assert sortie is None and isinstance(erreur, RuntimeError)


def test_un_etage_suivant_reussi_est_prefere_au_partiel():
    async def ocr(modele):
        return TEXTE_OCR

    async def structuration(texte, image):
        # 1er appel : incomplet ; 2e appel : bon résultat
        structuration.n += 1
        return dict(PARTIEL) if structuration.n == 1 else {"confidence": 0.9, "line_items": [{"label": "a"}, {"label": "b"}]}
    structuration.n = 0

    sortie, erreur, _, _ = _lancer(ocr, structuration)
    assert erreur is None and sortie["confidence"] == 0.9 and sortie["_ocr_engine"] != "résultat partiel"


def test_le_budget_total_arrete_la_cascade():
    async def ocr(modele):
        raise RuntimeError("ReadTimeout")

    async def structuration(texte, image):
        raise AssertionError("inutile")

    with patch.object(ai, "_OCR_CASCADE_BUDGET", -1.0):
        sortie, erreur, appels, _ = _lancer(ocr, structuration)
    assert len(appels["ocr"]) == 1                              # un seul étage tenté puis arrêt
    assert "budget" in str(erreur)


def test_l_etape_en_cours_est_signalee_et_une_panne_du_suivi_ne_casse_rien():
    async def ocr(modele):
        raise RuntimeError("ReadTimeout")

    async def structuration(texte, image):
        raise RuntimeError("x")

    _, _, _, progres = _lancer(ocr, structuration)
    assert [p["etape"] for p in progres][:2] == [1, 2]
    assert all({"etape", "total", "libelle", "debut"} <= set(p) for p in progres)

    async def casse(infos):
        raise RuntimeError("base indisponible")
    sortie, erreur, _, _ = _lancer(ocr, structuration, suivi=casse)
    assert "base indisponible" not in str(erreur)


def test_aucune_attente_d_etage_ne_depasse_le_plafond():
    # 06/10/2026 : Qwen2.5-VL attendait 704 s (1,2 x l'étage suivant) avant d'échouer.
    for preference in (None, "paddleocr-vl", "glm-ocr", "olmocr2"):
        for label, _, delai in ai._ocr_cascade_stages(preferred=preference):
            propre = round(ai._OCR_STAGE_TIMEOUT_MULTIPLIER * ai._OCR_STAGE_MEASURED_SECONDS.get(label, 300))
            # jamais coupé avant sa propre durée mesurée, jamais rallongé au-delà du plafond
            assert delai <= max(ai._OCR_STAGE_TIMEOUT_MAX, propre), (label, delai)
    qwen = {l: d for l, _, d in ai._ocr_cascade_stages(preferred="paddleocr-vl")}["Qwen2.5-VL-7B"]
    assert qwen <= ai._OCR_STAGE_TIMEOUT_MAX < 704
