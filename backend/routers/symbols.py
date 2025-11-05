# backend/routers/symbols.py
# ==============================
# 说明：符号索引路由（V4.0 - 基于新架构）
# 改动：
#   - 移除废弃依赖
#   - 改用声明式API触发刷新
# ==============================

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query, Request
from typing import Dict, Any, Optional

from backend.utils.errors import http_500_from_exc
from backend.db import select_symbol_index
from backend.utils.logger import get_logger, log_event
from backend.settings import DATA_TYPE_DEFINITIONS


router = APIRouter(prefix="/api/symbols", tags=["symbols"])
_LOG = get_logger("symbols.router")

@router.get("/index")
async def api_get_symbol_index(
    request: Request,
    refresh: Optional[int] = Query(0, description="传 1 可后台触发刷新"),
) -> Dict[str, Any]:
    """返回当前索引，可选触发后台刷新"""
    tid = request.headers.get("x-trace-id")
    
    log_event(
        logger=_LOG,
        service="symbols.router",
        level="INFO",
        file=__file__,
        func="api_get_symbol_index",
        line=0,
        trace_id=tid,
        event="api.read.start",
        message="GET /symbols/index",
        extra={"refresh": refresh}
    )
    
    try:
        if refresh:
            await trigger_symbol_index_refresh()
        
        db_items = await asyncio.to_thread(select_symbol_index)
        
        payload = {
            "ok": True,
            "rows": len(db_items),
            "items": db_items,
            "trace_id": tid,
        }
        
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="INFO",
            file=__file__,
            func="api_get_symbol_index",
            line=0,
            trace_id=tid,
            event="api.read.done",
            message="GET /symbols/index done",
            extra={"rows": len(db_items)}
        )
        
        return payload
        
    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="ERROR",
            file=__file__,
            func="api_get_symbol_index",
            line=0,
            trace_id=tid,
            event="api.read.fail",
            message="GET /symbols/index failed",
            extra={"error": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)

@router.post("/refresh")
async def api_refresh_symbol_index(request: Request) -> Dict[str, Any]:
    """手动触发标的列表刷新"""
    tid = request.headers.get("x-trace-id")
    
    log_event(
        logger=_LOG,
        service="symbols.router",
        level="INFO",
        file=__file__,
        func="api_refresh_symbol_index",
        line=0,
        trace_id=tid,
        event="api.write.start",
        message="POST /symbols/refresh"
    )
    
    try:
        await trigger_symbol_index_refresh()
        
        resp = {
            "ok": True,
            "message": "标的列表刷新已触发",
            "trace_id": tid
        }
        
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="INFO",
            file=__file__,
            func="api_refresh_symbol_index",
            line=0,
            trace_id=tid,
            event="api.write.done",
            message="POST /symbols/refresh done"
        )
        
        return resp
        
    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="ERROR",
            file=__file__,
            func="api_refresh_symbol_index",
            line=0,
            trace_id=tid,
            event="api.write.fail",
            message="POST /symbols/refresh failed",
            extra={"error": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)

@router.get("/summary")
async def api_symbols_summary(request: Request) -> Dict[str, Any]:
    """标的列表摘要统计"""
    tid = request.headers.get("x-trace-id")
    
    log_event(
        logger=_LOG,
        service="symbols.router",
        level="INFO",
        file=__file__,
        func="api_symbols_summary",
        line=0,
        trace_id=tid,
        event="api.read.start",
        message="GET /symbols/summary"
    )
    
    try:
        from backend.db.connection import get_conn
        
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT type, COUNT(*) AS n FROM symbol_index GROUP BY type ORDER BY n DESC;")
        by_type = [{"type": r[0], "n": r[1]} for r in cur.fetchall()]
        
        cur.execute("SELECT type, market, COUNT(*) AS n FROM symbol_index GROUP BY type, market ORDER BY n DESC;")
        by_type_market = [{"type": r[0], "market": r[1], "n": r[2]} for r in cur.fetchall()]
        
        payload = {
            "ok": True,
            "by_type": by_type,
            "by_type_market": by_type_market,
            "trace_id": tid
        }
        
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="INFO",
            file=__file__,
            func="api_symbols_summary",
            line=0,
            trace_id=tid,
            event="api.read.done",
            message="GET /symbols/summary done"
        )
        
        return payload
        
    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="ERROR",
            file=__file__,
            func="api_symbols_summary",
            line=0,
            trace_id=tid,
            event="api.read.fail",
            message="GET /symbols/summary failed",
            extra={"error": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)

async def trigger_symbol_index_refresh():
    """触发标的列表刷新（内部函数）"""
    from backend.services.data_requirement_parser import get_requirement_parser
    from backend.services.priority_queue import get_priority_queue
    
    parser = get_requirement_parser()
    queue = get_priority_queue()
    
    requirements = [{
        'scope': 'global',
        'includes': [{
            'type': 'symbol_index',
            'priority': DATA_TYPE_DEFINITIONS['symbol_index']['priority']
        }]
    }]
    
    tasks = parser.parse_requirements(requirements)
    
    for task in tasks:
        await queue.enqueue(task)
    
    _LOG.info(f"[手动刷新] 已生成 {len(tasks)} 个标的列表刷新任务")
