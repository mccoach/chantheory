# backend/routers/debug.py
# ==============================
# 说明：调试路由（V4.0 - 精简版）
# 保留功能：
#   1. 查看原始字段
#   2. 一键全量同步
# ==============================

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query, Request
from typing import Dict, Any, Optional
import importlib

from backend.utils.errors import http_500_from_exc
from backend.utils.time import normalize_date_range
from backend.utils.logger import get_logger, log_event
from backend.settings import settings, DATA_TYPE_DEFINITIONS

_LOG = get_logger("debug")

router = APIRouter(prefix="/api/debug", tags=["debug"])

def _lazy_import_ak():
    """懒加载 akshare"""
    return importlib.import_module("akshare")

@router.post("/sync-all")
async def trigger_full_sync_route(request: Request) -> Dict[str, Any]:
    """
    一键全量同步（调试用）
    
    功能：
      - 同步标的列表
      - 同步自选池数据（6个频率 + 档案 + 因子）
      - 同步全量档案补缺
    """
    tid = request.headers.get("x-trace-id")
    
    log_event(
        logger=_LOG,
        service="debug",
        level="INFO",
        file=__file__,
        func="trigger_full_sync_route",
        line=0,
        trace_id=tid,
        event="api.debug.sync_all.start",
        message="触发完整同步"
    )
    
    try:
        from backend.services.data_requirement_parser import get_requirement_parser
        from backend.services.priority_queue import get_priority_queue
        from backend.db.watchlist import select_user_watchlist
        
        parser = get_requirement_parser()
        queue = get_priority_queue()
        
        watchlist = await asyncio.to_thread(select_user_watchlist)
        watchlist_symbols = [w['symbol'] for w in watchlist]
        
        requirements = []
        
        # 1. 标的列表
        requirements.append({
            'scope': 'global',
            'includes': [{
                'type': 'symbol_index',
                'priority': DATA_TYPE_DEFINITIONS['symbol_index']['priority']
            }]
        })
        
        # 2. 自选池数据
        if watchlist_symbols:
            includes = []
            for freq in settings.sync_standard_freqs:
                dt_id = f'watchlist_kline_{freq}'
                includes.append({
                    'type': dt_id,
                    'freq': freq,
                    'priority': DATA_TYPE_DEFINITIONS[dt_id]['priority']
                })
            includes.append({'type': 'watchlist_profile', 'priority': DATA_TYPE_DEFINITIONS['watchlist_profile']['priority']})
            includes.append({'type': 'watchlist_factors', 'priority': DATA_TYPE_DEFINITIONS['watchlist_factors']['priority']})
            
            requirements.append({
                'scope': 'watchlist',
                'symbols': watchlist_symbols,
                'includes': includes
            })
        
        # 3. 全量档案补缺
        requirements.append({
            'scope': 'all_symbols',
            'includes': [{
                'type': 'all_symbols_profile',
                'priority': DATA_TYPE_DEFINITIONS['all_symbols_profile']['priority']
            }]
        })
        
        tasks = parser.parse_requirements(requirements)
        
        for task in tasks:
            await queue.enqueue(task)
        
        log_event(
            logger=_LOG,
            service="debug",
            level="INFO",
            file=__file__,
            func="trigger_full_sync_route",
            line=0,
            trace_id=tid,
            event="api.debug.sync_all.done",
            message=f"完整同步已触发，共生成 {len(tasks)} 个任务"
        )
        
        return {
            "ok": True,
            "tasks_generated": len(tasks),
            "message": "完整同步已触发，请通过SSE监听进度"
        }
    
    except Exception as e:
        log_event(
            logger=_LOG,
            service="debug",
            level="ERROR",
            file=__file__,
            func="trigger_full_sync_route",
            line=0,
            trace_id=tid,
            event="api.debug.sync_all.fail",
            message=f"触发失败: {e}",
            extra={"error": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)

@router.get("/daily_columns")
async def api_debug_daily_columns(
    request: Request,
    code: str = Query(..., description="股票代码"),
    start: Optional[str] = Query(None, description="起始日期"),
    end: Optional[str] = Query(None, description="结束日期"),
) -> Dict[str, Any]:
    """
    调试：直接走 AkShare 拉日线，查看原始字段
    
    用途：
      - 验证数据源返回的字段名
      - 排查标准化问题
    """
    tid = request.headers.get("x-trace-id")
    
    try:
        ak = _lazy_import_ak()
        
        s_ymd, e_ymd = normalize_date_range(start, end, default_start=19900101)
        start_s = f"{s_ymd:08d}"
        end_s = f"{e_ymd:08d}"
        
        log_event(
            logger=_LOG,
            service="debug",
            level="INFO",
            file=__file__,
            func="api_debug_daily_columns",
            line=0,
            trace_id=tid,
            event="api.debug.daily_columns.start",
            message="查询原始字段",
            extra={"code": code, "start": start_s, "end": end_s}
        )
        
        df = await asyncio.to_thread(
            ak.stock_zh_a_hist,
            symbol=code,
            period="daily",
            start_date=start_s,
            end_date=end_s,
            adjust=''  # 固定查询不复权数据
        )
        
        cols_raw = df.columns.tolist() if df is not None else []
        sample = df.head(5).to_dict(orient="records") if (df is not None and not df.empty) else []
        
        log_event(
            logger=_LOG,
            service="debug",
            level="INFO",
            file=__file__,
            func="api_debug_daily_columns",
            line=0,
            trace_id=tid,
            event="api.debug.daily_columns.done",
            message="查询完成",
            extra={"rows": len(df) if df is not None else 0}
        )
        
        return {
            "ok": True,
            "symbol": code,
            "start": start_s,
            "end": end_s,
            "columns": cols_raw,
            "rows": len(df) if df is not None else 0,
            "sample": sample,
            "trace_id": tid
        }
        
    except Exception as e:
        log_event(
            logger=_LOG,
            service="debug",
            level="ERROR",
            file=__file__,
            func="api_debug_daily_columns",
            line=0,
            trace_id=tid,
            event="api.debug.daily_columns.fail",
            message="查询失败",
            extra={"error": str(e)}
        )
        raise http_500_from_exc(e, trace_id=tid)
