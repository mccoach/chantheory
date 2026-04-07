# backend/routers/candles.py
# ==============================
# /api/candles 路由（正式版）
#
# 改动：
#   - 强制要求 market + code 双键
#   - 增加 refresh_interval_seconds（int 语义版）
#       * 0   = 静态查看，不自动刷新
#       * >=1 = 自动刷新周期（秒）
#   - 增加缓存释放接口：
#       POST /api/candles/cache/release
# ==============================

from __future__ import annotations

import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from backend.services.market import get_candles
from backend.services.market_cache import get_market_cache
from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("candles")
router = APIRouter(prefix="/api", tags=["candles"])


class ReleaseCacheRequest(BaseModel):
    market: str
    code: str
    freq: str


def _normalize_refresh_interval_seconds(raw: Optional[int]) -> Optional[int]:
    """
    refresh_interval_seconds 统一语义：
      - None / 0 -> 静态查看，不自动刷新
      - >=1      -> 自动刷新周期（秒）
      - <0       -> 归一化为 None
    """
    if raw is None:
        return None

    try:
        val = int(raw)
    except Exception:
        return None

    if val <= 0:
        return None

    return val


@router.get("/candles")
async def api_candles(
    request: Request,
    code: str = Query(..., description="证券代码，如 600519"),
    market: str = Query(..., description="市场代码：SH / SZ / BJ"),
    freq: str = Query("1d", description="频率：1m|5m|15m|30m|60m|1d|1w|1M"),
    adjust: str = Query(
        "none",
        description="复权方式：none(不复权) | qfq(前复权) | hfq(后复权)",
    ),
    refresh_interval_seconds: int = Query(
        0,
        description="页面自动刷新周期（秒）。0=静态查看，>=1=自动刷新",
    ),
    trace_id: Optional[str] = Query(None, description="客户端追踪ID（可选）"),
):
    tid = request.headers.get("x-trace-id") or trace_id
    t0 = time.time()

    refresh_interval_seconds_norm = _normalize_refresh_interval_seconds(
        refresh_interval_seconds
    )

    log_event(
        logger=_LOG,
        service="candles",
        level="INFO",
        file=__file__,
        func="api_candles",
        line=0,
        trace_id=tid,
        event="api.candles.start",
        message="incoming /api/candles",
        extra={
            "category": "api",
            "action": "start",
            "request": {
                "endpoint": "/api/candles",
                "method": "GET",
                "query": {
                    "code": code,
                    "market": market,
                    "freq": freq,
                    "adjust": adjust,
                    "refresh_interval_seconds_raw": refresh_interval_seconds,
                    "refresh_interval_seconds": refresh_interval_seconds_norm,
                },
            },
        },
    )

    try:
        resp = await get_candles(
            symbol=code,
            market=market,
            freq=freq,
            adjust=adjust,
            refresh_interval_seconds=refresh_interval_seconds_norm,
            trace_id=tid,
        )

        rows = int(resp.get("meta", {}).get("all_rows") or 0)
        log_event(
            logger=_LOG,
            service="candles",
            level="INFO",
            file=__file__,
            func="api_candles",
            line=0,
            trace_id=tid,
            event="api.candles.done",
            message="served /api/candles",
            extra={
                "category": "api",
                "action": "done",
                "duration_ms": int((time.time() - t0) * 1000),
                "result": {"rows": rows, "status_code": 200},
            },
        )
        return resp
    except Exception as e:
        log_event(
            logger=_LOG,
            service="candles",
            level="ERROR",
            file=__file__,
            func="api_candles",
            line=0,
            trace_id=tid,
            event="api.candles.fail",
            message="failed /api/candles",
            extra={
                "category": "api",
                "action": "fail",
                "error_code": "API_CANDLES_FAIL",
                "error_message": str(e),
            },
        )
        raise http_500_from_exc(e, trace_id=tid)


@router.post("/candles/cache/release")
async def api_release_candles_cache(
    request: Request,
    payload: ReleaseCacheRequest,
) -> Dict[str, Any]:
    tid = request.headers.get("x-trace-id")
    try:
        cache = get_market_cache()
        released = cache.release(
            market=str(payload.market or "").strip().upper(),
            code=str(payload.code or "").strip(),
            request_freq=str(payload.freq or "").strip(),
        )
        return {
            "ok": True,
            "released": bool(released),
            "message": "cache released" if released else "cache not found, ignored",
        }
    except Exception as e:
        raise http_500_from_exc(e, trace_id=tid)
