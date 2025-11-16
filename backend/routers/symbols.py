# backend/routers/symbols.py
# ==============================
# 说明：符号索引路由（V7.0 - 带档案信息版）
# 改动：
#   - GET /api/symbols/index 改为 JOIN symbol_profile
#   - 返回完整档案字段（total_shares/float_shares/listing_date/industry/region/concepts）
# ==============================

from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Query, Request
from typing import Dict, Any, Optional
from datetime import datetime

from backend.utils.errors import http_500_from_exc
from backend.db.connection import get_conn
from backend.utils.logger import get_logger, log_event
from backend.settings import DATA_TYPE_DEFINITIONS

router = APIRouter(prefix="/api/symbols", tags=["symbols"])
_LOG = get_logger("symbols.router")

@router.get("/index")
async def api_get_symbol_index(
    request: Request,
    refresh: Optional[int] = Query(0, description="传 1 可后台触发刷新"),
) -> Dict[str, Any]:
    """
    返回标的索引（带档案信息）
    
    返回字段：
      索引字段：symbol, name, market, type, listing_date, status, updated_at
      档案字段：total_shares, float_shares, industry, region, concepts
    """
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
        
        # ===== 核心修改：JOIN symbol_profile =====
        db_items = await asyncio.to_thread(_select_symbol_index_with_profile)
        
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
    """手动触发标的列表刷新（会判断缺口）"""
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

@router.post("/refresh-force")
async def api_force_refresh_symbol_index(request: Request) -> Dict[str, Any]:
    """
    强制刷新标的列表（绕过缺口判断）
    
    用途：
      - 用户发现个别标的缺失时手动触发
      - 直接调用同步函数，不走任务队列
      - 不判断缺口，总是执行完整同步
    """
    tid = request.headers.get("x-trace-id")
    
    log_event(
        logger=_LOG,
        service="symbols.router",
        level="INFO",
        file=__file__,
        func="api_force_refresh_symbol_index",
        line=0,
        trace_id=tid,
        event="api.write.start",
        message="POST /symbols/refresh-force（强制模式）"
    )
    
    try:
        from backend.services.symbol_sync import sync_all_symbols
        
        _LOG.info("[强制刷新] 绕过缺口判断，直接执行同步")
        
        result = await sync_all_symbols()
        
        resp = {
            "ok": True,
            "message": "强制刷新完成",
            "result": result,
            "trace_id": tid
        }
        
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="INFO",
            file=__file__,
            func="api_force_refresh_symbol_index",
            line=0,
            trace_id=tid,
            event="api.write.done",
            message="POST /symbols/refresh-force done",
            extra={"success": result.get('success'), "total": result.get('total_in_db')}
        )
        
        return resp
        
    except Exception as e:
        log_event(
            logger=_LOG,
            service="symbols.router",
            level="ERROR",
            file=__file__,
            func="api_force_refresh_symbol_index",
            line=0,
            trace_id=tid,
            event="api.write.fail",
            message="POST /symbols/refresh-force failed",
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

# ===== 辅助函数：带档案信息的查询 =====
def _select_symbol_index_with_profile() -> list:
    """
    查询标的索引（LEFT JOIN symbol_profile）
    
    Returns:
        List[Dict]: 包含档案信息的标的列表
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
    SELECT 
        s.symbol,
        s.name,
        s.market,
        s.type,
        s.listing_date,
        s.status,
        s.updated_at,
        p.total_shares,
        p.float_shares,
        p.industry,
        p.region,
        p.concepts
    FROM symbol_index s
    LEFT JOIN symbol_profile p ON s.symbol = p.symbol
    ORDER BY s.symbol ASC;
    """)
    
    rows = cur.fetchall()
    
    results = []
    for row in rows:
        result = dict(row)
        
        # 解析 concepts（JSON字符串 → 列表）
        if result.get('concepts'):
            try:
                result['concepts'] = json.loads(result['concepts'])
            except (json.JSONDecodeError, TypeError):
                result['concepts'] = []
        else:
            result['concepts'] = []
        
        results.append(result)
    
    return results

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