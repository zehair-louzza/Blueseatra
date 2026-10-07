"""Tâches IA asynchrones (ia_runs.py) : lancement, point de contrôle, arrêt, délai, reprise, repli."""
import asyncio
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ia_runs  # noqa: E402

URL = "http://vps.test"
H = {"Authorization": "Bearer x"}


class FauxVps:
    """Imite /v1/runs : liste d'états successifs renvoyés par GET."""

    def __init__(self, etats, creation=200):
        self.etats, self.creation = list(etats), creation
        self.posts, self.stops, self.cles = 0, [], []

    def handler(self, request: httpx.Request):
        p = request.url.path
        if request.method == "POST" and p == "/v1/runs":
            self.posts += 1
            self.cles.append(request.headers.get("Idempotency-Key"))
            if self.creation != 200:
                return httpx.Response(self.creation, text="non")
            return httpx.Response(200, json={"run_id": "run_1", "status": "started"})
        if request.method == "POST" and p.endswith("/stop"):
            self.stops.append(p)
            return httpx.Response(200, json={"status": "stopping"})
        if request.method == "GET":
            e = self.etats.pop(0) if len(self.etats) > 1 else self.etats[0]
            return httpx.Response(200, json=e)
        return httpx.Response(404)


@pytest.fixture
def vps(monkeypatch):
    def fabrique(etats, creation=200):
        f = FauxVps(etats, creation)
        vrai = httpx.AsyncClient
        monkeypatch.setattr(ia_runs.httpx, "AsyncClient",
                            lambda **kw: vrai(transport=httpx.MockTransport(f.handler), **kw))
        return f
    return fabrique


async def _vite(_):
    await asyncio.sleep(0)


def _corps():
    return ia_runs.construire_corps("gpt-oss:20b", "custom:ollama", "sys", "bonjour")


def test_corps_texte_et_image():
    assert _corps() == {"input": "bonjour", "model": "gpt-oss:20b", "provider": "custom:ollama", "instructions": "sys"}
    c = ia_runs.construire_corps("m", "p", None, "t", image_b64="AAA")
    assert "instructions" not in c
    assert c["input"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,AAA")


@pytest.mark.asyncio
async def test_termine_et_signale_les_etapes(vps):
    f = vps([{"status": "running"}, {"status": "completed", "output": " {\"a\":1} "}])
    vus = []

    async def suivi(infos):
        vus.append(infos)

    with ia_runs.demande("r1", "n1", suivi):
        sortie = await ia_runs.executer(URL, H, _corps(), role="structuration", delai=60, dormir=_vite)
    assert sortie == '{"a":1}'
    assert [v["statut"] for v in vus] == ["started", "running", "completed"]
    assert f.cles[0] and len(f.cles[0]) == 64
    assert ia_runs.runs_actifs("r1") == {}


@pytest.mark.asyncio
async def test_meme_tentative_meme_cle_nouvelle_tentative_autre_cle(vps):
    f = vps([{"status": "completed", "output": "ok"}])
    for nonce in ("n1", "n1", "n2"):
        with ia_runs.demande("r2", nonce):
            await ia_runs.executer(URL, H, _corps(), role="x", delai=60, dormir=_vite)
    assert f.cles[0] == f.cles[1] != f.cles[2]


@pytest.mark.asyncio
async def test_delai_depasse_arrete_la_tache_sur_le_vps(vps):
    f = vps([{"status": "running"}])
    with ia_runs.demande("r3", "n"):
        with pytest.raises(ia_runs.DelaiDepasse):
            await ia_runs.executer(URL, H, _corps(), role="x", delai=0, dormir=_vite)
    assert f.stops == ["/v1/runs/run_1/stop"]


@pytest.mark.asyncio
async def test_arret_utilisateur_pendant_l_attente(vps):
    f = vps([{"status": "running"}])

    async def dormir(_):
        await ia_runs.arreter_demande("r4")

    with ia_runs.demande("r4", "n"):
        with pytest.raises(ia_runs.RunAnnule):
            await ia_runs.executer(URL, H, _corps(), role="x", delai=60, dormir=dormir)
    assert f.stops
    ia_runs.reinitialiser("r4")
    assert not ia_runs.est_arretee("r4")


@pytest.mark.asyncio
async def test_arret_via_arreter_demande_stoppe_les_runs_actifs(vps):
    f = vps([{"status": "running"}])

    async def dormir(_):
        await asyncio.sleep(0.01)

    async def lecture():
        with ia_runs.demande("r5", "n"):
            return await ia_runs.executer(URL, H, _corps(), role="x", delai=60, dormir=dormir)

    t = asyncio.create_task(lecture())
    await asyncio.sleep(0.05)
    assert "run_1" in ia_runs.runs_actifs("r5")
    assert await ia_runs.arreter_demande("r5") == 1
    with pytest.raises(ia_runs.RunAnnule):
        await t
    assert f.stops


@pytest.mark.asyncio
async def test_annulation_asyncio_arrete_la_tache(vps):
    f = vps([{"status": "running"}])

    async def dormir(_):
        await asyncio.sleep(5)

    async def lecture():
        with ia_runs.demande("r6", "n"):
            await ia_runs.executer(URL, H, _corps(), role="x", delai=60, dormir=dormir)

    t = asyncio.create_task(lecture())
    await asyncio.sleep(0.05)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert f.stops
    assert ia_runs.runs_actifs("r6") == {}


@pytest.mark.asyncio
async def test_echec_vps(vps):
    vps([{"status": "failed", "error": "boom"}])
    with ia_runs.demande("r7", "n"):
        with pytest.raises(ia_runs.RunEchec):
            await ia_runs.executer(URL, H, _corps(), role="x", delai=60, dormir=_vite)


@pytest.mark.asyncio
async def test_interface_absente_demande_le_repli(vps):
    vps([{"status": "completed", "output": "x"}], creation=404)
    with ia_runs.demande("r8", "n"):
        with pytest.raises(ia_runs.RunsIndisponible):
            await ia_runs.executer(URL, H, _corps(), role="x", delai=60, dormir=_vite)


@pytest.mark.asyncio
async def test_point_de_controle_tache_inconnue(vps):
    vps([{"status": "completed"}])
    f = vps  # noqa: F841
    e = await ia_runs.etat(URL, H, "run_1")
    assert e["status"] == "completed"


# ---------- branchement dans _hermes_chat ----------

@pytest.mark.asyncio
async def test_hermes_chat_utilise_les_taches_dans_une_demande(vps, monkeypatch):
    import ai_service
    monkeypatch.setattr(ai_service, "HERMES_GATEWAY_URL", URL)
    f = vps([{"status": "completed", "output": "reponse"}])
    with ia_runs.demande("r9", "n"):
        assert await ai_service._hermes_chat("gpt-oss:20b", "sys", "q", role="t") == "reponse"
    assert f.posts == 1


@pytest.mark.asyncio
async def test_hermes_chat_repli_si_interface_absente(monkeypatch):
    import ai_service
    monkeypatch.setattr(ai_service, "HERMES_GATEWAY_URL", URL)
    appels = []
    vrai = httpx.AsyncClient

    def handler(request):
        appels.append(request.url.path)
        if request.url.path == "/v1/runs":
            return httpx.Response(404)
        return httpx.Response(200, json={"choices": [{"message": {"content": "via chat"}}]})

    monkeypatch.setattr(ia_runs.httpx, "AsyncClient", lambda **kw: vrai(transport=httpx.MockTransport(handler), **kw))
    with ia_runs.demande("r10", "n"):
        assert await ai_service._hermes_chat("gpt-oss:20b", "sys", "q", role="t") == "via chat"
    assert appels == ["/v1/runs", "/v1/chat/completions"]


@pytest.mark.asyncio
async def test_hermes_chat_hors_demande_reste_sur_chat_completions(monkeypatch):
    import ai_service
    monkeypatch.setattr(ai_service, "HERMES_GATEWAY_URL", URL)
    appels = []
    vrai = httpx.AsyncClient

    def handler(request):
        appels.append(request.url.path)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(ia_runs.httpx, "AsyncClient", lambda **kw: vrai(transport=httpx.MockTransport(handler), **kw))
    assert await ai_service._hermes_chat("gpt-oss:20b", "sys", "q", role="t") == "ok"
    assert appels == ["/v1/chat/completions"]
