# backend/services/task_events.py
# ==============================
# Task / Job 事件工具（统一状态码/错误码/SSE协议版）
#
# 本轮关键修复：
#   - Bulk 真相源写库（bulk_tasks.last_error_code/message）必须落最准确错误：
#       * 以 task.finished.summary.extra.primary_error 为唯一首选来源
#       * 不再使用 summary 内“占位错误”（如 INTERNAL_ERROR/see job result）
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple
from backend.services.task_model import Task
from backend.utils.events import publish as publish_event
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

from backend.db.bulk_batches import finalize_task_terminal
from backend.services.bulk_events import emit_bulk_batch_snapshot
from backend.services.bulk_scheduler import (
    tick as bulk_tick,
    refill_inflight as bulk_refill_inflight,
)

_LOG = get_logger("task_events")


_ALLOWED_JOB_STATUS = {"success", "failed", "cancelled", "skipped"}
_ALLOWED_TASK_STATUS = {"success", "failed", "cancelled", "skipped", "partial_fail"}


def _safe_job_status(value: str) -> str:
    v = (value or "").strip().lower()
    return v if v in _ALLOWED_JOB_STATUS else "failed"


def _safe_task_status(value: str) -> str:
    v = (value or "").strip().lower()
    return v if v in _ALLOWED_TASK_STATUS else "failed"


def _extract_error_fields(obj: Dict[str, Any] | None) -> Tuple[Optional[str], Optional[str], Optional[str], Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None, None, None, {}

    code = obj.get("error_code")
    if code is not None:
        code = str(code).strip() or None

    msg = obj.get("error_message")
    if msg is not None:
        msg = str(msg)

    details = obj.get("details")
    if details is not None:
        details = str(details)

    extra = obj.get("extra") if isinstance(obj.get("extra"), dict) else {}
    return code, msg, details, extra


def _extract_primary_error_from_summary_extra(summary: Dict[str, Any] | None) -> Tuple[Optional[str], Optional[str]]:
    """
    方案A：从 task.finished.summary.extra.primary_error 提取真相源要写入的错误信息。

    返回：
      (error_code, error_message)
    """
    if not isinstance(summary, dict):
        return None, None
    extra = summary.get("extra") if isinstance(summary.get("extra"), dict) else {}
    pe = extra.get("primary_error") if isinstance(extra.get("primary_error"), dict) else {}

    code = pe.get("error_code")
    if code is not None:
        code = str(code).strip() or None

    msg = pe.get("error_message")
    if msg is not None:
        msg = str(msg).strip() or None

    # 如果 primary_error 没给 message，允许用 details 兜底
    if not msg:
        det = pe.get("details")
        msg = str(det).strip() if det else None

    return code, msg


def emit_job_finished(
    task: Task,
    *,
    job_type: str,
    job_index: int,
    job_count: int,
    status: str,
    result: Dict[str, Any] | None = None,
) -> None:
    st = _safe_job_status(status)
    res = dict(result or {})

    code, err_msg, details, extra = _extract_error_fields(res)

    event = {
        "type": "task.job.finished",
        "timestamp": now_iso(),

        "trace_id": task.trace_id,
        "task_id": task.task_id,
        "task_type": task.type,
        "task_scope": task.scope,
        "symbol": task.symbol,
        "freq": task.freq,
        "adjust": task.adjust,
        "class": task.cls,

        "job_type": str(job_type),
        "job_index": int(job_index),
        "job_count": int(job_count),

        "status": st,

        "result": {
            "rows": res.get("rows"),
            "message": res.get("message"),
            "error_code": code,
            "error_message": err_msg,
            "details": details,
            "extra": extra or {},
        },
    }

    publish_event(event)

    _LOG.info(
        "[SSE] task.job.finished task=%s job_type=%s idx=%s/%s status=%s error_code=%s",
        task.task_id,
        job_type,
        job_index,
        job_count,
        st,
        code,
    )


def _summarize_overall_status(job_status_map: Dict[str, str]) -> str:
    if not job_status_map:
        return "failed"

    statuses = [str(s).strip().lower() for s in job_status_map.values()]
    statuses = [_safe_job_status(s) for s in statuses]

    if any(s == "cancelled" for s in statuses):
        return "cancelled"

    succ = sum(1 for s in statuses if s == "success")
    fail = sum(1 for s in statuses if s == "failed")
    skip = sum(1 for s in statuses if s == "skipped")

    if skip and not succ and not fail:
        return "skipped"
    if fail and succ:
        return "partial_fail"
    if fail and not succ:
        return "failed"
    return "success"


def emit_task_finished(
    task: Task,
    *,
    jobs: Dict[str, str],
    completion_policy: str,
    summary: Dict[str, Any] | None = None,
) -> None:
    norm_jobs: Dict[str, str] = {}
    for k, v in (jobs or {}).items():
        norm_jobs[str(k)] = _safe_job_status(str(v))

    overall_status = _safe_task_status(_summarize_overall_status(norm_jobs))
    cp = (completion_policy or "all_required").strip()
    if cp not in ("all_required", "best_effort"):
        cp = "all_required"

    summ = dict(summary or {})
    code, err_msg, details, extra = _extract_error_fields(summ)

    event: Dict[str, Any] = {
        "type": "task.finished",
        "timestamp": now_iso(),

        "trace_id": task.trace_id,
        "task_id": task.task_id,
        "task_type": task.type,
        "task_scope": task.scope,
        "symbol": task.symbol,
        "freq": task.freq,
        "adjust": task.adjust,
        "class": task.cls,

        "jobs": norm_jobs,
        "overall_status": overall_status,
        "completion_policy": cp,

        "summary": {
            "total_rows": summ.get("total_rows"),
            "message": summ.get("message"),
            "error_code": code,
            "error_message": err_msg,
            "details": details,
            "extra": extra or {},  # 必含 primary_error（由配方提供）
        },
    }

    publish_event(event)

    _LOG.info(
        "[SSE] task.finished task=%s type=%s scope=%s status=%s error_code=%s",
        task.task_id,
        task.type,
        task.scope,
        overall_status,
        code,
    )

    # ==============================
    # After Hours Bulk hook
    # ==============================
    try:
        md = task.metadata or {}
        batch_id = md.get("batch_id")
        client_task_key = md.get("client_task_key")
        client_instance_id = md.get("client_instance_id")

        if isinstance(batch_id, str) and batch_id.strip() and isinstance(client_task_key, str) and client_task_key.strip():
            bid = batch_id.strip()
            ckey = client_task_key.strip()

            if overall_status == "success":
                term = "success"
            elif overall_status == "cancelled":
                term = "cancelled"
            elif overall_status == "skipped":
                term = "skipped"
            else:
                term = "failed"

            # ===== NEW: 真相源错误信息从 primary_error 取 =====
            pe_code, pe_msg = _extract_primary_error_from_summary_extra(event.get("summary"))

            # 防御性回退：若 primary_error 缺失，再回退到 summary.error_code/error_message
            if not pe_code and code:
                pe_code = code
            if not pe_msg and err_msg:
                pe_msg = err_msg
            if not pe_msg and isinstance(summ, dict) and summ.get("message"):
                pe_msg = str(summ.get("message"))

            snap = finalize_task_terminal(
                batch_id=bid,
                client_task_key=ckey,
                terminal_status=term,
                error_code=pe_code,
                error_message=pe_msg,
            )

            if snap:
                emit_bulk_batch_snapshot(snap)

                st = str(snap.get("state") or "").strip().lower()

                if st in ("failed", "success", "cancelled") and isinstance(client_instance_id, str) and client_instance_id.strip():
                    awaitable = bulk_tick(
                        client_instance_id=client_instance_id.strip(),
                        trace_id=task.trace_id,
                    )
                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(awaitable)
                    except Exception:
                        pass

                if st == "running" and isinstance(client_instance_id, str) and client_instance_id.strip():
                    awaitable2 = bulk_refill_inflight(
                        batch_id=bid,
                        client_instance_id=client_instance_id.strip(),
                        trace_id=task.trace_id,
                    )
                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(awaitable2)
                    except Exception:
                        pass

    except Exception as e:
        _LOG.error("[Bulk] task.finished hook failed: %s", e, exc_info=True)
