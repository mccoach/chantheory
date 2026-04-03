# backend/routers/data_sync.py
# ==============================
# 数据同步API（非 bulk 版）
#
# 当前正式入口：
#   - trade_calendar
#   - symbol_index
#   - profile_snapshot
#   - current_kline
#   - factor_events_snapshot
#
# 本轮改动：
#   - 将原 factors_snapshot / current_factors 相关思路彻底废弃
#   - 复权基础数据正式入口统一为：
#       factor_events_snapshot
#   - create_task 已正式支持 market 字段，本文件同步适配新签名
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional, Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.services.task_model import create_task
from backend.services.priority_queue import get_priority_queue

router = APIRouter(prefix="/api", tags=["data_sync"])

class EnsureDataParams(BaseModel):
    force_fetch: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class EnsureDataRequest(BaseModel):
    type: Literal[
        "trade_calendar",
        "symbol_index",
        "profile_snapshot",
        "current_kline",
        "factor_events_snapshot",
    ] = Field(..., description="任务类型")

    scope: Optional[str] = Field(None, description="任务作用范围：单标的 / 全局")
    symbol: Optional[str] = Field(None, description="标的代码")
    market: Optional[str] = Field(None, description="市场代码：SH / SZ / BJ")
    freq: Optional[str] = Field(None, description="频率")
    adjust: Optional[str] = Field(None, description="复权方式：none/qfq/hfq")
    params: Optional[EnsureDataParams] = Field(default=None)

@router.post("/ensure-data")
async def ensure_data(request: Request, payload: EnsureDataRequest) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")

    try:
        task_type = payload.type

        if task_type == "symbol_index":
            task = create_task(
                type="symbol_index",
                scope="global",
                symbol=None,
                market=None,
                freq=None,
                adjust=None,
                trace_id=trace_id,
                params={},
                source="api/ensure-data",
            )
        elif task_type == "profile_snapshot":
            task = create_task(
                type="profile_snapshot",
                scope="global",
                symbol=None,
                market=None,
                freq=None,
                adjust=None,
                trace_id=trace_id,
                params={},
                source="api/ensure-data",
            )
        elif task_type == "trade_calendar":
            task = create_task(
                type="trade_calendar",
                scope="global",
                symbol=None,
                market=None,
                freq=None,
                adjust=None,
                trace_id=trace_id,
                params={},
                source="api/ensure-data",
            )
        elif task_type == "factor_events_snapshot":
            task = create_task(
                type="factor_events_snapshot",
                scope="global",
                symbol=None,
                market=None,
                freq=None,
                adjust=None,
                trace_id=trace_id,
                params={},
                source="api/ensure-data",
            )
        else:
            params_dict = payload.params.dict() if payload.params else {}
            task = create_task(
                type=payload.type,
                scope=payload.scope or "symbol",
                symbol=payload.symbol,
                market=payload.market,
                freq=payload.freq,
                adjust=payload.adjust,
                trace_id=trace_id,
                params=params_dict,
                source="api/ensure-data",
            )

        queue = get_priority_queue()
        await queue.enqueue(task)
        return {
            "ok": True,
            "task_id": task.task_id,
            "message": "任务已创建，后台处理中",
            "trace_id": trace_id,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace_id": trace_id,
        }