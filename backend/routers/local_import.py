# backend/routers/local_import.py
# ==============================
# 盘后数据导入 import 路由
#
# 正式接口：
#   - GET  /api/local-import/candidates
#   - POST /api/local-import/start
#   - GET  /api/local-import/status
#   - GET  /api/local-import/tasks?batch_id=...
#   - POST /api/local-import/cancel
#   - POST /api/local-import/retry
#
# 说明：
#   - SSE 为主状态同步链路
#   - 这些 HTTP 接口承担：
#       * 初始化快照
#       * 用户操作入口
#       * SSE 断连后的状态恢复与纠偏
# ==============================

from __future__ import annotations

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from backend.services.local_import.candidates import build_import_candidates_snapshot
from backend.services.local_import.repository import (
    build_status_snapshot,
    get_batch,
    list_tasks_for_batch,
)
from backend.services.local_import.orchestrator import (
    start_import_batch,
    cancel_import_batch,
    retry_import_batch,
)
from backend.utils.logger import get_logger, log_event
from backend.utils.errors import http_500_from_exc

router = APIRouter(prefix="/api/local-import", tags=["local-import"])
_LOG = get_logger("local_import.router")


class ImportSelectionItem(BaseModel):
    market: str
    symbol: str
    freq: str


class ImportStartRequest(BaseModel):
    items: List[ImportSelectionItem] = Field(..., min_length=1)


class BatchOpRequest(BaseModel):
    batch_id: str


@router.get("/candidates")
async def api_local_import_candidates(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    log_event(
        logger=_LOG,
        service="local_import.router",
        level="INFO",
        file=__file__,
        func="api_local_import_candidates",
        line=0,
        trace_id=tid,
        event="local_import.candidates.start",
        message="GET /api/local-import/candidates",
    )

    try:
        payload = build_import_candidates_snapshot()

        log_event(
            logger=_LOG,
            service="local_import.router",
            level="INFO",
            file=__file__,
            func="api_local_import_candidates",
            line=0,
            trace_id=tid,
            event="local_import.candidates.done",
            message="GET /api/local-import/candidates done",
            extra={"rows": len(payload.get("items") or [])},
        )
        return payload

    except Exception as e:
        log_event(
            logger=_LOG,
            service="local_import.router",
            level="ERROR",
            file=__file__,
            func="api_local_import_candidates",
            line=0,
            trace_id=tid,
            event="local_import.candidates.fail",
            message="GET /api/local-import/candidates failed",
            extra={"error": str(e)},
        )
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/start")
async def api_local_import_start(request: Request, payload: ImportStartRequest) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        items = []
        seen = set()

        for item in payload.items:
            market = str(item.market or "").strip().upper()
            symbol = str(item.symbol or "").strip()
            freq = str(item.freq or "").strip()

            if market not in ("SH", "SZ", "BJ"):
                return {
                    "ok": False,
                    "display_batch": None,
                    "queued_batches": [],
                    "ui_message": f"非法 market: {market}",
                }
            if not symbol or not symbol.isdigit():
                return {
                    "ok": False,
                    "display_batch": None,
                    "queued_batches": [],
                    "ui_message": f"非法 symbol: {symbol}",
                }
            if freq != "1d":
                return {
                    "ok": False,
                    "display_batch": None,
                    "queued_batches": [],
                    "ui_message": f"当前仅支持 freq=1d，收到: {freq}",
                }

            key = (market, symbol, freq)
            if key in seen:
                continue
            seen.add(key)

            items.append({
                "market": market,
                "symbol": symbol,
                "freq": freq,
            })

        if not items:
            return {
                "ok": False,
                "display_batch": None,
                "queued_batches": [],
                "ui_message": "items 不能为空",
            }

        resp = await start_import_batch(items)

        return {
            "ok": True,
            "display_batch": resp.get("display_batch"),
            "queued_batches": resp.get("queued_batches") or [],
            "ui_message": resp.get("ui_message"),
        }

    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.get("/status")
async def api_local_import_status(request: Request) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        snap = build_status_snapshot()
        return {
            "ok": True,
            "display_batch": snap.get("display_batch"),
            "queued_batches": snap.get("queued_batches") or [],
            "ui_message": snap.get("ui_message"),
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.get("/tasks")
async def api_local_import_tasks(
    request: Request,
    batch_id: str = Query(..., description="要查看任务列表的批次ID"),
) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    bid = str(batch_id or "").strip()

    try:
        batch = get_batch(bid)
        if not batch:
            return {
                "ok": True,
                "batch_id": bid,
                "items": [],
                "ui_message": "未找到对应批次",
            }

        items = list_tasks_for_batch(bid)
        return {
            "ok": True,
            "batch_id": bid,
            "items": items,
            "ui_message": None if items else "当前批次暂无任务列表",
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/cancel")
async def api_local_import_cancel(request: Request, payload: BatchOpRequest) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        resp = await cancel_import_batch(payload.batch_id)
        return {
            "ok": True,
            "display_batch": resp.get("display_batch"),
            "queued_batches": resp.get("queued_batches") or [],
            "ui_message": resp.get("ui_message"),
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/retry")
async def api_local_import_retry(request: Request, payload: BatchOpRequest) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")

    try:
        resp = await retry_import_batch(payload.batch_id)
        return {
            "ok": True,
            "display_batch": resp.get("display_batch"),
            "queued_batches": resp.get("queued_batches") or [],
            "ui_message": resp.get("ui_message"),
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)
