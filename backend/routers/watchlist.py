# backend/routers/watchlist.py
# ==============================
# V8.1 - 自选池 Task/Job/SSE 双主键最终版
#
# 改动：
#   - watchlist 正式升级为 (symbol, market) 双主键体系
#   - 不再发布 "watchlist_updated" 自定义事件
#   - 每次添加/删除自选都视为一个 Task(type='watchlist_update', scope='symbol')
#   - Job 拆解与 SSE(job_done/task_done) 完全由 data_recipes.run_watchlist_update 负责
#   - 路由只负责：
#       * 构造 Task（create_task）
#       * 调用配方 run_watchlist_update(Task)
#       * 将结果转为 HTTP 响应 / HTTPException
#
# 最终接口：
#   - GET    /api/watchlist
#   - POST   /api/watchlist              body: { symbol, market, tags?, sort_order? }
#   - DELETE /api/watchlist/{market}/{symbol}
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.services.task_model import create_task
from backend.services.data_recipes import run_watchlist_update
from backend.utils.logger import get_logger

_LOG = get_logger("watchlist")
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

class AddWatchlistRequest(BaseModel):
    symbol: str
    market: str
    tags: List[str] = []
    sort_order: int = 0

@router.get("")
async def get_watchlist(request: Request) -> Dict[str, Any]:
    """
    获取自选池（带标的详细信息，双主键版）
    """
    try:
        from backend.db.watchlist import select_user_watchlist_with_details

        items = await asyncio.to_thread(select_user_watchlist_with_details)
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def add_to_watchlist(
    request: Request,
    payload: AddWatchlistRequest,
) -> Dict[str, Any]:
    """
    添加到自选池（通过 Task/Job 配方执行）
    """
    tid = request.headers.get("x-trace-id")
    symbol = str(payload.symbol or "").strip()
    market = str(payload.market or "").strip().upper()

    task = create_task(
        type="watchlist_update",
        scope="symbol",
        symbol=symbol,
        market=market,
        freq=None,
        adjust="none",
        trace_id=tid,
        params={
            "action": "add",
            "tags": payload.tags,
            "sort_order": payload.sort_order,
        },
        source="api/watchlist[POST]",
    )

    result = await run_watchlist_update(task)

    status = result.get("status")
    error_code = result.get("error_code")
    error_message = result.get("error_message")
    items = result.get("items") or []

    if status != "success":
        if error_code == "WATCHLIST_SYMBOL_NOT_FOUND":
            raise HTTPException(status_code=400, detail=error_message or "标的不存在")
        if error_code == "WATCHLIST_PARAM_ERROR":
            raise HTTPException(status_code=400, detail=error_message or "参数错误")
        if error_code == "WATCHLIST_INSERT_FAILED":
            raise HTTPException(status_code=400, detail=error_message or "添加失败")
        if error_code == "WATCHLIST_ACTION_ERROR":
            raise HTTPException(status_code=400, detail=error_message or "action 非法")
        if error_code == "WATCHLIST_EXCEPTION":
            raise HTTPException(status_code=500, detail=error_message or "服务异常")

        raise HTTPException(status_code=500, detail=error_message or "添加失败")

    _LOG.info("[自选池] 已添加 %s.%s", market, symbol)
    return {"ok": True, "items": items}

@router.delete("/{market}/{symbol}")
async def remove_from_watchlist(
    request: Request,
    market: str,
    symbol: str,
) -> Dict[str, Any]:
    """
    从自选池移除（通过 Task/Job 配方执行）
    """
    tid = request.headers.get("x-trace-id")
    mkt = str(market or "").strip().upper()
    sym = str(symbol or "").strip()

    task = create_task(
        type="watchlist_update",
        scope="symbol",
        symbol=sym,
        market=mkt,
        freq=None,
        adjust="none",
        trace_id=tid,
        params={
            "action": "remove",
        },
        source="api/watchlist[DELETE]",
    )

    result = await run_watchlist_update(task)

    status = result.get("status")
    error_code = result.get("error_code")
    error_message = result.get("error_message")
    items = result.get("items") or []

    if status != "success":
        if error_code == "WATCHLIST_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error_message or "标的不在自选池中")
        if error_code == "WATCHLIST_PARAM_ERROR":
            raise HTTPException(status_code=400, detail=error_message or "参数错误")
        if error_code == "WATCHLIST_ACTION_ERROR":
            raise HTTPException(status_code=400, detail=error_message or "action 非法")
        if error_code == "WATCHLIST_EXCEPTION":
            raise HTTPException(status_code=500, detail=error_message or "服务异常")

        raise HTTPException(status_code=500, detail=error_message or "移除失败")

    _LOG.info("[自选池] 已移除 %s.%s", mkt, sym)
    return {"ok": True, "items": items}