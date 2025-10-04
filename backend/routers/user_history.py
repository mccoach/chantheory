# backend/routers/user_history.py
# ==============================
# 说明：标的框历史记录路由
# - GET    /api/user/history?limit=50     查询最近历史
# - POST   /api/user/history              追加一条历史 {symbol,freq?}
# - DELETE /api/user/history              清空历史（谨慎使用）
# ==============================

from __future__ import annotations

from fastapi import APIRouter, Query, Body, Request
from typing import Dict, Any, Optional

from backend.services.user_history import add_history, list_history, clear_all
from backend.utils.errors import http_500_from_exc

router = APIRouter(prefix="/api/user", tags=["user-history"])

@router.get("/history")
def api_list_history(request: Request, limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        resp = list_history(limit=limit)
        resp["trace_id"] = tid
        return resp
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/history")
def api_add_history(request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        symbol = str(payload.get("symbol", "")).strip()
        freq = payload.get("freq")
        resp = add_history(symbol, freq=freq, source="ui")
        resp["trace_id"] = tid
        return resp
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)

@router.delete("/history")
def api_clear_history(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        resp = clear_all()
        resp["trace_id"] = tid
        return resp
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)
