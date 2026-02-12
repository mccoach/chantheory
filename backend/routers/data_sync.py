# backend/routers/data_sync.py
# ==============================
# 数据同步API（Task/Job/SSE 版）
#
# After Hours Bulk v2.1.2 (project edition)
#   - 删旧换新：移除旧 /api/ensure-data/bulk（v1.*）入口
#   - 新增：
#       POST /api/ensure-data/bulk/start
#       GET  /api/ensure-data/bulk/status
#       GET  /api/ensure-data/bulk/status/active
#       POST /api/ensure-data/bulk/cancel
#       POST /api/ensure-data/bulk/resume
#       POST /api/ensure-data/bulk/retry-failed
#       GET  /api/ensure-data/bulk/failures
#
# 关键契约：
#   - 所有 bulk 业务失败必须 HTTP 200，返回顶层 ok=false envelope（不使用 FastAPI detail）
#   - 查询类（status/failures）not found 或隔离不匹配：ok=true, batch/items为空（不泄露）
# ==============================

from __future__ import annotations

import asyncio
import re
from typing import Dict, Any, Optional, Literal, List
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, Field

from backend.services.task_model import create_task
from backend.services.priority_queue import get_priority_queue
from backend.utils.logger import get_logger, log_event
from backend.settings import settings

from backend.services.server_identity import get_backend_instance_id
from backend.services.bulk_scheduler import enqueue_batch, tick as bulk_tick

from backend.db.bulk_batches import (
    start_batch_idempotent,
    get_batch_snapshot_for_client,
    get_active_batch_for_client,
    list_queued_batches_for_client,
    get_queue_position,
    enter_stopping,
    apply_stopping_sweep,
    resume_batch,
    retry_failed_reset,
    list_failed_tasks,
)

_LOG = get_logger("data_sync")
router = APIRouter(prefix="/api", tags=["data_sync"])

# ==============================
# 非 bulk：原 ensure-data Task 入队接口保留
# ==============================

class EnsureDataParams(BaseModel):
    force_fetch: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class EnsureDataRequest(BaseModel):
    type: Literal[
        "trade_calendar",
        "symbol_index",
        "current_kline",
        "current_factors",
        "current_profile",
    ] = Field(..., description="任务类型")
    scope: Literal["symbol", "global"] = Field(..., description="任务作用范围：单标的 / 全局")
    symbol: Optional[str] = Field(None, description="标的代码")
    freq: Optional[str] = Field(None, description="频率")
    adjust: Optional[str] = Field("none", description="复权方式：none/qfq/hfq")
    params: EnsureDataParams = Field(default_factory=EnsureDataParams)


@router.post("/ensure-data")
async def ensure_data(request: Request, payload: EnsureDataRequest) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")

    try:
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

# ==============================
# Bulk v2.1.2
# ==============================

_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")


def _ok(
    *,
    trace_id: Optional[str],
    batch: Optional[Dict[str, Any]],
    active_batch: Optional[Dict[str, Any]] = None,
    queue_position: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resp: Dict[str, Any] = {
        "ok": True,
        "backend_instance_id": get_backend_instance_id(),
        "batch": batch,
        "trace_id": trace_id,
    }
    if active_batch is not None:
        resp["active_batch"] = active_batch
    if queue_position is not None:
        resp["queue_position"] = queue_position
    else:
        resp["queue_position"] = None
    if extra:
        resp.update(extra)
    return resp


def _fail(
    *,
    trace_id: Optional[str],
    code: str,
    message: str,
    batch: Optional[Dict[str, Any]] = None,
    active_batch: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "code": code,
        "message": message,
        "backend_instance_id": get_backend_instance_id(),
        "batch": batch,
        "active_batch": active_batch,
        "trace_id": trace_id,
    }


def _get_client_instance_id(request: Request) -> str:
    return str(request.headers.get("x-client-instance-id") or "").strip()


def _validate_client_instance_id(cid: str) -> bool:
    return bool(cid) and bool(_BATCH_ID_RE.match(cid)) and len(cid) <= 64


def _validate_batch_id(bid: str) -> bool:
    return bool(bid) and bool(_BATCH_ID_RE.match(bid)) and len(bid) <= 64


class BulkSubmitPolicy(BaseModel):
    when_active_exists: Literal["replace", "enqueue", "abort"] = "enqueue"


class BulkBatchInfo(BaseModel):
    batch_id: str
    client_instance_id: str
    started_at: Optional[str] = None
    selected_symbols: Optional[int] = None
    planned_total_tasks: Optional[int] = None


class BulkTaskItem(BaseModel):
    client_task_key: str
    type: str
    scope: str
    symbol: Optional[str] = None
    freq: Optional[str] = None
    adjust: Optional[str] = "none"
    params: Dict[str, Any] = Field(default_factory=dict)


class BulkStartRequest(BaseModel):
    purpose: Literal["after_hours"] = "after_hours"
    batch: BulkBatchInfo
    force_fetch: bool = False
    priority: Optional[int] = None
    bulk_tasks: List[BulkTaskItem]
    submit_policy: BulkSubmitPolicy = Field(default_factory=BulkSubmitPolicy)


@router.post("/ensure-data/bulk/start")
async def bulk_start(request: Request, payload: BulkStartRequest) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    if not _validate_client_instance_id(header_cid):
        return _fail(
            trace_id=trace_id,
            code="VALIDATION_ERROR",
            message="missing or invalid x-client-instance-id header",
            batch=None,
            active_batch=None,
        )

    body_cid = str(payload.batch.client_instance_id or "").strip()
    if header_cid != body_cid:
        return _fail(
            trace_id=trace_id,
            code="CLIENT_INSTANCE_MISMATCH",
            message="x-client-instance-id header does not match body.batch.client_instance_id",
            batch=None,
            active_batch=None,
        )

    bid = str(payload.batch.batch_id or "").strip()
    if not _validate_batch_id(bid):
        return _fail(
            trace_id=trace_id,
            code="VALIDATION_ERROR",
            message="invalid batch_id",
            batch=None,
            active_batch=None,
        )

    # bulk_tasks 基本校验：必须非空 + client_task_key 唯一
    tasks = payload.bulk_tasks or []
    if not tasks:
        return _fail(
            trace_id=trace_id,
            code="VALIDATION_ERROR",
            message="bulk_tasks must not be empty",
            batch=None,
            active_batch=None,
        )

    seen = set()
    for t in tasks:
        ckey = str(t.client_task_key or "").strip()
        if not ckey:
            return _fail(
                trace_id=trace_id,
                code="VALIDATION_ERROR",
                message="client_task_key must be non-empty",
                batch=None,
                active_batch=None,
            )
        if ckey in seen:
            return _fail(
                trace_id=trace_id,
                code="VALIDATION_ERROR",
                message=f"duplicate client_task_key in request: {ckey}",
                batch=None,
                active_batch=None,
            )
        seen.add(ckey)

    # 组装 DB 所需结构
    bulk_tasks_list = [t.dict() for t in tasks]

    try:
        res = await asyncio.to_thread(
            start_batch_idempotent,
            purpose=payload.purpose,
            batch=payload.batch.dict(),
            submit_policy=payload.submit_policy.dict(),
            bulk_tasks=bulk_tasks_list,
        )
    except Exception as e:
        return _fail(
            trace_id=trace_id,
            code="INTERNAL",
            message=f"start failed: {e}",
            batch=None,
            active_batch=None,
        )

    if res.get("mode") == "aborted":
        return _fail(
            trace_id=trace_id,
            code="ACTIVE_EXISTS",
            message="active batch exists, submission aborted",
            batch=None,
            active_batch=res.get("active_batch"),
        )

    batch_snap = res.get("batch")
    active_snap = res.get("active_batch")
    qp = res.get("queue_position")

    # 若新批次直接 running，则 enqueue 其 tasks
    if res.get("need_enqueue") and batch_snap and batch_snap.get("state") == "running":
        try:
            await enqueue_batch(
                batch_id=batch_snap["batch_id"],
                client_instance_id=header_cid,
                trace_id=trace_id,
            )
        except Exception as e:
            # enqueue 失败算 INTERNAL，但批次已创建；返回 ok=false 会让前端困惑
            # 最短路径：返回 ok=true，让前端 watchdog/status 继续拉真相源
            log_event(
                logger=_LOG,
                service="data_sync",
                level="ERROR",
                file=__file__,
                func="bulk_start",
                line=0,
                trace_id=trace_id,
                event="bulk.start.enqueue_fail",
                message="enqueue_batch failed",
                extra={"batch_id": bid, "error": str(e)},
            )

    # queued 批次必须返回 queue_position；running 则 null
    if batch_snap and str(batch_snap.get("state")).lower() == "queued":
        qp = await asyncio.to_thread(get_queue_position, bid, header_cid, "after_hours")

    return _ok(
        trace_id=trace_id,
        batch=batch_snap,
        active_batch=active_snap,
        queue_position=qp if batch_snap and batch_snap.get("state") == "queued" else None,
    )


@router.get("/ensure-data/bulk/status")
async def bulk_status(
    request: Request,
    batch_id: str = Query(..., description="批次ID"),
) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    if not _validate_client_instance_id(header_cid):
        # 查询类：不泄露，按 ok=true batch=null
        return _ok(trace_id=trace_id, batch=None, active_batch=None, queue_position=None)

    bid = str(batch_id or "").strip()
    if not _validate_batch_id(bid):
        return _ok(trace_id=trace_id, batch=None, active_batch=None, queue_position=None)

    snap = await asyncio.to_thread(get_batch_snapshot_for_client, bid, header_cid)
    if not snap:
        return _ok(trace_id=trace_id, batch=None, active_batch=None, queue_position=None)

    qp = None
    if str(snap.get("state")).lower() == "queued":
        qp = await asyncio.to_thread(get_queue_position, bid, header_cid, "after_hours")

    return _ok(trace_id=trace_id, batch=snap, active_batch=None, queue_position=qp)


@router.get("/ensure-data/bulk/status/active")
async def bulk_status_active(
    request: Request,
    purpose: Optional[str] = Query("after_hours", description="用途标记"),
) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    if not _validate_client_instance_id(header_cid):
        return {
            "ok": True,
            "backend_instance_id": get_backend_instance_id(),
            "active_batch": None,
            "queued_batches": [],
            "trace_id": trace_id,
        }

    pur = str(purpose or "after_hours").strip()
    if pur != "after_hours":
        pur = "after_hours"

    active = await asyncio.to_thread(get_active_batch_for_client, header_cid, pur)
    queued = await asyncio.to_thread(list_queued_batches_for_client, header_cid, pur)

    queued_items = []
    for idx, b in enumerate(queued, start=1):
        # queued item schema（FINAL++ 必须字段集合）
        queued_items.append({
            "batch_id": b["batch_id"],
            "client_instance_id": b["client_instance_id"],
            "purpose": b["purpose"],
            "state": b["state"],
            "started_at": b.get("started_at"),
            "server_received_at": b.get("server_received_at"),
            "queue_ts": b.get("queue_ts"),
            "queue_position": idx,
            "progress": b.get("progress"),
        })

    return {
        "ok": True,
        "backend_instance_id": get_backend_instance_id(),
        "active_batch": active,
        "queued_batches": queued_items,
        "trace_id": trace_id,
    }


class BulkOpRequest(BaseModel):
    batch_id: str


@router.post("/ensure-data/bulk/cancel")
async def bulk_cancel(request: Request, payload: BulkOpRequest) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    if not _validate_client_instance_id(header_cid):
        return _fail(trace_id=trace_id, code="VALIDATION_ERROR", message="invalid client_instance_id", batch=None, active_batch=None)

    bid = str(payload.batch_id or "").strip()
    if not _validate_batch_id(bid):
        return _fail(trace_id=trace_id, code="VALIDATION_ERROR", message="invalid batch_id", batch=None, active_batch=None)

    snap0 = await asyncio.to_thread(get_batch_snapshot_for_client, bid, header_cid)
    if not snap0:
        active = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
        return _fail(trace_id=trace_id, code="NOT_FOUND", message="batch not found", batch=None, active_batch=active)

    # 进入 stopping 并 sweep
    snap1 = await asyncio.to_thread(enter_stopping, batch_id=bid, client_instance_id=header_cid)
    snap2 = await asyncio.to_thread(apply_stopping_sweep, batch_id=bid, client_instance_id=header_cid)

    # cancel 可能让批次结束态，触发 tick
    try:
        await bulk_tick(client_instance_id=header_cid, trace_id=trace_id)
    except Exception:
        pass

    active = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
    return _ok(trace_id=trace_id, batch=snap2 or snap1 or snap0, active_batch=active, queue_position=None)


@router.post("/ensure-data/bulk/resume")
async def bulk_resume(request: Request, payload: BulkOpRequest) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    if not _validate_client_instance_id(header_cid):
        return _fail(trace_id=trace_id, code="VALIDATION_ERROR", message="invalid client_instance_id", batch=None, active_batch=None)

    bid = str(payload.batch_id or "").strip()
    if not _validate_batch_id(bid):
        return _fail(trace_id=trace_id, code="VALIDATION_ERROR", message="invalid batch_id", batch=None, active_batch=None)

    snap0 = await asyncio.to_thread(get_batch_snapshot_for_client, bid, header_cid)
    if not snap0:
        active = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
        return _fail(trace_id=trace_id, code="NOT_FOUND", message="batch not found", batch=None, active_batch=active)

    snap, err = await asyncio.to_thread(resume_batch, batch_id=bid, client_instance_id=header_cid)
    if err == "BAD_STATE":
        return _fail(
            trace_id=trace_id,
            code="BAD_STATE",
            message="resume only allowed in paused",
            batch=snap0,
            active_batch=await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours"),
        )
    if err == "NOT_FOUND":
        active = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
        return _fail(trace_id=trace_id, code="NOT_FOUND", message="batch not found", batch=None, active_batch=active)

    # resume 后入队其 queued tasks
    if snap and str(snap.get("state")).lower() == "running":
        try:
            await enqueue_batch(batch_id=bid, client_instance_id=header_cid, trace_id=trace_id)
        except Exception as e:
            log_event(
                logger=_LOG,
                service="data_sync",
                level="ERROR",
                file=__file__,
                func="bulk_resume",
                line=0,
                trace_id=trace_id,
                event="bulk.resume.enqueue_fail",
                message="enqueue_batch failed",
                extra={"batch_id": bid, "error": str(e)},
            )

    return _ok(trace_id=trace_id, batch=snap or snap0, active_batch=None, queue_position=None)


@router.post("/ensure-data/bulk/retry-failed")
async def bulk_retry_failed(request: Request, payload: BulkOpRequest) -> Dict[str, Any]:
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    if not _validate_client_instance_id(header_cid):
        return _fail(trace_id=trace_id, code="VALIDATION_ERROR", message="invalid client_instance_id", batch=None, active_batch=None)

    bid = str(payload.batch_id or "").strip()
    if not _validate_batch_id(bid):
        return _fail(trace_id=trace_id, code="VALIDATION_ERROR", message="invalid batch_id", batch=None, active_batch=None)

    snap0 = await asyncio.to_thread(get_batch_snapshot_for_client, bid, header_cid)
    if not snap0:
        active = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
        return _fail(trace_id=trace_id, code="NOT_FOUND", message="batch not found", batch=None, active_batch=active)

    active = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
    has_active = bool(active and str(active.get("state")).lower() in ("running", "paused", "stopping"))

    snap, err = await asyncio.to_thread(
        retry_failed_reset,
        batch_id=bid,
        client_instance_id=header_cid,
        has_active=has_active,
    )
    if err == "NOT_FOUND":
        active2 = await asyncio.to_thread(get_active_batch_for_client, header_cid, "after_hours")
        return _fail(trace_id=trace_id, code="NOT_FOUND", message="batch not found", batch=None, active_batch=active2)

    # 若没有 active，则本批会变 running，需要 enqueue
    if snap and str(snap.get("state")).lower() == "running":
        try:
            await enqueue_batch(batch_id=bid, client_instance_id=header_cid, trace_id=trace_id)
        except Exception as e:
            log_event(
                logger=_LOG,
                service="data_sync",
                level="ERROR",
                file=__file__,
                func="bulk_retry_failed",
                line=0,
                trace_id=trace_id,
                event="bulk.retry_failed.enqueue_fail",
                message="enqueue_batch failed",
                extra={"batch_id": bid, "error": str(e)},
            )

    qp = None
    if snap and str(snap.get("state")).lower() == "queued":
        qp = await asyncio.to_thread(get_queue_position, bid, header_cid, "after_hours")

    return _ok(
        trace_id=trace_id,
        batch=snap or snap0,
        active_batch=active,
        queue_position=qp if snap and snap.get("state") == "queued" else None,
    )


@router.get("/ensure-data/bulk/failures")
async def bulk_failures(
    request: Request,
    batch_id: str = Query(..., description="批次ID"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(200, ge=1, le=1000, description="分页大小"),
) -> Dict[str, Any]:
    """
    查询失败明细（A语义）：
      - not found / 隔离不匹配 => ok=true, total_failed=0, items=[]
    """
    trace_id = request.headers.get("x-trace-id")
    header_cid = _get_client_instance_id(request)

    # 查询类不泄露：header 无效直接空返回
    if not _validate_client_instance_id(header_cid):
        return {
            "ok": True,
            "backend_instance_id": get_backend_instance_id(),
            "batch_id": str(batch_id or "").strip(),
            "total_failed": 0,
            "offset": int(offset),
            "limit": int(limit),
            "items": [],
            "trace_id": trace_id,
        }

    bid = str(batch_id or "").strip()
    if not _validate_batch_id(bid):
        return {
            "ok": True,
            "backend_instance_id": get_backend_instance_id(),
            "batch_id": bid,
            "total_failed": 0,
            "offset": int(offset),
            "limit": int(limit),
            "items": [],
            "trace_id": trace_id,
        }

    snap = await asyncio.to_thread(get_batch_snapshot_for_client, bid, header_cid)
    if not snap:
        return {
            "ok": True,
            "backend_instance_id": get_backend_instance_id(),
            "batch_id": bid,
            "total_failed": 0,
            "offset": int(offset),
            "limit": int(limit),
            "items": [],
            "trace_id": trace_id,
        }

    total_failed, items = await asyncio.to_thread(
        list_failed_tasks,
        batch_id=bid,
        offset=int(offset),
        limit=int(limit),
    )

    return {
        "ok": True,
        "backend_instance_id": get_backend_instance_id(),
        "batch_id": bid,
        "total_failed": total_failed,
        "offset": int(offset),
        "limit": int(limit),
        "items": items,
        "trace_id": trace_id,
    }
