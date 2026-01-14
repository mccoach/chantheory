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
#
# ==============================
# V8.1 - 新增盘后批量入队接口：POST /api/ensure-data/bulk
#
# 设计：
#   - bulk 仅负责“批量创建 Task 并入队”，不做批次聚合器；
#   - 前端依赖 SSE task_done 进行统计与失败识别；
#   - priority 策略：
#       * payload.priority 非空 → 覆盖本批所有任务优先级
#       * 否则：
#           purpose == 'after_hours' → settings.after_hours_priority（默认 1000）
#           其他/缺失 → 使用 create_task 的默认优先级（来自 DATA_TYPE_DEFINITIONS）
#   - max_jobs：
#       * 从 settings.bulk_max_jobs 读取（默认 30000）
#       * 作为建议值回传给前端；不因超限拒绝（按你的要求）。
#   - reason：
#       * rejected 必须返回结构化 reason（code/message/details）
#       * accepted reason 为 null
# ==============================

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional, Literal, List
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.settings import settings
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


# ==============================================================================
# After Hours Bulk: /api/ensure-data/bulk
# ==============================================================================

class EnsureDataBulkJob(BaseModel):
    job_id: str = Field(..., description="客户端相关ID（批次内唯一），后端不解析，仅回传")
    type: str = Field(..., description="任务类型，如 current_kline/current_factors 等")
    scope: str = Field(..., description="任务作用范围：symbol/global")
    symbol: Optional[str] = Field(None, description="标的代码")
    freq: Optional[str] = Field(None, description="频率，仅 current_kline 有意义")
    adjust: Optional[str] = Field("none", description="复权方式：none/qfq/hfq")
    params: Dict[str, Any] = Field(default_factory=dict, description="任务参数对象，可为空 {}")


class EnsureDataBulkRequest(BaseModel):
    purpose: str = Field(..., description="用途标记，盘后任务固定为 after_hours（当前仅用作优先级策略）")
    force_fetch: bool = Field(False, description="批次默认 force_fetch（job 可在 params.force_fetch 覆盖）")
    priority: Optional[int] = Field(None, description="可选：覆盖本批所有任务优先级（调试/应急）")
    jobs: List[EnsureDataBulkJob] = Field(..., description="任务列表")
    client_meta: Optional[Dict[str, Any]] = Field(None, description="仅用于日志排错，不参与业务逻辑")


def _make_reason(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r: Dict[str, Any] = {"code": code, "message": message}
    if details:
        r["details"] = details
    return r


def _resolve_bulk_priority(purpose: str, override_priority: Optional[int]) -> Optional[int]:
    """
    解析 bulk 的优先级策略：
      - override_priority 非空 → 直接使用
      - purpose == 'after_hours' → settings.after_hours_priority
      - 其他 → None（表示使用 create_task 的默认优先级）
    """
    if override_priority is not None:
        try:
            return int(override_priority)
        except Exception:
            # 覆盖值无法转 int：回退为 None，避免整个批次失败
            return None

    if str(purpose or "").strip() == "after_hours":
        return int(settings.after_hours_priority)

    return None


@router.post("/ensure-data/bulk")
async def ensure_data_bulk(request: Request, payload: EnsureDataBulkRequest) -> Dict[str, Any]:
    """
    盘后批量入队接口（After Hours Bulk）

    约定：
      - 不引入新的任务类型，仍使用现有 Task 字段集合。
      - 本接口仅负责“批量创建 Task 并入队”，执行结果通过 SSE task_done 获取。
      - 不因 jobs 数量超出 max_jobs 拒绝（max_jobs 仅作建议值回传给前端）。
      - 单条 job 参数错误 → rejected（结构化 reason），不影响其他 job。
    """
    trace_id = request.headers.get("x-trace-id")

    max_jobs = int(settings.bulk_max_jobs)

    log_event(
        logger=_LOG,
        service="data_sync",
        level="INFO",
        file=__file__,
        func="ensure_data_bulk",
        line=0,
        trace_id=trace_id,
        event="api.ensure_data.bulk.start",
        message="收到 bulk 数据需求声明",
        extra={
            "purpose": payload.purpose,
            "force_fetch": payload.force_fetch,
            "priority": payload.priority,
            "jobs": len(payload.jobs or []),
            "max_jobs": max_jobs,
            "client_meta": payload.client_meta or {},
        },
    )

    # 建议值提示：不拒绝，只记日志，便于你后续调参
    try:
        if payload.jobs is not None and len(payload.jobs) > max_jobs:
            log_event(
                logger=_LOG,
                service="data_sync",
                level="WARN",
                file=__file__,
                func="ensure_data_bulk",
                line=0,
                trace_id=trace_id,
                event="api.ensure_data.bulk.hint.too_many_jobs",
                message="bulk jobs 数量超过建议 max_jobs（不拒绝，仅提示）",
                extra={
                    "jobs": len(payload.jobs),
                    "max_jobs": max_jobs,
                },
            )
    except Exception:
        pass

    queue = get_priority_queue()

    purpose = str(payload.purpose or "").strip()
    bulk_force_fetch = bool(payload.force_fetch)
    bulk_priority = _resolve_bulk_priority(purpose, payload.priority)

    accepted = 0
    rejected = 0
    items: List[Dict[str, Any]] = []

    # job_id 批次内唯一校验（仅用于拒绝重复，不阻断整批）
    seen_job_ids: set[str] = set()

    # 防止长循环占用事件循环：分段让出（最小且稳健）
    YIELD_EVERY = 500

    for idx, job in enumerate(payload.jobs or []):
        job_id = job.job_id

        # ---- 1) job_id 校验 ----
        if not isinstance(job_id, str) or not job_id.strip():
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="invalid_job_id",
                    message="job_id must be a non-empty string",
                ),
            })
            continue

        job_id = job_id.strip()

        if job_id in seen_job_ids:
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="duplicate_job_id",
                    message="job_id must be unique within the same bulk request",
                    details={"job_id": job_id},
                ),
            })
            continue

        seen_job_ids.add(job_id)

        # ---- 2) 参数继承：force_fetch ----
        params = dict(job.params or {})
        if "force_fetch" not in params:
            params["force_fetch"] = bulk_force_fetch

        # ---- 3) 基础字段校验（只做“能否构造 Task”的最小检查）----
        task_type = str(job.type or "").strip()
        task_scope = str(job.scope or "").strip()
        symbol = (str(job.symbol).strip() if job.symbol is not None else None)
        freq = (str(job.freq).strip() if job.freq is not None else None)
        adjust = str(job.adjust or "none").strip().lower()

        if not task_type:
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="missing_field",
                    message="missing required field: type",
                    details={"field": "type"},
                ),
            })
            continue

        if not task_scope:
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="missing_field",
                    message="missing required field: scope",
                    details={"field": "scope"},
                ),
            })
            continue

        # scope='symbol' 时 symbol 必须存在（这是“能否构造 Task”的最低要求）
        if task_scope == "symbol" and not symbol:
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="missing_field",
                    message="missing required field: symbol (scope='symbol')",
                    details={"field": "symbol"},
                ),
            })
            continue

        # current_kline 必须有 freq（同样是最低构造要求）
        if task_type == "current_kline" and not freq:
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="missing_field",
                    message="missing required field: freq (type='current_kline')",
                    details={"field": "freq"},
                ),
            })
            continue

        # ---- 4) 构造 Task 并入队 ----
        try:
            task = create_task(
                type=task_type,
                scope=task_scope,
                symbol=symbol,
                freq=freq,
                adjust=adjust,
                trace_id=trace_id,
                params=params,
                source="api/ensure-data/bulk",
                priority=bulk_priority,  # None 表示沿用 create_task 默认优先级
            )
            await queue.enqueue(task)

            accepted += 1
            items.append({
                "job_id": job_id,
                "status": "accepted",
                "task_id": task.task_id,
                "reason": None,
            })

        except Exception as e:
            rejected += 1
            items.append({
                "job_id": job_id,
                "status": "rejected",
                "task_id": None,
                "reason": _make_reason(
                    code="enqueue_failed",
                    message=f"failed to enqueue task: {e}",
                ),
            })

        # ---- 5) 定期让出事件循环，避免大批量入队阻塞服务 ----
        if (idx + 1) % YIELD_EVERY == 0:
            await asyncio.sleep(0)

    log_event(
        logger=_LOG,
        service="data_sync",
        level="INFO",
        file=__file__,
        func="ensure_data_bulk",
        line=0,
        trace_id=trace_id,
        event="api.ensure_data.bulk.done",
        message="bulk Task 入队完成",
        extra={
            "accepted": accepted,
            "rejected": rejected,
            "max_jobs": max_jobs,
        },
    )

    return {
        "ok": True,
        "accepted": accepted,
        "rejected": rejected,
        "max_jobs": max_jobs,
        "items": items,
        "trace_id": trace_id,
    }
