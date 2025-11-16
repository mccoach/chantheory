# backend/routers/debug.py
# ==============================
# V5.0 - 精简调试路由
# ==============================

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query, Request
from typing import Dict, Any, Optional

from backend.utils.errors import http_500_from_exc
from backend.utils.logger import get_logger
from backend.settings import DATA_TYPE_DEFINITIONS

_LOG = get_logger("debug")

router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.post("/sync-current")
async def trigger_current_sync(
    request: Request,
    symbol: str = Query(..., description="标的代码"),
    freq: str = Query("1d", description="频率")
) -> Dict[str, Any]:
    """手动触发当前标的同步（调试用）"""
    
    tid = request.headers.get("x-trace-id")
    
    _LOG.info(f"[调试] 手动同步: {symbol} {freq}")
    
    try:
        from backend.services.data_requirement_parser import get_requirement_parser
        from backend.services.priority_queue import get_priority_queue
        
        parser = get_requirement_parser()
        queue = get_priority_queue()
        
        requirements = [{
            'scope': 'symbol',
            'symbol': symbol,
            'includes': [
                {'type': 'current_kline', 'freq': freq, 'priority': 20},
                {'type': 'current_factors', 'priority': 20},
                {'type': 'current_profile', 'priority': 30},
            ]
        }]
        
        tasks = parser.parse_requirements(requirements)
        
        for task in tasks:
            await queue.enqueue(task)
        
        _LOG.info(f"[调试] 已生成 {len(tasks)} 个任务")
        
        return {
            "ok": True,
            "tasks_generated": len(tasks),
            "message": f"已触发 {symbol} {freq} 的同步任务",
            "trace_id": tid
        }
        
    except Exception as e:
        _LOG.error(f"[调试] 触发失败: {e}")
        raise http_500_from_exc(e, trace_id=tid)

@router.get("/daily_columns")
async def api_debug_daily_columns(
    request: Request,
    code: str = Query(..., description="股票代码"),
    start: Optional[str] = Query(None, description="起始日期"),
    end: Optional[str] = Query(None, description="结束日期"),
) -> Dict[str, Any]:
    """调试：直接走 AkShare 拉日线，查看原始字段"""
    
    tid = request.headers.get("x-trace-id")
    
    try:
        import importlib
        ak = importlib.import_module("akshare")
        
        from backend.utils.time import normalize_date_range
        
        s_ymd, e_ymd = normalize_date_range(start, end, default_start=19900101)
        start_s = f"{s_ymd:08d}"
        end_s = f"{e_ymd:08d}"
        
        _LOG.info(f"[调试] 查询原始字段: {code} {start_s}-{end_s}")
        
        df = await asyncio.to_thread(
            ak.stock_zh_a_hist,
            symbol=code,
            period="daily",
            start_date=start_s,
            end_date=end_s,
            adjust=''
        )
        
        cols_raw = df.columns.tolist() if df is not None else []
        sample = df.head(5).to_dict(orient="records") if (df is not None and not df.empty) else []
        
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
        _LOG.error(f"[调试] 查询失败: {e}")
        raise http_500_from_exc(e, trace_id=tid)