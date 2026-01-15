# backend/services/task_events.py
# ==============================
# 说明：Task / Job 事件工具
#
# 职责：
#   - 提供 emit_job_done / emit_task_done 两个统一出口；
#   - 按共识文档构造 job_done / task_done SSE 事件；
#   - 通过 utils.events.publish 转发到全局事件总线 → SSE。
#
# V1.1 - After Hours Bulk（批次真相源在后端）
#   - 若 task.metadata 含 batch_id：
#       * 以 task_done 为触发点更新批次进度（真相源）
#       * 失败时写入失败明细（真相源）
#       * 将最新 batch 快照写入 task_done 事件的 'batch' 字段
#   - 普通（非 bulk）任务：不携带 batch 字段，避免污染。
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional
from datetime import datetime

from backend.services.task_model import Task
from backend.utils.events import publish as publish_event
from backend.utils.time import now_iso
from backend.utils.logger import get_logger

# After Hours Bulk v1.1 DB
from backend.db.bulk_batches import (
    update_progress_on_task_done,
    upsert_failure_once,
    get_batch,
)

_LOG = get_logger("task_events")


def _safe_status(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in ("success", "failed"):
        return "failed"
    return v


def emit_job_done(
    task: Task,
    *,
    job_type: str,
    job_index: int,
    job_count: int,
    status: str,
    result: Dict[str, Any] | None = None,
) -> None:
    """
    发送 job_done 事件（Job 层）。

    参数：
      - task       : Task 对象
      - job_type   : 'gap_check'/'sync_kline'/'sync_sh_stock'/...
      - job_index  : 当前 Job 在该 Task 中的顺序（从1开始）
      - job_count  : 该 Task 中 Job 总数
      - status     : 'success'/'failed'
      - result     : 结果 dict，结构自由扩展：
                       { 'rows': int, 'message': str, 'error_code': str, 'error_message': str, ... }
    """
    st = _safe_status(status)
    res = dict(result or {})

    event = {
        "type": "job_done",

        "trace_id": task.trace_id,
        "task_id": task.task_id,
        "task_type": task.type,
        "task_scope": task.scope,
        "symbol": task.symbol,
        "freq": task.freq,
        "adjust": task.adjust,
        "class": task.cls,

        "job_type": job_type,
        "job_index": int(job_index),
        "job_count": int(job_count),

        "status": st,
        "result": {
            "rows": res.get("rows"),
            "message": res.get("message"),
            "error_code": res.get("error_code"),
            "error_message": res.get("error_message"),
            # 其余字段原样透传在 'extra' 中，避免 schema 爆炸
            "extra": {k: v for k, v in res.items()
                      if k not in ("rows", "message", "error_code", "error_message")}
            if res else {},
        },

        "timestamp": now_iso(),
    }

    publish_event(event)

    _LOG.info(
        "[SSE] job_done task=%s job_type=%s idx=%s/%s status=%s rows=%s msg=%s",
        task.task_id,
        job_type,
        job_index,
        job_count,
        st,
        event["result"]["rows"],
        event["result"]["message"],
    )


def _summarize_overall_status(status_list: list[str]) -> str:
    """
    汇总整体状态：
      - 全 success         → 'success'
      - 既有 success 又有 failed → 'partial_fail'
      - 全 failed          → 'failed'
    """
    if not status_list:
        return "failed"

    succ = sum(1 for s in status_list if s == "success")
    fail = sum(1 for s in status_list if s == "failed")

    if succ and not fail:
        return "success"
    if succ and fail:
        return "partial_fail"
    return "failed"


def _extract_failure_from_task_done_summary(summary: Dict[str, Any] | None) -> tuple[Optional[str], Optional[str]]:
    """
    从 task_done.summary 中尽力提取 error_code / error_message（用于 failures 明细）。
    当前 schema：
      summary: { total_rows, message, extra:{...} }
    v1.1 要求失败明细包含 error_code/error_message。
    由于各配方的 task_done summary 不保证包含 error_code，我们采取“尽量提取”：
      - 优先 summary.extra.error_code / error_message
      - 其次用 summary.message 作为 error_message 兜底
    """
    if not isinstance(summary, dict):
        return None, None

    extra = summary.get("extra") if isinstance(summary.get("extra"), dict) else {}
    code = extra.get("error_code") or None
    msg = extra.get("error_message") or None

    if not msg:
        m = summary.get("message")
        msg = str(m) if m is not None else None

    return (str(code) if code else None, str(msg) if msg else None)


def emit_task_done(
    task: Task,
    *,
    jobs: Dict[str, str],
    completion_policy: str,
    summary: Dict[str, Any] | None = None,
) -> None:
    """
    发送 task_done 事件（Task 层）。

    参数：
      - task             : Task 对象
      - jobs             : { job_type: status }，status ∈ {'success','failed'}
      - completion_policy: 'all_required' / 'best_effort'
      - summary          : { 'total_rows': int, 'message': str, ... }
    """
    # 归一化 job 状态
    norm_jobs: Dict[str, str] = {}
    for k, v in (jobs or {}).items():
        norm_jobs[str(k)] = _safe_status(str(v))

    overall_status = _summarize_overall_status(list(norm_jobs.values()))
    cp = (completion_policy or "all_required").strip()
    if cp not in ("all_required", "best_effort"):
        cp = "all_required"

    summ = dict(summary or {})

    event: Dict[str, Any] = {
        "type": "task_done",

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
            # 其余字段统一放到 extra
            "extra": {k: v for k, v in summ.items()
                      if k not in ("total_rows", "message")}
            if summ else {},
        },

        "timestamp": now_iso(),
    }

    # ======================================================================
    # After Hours Bulk v1.1: task_done 携带 batch 快照（真相源在后端）
    # 触发点：task_done（而非 job_done），避免前端乱序/重复统计
    # ======================================================================
    try:
        md = task.metadata or {}
        batch_id = md.get("batch_id")
        if isinstance(batch_id, str) and batch_id.strip():
            bid = batch_id.strip()

            # 1) 更新批次进度（partial_fail 计失败）
            batch_snapshot = update_progress_on_task_done(
                batch_id=bid,
                overall_status=overall_status,
            )

            # 2) 若失败，写 failures 明细（按 batch_id+task_id 幂等）
            if overall_status in ("failed", "partial_fail"):
                code, msg = _extract_failure_from_task_done_summary(event.get("summary"))
                upsert_failure_once(
                    batch_id=bid,
                    task_id=task.task_id,
                    task_type=task.type,
                    symbol=task.symbol,
                    freq=task.freq,
                    adjust=task.adjust,
                    overall_status=overall_status,
                    error_code=code,
                    error_message=msg,
                    timestamp=event.get("timestamp") or now_iso(),
                )

            # 3) event 携带 batch 快照（进度真相源）
            # 若更新失败（例如批次被清理），尽力回退读取
            if not batch_snapshot:
                batch_snapshot = get_batch(bid)
            if batch_snapshot:
                event["batch"] = batch_snapshot

    except Exception as e:
        # 绝不让批次统计问题阻断 task_done 的发布（但要有日志可查）
        _LOG.error("[Bulk] attach batch snapshot failed: %s", e, exc_info=True)

    publish_event(event)

    _LOG.info(
        "[SSE] task_done task=%s type=%s scope=%s status=%s policy=%s summary=%s",
        task.task_id,
        task.type,
        task.scope,
        overall_status,
        cp,
        event["summary"],
    )
