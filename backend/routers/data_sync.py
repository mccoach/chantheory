# backend/routers/data_sync.py
# ==============================
# 数据同步API（Task/Job/SSE 版）
#
# 改动要点：
#   - 一次 HTTP 请求 = 一个 Task（type 唯一，不再有 includes 列表）；
#   - 不再使用 DataRequirementParser / TaskGroup；
#   - 仅负责：
#       * 从请求体构造 Task（create_task）；
#       * 将 Task 入队 AsyncPriorityQueue；
#       * 立即返回 task_id，实际执行由 UnifiedSyncExecutor 完成；
#   - Job 拆解与 SSE(job_done/task_done) 由各 run_* 配方内部负责。
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional, Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.services.task_model import create_task
from backend.services.priority_queue import get_priority_queue
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_sync")
router = APIRouter(prefix="/api", tags=["data_sync"])


class EnsureDataParams(BaseModel):
    """
    任务参数：
      - force_fetch : 是否强制刷新（忽略缺口/updated_at 判断）
      - start_date  : 可选起始日期（保留扩展）
      - end_date    : 可选结束日期（保留扩展）
    """
    force_fetch: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class EnsureDataRequest(BaseModel):
    """
    一次请求 = 一个 Task
      - type  : 'current_kline' / 'symbol_index' / 'trade_calendar' / 'current_factors' / 'current_profile'
      - scope : 'symbol' / 'global'
      - symbol: scope='symbol' 时需要
      - freq  : current_kline 时需要
      - adjust: current_kline 的复权方式
      - params: 任务参数（含 force_fetch）
    """
    type: Literal[
        "trade_calendar",
        "symbol_index",
        "current_kline",
        "current_factors",
        "current_profile",
    ] = Field(..., description="任务类型")
    scope: Literal["symbol", "global"] = Field(
        ...,
        description="任务作用范围：单标的 / 全局",
    )
    symbol: Optional[str] = Field(
        None,
        description="标的代码（scope='symbol' 时建议必填）",
    )
    freq: Optional[str] = Field(
        None,
        description="频率，仅 current_kline 有意义，如 '1d','5m','1w','1M'",
    )
    adjust: Optional[str] = Field(
        "none",
        description="复权方式：none/qfq/hfq，仅 current_kline 有意义",
    )
    params: EnsureDataParams = Field(
        default_factory=EnsureDataParams,
        description="任务参数（force_fetch/start_date/end_date 等）",
    )


@router.post("/ensure-data")
async def ensure_data(
    request: Request,
    payload: EnsureDataRequest,
) -> Dict[str, Any]:
    """
    声明式数据需求入口（一次请求 = 一个 Task）

    示例请求体：
    {
      "type": "current_kline",
      "scope": "symbol",
      "symbol": "510300",
      "freq": "5m",
      "adjust": "qfq",
      "params": {
        "force_fetch": false
      }
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
            "type": payload.type,
            "scope": payload.scope,
            "symbol": payload.symbol,
            "freq": payload.freq,
            "adjust": payload.adjust,
            "params": payload.params.dict(),
        },
    )

    try:
        # 1. 从请求体构造 Task
        task = create_task(
            type=payload.type,
            scope=payload.scope,
            symbol=payload.symbol,
            freq=payload.freq,
            adjust=payload.adjust,
            trace_id=trace_id,
            params=payload.params.dict(),
            source="api/ensure-data",
        )

        # 2. 将 Task 入队，等待执行器处理（异步后台）
        queue = get_priority_queue()
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
            message="Task 已入队等待执行",
            extra={
                "task_id": task.task_id,
                "type": task.type,
                "scope": task.scope,
            },
        )

        return {
            "ok": True,
            "task_id": task.task_id,
            "message": "任务已创建，后台处理中",
            "trace_id": trace_id,
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
            extra={"error": str(e)},
        )
        return {
            "ok": False,
            "error": str(e),
            "trace_id": trace_id,
        }