"""2026-08-23 : filet de securite pour la file durable Redis/RQ.

Verifie _watchdog_reprocess_if_stuck (server.py) sans base de donnees ni
Redis reels -- alternative CODE au risque "REDIS_URL renseignee sans worker
actif = demande bloquee indefiniment sur 'received'" identifie lors de la
revue de la PR #44. Patch la methode de classe _Collection.update_one
(pg_adapter.py) plutot que l'instance db.requests : PGDatabase.__getattr__
cree une nouvelle _Collection a chaque acces, donc patcher une instance ne
toucherait jamais l'appel reel dans le code de production.
"""
import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, "/app/backend")
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
import server  # noqa: E402
import pg_adapter  # noqa: E402


class _FakeUpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


@pytest.mark.asyncio
async def test_watchdog_processes_when_no_worker_claimed_it():
    """Aucun worker n'a touche la demande (matched_count=1 sur la prise
    atomique) -> le watchdog doit basculer le statut lui-meme ET appeler
    process_request en secours."""
    with patch.object(pg_adapter._Collection, "update_one",
                       new=AsyncMock(return_value=_FakeUpdateResult(1))) as mock_update, \
         patch.object(server.asyncio, "sleep", new=AsyncMock()), \
         patch.object(server, "process_request", new=AsyncMock()) as mock_process, \
         patch.object(server, "logger"):
        await server._watchdog_reprocess_if_stuck("req-1", "tenant-1")

    assert mock_update.await_count == 1
    filt, _update = mock_update.await_args.args
    assert filt == {"id": "req-1", "tenant_id": "tenant-1", "status": "received"}
    assert mock_process.await_count == 1


@pytest.mark.asyncio
async def test_watchdog_noop_when_worker_already_claimed_it():
    """Un vrai worker RQ a deja bascule le statut sur 'processing' avant le
    reveil du watchdog (matched_count=0 sur la prise atomique) -> AUCUN
    appel a process_request, pour ne jamais retraiter la meme demande deux
    fois en parallele."""
    with patch.object(pg_adapter._Collection, "update_one",
                       new=AsyncMock(return_value=_FakeUpdateResult(0))) as mock_update, \
         patch.object(server.asyncio, "sleep", new=AsyncMock()), \
         patch.object(server, "process_request", new=AsyncMock()) as mock_process, \
         patch.object(server, "logger"):
        await server._watchdog_reprocess_if_stuck("req-2", "tenant-1")

    assert mock_update.await_count == 1
    assert mock_process.await_count == 0
