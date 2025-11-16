# backend/routers/factors.py
# ==============================
# 说明：复权因子查询路由
# 职责：提供前端查询复权因子的接口
# ==============================

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Query, Request

from backend.db.factors import select_factors
from backend.utils.time import parse_yyyymmdd
from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("factors")
router = APIRouter(prefix="/api", tags=["factors"])

@router.get("/factors")
async def api_get_factors(
    request: Request,
    symbol: str = Query(..., description="标的代码"),
    start_date: Optional[str] = Query(None, description="起始日期（YYYYMMDD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYYMMDD）"),
    trace_id: Optional[str] = Query(None, description="追踪ID"),
) -> Dict[str, Any]:
    """
    查询复权因子
    
    返回：
      - date: 日期（YYYYMMDD整数）
      - qfq_factor: 前复权因子
      - hfq_factor: 后复权因子
    """
    tid = request.headers.get("x-trace-id") or trace_id
    
    log_event(
        logger=_LOG,
        service="factors",
        level="INFO",
        file=__file__,
        func="api_get_factors",
        line=0,
        trace_id=tid,
        event="api.factors.start",
        message=f"查询复权因子 {symbol}",
        extra={"symbol": symbol, "start_date": start_date, "end_date": end_date}
    )
    
    try:
        # 解析日期参数
        start_ymd = parse_yyyymmdd(start_date) if start_date else None
        end_ymd = parse_yyyymmdd(end_date) if end_date else None
        
        # 查询因子
        factors = await asyncio.to_thread(
            select_factors,
            symbol=symbol,
            start_date=start_ymd,
            end_date=end_ymd
        )
        
        log_event(
            logger=_LOG,
            service="factors",
            level="INFO",
            file=__file__,
            func="api_get_factors",
            line=0,
            trace_id=tid,
            event="api.factors.done",
            message=f"返回 {len(factors)} 条因子",
            extra={"rows": len(factors)}
        )
        
        return {
            "ok": True,
            "factors": factors,
            "trace_id": tid
        }
        
    except Exception as e:
        log_event(
            logger=_LOG,
            service="factors",
            level="ERROR",
            file=__file__,
            func="api_get_factors",
            line=0,
            trace_id=tid,
            event="api.factors.fail",
            message=f"查询失败: {e}",
            extra={"error": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)