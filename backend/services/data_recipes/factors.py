# backend/services/data_recipes/factors.py
# ==============================
# current_factors 任务配方（primary_error 统一版）
# ==============================

from __future__ import annotations

from typing import Dict, Any, Optional

from backend.services.task_model import Task
from backend.services.task_events import emit_job_finished, emit_task_finished
from backend.services.data_recipes.common import bool_param
from backend.services import bars_recipes
from backend.db.async_writer import get_async_writer
from backend.utils.gap_checker import check_info_updated_today
from backend.utils.logger import get_logger, log_event

_LOG = get_logger("data_recipes.factors")
_writer = get_async_writer()


def _primary_error(
    *,
    error_code: str,
    error_message: str | None,
    details: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "error_code": str(error_code),
        "error_message": str(error_message) if error_message is not None else None,
        "details": str(details) if details is not None else None,
        "extra": extra or {},
    }


async def run_current_factors(task: Task) -> Dict[str, Any]:
    trace_id = task.trace_id
    symbol = (task.symbol or "").strip()
    cls = (task.cls or "").strip().lower()
    force_fetch = bool_param(task, "force_fetch", False)

    job_type = "sync_factors"
    jobs_status: Dict[str, str] = {}

    # 系统规则：仅 stock 支持因子
    if cls != "stock":
        jobs_status[job_type] = "skipped"
        pe = _primary_error(
            error_code="INVALID_PARAMS",
            error_message=f"current_factors only supports stock; class={cls or 'None'}",
            details="current_factors is only applicable to stock",
            extra={"class": cls},
        )
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="skipped",
            result={
                "rows": 0,
                "message": "因系统规则不支持，该任务已跳过",
                **pe,
            },
        )
        emit_task_finished(
            task,
            jobs=jobs_status,
            completion_policy="all_required",
            summary={
                "total_rows": 0,
                "message": "current_factors 已跳过（系统规则不支持）",
                **pe,
                "extra": {"primary_error": pe, "symbol": symbol},
            },
        )
        return {"updated": False, "rows": 0, "source_id": None}

    log_event(
        logger=_LOG,
        service="data_recipes.factors",
        level="INFO",
        file=__file__,
        func="run_current_factors",
        line=0,
        trace_id=trace_id,
        event="factors.start",
        message="运行 current_factors 配方",
        extra={"task_id": task.task_id, "symbol": symbol, "force_fetch": force_fetch},
    )

    pe: Optional[Dict[str, Any]] = None

    try:
        need_sync = True
        if not force_fetch:
            need_sync = check_info_updated_today(symbol=symbol, data_type_id="current_factors")

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
                    "message": "因子无需同步（本地已最新）",
                    "error_code": None,
                    "error_message": None,
                    "details": None,
                    "extra": {"need_sync": False},
                },
            )
        else:
            ok = await bars_recipes.run_stock_factors(symbol=symbol, force_fetch=force_fetch, trace_id=trace_id)
            if not ok:
                jobs_status[job_type] = "failed"
                pe = _primary_error(
                    error_code="INTERNAL_ERROR",
                    error_message="need_sync=True but no data written",
                    details="unexpected noop when need_sync=True",
                    extra={"need_sync": True},
                )
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="failed",
                    result={"rows": 0, "message": "因子同步失败：内部异常（未产生写入）", **pe},
                )
            else:
                jobs_status[job_type] = "success"
                emit_job_finished(
                    task,
                    job_type=job_type,
                    job_index=1,
                    job_count=1,
                    status="success",
                    result={
                        "rows": None,
                        "message": "因子已同步至最新",
                        "error_code": None,
                        "error_message": None,
                        "details": None,
                        "extra": {"need_sync": True},
                    },
                )

    except bars_recipes.RemoteEmptyDataError as e:
        jobs_status[job_type] = "failed"
        pe = _primary_error(
            error_code="REMOTE_EMPTY",
            error_message=str(e),
            details="remote fetch returned empty or normalized empty",
            extra={"symbol": symbol},
        )
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={"rows": 0, "message": "因子同步失败：远端返回空数据（强规则）", **pe},
        )
    except Exception as e:
        jobs_status[job_type] = "failed"
        pe = _primary_error(
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            details="exception in current_factors recipe",
            extra={"exception_type": type(e).__name__},
        )
        emit_job_finished(
            task,
            job_type=job_type,
            job_index=1,
            job_count=1,
            status="failed",
            result={"rows": 0, "message": "因子同步失败：内部异常", **pe},
        )
        _LOG.error("[current_factors配方] 同步异常: %s", e, exc_info=True)

    await _writer.flush()

    st = jobs_status.get(job_type)
    if st == "success":
        summary = {
            "total_rows": None,
            "message": "current_factors 成功",
            "error_code": None,
            "error_message": None,
            "details": None,
            "extra": {"primary_error": None, "symbol": symbol},
        }
    elif st == "skipped":
        # skipp 场景上面已 return，理论不会到这里，保留防御
        pe = pe or _primary_error(error_code="INVALID_PARAMS", error_message="skipped by rule")
        summary = {
            "total_rows": 0,
            "message": "current_factors 已跳过",
            **pe,
            "extra": {"primary_error": pe, "symbol": symbol},
        }
    else:
        pe = pe or _primary_error(error_code="INTERNAL_ERROR", error_message="unknown error")
        summary = {
            "total_rows": 0,
            "message": "current_factors 失败",
            **pe,
            "extra": {"primary_error": pe, "symbol": symbol},
        }

    emit_task_finished(
        task,
        jobs=jobs_status,
        completion_policy="all_required",
        summary=summary,
    )

    return {
        "updated": jobs_status.get(job_type) == "success",
        "source_id": "baostock.get_adj_factors",
        "rows": None,
    }
