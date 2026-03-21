# backend/services/task_events.py
# ==============================
# Task / Job 事件工具（统一状态码/错误码/SSE协议版）
#
# 本轮改动：
#   - 彻底删除 old bulk hook
#   - 本文件只负责：
#       * task.job.finished 事件
#       * task.finished 事件
#   - 不再推进任何旧盘后 bulk 真相源
#   - local-import 有自己独立的 SSE 事件链路，不走这里
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple
from backend.services.task_model import Task
from backend.utils.events import publish as publish_event
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

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
            "extra": extra or {},
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
