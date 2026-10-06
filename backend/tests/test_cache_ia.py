"""Cache des extractions IA par empreinte du contenu (cache_ia.py).

Sans base ni IA réelles : la clé, la décision de mise en cache et le branchement dans
process_request (réutilisation, écriture, jamais d'échec figé, « Retraiter » ignore le cache).
"""
import asyncio
import base64
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cache_ia  # noqa: E402
import server  # noqa: E402

REGLAGES = {"ai_provider": "hermes", "ai_model": "gpt-oss:20b", "ocr_model_preference": "glm-ocr"}
TEXTE = {"source_type": "pdf", "raw_text": "Remplacer 12 spots LED au RDC."}
BON = {"confidence": 0.9, "line_items": [{"label": "spot LED"}], "language": "fr"}


# ---------- clé ----------

def test_cle_stable_pour_meme_contenu_et_meme_configuration():
    assert cache_ia.cle_demande(TEXTE, REGLAGES) == cache_ia.cle_demande(dict(TEXTE), dict(REGLAGES))
    source, cle = cache_ia.cle_demande(TEXTE, REGLAGES)
    assert source == "texte" and len(cle) == 64


def test_cle_change_si_le_contenu_change():
    a = cache_ia.cle_demande(TEXTE, REGLAGES)[1]
    b = cache_ia.cle_demande({**TEXTE, "raw_text": TEXTE["raw_text"] + " "}, REGLAGES)[1]
    assert a != b


@pytest.mark.parametrize("modif", [{"ai_model": "qwen2.5:7b"}, {"ai_provider": "mistral"},
                                   {"ocr_model_preference": "lightonocr"}])
def test_cle_change_si_la_configuration_change(modif):
    assert cache_ia.cle_demande(TEXTE, REGLAGES)[1] != cache_ia.cle_demande(TEXTE, {**REGLAGES, **modif})[1]


def test_cle_change_si_la_consigne_ou_le_schema_change(monkeypatch):
    import ai_service
    avant = cache_ia.cle_demande(TEXTE, REGLAGES)[1]
    monkeypatch.setattr(ai_service, "EXTRACTION_SYSTEM", ai_service.EXTRACTION_SYSTEM + " règle ajoutée")
    assert cache_ia.cle_demande(TEXTE, REGLAGES)[1] != avant
    monkeypatch.undo()
    monkeypatch.setattr(ai_service, "HERMES_STRUCTURING_MODEL_1", "autre-modele")
    assert cache_ia.cle_demande(TEXTE, REGLAGES)[1] != avant


def test_texte_saisi_et_texte_de_fichier_ont_des_cles_distinctes():
    # from_file change le comportement de l'extraction.
    saisi = cache_ia.cle_demande({"source_type": "text", "raw_text": "x"}, REGLAGES)[1]
    fichier = cache_ia.cle_demande({"source_type": "pdf", "raw_text": "x"}, REGLAGES)[1]
    assert saisi != fichier


def test_cle_image_et_pages_rendues():
    octets = b"\x89PNG-image-1"
    img = {"source_type": "image", "file_b64": base64.b64encode(octets).decode()}
    assert cache_ia.cle_demande(img, REGLAGES)[0] == "image"
    autre = {"source_type": "image", "file_b64": base64.b64encode(octets + b"2").decode()}
    assert cache_ia.cle_demande(img, REGLAGES)[1] != cache_ia.cle_demande(autre, REGLAGES)[1]
    scan = {"source_type": "pdf_ocr", "raw_text": ""}
    assert cache_ia.cle_demande(scan, REGLAGES) is None                       # pages absentes (retraitement)
    k1 = cache_ia.cle_demande(scan, REGLAGES, [b"p1", b"p2"])
    assert k1[0] == "pdf_ocr" and k1[1] != cache_ia.cle_demande(scan, REGLAGES, [b"p2", b"p1"])[1]


def test_sans_contenu_pas_de_cle():
    assert cache_ia.cle_demande({"source_type": "pdf", "raw_text": "  "}, REGLAGES) is None


# ---------- décision de mise en cache ----------

@pytest.mark.parametrize("extracted,attendu", [
    (BON, True),
    ({**BON, "_error": "boom"}, False),
    ({**BON, "confidence": 0.59}, False),
    ({**BON, "confidence": None}, False),
    ({**BON, "confidence": "abc"}, False),
    (None, False),
])
def test_cachable(extracted, attendu):
    assert cache_ia.cachable(extracted) is attendu


def test_ecrire_refuse_un_echec_sans_toucher_a_la_base():
    with patch.object(cache_ia, "tenant_session", side_effect=AssertionError("ne doit pas ouvrir de session")):
        assert asyncio.run(cache_ia.ecrire("t", "c" * 64, "texte", {**BON, "_error": "x"})) is False


def test_cache_en_panne_ne_leve_jamais():
    with patch.object(cache_ia, "tenant_session", side_effect=RuntimeError("base indisponible")):
        assert asyncio.run(cache_ia.lire("t", "c" * 64)) is None
        assert asyncio.run(cache_ia.ecrire("t", "c" * 64, "texte", BON)) is False
        assert asyncio.run(cache_ia.purger_entreprise("t")) == 0
        asyncio.run(cache_ia.invalider("t", "c" * 64))


# ---------- branchement dans process_request ----------

class _Requetes:
    def __init__(self, req):
        self.req, self.maj = req, []

    async def find_one(self, *a, **k):
        return dict(self.req)

    async def update_one(self, filtre, maj, **k):
        self.maj.append(maj["$set"])


class _Base:
    def __init__(self, req):
        self.requests = _Requetes(req)


async def _lancer(req, *, cache_lu=None, resultat_ia=None):
    base = _Base(req)
    ia = AsyncMock(return_value=resultat_ia or dict(BON))
    lire, ecrire = AsyncMock(return_value=cache_lu), AsyncMock(return_value=True)
    with patch.object(server, "db", base), \
         patch.object(server, "get_tenant_ai_settings", new=AsyncMock(return_value=REGLAGES)), \
         patch.object(server, "audit", new=AsyncMock()), \
         patch.object(server.clients_module, "suggerer_depuis_extraction", new=AsyncMock()), \
         patch.object(server, "_auto_generate_quote_if_needed", new=AsyncMock()), \
         patch.object(server.quotas, "annuler", new=AsyncMock()), \
         patch.object(server.ai_service, "extract_from_text", new=ia), \
         patch.object(cache_ia, "lire", new=lire), patch.object(cache_ia, "ecrire", new=ecrire):
        await server.process_request("r1", "t1")
    return base, ia, lire, ecrire


REQ = {"id": "r1", "tenant_id": "t1", "created_by": "u", **TEXTE}


def test_resultat_en_cache_reutilise_sans_appeler_l_ia():
    en_cache = {**BON, "_cache_ia": "2026-10-06T10:00:00+00:00"}
    base, ia, lire, ecrire = asyncio.run(_lancer(REQ, cache_lu=en_cache))
    assert ia.await_count == 0
    assert ecrire.await_count == 0                      # pas de réécriture d'un résultat réutilisé
    assert base.requests.maj[-1]["status"] == "done"
    assert base.requests.maj[-1]["extracted"]["_cache_ia"].startswith("2026-10-06")


def test_absence_de_cache_appelle_l_ia_puis_ecrit_le_resultat():
    base, ia, lire, ecrire = asyncio.run(_lancer(REQ, cache_lu=None))
    assert ia.await_count == 1 and ecrire.await_count == 1
    tenant, cle, source, extracted = ecrire.await_args.args
    assert tenant == "t1" and source == "texte" and extracted["confidence"] == 0.9
    assert base.requests.maj[-1]["status"] == "done"


def test_un_echec_n_est_jamais_mis_en_cache():
    base, ia, lire, ecrire = asyncio.run(_lancer(REQ, resultat_ia={"_error": "ReadTimeout"}))
    assert ecrire.await_count == 0
    assert base.requests.maj[-1]["status"] == "failed"


def test_un_resultat_douteux_est_ecrit_seulement_si_la_regle_l_accepte():
    # process_request délègue : l'écriture est tentée, c'est cache_ia.ecrire qui refuse < 0.6.
    assert cache_ia.cachable({**BON, "confidence": 0.4}) is False


def test_retraiter_retire_l_entree_du_cache_avant_la_mise_en_file():
    invalider = AsyncMock()
    reserver = AsyncMock()
    file = AsyncMock()

    class _Col:
        async def find_one(self, *a, **k):
            return dict(REQ)

        async def update_one(self, *a, **k):
            return None

    class _Db:
        requests = _Col()

    class _Fond:
        def add_task(self, *a, **k):
            pass

    with patch.object(server, "db", _Db()), patch.object(server.quotas, "reserver", new=reserver), \
         patch.object(server, "get_tenant_ai_settings", new=AsyncMock(return_value=REGLAGES)), \
         patch.object(server, "_redis_sync", return_value=None), \
         patch.object(server._extraction_queue, "put", new=file), \
         patch.object(cache_ia, "invalider", new=invalider):
        cu = type("CU", (), {"tenant_id": "t1", "email": "a@b.fr"})()
        sortie = asyncio.run(server.reprocess_request("r1", _Fond(), cu))
    assert sortie["status"] == "queued"
    assert invalider.await_count == 1
    assert invalider.await_args.args == ("t1", cache_ia.cle_demande(REQ, REGLAGES)[1])
