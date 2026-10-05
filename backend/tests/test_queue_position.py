"""La lecture d'une demande en attente ne doit pas lever sur le filtre $lt."""
import asyncio
from types import SimpleNamespace

from models_sql import Request
from pg_adapter import _build_where


def test_queued_request_position_uses_bound_tenant_filter(monkeypatch):
    import server

    row = {"id": "R", "tenant_id": "T", "status": "queued",
           "created_at": "2026-10-05T00:00:00+00:00"}
    captured = {}

    async def find_one(flt, *args):
        assert flt == {"id": "R", "tenant_id": "T"}
        return dict(row)

    async def count_documents(flt):
        compiled = _build_where(Request, flt).compile()
        captured.update(sql=str(compiled), values=list(compiled.params.values()))
        return 2

    async def to_list(*args):
        return []

    monkeypatch.setattr(server, "db", SimpleNamespace(
        requests=SimpleNamespace(find_one=find_one, count_documents=count_documents),
        quotes=SimpleNamespace(find=lambda *args: SimpleNamespace(to_list=to_list)),
    ))
    result = asyncio.run(server.get_request("R", SimpleNamespace(tenant_id="T")))
    assert result["queue_position"] == 3
    assert "tenant_id" in captured["sql"] and "created_at <" in captured["sql"]
    assert "T" in captured["values"] and row["created_at"] in captured["values"]
