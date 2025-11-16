# backend/routers/data_sync.py
# ==============================
# 数据同步API（V5.0 - 确认兼容新数据类型）
# ==============================

from __future__ import annotations

from typing import List, Dict, Any
from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.services.data_requirement_parser import get_requirement_parser
from backend.services.priority_queue import get_priority_queue
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_sync")
router = APIRouter(prefix="/api", tags=["data_sync"])

class DataRequirement(BaseModel):
    """单个数据需求"""
    scope: str  # 'symbol' / 'global'
    symbol: str = None
    symbols: List[str] = None
    includes: List[Dict[str, Any]]

class EnsureDataRequest(BaseModel):
    """批量数据需求请求体"""
    requirements: List[DataRequirement]

@router.post("/ensure-data")
async def ensure_data(
    request: Request,
    payload: EnsureDataRequest
):
    """
    确保数据可用（声明式API）
    
    请求体示例：
    {
        "requirements": [
            {
                "scope": "symbol",
                "symbol": "600519",
                "includes": [
                    {"type": "current_kline", "freq": "1d", "priority": 20},
                    {"type": "current_factors", "priority": 20},
                    {"type": "current_profile", "priority": 30}
                ]
            }
        ]
    }
    """
    trace_id = request.headers.get("x-trace-id")
    
    log_event(
        logger=_LOG,
        service="data_sync",
        level="INFO",
        file=__file__,
        func="ensure_data",
        line=0,
        trace_id=trace_id,
        event="api.ensure_data.start",
        message="收到数据需求声明",
        extra={
            "requirements_count": len(payload.requirements)
        }
    )
    
    try:
        # 1. 解析需求为任务列表
        parser = get_requirement_parser()
        tasks = parser.parse_requirements(
            [req.dict() for req in payload.requirements]
        )
        
        # 2. 批量入队
        queue = get_priority_queue()
        for task in tasks:
            await queue.enqueue(task)
        
        log_event(
            logger=_LOG,
            service="data_sync",
            level="INFO",
            file=__file__,
            func="ensure_data",
            line=0,
            trace_id=trace_id,
            event="api.ensure_data.done",
            message=f"已生成 {len(tasks)} 个任务并入队",
            extra={"tasks_count": len(tasks)}
        )
        
        return {
            "ok": True,
            "tasks_generated": len(tasks),
            "message": "数据需求已接收，后台处理中"
        }
    
    except Exception as e:
        log_event(
            logger=_LOG,
            service="data_sync",
            level="ERROR",
            file=__file__,
            func="ensure_data",
            line=0,
            trace_id=trace_id,
            event="api.ensure_data.error",
            message=f"处理需求失败: {e}",
            extra={"error": str(e)}
        )
        
        return {
            "ok": False,
            "error": str(e)
        }