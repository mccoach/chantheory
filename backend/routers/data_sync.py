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
# V8.2 - After Hours Bulk v1.1（契约落地版）
#   - bulk 变为“批次真相源在后端”的入口：
#       * 新增 payload.batch（batch_id/client_instance_id/...）
#       * 幂等/冲突语义：
#           - batch 不存在：创建并入队
#           - batch 已存在且 running：幂等（不重复入队），返回快照
#           - batch 已存在且 finished：409（detail 内含 code/message/trace_id）
#       * 新增查询接口：
#           - GET /api/ensure-data/bulk/status
#           - GET /api/ensure-data/bulk/status/latest
#           - GET /api/ensure-data/bulk/failures
#   - 错误响应结构：非2xx一律 { "detail": {code,message,trace_id} }
# ==============================

from __future__ import annotations

import asyncio
import re
from typing import Dict, Any, Optional, Literal, List
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field

from backend.settings import settings
from backend.services.task_model import create_task
from backend.services.priority_queue import get_priority_queue
from backend.utils.logger import get_logger, log_event

# After Hours Bulk v1.1 DB
from backend.db.bulk_batches import (
    get_batch,
    get_batch_state,
    create_batch_if_not_exists,
    get_latest_batch,
    list_failures,
)

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
# After Hours Bulk: /api/ensure-data/bulk  (v1.1)
# ==============================================================================

class EnsureDataBulkBatch(BaseModel):
    batch_id: str = Field(..., description="前端生成的批次ID，全局唯一")
    client_instance_id: str = Field(..., description="前端生成的浏览器实例ID(UUID)，用于 latest 过滤")
    started_at: Optional[str] = Field(None, description="前端记录的开始时间（ISO8601）")
    selected_symbols: Optional[int] = Field(None, description="选中的标的数（展示字段）")
    planned_total_tasks: Optional[int] = Field(None, description="计划任务总数（展示字段，通常jobs.length）")


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
    batch: EnsureDataBulkBatch = Field(..., description="批次信息（v1.1新增）")
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


_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")


def _validate_batch_fields(batch_id: str, client_instance_id: str, trace_id: Optional[str]) -> None:
    """
    v1.1 强制校验：
      - batch_id: [A-Za-z0-9._:-], len<=64
      - client_instance_id: 同样规则与长度（避免写入异常/污染latest）
    非法一律抛 HTTPException(400) 且 detail 结构固定：{code,message,trace_id}
    """
    bid = str(batch_id or "").strip()
    cid = str(client_instance_id or "").strip()

    if not bid or not _BATCH_ID_RE.match(bid):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BATCH_ID_INVALID",
                "message": "invalid batch_id",
                "trace_id": trace_id,
            },
        )

    if not cid or not _BATCH_ID_RE.match(cid) or len(cid) > 64:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CLIENT_INSTANCE_ID_INVALID",
                "message": "invalid client_instance_id",
                "trace_id": trace_id,
            },
        )


@router.post("/ensure-data/bulk")
async def ensure_data_bulk(request: Request, payload: EnsureDataBulkRequest) -> Dict[str, Any]:
    """
    盘后批量入队接口（After Hours Bulk v1.1）

    关键契约：
      - 批次真相源在后端（bulk_batches）
      - 幂等/冲突语义（写死）：
          * batch_id 不存在：创建并入队
          * batch_id 存在且 running：幂等（不重复入队），返回快照（200）
          * batch_id 存在且 finished：409（detail.code=BATCH_ID_CONFLICT_FINISHED）
      - rejected 不进入 progress.total（total=accepted_tasks）
      - 响应在成功(200)时回显 batch 快照
    """
    trace_id = request.headers.get("x-trace-id")

    max_jobs = int(settings.bulk_max_jobs)

    batch_id = str(payload.batch.batch_id or "").strip()
    client_instance_id = str(payload.batch.client_instance_id or "").strip()

    _validate_batch_fields(batch_id, client_instance_id, trace_id)

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
            "batch_id": batch_id,
            "client_instance_id": client_instance_id,
            "force_fetch": payload.force_fetch,
            "priority": payload.priority,
            "jobs": len(payload.jobs or []),
            "max_jobs": max_jobs,
            "client_meta": payload.client_meta or {},
        },
    )

    # 建议值提示：不拒绝，只记日志
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

    # ---- batch 幂等/冲突语义（先查 state）----
    existing_state = await asyncio.to_thread(get_batch_state, batch_id)
    if existing_state == "finished":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BATCH_ID_CONFLICT_FINISHED",
                "message": "batch_id already exists and is finished; please generate a new batch_id",
                "trace_id": trace_id,
            },
        )

    # running 幂等：直接回显快照，不重复入队
    if existing_state == "running":
        snap = await asyncio.to_thread(get_batch, batch_id)
        return {
            "ok": True,
            "accepted": int(snap.get("accepted_tasks") or 0) if snap else 0,
            "rejected": int(snap.get("rejected_tasks") or 0) if snap else 0,
            "max_jobs": max_jobs,
            "items": [],
            "batch": snap,
            "trace_id": trace_id,
        }

    # ---- 不存在：开始创建批次，并入队任务 ----
    queue = get_priority_queue()

    purpose = str(payload.purpose or "").strip()
    bulk_force_fetch = bool(payload.force_fetch)
    bulk_priority = _resolve_bulk_priority(purpose, payload.priority)

    accepted = 0
    rejected = 0
    items: List[Dict[str, Any]] = []

    seen_job_ids: set[str] = set()
    YIELD_EVERY = 500

    # 先按规则构建 Task（但在写 batch 之前我们需要知道 accepted/rejected 计数）
    tasks_to_enqueue = []

    for idx, job in enumerate(payload.jobs or []):
        job_id = job.job_id

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

        params = dict(job.params or {})
        if "force_fetch" not in params:
            params["force_fetch"] = bulk_force_fetch

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
                priority=bulk_priority,
            )
            # v1.1：绑定 batch 元信息到 task.metadata（用于 task_done 时更新真相源）
            task.metadata["batch_id"] = batch_id
            task.metadata["client_instance_id"] = client_instance_id
            task.metadata["batch_purpose"] = purpose

            tasks_to_enqueue.append((job_id, task))
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
                    message=f"failed to build task: {e}",
                ),
            })

        if (idx + 1) % YIELD_EVERY == 0:
            await asyncio.sleep(0)

    # 先创建 batch 记录（不存在才创建；若并发创建，这里以 DB 原子性为准）
    mode, batch_snapshot = await asyncio.to_thread(
        create_batch_if_not_exists,
        batch_id=batch_id,
        client_instance_id=client_instance_id,
        purpose=purpose,
        started_at=payload.batch.started_at,
        selected_symbols=payload.batch.selected_symbols,
        planned_total_tasks=payload.batch.planned_total_tasks,
        accepted_tasks=accepted,
        rejected_tasks=rejected,
    )

    # 若 mode == existing（极端并发）：
    # - 仍按 v1.1 幂等，不重复入队（避免重复执行）
    if mode == "existing":
        # 若已存在但不是 running/finished（理论不会出现），按快照回显
        return {
            "ok": True,
            "accepted": int(batch_snapshot.get("accepted_tasks") or 0),
            "rejected": int(batch_snapshot.get("rejected_tasks") or 0),
            "max_jobs": max_jobs,
            "items": [],
            "batch": batch_snapshot,
            "trace_id": trace_id,
        }

    # 新建成功：入队 accepted 的 task
    for _, task in tasks_to_enqueue:
        await queue.enqueue(task)

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
            "batch_id": batch_id,
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
        "batch": batch_snapshot,
        "trace_id": trace_id,
    }


# ==============================================================================
# After Hours Bulk v1.1 - 快照查询
# ==============================================================================

@router.get("/ensure-data/bulk/status")
async def ensure_data_bulk_status(
    request: Request,
    batch_id: str = Query(..., description="批次ID"),
) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    bid = str(batch_id or "").strip()

    if not bid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BATCH_ID_INVALID",
                "message": "invalid batch_id",
                "trace_id": trace_id,
            },
        )

    batch = await asyncio.to_thread(get_batch, bid)
    return {
        "ok": True,
        "batch": batch,
        "trace_id": trace_id,
    }


@router.get("/ensure-data/bulk/status/latest")
async def ensure_data_bulk_status_latest(
    request: Request,
    purpose: Optional[str] = Query(None, description="用途标记，如 after_hours"),
    state: Optional[Literal["running", "finished"]] = Query(None, description="批次状态过滤"),
    client_instance_id: Optional[str] = Query(None, description="可选过滤，降低误拾取概率"),
) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")

    pur = str(purpose).strip() if purpose is not None else None
    st = str(state).strip() if state is not None else None
    cid = str(client_instance_id).strip() if client_instance_id is not None else None

    if cid:
        # 同 batch 规则做最小校验（不强制必须传）
        if not _BATCH_ID_RE.match(cid) or len(cid) > 64:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "CLIENT_INSTANCE_ID_INVALID",
                    "message": "invalid client_instance_id",
                    "trace_id": trace_id,
                },
            )

    batch = await asyncio.to_thread(
        get_latest_batch,
        purpose=pur,
        state=st,
        client_instance_id=cid,
    )

    return {
        "ok": True,
        "batch": batch,
        "trace_id": trace_id,
    }


@router.get("/ensure-data/bulk/failures")
async def ensure_data_bulk_failures(
    request: Request,
    batch_id: str = Query(..., description="批次ID"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(200, ge=1, le=1000, description="分页大小"),
) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    bid = str(batch_id or "").strip()

    if not bid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BATCH_ID_INVALID",
                "message": "invalid batch_id",
                "trace_id": trace_id,
            },
        )

    total_failed, items = await asyncio.to_thread(
        list_failures,
        batch_id=bid,
        offset=int(offset),
        limit=int(limit),
    )

    return {
        "ok": True,
        "batch_id": bid,
        "total_failed": total_failed,
        "items": items,
        "trace_id": trace_id,
    }
