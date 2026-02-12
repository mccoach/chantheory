# backend/services/data_recipes/profile.py
# ==============================
# current_profile 任务配方（统一状态/错误码/SSE协议版）
# ==============================

from __future__ import annotations

from typing import Dict, Any

from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.services.data_recipes.common import bool_param
from backend.services import profile_sync
from backend.db.async_writer import get_async_writer
from backend.utils.gap_checker import check_info_updated_today
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.profile")
_writer = get_async_writer()


async def run_current_profile(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    force_fetch = bool_param(task, "force_fetch", False)

    job_type = "sync_profile"
    jobs_status: Dict[str, str] = {}

    log_event(
        logger=_LOG,
        service="data_recipes.profile",
        level="INFO",
        file=__file__,
        func="run_current_profile",
        line=0,
        trace_id=trace_id,
        event="profile.start",
        message="运行 current_profile 配方",
        extra={
            "task_id": task.task_id,
            "symbol": symbol,
            "force_fetch": force_fetch,
        },
    )

    rows_written = 0
    updated = False

    try:
        need_sync = True
        if not force_fetch:
            need_sync = check_info_updated_today(symbol=symbol, data_type_id="current_profile")

        if not need_sync:
            jobs_status[job_type] = "success"
            emit_job_finished(
                task,
                job_type=job_type,
                job_index=1,
                job_count=1,
                status="success",
                result={
                    "rows": 0,
                    "message": "档案无需同步（本地已最新）",
                    "error_code": None,
                    "error_message": None,
                    "details": None,
                    "extra": {"need_sync": False},
                },
            )
        else:
            snapshot = await profile_sync.fetch_profile_snapshot(symbol)
            if not snapshot:
                jobs_status[job_type] = "failed"
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="failed",
                    result={
                        "rows": 0,
                        "message": "档案同步失败：远端返回空/无有效数据",
                        "error_code": "REMOTE_EMPTY",
                        "error_message": "profile snapshot is empty",
                        "details": "profile_sync returned None/empty snapshot",
                        "extra": {"symbol": symbol, "need_sync": True},
                    },
                )
            else:
                await _writer.write_profile(snapshot)
                rows_written = 1
                updated = True
                jobs_status[job_type] = "success"
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="success",
                    result={
                        "rows": rows_written,
                        "message": "档案已同步至最新",
                        "error_code": None,
                        "error_message": None,
                        "details": None,
                        "extra": {"need_sync": True, "symbol": symbol},
                    },
                )

    except Exception as e:
        jobs_status[job_type] = "failed"
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={
                "rows": 0,
                "message": "档案同步失败：内部异常",
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e),
                "details": "exception in current_profile recipe",
                "extra": {"exception_type": type(e).__name__},
            },
        )
        _LOG.error("[current_profile配方] 同步异常: %s", e, exc_info=True)

    await _writer.flush()

    st = jobs_status.get(job_type)
    if st == "success":
        summary_msg = "current_profile 成功"
        summary_code = None
        summary_err = None
    else:
        summary_msg = "current_profile 失败"
        summary_code = "INTERNAL_ERROR"
        summary_err = "see job result"

    emit_task_finished(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary={
            "total_rows": rows_written,
            "message": summary_msg,
            "error_code": summary_code,
            "error_message": summary_err,
            "details": None,
            "extra": {"symbol": symbol, "updated": updated},
        },
    )

    return {
        "updated": updated and jobs_status.get(job_type) == "success",
        "source_id": "SSE_SZSE",
        "rows": rows_written,
    }
