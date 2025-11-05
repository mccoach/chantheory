# E:\AppProject\ChanTheory\backend\routers\candles.py
# ==============================
# 说明：/api/candles 路由（V4.0 - 极简版）
# 改动：
#   - 删除复权参数
#   - 删除窗口截取参数（交给前端）
#   - 删除数据源路由参数
# ==============================

from __future__ import annotations

import time
import json
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
    code: str = Query(..., description="股票代码，如 600519"),
    freq: str = Query("1d", description="频率：1m|5m|15m|30m|60m|1d|1w|1M"),
    include: Optional[str] = Query(None, description="指标：ma,macd,kdj,rsi,boll,vol（逗号分隔）"),
    ma_periods: Optional[str] = Query(None, description="MA 周期，JSON 字符串：'{\"MA5\":12, \"MA10\":21}'"),
    trace_id: Optional[str] = Query(None, description="客户端追踪ID（可选）"),
):
    """
    获取K线数据
    
    返回：
      - 不复权的原始价格
      - 全量数据（窗口截取由前端处理）
      - 可选指标
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
                    "include": include
                }
            }
        }
    )
    
    try:
        include_set = set([s.strip().lower() for s in (include or "").split(",") if s and s.strip()])
        ma_periods_dict = {}
        if ma_periods:
            try:
                ma_periods_dict = json.loads(ma_periods)
                if not isinstance(ma_periods_dict, dict):
                    ma_periods_dict = {}
            except json.JSONDecodeError:
                ma_periods_dict = {}
        
        resp = await get_candles(
            symbol=code,
            freq=freq,
            include=include_set,
            ma_periods_map=ma_periods_dict,
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
                "result": {"rows": rows, "status_code": 200}
            }
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
                "error_message": str(e)
            }
        )
        raise http_500_from_exc(e, trace_id=tid)
