# E:\AppProject\ChanTheory\backend\routers\candles.py
# ==============================
# 说明：/api/candles 路由（V5.1 - 带 adjust 参数）
# 改动：
#   - 新增 adjust 参数：'none' | 'qfq' | 'hfq'
#   - 其余保持“纯数据版”语义不变
# ==============================

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Query, Request
from backend.services.market import get_candles
from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("candles")
router = APIRouter(prefix="/api", tags=["candles"])


@router.get("/candles")
async def api_candles(
    request: Request,
    code: str = Query(..., description="股票/基金代码，如 600519 或 510300"),
    freq: str = Query("1d", description="频率：1m|5m|15m|30m|60m|1d|1w|1M"),
    adjust: str = Query(
        "none",
        description="复权方式：none(不复权) | qfq(前复权) | hfq(后复权)",
    ),
    trace_id: Optional[str] = Query(None, description="客户端追踪ID（可选）"),
):
    """
    获取K线数据（纯数据版，带 adjust 维度）
    
    返回：
      - K线原始数据（不计算技术指标）
      - meta 中包含 adjust 信息
    """
    tid = request.headers.get("x-trace-id") or trace_id
    t0 = time.time()
    
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
                    "freq": freq,
                    "adjust": adjust,
                },
            },
        },
    )
    
    try:
        resp = await get_candles(
            symbol=code,
            freq=freq,
            adjust=adjust,
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