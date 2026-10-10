# -*- coding: utf-8 -*-
"""Extraction sur VPS CPU : prompt borné et cascade réordonnée (04/10/2026).

Mesures Ollama sur le VPS : évaluation de prompt ~16 jetons/s, génération
~3 jetons/s. Un prompt de ~6 000 jetons = 6 minutes de silence — au-delà du
timeout d'étage (600 s) et du seuil « stream stale » de la passerelle
(900 s). Le document envoyé à la structuration est donc borné (tête + queue)
et les étages de la cascade rejouent un prompt COMPACT au lieu du même
prompt full déjà mort au timeout précédent.

Tests sans base de données.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8000")

import ai_service  # noqa: E402


# ------------------------------------------------------------- troncature
def test_document_court_inchange():
    doc = "DEVIS N° 42\n\nPompe de relevage 1 u"
    assert ai_service._tronque_document(doc) == doc


def test_document_long_borne_tete_et_queue():
    tete = "A" * 200
    milieu = "B" * 500
    queue = "C" * 200
    doc = tete + milieu + queue  # 900 caractères, borne à 400
    out = ai_service._tronque_document(doc, max_chars=400, tete=150, queue=100)
    assert len(out) < 900
    assert out.startswith("A" * 150)               # la tête survit
    assert out.endswith("C" * 100)                 # la queue survit (totaux)
    assert "tronquée" in out                        # le marqueur est présent


def test_document_long_par_defaut_respecte_la_borne():
    doc = "x" * (ai_service.EXTRACTION_DOC_MAX + 5_000)
    out = ai_service._tronque_document(doc)
    assert len(out) <= ai_service.EXTRACTION_DOC_MAX + 200  # marge marqueur


def test_troncature_compacte_pour_second_essai():
    doc = "T" * 3_000 + "M" * 5_000 + "Q" * 2_000
    out = ai_service._tronque_document(
        doc, max_chars=ai_service.EXTRACTION_DOC_COMPACT_MAX, tete=2000, queue=1000)
    assert len(out) <= ai_service.EXTRACTION_DOC_COMPACT_MAX + 200
    assert out.startswith("T" * 2000) and out.endswith("Q" * 1000)


def test_document_vide_renvoie_vide():
    assert ai_service._tronque_document("") == ""
    assert ai_service._tronque_document(None) == ""


# --------------------------------------------------------- cascade réordonnée
def test_cascade_sans_modele_vision_sans_image():
    """La cascade de structuration ne reçoit jamais d'image (garanti par
    use_structuring_cascade) : un étage VISION n'y a rien à faire."""
    labels = [label for label, _, _ in ai_service._structuring_cascade_stages()]
    assert len(labels) == 3
    assert not any("VL" in l or "vision" in l.lower() for l in labels), labels


def test_cascade_deuxieme_essai_compact_meme_modele_rapide():
    stages = ai_service._structuring_cascade_stages()
    premier = stages[0]
    second = stages[1]
    # Le 2e essai rejoue le modèle RAPIDE (7B) sur un prompt compact,
    # pas le même prompt full déjà mort au timeout de l'étage 1.
    assert "(compact)" in second[0]
    assert second[1] == premier[1]


def test_cascade_timeouts_toujours_definis():
    for label, model, timeout in ai_service._structuring_cascade_stages():
        assert model
        assert timeout >= 60, (label, timeout)


def test_cascade_choisit_le_message_compact_pour_le_bon_etage():
    """_call_structuring_cascade doit envoyer le message compact UNIQUEMENT
    aux étages marqués (compact), le full aux autres — vérifié en simulant
    IA_VIA_HERMES avec un faux _hermes_chat qui capture le message."""
    import asyncio

    captures = []
    appels = []

    async def faux_hermes_chat(model, system_prompt, user_message, **kw):
        appels.append((model, user_message))
        if len(appels) == 1:
            raise RuntimeError("ReadTimeout simule de l'etage 1")
        return '{"ok": true}'

    capture_orig = ai_service._hermes_chat
    ia_via_orig = ai_service.IA_VIA_HERMES
    ai_service._hermes_chat = faux_hermes_chat
    ai_service.IA_VIA_HERMES = True
    try:
        contenu, label = asyncio.run(ai_service._call_structuring_cascade(
            "SYSTEM", "MESSAGE-FULL", user_message_compact="MESSAGE-COMPACT"))
        assert label.endswith("(compact)")
        assert appels[0][1] == "MESSAGE-FULL"
        assert appels[1][1] == "MESSAGE-COMPACT"
    finally:
        ai_service._hermes_chat = capture_orig
        ai_service.IA_VIA_HERMES = ia_via_orig


# ----------------------------------------------- listes narratives IA (04/10)
def test_liste_chaine_avec_numerotation_decoupee():
    v = "1. Réseaux repérés. 2. Mise en place. 3. Dépose de l'existant. 4. Essais."
    out = ai_service._liste_propre(v, min_items=4)
    assert len(out) == 4 and all(len(x) >= 4 for x in out)


def test_liste_chaine_simple_une_seule_entree():
    v = "Rendez-vous et accueil par l'occupant, repérage des réseaux."
    out = ai_service._liste_propre(v, min_items=4)
    assert out == [v]


def test_liste_cassee_en_caracteres_recollee():
    """Le bug réel du 04/10 : itérer une chaîne caractère par caractère
    produisait un devis de 9 pages avec une lettre par ligne."""
    casse = list("Rendez-vous et accueil par l'occupant")
    out = ai_service._liste_propre(casse, min_items=4)
    assert len(out) == 1
    assert out[0] == "Rendez-vous et accueil par l'occupant"


def test_liste_valide_intacte():
    v = ["Couper l'eau", "Protéger les sols", "Baliser la zone"]
    assert ai_service._liste_propre(v, min_items=4) == v


def test_liste_vide_ou_nulle():
    assert ai_service._liste_propre(None) == []
    assert ai_service._liste_propre("") == []
    assert ai_service._liste_propre("   ") == []


def test_liste_chaine_avec_sauts_de_ligne():
    v = "Couper l'eau\nProtéger les sols\nBaliser la zone de travail"
    out = ai_service._liste_propre(v, min_items=4)
    assert len(out) == 3
