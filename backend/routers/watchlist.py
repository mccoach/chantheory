# backend/routers/watchlist.py
# ==============================
# 说明：自选池路由（简化）
# - GET    /api/watchlist                查看自选与状态
# - POST   /api/watchlist                增加标的 {symbol}
# - DELETE /api/watchlist/{symbol}       移除标的
# - POST   /api/watchlist/sync           触发全量后台同步（仅 1d 近端）
# - POST   /api/watchlist/sync/{symbol}  触发单标后台同步（仅 1d 近端）
# ==============================

from __future__ import annotations

from fastapi import APIRouter, Body, Path, Request
from typing import Dict, Any

from backend.services.watchlist import (
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    sync_all_async, sync_symbol_async, get_status_snapshot
)
from backend.utils.errors import http_500_from_exc

router = APIRouter(prefix="/api", tags=["watchlist"])

@router.get("/watchlist")
def api_get_watchlist(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        return {"ok": True, "items": get_watchlist(), "status": get_status_snapshot(), "trace_id": tid}
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/watchlist")
def api_add_watchlist(request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        symbol = str(payload.get("symbol","")).strip()
        if not symbol:
            return {"ok": False, "error": "symbol is required", "trace_id": tid}
        items = add_to_watchlist(symbol)
        return {"ok": True, "items": items, "trace_id": tid}
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.delete("/watchlist/{symbol}")
def api_del_watchlist(request: Request, symbol: str = Path(...)) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        items = remove_from_watchlist(str(symbol).strip())
        return {"ok": True, "items": items, "trace_id": tid}
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/watchlist/sync")
def api_sync_all(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        summary = sync_all_async()
        return {"ok": True, "summary": summary, "trace_id": tid}
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/watchlist/sync/{symbol}")
def api_sync_one(request: Request, symbol: str = Path(...)) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        ok = sync_symbol_async(str(symbol).strip())
        return {"ok": ok, "trace_id": tid}
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)
