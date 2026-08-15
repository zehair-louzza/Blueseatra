"""Remote MCP (Streamable HTTP JSON-RPC) for Perplexity Computer.

Endpoint: POST /mcp
Auth: Authorization: Bearer <MCP_API_KEY>  or  X-Api-Key: <MCP_API_KEY>
Docs: https://www.perplexity.ai/help-center/en/articles/13915507-adding-custom-remote-connectors
"""
from __future__ import annotations

import os
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from pg_adapter import PGDatabase

logger = logging.getLogger("blueseatra.mcp")
db = PGDatabase()
router = APIRouter()

PROTOCOL = "2025-03-26"
SERVER_NAME = "blueseatra"
SERVER_VERSION = "1.0.0"


def _configured_key() -> str:
    return (os.environ.get("MCP_API_KEY") or "").strip()


def _tenant_id() -> str:
    return (os.environ.get("MCP_TENANT_ID") or "").strip()


def _unauthorized() -> JSONResponse:
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _rpc_error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _rpc_ok(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _check_auth(authorization: str | None, x_api_key: str | None) -> bool:
    expected = _configured_key()
    if not expected:
        return False
    if x_api_key and x_api_key.strip() == expected:
        return True
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip() == expected:
            return True
        if authorization.strip() == expected:
            return True
    return False


TOOLS = [
    {
        "name": "blueseatra_list_requests",
        "description": "Liste les dernières demandes de devis Blueseatra (tenant configuré).",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        },
    },
    {
        "name": "blueseatra_get_request",
        "description": "Détail d'une demande (texte source + extraction IA).",
        "inputSchema": {
            "type": "object",
            "properties": {"request_id": {"type": "string"}},
            "required": ["request_id"],
        },
    },
    {
        "name": "blueseatra_list_quotes",
        "description": "Liste les derniers devis (numéro, client, totaux, statut).",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        },
    },
    {
        "name": "blueseatra_search_catalog",
        "description": "Cherche un article dans le catalogue tarifaire actif.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["query"],
        },
    },
]


async def _tool_list_requests(limit: int = 15) -> Any:
    tid = _tenant_id()
    rows = await db.requests.find({"tenant_id": tid}, {"_id": 0, "file_b64": 0, "raw_text": 0}).sort(
        "created_at", -1
    ).to_list(limit)
    out = []
    for r in rows:
        ex = r.get("extracted") or {}
        out.append({
            "id": r.get("id"),
            "title": r.get("title"),
            "status": r.get("status"),
            "client": ex.get("donneur_d_ordre") or ex.get("client_name"),
            "created_at": r.get("created_at"),
            "error": r.get("error"),
        })
    return out


async def _tool_get_request(request_id: str) -> Any:
    tid = _tenant_id()
    r = await db.requests.find_one({"id": request_id, "tenant_id": tid}, {"_id": 0, "file_b64": 0})
    if not r:
        return {"error": "not_found"}
    return r


async def _tool_list_quotes(limit: int = 15) -> Any:
    tid = _tenant_id()
    rows = await db.quotes.find({"tenant_id": tid}, {"_id": 0, "lines": 0, "pricing_snapshot": 0}).sort(
        "created_at", -1
    ).to_list(limit)
    return [
        {
            "id": q.get("id"),
            "number": q.get("number"),
            "client": q.get("client"),
            "status": q.get("status"),
            "total_ht": q.get("total_ht"),
            "total_ttc": q.get("total_ttc"),
            "object": q.get("object"),
        }
        for q in rows
    ]


async def _tool_search_catalog(query: str, limit: int = 15) -> Any:
    tid = _tenant_id()
    cat = await db.catalogs.find_one(
        {"tenant_id": tid, "active_version_id": {"$ne": None}},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not cat:
        return {"error": "no_active_catalog"}
    items = await db.pricing_items.find(
        {"tenant_id": tid, "version_id": cat["active_version_id"]},
        {"_id": 0},
    ).to_list(2000)
    qn = (query or "").lower()
    hits = []
    for it in items:
        blob = " ".join(
            str(it.get(k) or "") for k in ("item_label", "item_code", "category", "label_norm")
        ).lower()
        if qn in blob:
            hits.append({
                "item_code": it.get("item_code"),
                "item_label": it.get("item_label"),
                "category": it.get("category"),
                "unit": it.get("unit"),
                "unit_price_ht": it.get("unit_price_ht"),
                "vat_rate": it.get("vat_rate"),
            })
        if len(hits) >= limit:
            break
    return {"catalog": cat.get("name"), "hits": hits}


async def _call_tool(name: str, arguments: dict) -> Any:
    arguments = arguments or {}
    if name == "blueseatra_list_requests":
        return await _tool_list_requests(int(arguments.get("limit") or 15))
    if name == "blueseatra_get_request":
        rid = arguments.get("request_id") or ""
        if not rid:
            raise ValueError("request_id required")
        return await _tool_get_request(rid)
    if name == "blueseatra_list_quotes":
        return await _tool_list_quotes(int(arguments.get("limit") or 15))
    if name == "blueseatra_search_catalog":
        q = arguments.get("query") or ""
        if not q:
            raise ValueError("query required")
        return await _tool_search_catalog(q, int(arguments.get("limit") or 15))
    raise ValueError(f"unknown tool: {name}")


async def _handle_rpc(msg: dict) -> dict | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "notifications/initialized" or str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        return _rpc_ok(req_id, {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method == "ping":
        return _rpc_ok(req_id, {})
    if method == "tools/list":
        return _rpc_ok(req_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            data = await _call_tool(name, args)
            return _rpc_ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, default=str)}],
                "isError": isinstance(data, dict) and data.get("error") in ("not_found", "no_active_catalog"),
            })
        except Exception as exc:
            logger.exception("mcp tool %s failed", name)
            return _rpc_ok(req_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
    return _rpc_error(req_id, -32601, f"method not found: {method}")


@router.api_route("/mcp", methods=["POST", "GET"])
async def mcp_endpoint(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
):
    if not _configured_key() or not _tenant_id():
        return JSONResponse({"error": "mcp_not_configured"}, status_code=503)
    if not _check_auth(authorization, x_api_key):
        return _unauthorized()
    if request.method == "GET":
        return JSONResponse({
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "transport": "streamable-http",
        })
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(_rpc_error(None, -32700, "parse error"), status_code=400)
    if isinstance(payload, list):
        results = []
        for item in payload:
            handled = await _handle_rpc(item)
            if handled is not None:
                results.append(handled)
        return JSONResponse(results)
    handled = await _handle_rpc(payload)
    if handled is None:
        return JSONResponse(status_code=202, content=None)
    return JSONResponse(handled)
